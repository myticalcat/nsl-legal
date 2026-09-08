#!/usr/bin/env python3
"""
OCR numeral recovery for scanned Indonesian legislation.

Indonesian legal drafting writes every figure twice: digits, then the same
figure spelled out in parentheses. Scanning corrupts both, but independently
and in different ways -- glyph confusion hits the digits, word-shape errors
hit the words. Parsing both channels and reconciling them recovers values
neither channel gives alone, and flags the residue instead of guessing.
"""

import re
import unicodedata

# ------------------------------------------------------- channel 1: digits

# Glyph confusions observed in UU 1/2022 (Canon scan, Helvetica text layer).
GLYPH = str.maketrans({"l": "1", "I": "1", "O": "0", "o": "0", "S": "5", "B": "8"})

# Values above 100 are legitimate: a tax-inclusive base is divided by 110% to
# recover the pre-tax figure (Perwal Jogja 51/2024), and a room-class tariff is
# capped at 125% of the class below it (Perda Tangerang 1/2025). The bound is
# only here to catch a mangled '%' that left its digits glued to the number --
# '2070%' is 20%, not 2070% -- which inflates by roughly 100x, so anything in
# the plausible-rate range still fails it. Raise it if a real rate exceeds it;
# the highest yet observed is 125%.
CEILING = 300

# The percent sign degrades into a family of look-alikes.
#
# 'o%' is deliberately absent. It is indistinguishable from a corrupted zero
# ('O' for '0') sitting in front of an intact '%', and the alternation would
# match it two characters from the right, stripping the digit before GLYPH
# could repair it -- '1O%' parsed as 1%, '6O%' as 6%. Real occurrences in
# PP 35/2023 and Perda Mojokerto 7/2023 are corrupted zeroes, not corrupted
# percent signs, so the bare '%' branch must win and leave the 'O' in the body.
PCT_TAIL = re.compile(r"(?:%|Vo|Yo|o/o|7o|%o|Zo)\s*$", re.IGNORECASE)


def parse_digits(raw):
    """'2Oo/o' -> (0.20, True). Returns (value, was_repaired) or (None, _)."""
    s = raw.strip()
    # A leading huruf/angka marker ('i ', 'b. ') is followed by space or period.
    # A corrupted leading digit ('l0%', 'I2%') is not -- so the separator
    # is what distinguishes 'b. 10%' from 'l0%'.
    s = re.sub(r"^[a-zA-Z]\.?\s+", "", s)
    body = PCT_TAIL.sub("", s)
    if body == s:
        return None, False
    repaired = body.translate(GLYPH).replace(",", ".").replace(" ", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", repaired)
    if not m:
        return None, False
    val = float(m.group(1))
    if val > CEILING:
        return None, True
    return val / 100.0, repaired != body


# -------------------------------------------------------- channel 2: words

UNITS = {
    "nol": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
}
SPECIAL = {"sepuluh": 10, "sebelas": 11, "seratus": 100, "seribu": 1000}
STRUCT = {"belas", "puluh", "ratus", "koma", "persen"}
VOCAB = set(UNITS) | set(SPECIAL) | STRUCT


def _lev(a, b):
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _segment(tok):
    """
    Split a glued token into vocabulary words: 'duabelas' -> ['dua','belas'].

    Safe because the vocabulary is closed and no 'se-' form has a vocabulary
    word as a prefix ('se' is not a word), so 'sepuluh' and 'sebelas' cannot
    be wrongly decomposed. Prefers the segmentation with fewest pieces.
    """
    n = len(tok)
    best = [None] * (n + 1)
    best[0] = []
    for i in range(1, n + 1):
        for w in VOCAB:
            L = len(w)
            if L <= i and best[i - L] is not None and tok[i - L:i] == w:
                cand = best[i - L] + [w]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    return best[n]


def _snap(tok):
    """Nearest vocabulary word within edit distance 1. 'liga' -> 'tiga'."""
    if tok in VOCAB:
        return tok, False
    best, bd = None, 2
    for w in VOCAB:
        d = _lev(tok, w)
        if d < bd:
            best, bd = w, d
    return (best, True) if best else (tok, True)


def _normalise_token(tok):
    """
    Resolve one raw token into vocabulary words.

    Order matters: exact, then segmentation, then fuzzy. Trying fuzzy first
    would snap 'duabelas' onto 'sebelas' territory or fail outright; trying
    segmentation on a merely misspelled token wastes nothing because it
    returns None.
    """
    if tok in VOCAB:
        return [tok], False
    seg = _segment(tok)
    if seg:
        return seg, True
    snapped, fixed = _snap(tok)
    return [snapped], fixed


def _int_from(tokens):
    """Fold Indonesian number words into an integer. Handles belas/puluh/ratus."""
    total, cur = 0, 0
    for t in tokens:
        if t in UNITS:
            cur = UNITS[t]
        elif t == "sepuluh":
            cur = 10
        elif t == "sebelas":
            cur = 11
        elif t == "seratus":
            total += 100
            cur = 0
        elif t == "belas":
            cur = 10 + cur
        elif t == "puluh":
            total += (cur or 1) * 10
            cur = 0
        elif t == "ratus":
            total += (cur or 1) * 100
            cur = 0
    return total + cur


def parse_words(raw):
    """'empat puluh persen' -> (0.40, False). Returns (value, was_repaired)."""
    s = unicodedata.normalize("NFKD", raw.lower())
    s = re.sub(r"[^a-z ]", " ", s)
    toks, repaired = [], False
    for t in s.split():
        pieces, fixed = _normalise_token(t)
        repaired |= fixed
        toks.extend(pieces)

    if "persen" not in toks:
        return None, repaired
    toks = toks[: toks.index("persen")]
    if not toks:
        return None, repaired

    if "koma" in toks:
        i = toks.index("koma")
        whole = _int_from(toks[:i])
        frac_digits = "".join(str(UNITS[t]) for t in toks[i + 1:] if t in UNITS)
        val = float(f"{whole}.{frac_digits}") if frac_digits else float(whole)
    else:
        val = float(_int_from(toks))

    if val > CEILING:
        return None, repaired
    return val / 100.0, repaired


# ---------------------------------------------------------- reconciliation

# Numeral-plus-parenthetical pair. Case-sensitive on purpose: with IGNORECASE
# the 'I' in the digit class matched the lowercase 'i' of "paling tinggi",
# dragging a stray letter into every capture. The words may wrap across lines,
# so whitespace inside the parenthetical includes newlines -- but the digit
# body allows only spaces, or it would swallow the next line.
PAIR = re.compile(
    r"([0-9lIOoSB][0-9lIOoSB,. ]{0,8}(?:%|[VY]o|o/o|7o|o%|%o|Zo))"
    r"\s*[\(\[l]\s*([a-zA-Z][a-zA-Z\s]*?persen)\s*[\)\]]?"
)


def recover(numeral, words):
    """
    Reconcile the two channels into one value plus a provenance record.

    status:
      agree           both parsed, identical            -> trust
      recovered       one channel repaired, agrees      -> trust, flag
      single_channel  only one channel parsed           -> trust, flag
      disagree        both parsed, different values     -> HUMAN REVIEW
      unparsed        neither channel                   -> HUMAN REVIEW
    """
    dv, dr = parse_digits(numeral)
    wv, wr = parse_words(words)

    rec = {
        "source_numeral": numeral,
        "source_words": words,
        "digit_value": dv, "digit_repaired": dr,
        "word_value": wv, "word_repaired": wr,
    }

    if dv is not None and wv is not None:
        if abs(dv - wv) < 1e-9:
            rec["value"] = dv
            rec["status"] = "recovered" if (dr or wr) else "agree"
        else:
            # both parsed but disagree: prefer the channel that needed no repair
            if dr and not wr:
                rec["value"], rec["status"] = wv, "recovered"
            elif wr and not dr:
                rec["value"], rec["status"] = dv, "recovered"
            else:
                rec["value"], rec["status"] = None, "disagree"
    elif dv is not None:
        rec["value"], rec["status"] = dv, "single_channel"
    elif wv is not None:
        rec["value"], rec["status"] = wv, "single_channel"
    else:
        rec["value"], rec["status"] = None, "unparsed"

    rec["ocr_recovered"] = rec["status"] in ("recovered", "single_channel")
    rec["needs_review"] = rec["status"] in ("disagree", "unparsed")
    return rec


def scan(text):
    """Find and recover every digits-plus-words percentage pair in a document.

    Each record carries the character offsets of the whole match so callers
    can annotate the source text in place.
    """
    out = []
    for m in PAIR.finditer(text):
        rec = recover(m.group(1).strip(), m.group(2).strip())
        rec["start"], rec["end"] = m.start(), m.end()
        rec["matched_text"] = m.group(0)
        out.append(rec)
    return out


if __name__ == "__main__":
    import sys, collections
    txt = open(sys.argv[1]).read()
    results = scan(txt)
    tally = collections.Counter(r["status"] for r in results)

    print(f"{len(results)} numeral pairs found\n")
    for r in results:
        mark = "!!" if r["needs_review"] else ("~ " if r["ocr_recovered"] else "  ")
        val = f"{r['value']:.3%}" if r["value"] is not None else "REVIEW"
        print(f"{mark} {val:>9}  {r['status']:<15} "
              f"{r['source_numeral']:<10} ({r['source_words']})")
    print("\n" + "  ".join(f"{k}: {v}" for k, v in tally.most_common()))
