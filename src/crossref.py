#!/usr/bin/env python3
"""
Cross-reference resolution for Indonesian legal text.

Indonesian legal drafting cites other provisions constantly --
`sebagaimana dimaksud pada ayat (1)`, `sebagaimana dimaksud dalam Pasal 55
ayat (1) huruf l`. A norm extracted from a single Pasal in isolation is
often meaningless without resolving these: the panti pijat conflict only
exists because Pasal 58 (the tax band) and Pasal 55 (the category
enumeration) are different Pasal.

This module resolves references BEFORE extraction, not after: build_index()
segments a whole document into Pasal/ayat/huruf spans, and
resolve_references() looks up what a citation inside one Pasal actually
points to, so a cross-Pasal citation's text can be handed to the LLM as
extra context. A same-Pasal citation needs no such fetch -- the model
already sees the whole Pasal -- so resolve_references() still resolves it
fully (which Pasal, which ayat) but leaves its text unfetched.
"""

import re

from ocr_numerals import GLYPH, _lev

PASAL_HEADER = re.compile(r"(?m)^[ \t]*Pasal[ \t]+(\d+[A-Za-z]?)[ \t]*$")
PENJELASAN_HEADING = re.compile(r"(?m)^[ \t]*PENJELASAN[ \t]*$")
AYAT_MARKER = re.compile(r"(?m)^[ \t]*\((\d+)\)[ \t]+")
HURUF_MARKER = re.compile(r"(?m)^[ \t]*([a-z])\.[ \t]+")


def _index_huruf(text):
    markers = list(HURUF_MARKER.finditer(text))
    huruf = {}
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        huruf[m.group(1)] = {"start": start, "end": end, "text": text[start:end]}
    return huruf


def _index_ayat(pasal_text):
    markers = list(AYAT_MARKER.finditer(pasal_text))
    ayat = {}
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(pasal_text)
        ayat_text = pasal_text[start:end]
        ayat[m.group(1)] = {
            "start": start, "end": end, "text": ayat_text,
            "huruf": _index_huruf(ayat_text),
        }
    return ayat


def build_index(document_text):
    """Segment one document's operative text into a Pasal -> ayat -> huruf
    lookup of spans, stopping before any PENJELASAN appendix. Single
    document / single instrument scoped -- call once per document."""
    boundary = PENJELASAN_HEADING.search(document_text)
    body = document_text[:boundary.start()] if boundary else document_text

    headers = list(PASAL_HEADER.finditer(body))
    index = {}
    for i, h in enumerate(headers):
        pasal_num = h.group(1)
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        pasal_text = body[start:end]
        ayat = _index_ayat(pasal_text)
        index[pasal_num] = {
            "start": start, "end": end, "text": pasal_text,
            "ayat": ayat,
            "huruf": {} if ayat else _index_huruf(pasal_text),
        }
    return index


KEYWORDS = (
    "pasal", "ayat", "huruf", "angka", "dan", "atau", "pada", "dalam",
)

TOKEN_RE = re.compile(r"\(\s*[0-9A-Za-z]{1,3}\s*\)?|[A-Za-z]+|[0-9]+")


def _tokenize(span):
    return [t.lower() for t in TOKEN_RE.findall(span)]


def _canon(tok):
    """Snap a single-edit OCR misspelling of a citation keyword ('ayal',
    'alat' for 'ayat') onto the keyword. Verified against two real corpus
    corruptions; a typo two edits away ('hunrf' for 'huruf') is
    deliberately left unmatched."""
    if not tok.isalpha() or tok in KEYWORDS:
        return tok
    for kw in KEYWORDS:
        if _lev(tok, kw) <= 1:
            return kw
    return tok


def _is_plain_number(tok):
    return tok.isdigit()


def _is_paren_number(tok):
    return tok.startswith("(")


def _unparen_repair(tok):
    """'(l)' -> '1', '(2)' -> '2'. Returns None if no digit survives repair."""
    inner = tok.strip("()").translate(GLYPH)
    m = re.match(r"[0-9]+", inner)
    return m.group(0) if m else None


def _is_letter(tok):
    return len(tok) == 1 and tok.isalpha()


EXTERNAL_PATTERNS = [
    re.compile(r"undang-undang\s+dasar", re.IGNORECASE),
    re.compile(r"ketentuan\s+peraturan\s+perundang-undangan", re.IGNORECASE),
    re.compile(r"peraturan\s+perundang-undangan", re.IGNORECASE),
    re.compile(r"undang-undang\s+(mengenai|di\s+bidang|nomor)", re.IGNORECASE),
    re.compile(r"peraturan\s+(daerah|pemerintah|presiden|menteri)(\s+ini)?", re.IGNORECASE),
    re.compile(r"lampiran", re.IGNORECASE),
]


def _match_external(span):
    """If `span` names something outside this document's own Pasal
    structure (another named regulation, the Constitution, a Lampiran,
    the generic 'ketentuan peraturan perundang-undangan'), return a short
    human-readable note. Otherwise None -- span is a citation to parse."""
    for pat in EXTERNAL_PATTERNS:
        m = pat.search(span)
        if m:
            return span[m.start():m.start() + 60].strip()
    return None


def _read_targets(words, current_pasal):
    """Walk a tokenized citation span and build the list of targets it
    names. A named Pasal persists across a dan/atau list until a new Pasal
    is named ('Pasal 6 ayat (1) atau ayat (2)' -> both targets are Pasal
    6); when no Pasal is ever named, every target defaults to
    current_pasal (the common bare-ayat-list case, e.g. UU-58-4)."""
    targets = []
    pasal = None
    ayat = None
    pending_pasal_only = False
    i, n = 0, len(words)

    while i < n:
        w = _canon(words[i])

        if w in KEYWORDS and i + 1 < n and _canon(words[i + 1]) == w:
            i += 1  # doubled keyword: 'Pasal Pasal 44', 'pada pada ayat (7)'
            continue

        if w == "pasal" and i + 1 < n and _is_plain_number(words[i + 1]):
            pasal = words[i + 1]
            ayat = None
            pending_pasal_only = True
            i += 2
            continue

        if w == "ayat" and i + 1 < n and _is_paren_number(words[i + 1]):
            repaired = _unparen_repair(words[i + 1])
            if repaired is None:
                break
            ayat = repaired
            target_pasal = pasal if pasal is not None else current_pasal
            pending_pasal_only = False
            huruf = None
            j = i + 2
            if j + 1 < n and _canon(words[j]) == "huruf" and _is_letter(words[j + 1]):
                huruf = words[j + 1]
                j += 2
            targets.append({"pasal": target_pasal, "ayat": ayat, "huruf": huruf})
            i = j
            continue

        if w == "huruf" and i + 1 < n and _is_letter(words[i + 1]):
            target_pasal = pasal if pasal is not None else current_pasal
            pending_pasal_only = False
            targets.append({"pasal": target_pasal, "ayat": ayat, "huruf": words[i + 1]})
            i += 2
            continue

        if w in ("dan", "atau", "pada", "dalam"):
            i += 1
            continue

        break  # unrecognised token: the citation chain ends here

    if pending_pasal_only:
        targets.append({"pasal": pasal, "ayat": None, "huruf": None})
    return targets


ANCHOR_RE = re.compile(
    r"sebagaimana\s+(?:telah\s+)?(?:beberapa\s+kali\s+)?"
    r"(dimaksud|diatur|ditetapkan|tercantum|dimaksudkan|diubah)"
    r"[\s,]*(.{0,200}?)(?=\.|$)",
    re.IGNORECASE | re.DOTALL,
)


def _lookup_text(index, target):
    """Fetch text for a resolved target, falling back to the coarsest
    level that exists (huruf -> ayat -> Pasal) rather than failing outright
    on a partial miss. Returns (text_or_None, exact_match: bool)."""
    pasal_entry = index.get(target["pasal"])
    if pasal_entry is None:
        return None, False

    if target["ayat"] is not None:
        ayat_entry = pasal_entry["ayat"].get(target["ayat"])
        if ayat_entry is None:
            return pasal_entry["text"], False
        if target["huruf"] is not None:
            huruf_entry = ayat_entry["huruf"].get(target["huruf"])
            if huruf_entry is not None:
                return huruf_entry["text"], True
            return ayat_entry["text"], False
        return ayat_entry["text"], True

    if target["huruf"] is not None:
        huruf_entry = pasal_entry["huruf"].get(target["huruf"])
        if huruf_entry is not None:
            return huruf_entry["text"], True
        return pasal_entry["text"], False

    return pasal_entry["text"], True


def resolve_references(pasal_text, index, current_pasal):
    """Find every 'sebagaimana ...' occurrence in one Pasal's text and
    resolve each to a classified target. Cross-Pasal targets are looked up
    against `index` and have their text attached; same-Pasal targets are
    resolved (which ayat/huruf, explicitly) but left without fetched text,
    since the caller already has the whole current Pasal in view."""
    refs = []
    for m in ANCHOR_RE.finditer(pasal_text):
        verb = m.group(1).lower()
        span = m.group(2)
        phrase, start, end = m.group(0), m.start(), m.end()

        if verb == "diubah":
            refs.append({
                "phrase": phrase, "start": start, "end": end, "verb": verb,
                "status": "amendment_history", "targets": [],
                "needs_review": False, "note": None,
            })
            continue

        raw_targets = _read_targets(_tokenize(span), current_pasal)

        if not raw_targets:
            # Only consult the external check once the citation parser
            # has come up empty. Otherwise a legitimate same-Pasal
            # citation ("... ayat (1) tercantum dalam Lampiran...") would
            # be swallowed as "external" just because something external
            # is mentioned later in the same sentence.
            ext_note = _match_external(span)
            if ext_note:
                refs.append({
                    "phrase": phrase, "start": start, "end": end, "verb": verb,
                    "status": "external", "targets": [],
                    "needs_review": False, "note": ext_note,
                })
            else:
                refs.append({
                    "phrase": phrase, "start": start, "end": end, "verb": verb,
                    "status": "unresolved", "targets": [],
                    "needs_review": True, "note": span.strip(),
                })
            continue

        resolved, any_cross, any_imprecise = [], False, False
        for t in raw_targets:
            entry = dict(t)
            if t["pasal"] != current_pasal:
                any_cross = True
                text, exact = _lookup_text(index, t)
                entry["text"] = text
                if not exact:
                    any_imprecise = True
            else:
                entry["text"] = None
            resolved.append(entry)

        status = "cross_pasal" if any_cross else "same_pasal"
        refs.append({
            "phrase": phrase, "start": start, "end": end, "verb": verb,
            "status": status, "targets": resolved,
            "needs_review": any_cross and any_imprecise, "note": None,
        })
    return refs
