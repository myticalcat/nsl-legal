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

# Iterated, never just membership-tested. A `set` iterates in string-hash
# order, which Python randomises per process, so `_snap` and `_segment` picked
# a different winner between runs: `_snap('liga')` returned `lima` under some
# PYTHONHASHSEED values and `tiga` under others, silently turning a real corpus
# string into 5% or 3% depending on the run. Sorted, so a measurement made
# today reproduces tomorrow.
VOCAB_ORDER = tuple(sorted(VOCAB))

# What a word is worth, for deciding whether two repair candidates actually
# disagree. `belas` and `puluh` carry no value of their own.
WORD_VALUE = {**UNITS, **SPECIAL}


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
        for w in VOCAB_ORDER:
            L = len(w)
            if L <= i and best[i - L] is not None and tok[i - L:i] == w:
                cand = best[i - L] + [w]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    return best[n]


def _snap(tok):
    """Nearest vocabulary word within edit distance 1, or None if ambiguous.

    `liga` is one edit from both `lima` (5) and `tiga` (3), and the corpus
    contains it. Nothing inside the token breaks that tie, so repairing it is a
    guess dressed as recovery -- the same mistake as auto-correcting a
    `disagree`. Return None instead and let the digit channel or a human
    decide; `recover` already knows what to do with a channel that did not
    parse.

    Ties between words of the same value are not ambiguous and resolve
    normally. Measured: 4 of the 1,924 single-character corruptions of a
    numeral word are genuinely ambiguous, all of them lima/tiga via `tima`
    and `liga`.
    """
    if tok in VOCAB:
        return tok, False
    near = [w for w in VOCAB_ORDER if _lev(tok, w) == 1]
    if not near:
        return None, True
    if len({WORD_VALUE.get(w) for w in near}) > 1:
        return None, True
    return near[0], True


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
    return ([] if snapped is None else [snapped]), fixed


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


def _vocab_tokens(raw):
    """Normalise a parenthetical into vocabulary words.

    Returns (tokens, repaired, unresolved). `unresolved` matters because
    `_int_from` skips any token it does not recognise, so a word that could not
    be resolved would drop silently out of the fold and yield a confident wrong
    number -- `empat <noise> persen` as 4. Callers must refuse instead.
    """
    s = unicodedata.normalize("NFKD", raw.lower())
    s = re.sub(r"[^a-z ]", " ", s)
    toks, repaired, unresolved = [], False, False
    for t in s.split():
        pieces, fixed = _normalise_token(t)
        repaired |= fixed
        if not pieces:
            unresolved = True
        toks.extend(pieces)
    return toks, repaired, unresolved


def parse_words(raw):
    """'empat puluh persen' -> (0.40, False). Returns (value, was_repaired)."""
    toks, repaired, unresolved = _vocab_tokens(raw)
    if unresolved:
        return None, repaired

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


# ------------------------------------------------------- the duration channel

# A deadline writes its figure twice exactly as a rate does, but the shape
# differs: the unit sits *outside* the parenthetical (`12 (dua belas) bulan`)
# where a percentage keeps it inside (`10% (sepuluh persen)`). So this needs its
# own pattern rather than a wider PAIR.
#
# There are three day types, not two, and none is converted into another. A
# working day is not 1/7 of a week and the ratio depends on a calendar of
# public holidays; unqualified `hari` is conventionally calendar days but that
# is an interpretive claim, not a fact the parser may assume. Two norms
# measured in different day types are flagged, never reconciled.
#
# Measured over body pasal: 560 bulan, 327 tahun, 157 hari kerja, 50 hari,
# 8 hari kalender. Order matters -- the longer forms must precede bare `hari`
# in the alternation or `15 (lima belas) hari kalender` silently becomes a
# `hari`, which is the normalisation this is here to prevent.
TIME_UNITS = ("hari kerja", "hari kalender", "hari", "bulan", "tahun")
_UNIT_ALT = "|".join(u.replace(" ", r"\s+") for u in TIME_UNITS)

# The digit body carries the same glyph confusions as a rate, but there is no
# percent sign to anchor the right edge -- the closing parenthesis and the unit
# word do that job instead. Two things this pattern learned the hard way:
#
# Case-sensitive, for the same reason PAIR is. Under re.IGNORECASE the `I` in
# the digit class also matches the lowercase `i` of the preceding word, so
# `... lagi 12 (dua belas) bulan` captured `i 12`, which no longer parses as an
# integer. That silently dropped the digit channel on 51 pairs -- not a wrong
# value, but half the redundancy gone, which is worse because it is invisible.
# Only the unit alternation is case-folded, inline.
#
# Every gap allows a line break, because `pdftotext -layout` wraps a duration
# at each of them: `7\n   (tujuh) Hari` breaks before the parenthetical and
# `24 (dua puluh empat)\n   bulan` breaks before the unit. Forbidding newlines
# was measured and costs 235 of 1,181 real matches -- 113 at the first gap and
# 122 at the second -- so it is not an option.
#
# What actually caused the trouble is the missing left anchor. A percentage has
# `%` on its right; a duration has nothing, so the digit class happily started
# mid-number and let a lampiran tariff column bleed across lines:
# `1,500,000\n     (lima) hari` matched as the digits `000` against the words
# `lima`. The lookbehind fixes that at the source by refusing to begin inside a
# larger number, and costs exactly one match corpus-wide -- that artifact.
PAIR_DURATION = re.compile(
    r"(?<![\d.,])([0-9lIOoSB][0-9lIOoSB ]{0,5})"
    r"\s*[\(\[l]\s*([a-zA-Z][a-zA-Z\s]*?)\s*[\)\]]\s*"
    r"(?i:(" + _UNIT_ALT + r"))\b")

# A duration is a count, not a rate, so the percentage CEILING does not apply.
# This bound exists for the same reason that one does -- to catch digits glued
# together by a lost separator -- but at a scale a real deadline can reach.
# The longest observed in the corpus is 60 tahun.
DURATION_CEILING = 1000


def parse_digits_count(raw):
    """'l2' -> (12, True). A bare integer with glyph repair, no percent tail."""
    body = raw.strip().replace(" ", "")
    if not body:
        return None, False
    repaired = body.translate(GLYPH)
    if not re.fullmatch(r"\d+", repaired):
        return None, False
    val = int(repaired)
    if val > DURATION_CEILING:
        return None, True
    return val, repaired != body


def parse_words_count(raw):
    """'dua belas' -> (12, False). The word channel without a unit suffix."""
    toks, repaired, unresolved = _vocab_tokens(raw)
    if unresolved or not toks:
        return None, repaired
    # A duration is a whole count; `koma` here means the parenthetical is not
    # one, and `persen` means PAIR_DURATION matched something it should not.
    if "koma" in toks or "persen" in toks:
        return None, repaired
    val = _int_from(toks)
    if val == 0 or val > DURATION_CEILING:
        return None, repaired
    return val, repaired


def normalise_unit(raw):
    """'hari  kerja' -> 'hari_kerja'. Never collapses hari kerja into hari."""
    return re.sub(r"\s+", "_", raw.strip().lower())


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
    rec = _reconcile(numeral, words, *parse_digits(numeral), *parse_words(words))
    rec["unit"] = "fraction"
    return rec


def recover_duration(numeral, words, unit):
    """As `recover`, for a duration. The value is a count, and `unit` is kept
    verbatim rather than converted -- see TIME_UNITS."""
    rec = _reconcile(numeral, words,
                     *parse_digits_count(numeral), *parse_words_count(words))
    rec["unit"] = normalise_unit(unit)
    return rec


def _reconcile(numeral, words, dv, dr, wv, wr):
    """The channel arithmetic, shared by every unit.

    Deliberately knows nothing about what the number measures: the asymmetry it
    exploits is in the encoding, not the quantity. Measured over the numeral
    vocabulary, 78.3% of single-character digit corruptions parse to a valid
    but different number, while 0 of 1,924 word corruptions land on another
    vocabulary word -- the spelled-out channel is error-detecting and the digit
    channel is not. That is why a repaired channel yields to an unrepaired one,
    and why two clean channels that disagree are referred rather than resolved.
    """
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
    """Find and recover every double-written numeral in a document.

    Covers both shapes: a percentage, which keeps its unit inside the
    parenthetical, and a duration, which puts it after. Each record carries the
    character offsets of the whole match so callers can annotate the source
    text in place, and the list is returned in reading order so slot ids follow
    the page.
    """
    out = []
    for m in PAIR.finditer(text):
        rec = recover(m.group(1).strip(), m.group(2).strip())
        rec["start"], rec["end"] = m.start(), m.end()
        rec["matched_text"] = m.group(0)
        out.append(rec)

    taken = [(r["start"], r["end"]) for r in out]
    for m in PAIR_DURATION.finditer(text):
        # A percentage never has a time unit after its parenthetical, so the
        # two patterns should not compete. Assert it rather than assume it.
        if any(s < m.end() and m.start() < e for s, e in taken):
            continue
        rec = recover_duration(m.group(1).strip(), m.group(2).strip(), m.group(3))
        rec["start"], rec["end"] = m.start(), m.end()
        rec["matched_text"] = m.group(0)
        out.append(rec)

    out.sort(key=lambda r: (r["start"], r["end"]))
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
