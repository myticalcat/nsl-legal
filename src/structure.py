#!/usr/bin/env python3
"""
Structural segmentation of an Indonesian legal instrument.

Produces the nesting the extractor needs: pasal -> ayat -> huruf -> angka,
each span carrying a citation string and offsets back into the source text.

Three properties this module holds and `crossref.build_index` does not:

  Occurrences are a list, never a dict keyed by number. A document states
  `Pasal 1` in its operative text and again in its penjelasan, and keying by
  number silently discards one -- 94 of 232 pasal in Perda Sibolga 1/2024,
  74 of 181 in Lubuk Linggau. Duplicates here are recorded, not overwritten.

  Sections are found by numbering restart, not by heading text. The heading
  `PENJELASAN` does not survive OCR in either of those two documents, so a
  string match cannot be the primary signal. A pasal sequence that jumps
  backwards is structural evidence that survives a mangled scan.

  Sub-levels are accepted only as validated runs. A huruf list must open at
  `a` and advance by one; an angka list must open at `1`. Indonesian drafting
  is regular enough for this to hold, and it rejects the stray `b.` in prose
  or the `3.` inside a tariff table that a bare marker match would swallow.
  Reading order is unreliable on OCR'd pages, so no rule here depends on
  indentation column.
"""

import collections
import re

from crossref import AYAT_MARKER, PASAL_HEADER

# Sub-item markers come in both dotted and parenthesised forms, in comparable
# volume across the corpus, so both are recognised at both levels.
HURUF_MARKER = re.compile(r"(?m)^[ \t]*([a-z])[.)][ \t]+")
ANGKA_MARKER = re.compile(r"(?m)^[ \t]*(\d+)[.)][ \t]+")

LAMPIRAN_HEADING = re.compile(r"(?m)^[ \t]*LAMPIRAN\b")
PENJELASAN_HEADING = re.compile(r"(?m)^[ \t]*PENJELASAN\b")

# A pasal number can carry a genuine letter suffix -- `Pasal 12A` is how an
# amendment inserts an article -- so PASAL_HEADER captures `\d+[A-Za-z]?`. But
# the same shape is produced by the O-for-zero scan corruption: `Pasal 7O` is
# article 70, read as article 7 with an `O` suffix. The two are told apart by
# internal evidence, never by the glyph alone: repair the suffix to a digit
# only when doing so restores an ascending sequence. A real `12A` follows `12`
# and never looks like a jump backwards, so it is never a repair candidate.
SUFFIX_AS_DIGIT = {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"}


def pasal_sort_key(label):
    """Numeric value of a pasal label, ignoring any suffix. `12A` -> 12."""
    return int(re.match(r"\d+", label).group())


def _repair_candidate(label):
    """`7O` -> 70 if the suffix is a corrupted digit, else None."""
    m = re.fullmatch(r"(\d+)([A-Za-z])", label)
    if not m:
        return None
    digit = SUFFIX_AS_DIGIT.get(m.group(2))
    return int(m.group(1) + digit) if digit else None


def _runs(markers, first, nxt):
    """Keep only maximal runs that open at `first` and advance by one.

    Returns a list of (match, label) for markers inside an accepted run.
    """
    accepted, run = [], []
    for m in markers:
        label = m.group(1)
        if not run:
            if label == first:
                run = [(m, label)]
            continue
        if label == nxt(run[-1][1]):
            run.append((m, label))
        elif label == first:
            accepted.extend(run)
            run = [(m, label)]
        else:
            accepted.extend(run)
            run = []
    accepted.extend(run)
    return accepted


def _spans(accepted, text, limit):
    """Turn accepted markers into (label, body_start, body_end) spans."""
    out = []
    for i, (m, label) in enumerate(accepted):
        start = m.end()
        end = accepted[i + 1][0].start() if i + 1 < len(accepted) else limit
        out.append((label, start, end, text[start:end]))
    return out


def _next_letter(ch):
    return chr(ord(ch) + 1)


def _next_number(s):
    return str(int(s) + 1)


def _parse_angka(text, offset, citation):
    accepted = _runs(list(ANGKA_MARKER.finditer(text)), "1", _next_number)
    return [
        {
            "angka": label,
            "citation": f"{citation} angka {label}",
            "start": offset + start,
            "end": offset + end,
            "text": body,
        }
        for label, start, end, body in _spans(accepted, text, len(text))
    ]


def _parse_huruf(text, offset, citation):
    accepted = _runs(list(HURUF_MARKER.finditer(text)), "a", _next_letter)
    out = []
    for label, start, end, body in _spans(accepted, text, len(text)):
        cite = f"{citation} huruf {label}"
        out.append({
            "huruf": label,
            "citation": cite,
            "start": offset + start,
            "end": offset + end,
            "text": body,
            "angka": _parse_angka(body, offset + start, cite),
        })
    return out


def _parse_ayat(text, offset, citation):
    markers = list(AYAT_MARKER.finditer(text))
    accepted = _runs(markers, "1", _next_number)
    out = []
    for label, start, end, body in _spans(accepted, text, len(text)):
        cite = f"{citation} ayat ({label})"
        huruf = _parse_huruf(body, offset + start, cite)
        out.append({
            "ayat": label,
            "citation": cite,
            "start": offset + start,
            "end": offset + end,
            "text": body,
            "huruf": huruf,
            # A numbered list directly under an ayat, with no huruf between.
            "angka": [] if huruf else _parse_angka(body, offset + start, cite),
        })
    return out


# A backwards jump in pasal numbering is either a new section or a defect in
# the drafting, and the size of the drop tells them apart. Across the corpus
# every section restart drops by 122 or more (140->1, 144->22, 170->2) while
# both genuine numbering defects drop by exactly 2 -- Perda Bau-Bau 1/2024
# renumbers 18, 19, 20 a second time under `Bagian Keempat PBJT`, and Perda
# Pekalongan 8/2023 goes 176->174. The `num <= 2` arm keeps the rule working
# on a short instrument, where a real restart cannot clear the margin.
RESTART_MIN_DROP = 10


def _is_section_restart(previous, num):
    return num <= 2 or (previous - num) >= RESTART_MIN_DROP


def _label_leading_section(text, end):
    """Label the first section, which is operative text unless the file is
    itself an appendix -- Gorontalo 1/2024 ships body, penjelasan and lampiran
    as three separate PDFs, so a file can open directly in a penjelasan."""
    head = text[:min(end, 4000)]
    for rx, label in ((PENJELASAN_HEADING, "penjelasan"),
                      (LAMPIRAN_HEADING, "lampiran")):
        m = rx.search(head)
        if m and not PASAL_HEADER.search(head[:m.start()]):
            return label
    return "body"


def split_sections(text):
    """Partition a document into sections by pasal-numbering restart.

    The first section is operative text. A later section beginning where the
    pasal sequence jumps backwards is an appendix -- in practice the
    penjelasan, whose pasal mirror the body's one for one. Heading matches
    label the sections but never define them, because OCR loses headings.
    """
    headers = list(PASAL_HEADER.finditer(text))
    if not headers:
        label = "lampiran" if LAMPIRAN_HEADING.search(text) else (
            "penjelasan" if PENJELASAN_HEADING.search(text) else "body")
        return [{"section": label, "start": 0, "end": len(text), "restart": False}], []

    cuts = [0]
    anomalies = []
    previous = None
    for h in headers:
        num = pasal_sort_key(h.group(1))
        if previous is not None and num < previous:
            repaired = _repair_candidate(h.group(1))
            if repaired is not None and repaired >= previous:
                previous = repaired
                continue
            if not _is_section_restart(previous, num):
                # The instrument renumbers mid-body. Record it and read on:
                # this is the document's own defect, not a section boundary.
                anomalies.append({
                    "warning": "pasal_numbering_goes_backwards",
                    "from": previous, "to": num, "offset": h.start(),
                })
                previous = num
                continue
            # The restart tells us a new section began; its heading, when the
            # scan kept one, sits above the restarted pasal along with the
            # section's own preamble (`I. UMUM`). Snap the cut up to that
            # heading so the preamble is not counted as operative text.
            window_start = cuts[-1]
            heading = None
            for rx in (PENJELASAN_HEADING, LAMPIRAN_HEADING):
                for m in rx.finditer(text, window_start, h.start()):
                    if heading is None or m.start() > heading:
                        heading = m.start()
            cuts.append(heading if heading is not None else h.start())
        previous = num

    # A lampiran carries no pasal of its own, so without a cut here its
    # tariff tables are absorbed into whichever pasal precedes them -- half a
    # million characters of table inside one pasal in Perda Semarang 4/2025 --
    # and their rows then parse as ayat and huruf, because a table numbered
    # 1, 2, 3 is a valid ascending run and sequence checking cannot tell it
    # from a real list. The heading is the only reliable boundary.
    restarts = set(cuts[1:])
    cuts.extend(m.start() for m in LAMPIRAN_HEADING.finditer(text))
    # An explicit PENJELASAN heading is a boundary in its own right. Numbering
    # restart cannot be the only signal: a penjelasan that happens to open on
    # the number the body closed with is not a jump backwards at all.
    cuts.extend(m.start() for m in PENJELASAN_HEADING.finditer(text))
    cuts.append(len(text))
    cuts = sorted(set(cuts))

    sections = []
    for i, start in enumerate(cuts[:-1]):
        end = cuts[i + 1]
        chunk = text[start:end]
        if i == 0:
            label = _label_leading_section(text, end)
        elif LAMPIRAN_HEADING.match(chunk):
            label = "lampiran"
        elif PENJELASAN_HEADING.search(chunk[:4000]):
            label = "penjelasan"
        elif LAMPIRAN_HEADING.search(chunk[:4000]):
            label = "lampiran"
        else:
            # Numbering restarted with no heading to explain it. In this corpus
            # that is the penjelasan with its heading lost to OCR, but say
            # "unlabelled" rather than assert what cannot be read.
            label = "unlabelled_restart"
        sections.append({
            "section": label, "start": start, "end": end,
            "restart": start in restarts,
        })
    return sections, anomalies


# A penjelasan article and the operative article it explains are different
# provisions and must not share a citation: `Pasal 32` is a 25% reklame rate,
# `Penjelasan Pasal 32` is `Cukup jelas.` Indonesian practice already writes
# it this way. An unlabelled restart gets a bracketed marker instead of an
# asserted name, because what the section is cannot be read from the scan.
SECTION_PREFIX = {
    "body": "",
    "penjelasan": "Penjelasan ",
    "lampiran": "Lampiran ",
    "unlabelled_restart": "[bagian tak berlabel] ",
}


def _section_prefix(section):
    return SECTION_PREFIX.get(section, f"[{section}] ")


def _multirun_warnings(pasal):
    """Flag a container holding more than one list opening.

    Two `huruf a` under one ayat means a parent marker was missed -- typically
    page furniture pushed the next `(2)` off the line start, so that ayat
    absorbed its siblings. The nesting below such a container is unreliable.
    """
    out = []
    for a in pasal["ayat"]:
        if sum(1 for h in a["huruf"] if h["huruf"] == "a") > 1:
            out.append({"warning": "multiple_huruf_runs_in_ayat",
                        "citation": a["citation"]})
        if sum(1 for g in a["angka"] if g["angka"] == "1") > 1:
            out.append({"warning": "multiple_angka_runs_in_ayat",
                        "citation": a["citation"]})
    if sum(1 for h in pasal["huruf"] if h["huruf"] == "a") > 1:
        out.append({"warning": "multiple_huruf_runs_in_pasal",
                    "citation": pasal["citation"]})
    return out


def segment(text):
    """Segment one instrument's text. Returns sections, pasal list, warnings."""
    sections, warnings = split_sections(text)
    pasal = []
    seen = {}

    for sec in sections:
        chunk = text[sec["start"]:sec["end"]]
        headers = list(PASAL_HEADER.finditer(chunk))
        for i, h in enumerate(headers):
            number = h.group(1)
            start = h.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(chunk)
            body = chunk[start:end]
            absolute = sec["start"] + start

            key = (sec["section"], number)
            seen[key] = seen.get(key, 0) + 1
            occurrence = seen[key]
            if occurrence > 1:
                warnings.append({
                    "warning": "duplicate_pasal_in_section",
                    "section": sec["section"],
                    "pasal": number,
                    "occurrence": occurrence,
                })

            citation = f"{_section_prefix(sec['section'])}Pasal {number}"
            if occurrence > 1:
                # No legal notation exists for an article the drafter numbered
                # twice, so mark it rather than emit two identical citations.
                citation += f" #{occurrence}"
            ayat = _parse_ayat(body, absolute, citation)
            huruf = [] if ayat else _parse_huruf(body, absolute, citation)
            pasal.append({
                "pasal": number,
                "section": sec["section"],
                "occurrence": occurrence,
                "citation": citation,
                "start": absolute,
                "end": sec["start"] + end,
                "text": body,
                "ayat": ayat,
                "huruf": huruf,
                "angka": [] if (ayat or huruf) else _parse_angka(body, absolute, citation),
            })
            warnings.extend(_multirun_warnings(pasal[-1]))

    return {"sections": sections, "pasal": pasal, "warnings": warnings}


# Page furniture sits at the top or bottom of a page and interrupts a
# provision that spans the break. In PP 35/2023 a catchword and stamp land
# between `Pasal 3 ayat (1)` and `ayat (2)` -- `PAB . . . SK No 145757A
# PRESIOEN REPIJBLIK INDONESIA -13-` -- pushing `(2)` off the line start, so
# ayat (1) swallowed its siblings and their a./b./c. lists collapsed under one
# citation. Position is what identifies furniture, not wording: `PRESIDEN`
# occurs 102 times in PP 35/2023 and every one is a page's first line, while
# `Cukup jelas.` occurs 245 times mid-page and is real text. Frequency alone
# would delete the latter.
FURNITURE_ZONE = 3           # lines from either end of a page
FURNITURE_MIN_PAGES = 0.15   # share of pages a repeated header must cover

# A catchword repeats the next page's opening words followed by spaced dots.
CATCHWORD = re.compile(r"\.\s*\.\s*\.\s*$")
PAGE_NUMBER = re.compile(r"^[-–\s]*\d{1,4}\s*[A-Za-z]?[-–\s]*$")
STAMP = re.compile(r"^SK\s*No\b|ditandatangani secara elektronik|"
                   r"Balai Sertifikasi Elektronik|\bBSrE\b", re.IGNORECASE)


def _zones(lines):
    """Split a page's filled line indices into (edge, middle).

    The zone shrinks on a short page so that a middle always exists; without
    that, every line on a five-line page counts as an edge and repeated body
    wording becomes indistinguishable from a running header.
    """
    filled = [i for i, ln in enumerate(lines) if ln.strip()]
    z = min(FURNITURE_ZONE, max(1, len(filled) // 3))
    edge = set(filled[:z] + filled[-z:])
    return edge, [i for i in filled if i not in edge]


def _is_patterned_furniture(line):
    if len(line) > 90:
        return False
    return bool(CATCHWORD.search(line) or PAGE_NUMBER.match(line) or STAMP.search(line))


def strip_page_furniture(pages):
    """Blank out headers, footers, catchwords and stamps, page by page.

    Only the first and last few lines of each page are eligible, so repeated
    body wording is never touched. Lines are blanked rather than deleted so
    that page offsets, and therefore every pasal's page attribution, still
    line up with the source.
    """
    split = [[ln for ln in page["text"].splitlines()] for page in pages]

    # A document's own header is whatever short line recurs at the page edges
    # and never once in the middle. The second half of that test is what keeps
    # real wording safe: `Cukup jelas.` recurs 245 times in PP 35/2023 but
    # mid-page, so frequency alone would delete it.
    edge, middle = collections.Counter(), collections.Counter()
    for lines in split:
        zone, rest = _zones(lines)
        for i in zone:
            edge[lines[i].strip()] += 1
        for i in rest:
            middle[lines[i].strip()] += 1
    threshold = max(2, int(len(split) * FURNITURE_MIN_PAGES))
    repeated = {ln for ln, n in edge.items()
                if n >= threshold and len(ln) <= 90 and not middle[ln]}

    removed = 0
    out = []
    for lines in split:
        zone, _rest = _zones(lines)
        kept = list(lines)
        for i in zone:
            stripped = lines[i].strip()
            if stripped in repeated or _is_patterned_furniture(stripped):
                kept[i] = " " * len(lines[i])
                removed += 1
        out.append("\n".join(kept))
    return out, removed


def join_pages(pages, strip_furniture=True):
    """Concatenate page texts, returning the text and each page's offset.

    Offsets let a pasal report which pages it came from, and therefore whether
    any of them were OCR'd -- a pasal assembled from OCR'd pages carries the
    reading-order caveat and should not be trusted equally.
    """
    if strip_furniture:
        cleaned, _ = strip_page_furniture(pages)
    else:
        cleaned = [page["text"] for page in pages]

    parts, spans, cursor = [], [], 0
    for page, text in zip(pages, cleaned):
        spans.append((cursor, cursor + len(text), page["page"], page["method"]))
        parts.append(text)
        cursor += len(text) + 1  # the newline join() puts between pages
    return "\n".join(parts), spans


def pages_for(spans, start, end):
    """Pages overlapped by a span, and the extraction methods behind them."""
    hit = [(p, m) for (s, e, p, m) in spans if s < end and start < e]
    return [p for p, _ in hit], sorted({m for _, m in hit})


def count_levels(segmented):
    counts = {"pasal": 0, "ayat": 0, "huruf": 0, "angka": 0}
    for p in segmented["pasal"]:
        counts["pasal"] += 1
        counts["angka"] += len(p["angka"])
        for h in p["huruf"]:
            counts["huruf"] += 1
            counts["angka"] += len(h["angka"])
        for a in p["ayat"]:
            counts["ayat"] += 1
            counts["angka"] += len(a["angka"])
            for h in a["huruf"]:
                counts["huruf"] += 1
                counts["angka"] += len(h["angka"])
    counts["units"] = sum(1 for _ in iter_units(segmented))
    return counts


def _angka_units(items):
    for a in items:
        yield a["citation"], a["text"]


def _huruf_units(items):
    for h in items:
        if h["angka"]:
            yield from _angka_units(h["angka"])
        else:
            yield h["citation"], h["text"]


def iter_units(segmented):
    """Yield every addressable unit as (citation, text), deepest level only.

    The deepest level is what a norm cites; a parent's text is the
    concatenation of its children and would double-count. Each level is
    walked explicitly rather than by probing for a child list, because a
    node's label and its children's level share a key name -- an angka node
    holds the string `"angka": "1"` where a huruf node holds a list.
    """
    for p in segmented["pasal"]:
        if p["ayat"]:
            for a in p["ayat"]:
                if a["huruf"]:
                    yield from _huruf_units(a["huruf"])
                elif a["angka"]:
                    yield from _angka_units(a["angka"])
                else:
                    yield a["citation"], a["text"]
        elif p["huruf"]:
            yield from _huruf_units(p["huruf"])
        elif p["angka"]:
            yield from _angka_units(p["angka"])
        else:
            yield p["citation"], p["text"]


def segment_document(record):
    """Segment one src/extract_text.py record into an addressable structure."""
    text, spans = join_pages(record["pages"])
    seg = segment(text)

    for p in seg["pasal"]:
        pages, methods = pages_for(spans, p["start"], p["end"])
        p["pages"] = pages
        p["extraction_methods"] = methods

    return {
        "doc_id": record["doc_id"],
        "source_pdf": record["source_pdf"],
        "batch": record["batch"],
        "n_pages": record["n_pages"],
        "counts": count_levels(seg),
        "sections": seg["sections"],
        "warnings": seg["warnings"],
        "pasal": seg["pasal"],
    }


def main():
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Segment the extracted corpus.")
    parser.add_argument("--in-dir", type=Path, default=Path("data/extracted"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/structured"))
    parser.add_argument("--filter", help="only process doc_ids containing this")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    totals = {"pasal": 0, "ayat": 0, "huruf": 0, "angka": 0, "units": 0}
    manifest, warned = [], 0

    for path in sorted(args.in_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        record = json.loads(path.read_text())
        if args.filter and args.filter.lower() not in record["doc_id"].lower():
            continue

        out = segment_document(record)
        (args.out_dir / f"{out['doc_id']}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1))

        for k in totals:
            totals[k] += out["counts"][k]
        warned += len(out["warnings"])

        sections = ",".join(s["section"] for s in out["sections"])
        note = f"  warnings={len(out['warnings'])}" if out["warnings"] else ""
        c = out["counts"]
        print(f"{out['doc_id'][:44]:<46} pasal={c['pasal']:<5} ayat={c['ayat']:<5} "
              f"huruf={c['huruf']:<5} angka={c['angka']:<5} units={c['units']:<5} "
              f"[{sections}]{note}", flush=True)

        manifest.append({
            "doc_id": out["doc_id"],
            "counts": out["counts"],
            "sections": [s["section"] for s in out["sections"]],
            "warnings": out["warnings"],
        })

    (args.out_dir / "manifest.json").write_text(
        json.dumps({"totals": totals, "documents": manifest},
                   ensure_ascii=False, indent=1))
    print(f"\ntotals: {totals}")
    print(f"documents with warnings: {sum(1 for m in manifest if m['warnings'])}"
          f" ({warned} warnings)")
    print(f"manifest -> {args.out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
