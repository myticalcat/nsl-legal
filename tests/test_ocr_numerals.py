#!/usr/bin/env python3
"""Regression tests for numeral recovery. Every case below is a real string
observed in a scanned Indonesian statute, not a constructed example."""

from ocr_numerals import recover

# (numeral, words, expected_value)
CASES = [
    # --- glued word tokens (the failure class this suite was written for)
    ("l2%o",   "duabelas persen",                        0.12),
    ("0,2%",   "nol komadua persen",                     0.002),
    ("10%",    "sepuluhpersen",                          0.10),
    ("5%",     "limapersen",                             0.05),
    ("i 1,5%", "satu koma limapersen",                   0.015),
    ("2Oo/o",  "duapuluh persen",                        0.20),
    ("7,5%",   "tujuhkoma lima persen",                  0.075),
    ("8,9%",   "delapankoma sembilan persen",            0.089),
    ("16,2%o", "enambelas koma dua persen",              0.162),
    ("73,8%",  "tujuhpuluh tiga koma delapan persen",    0.738),
    ("O,8Vo",  "nol komadelapan persen",                 0.008),
    ("1,27o",  "satu komadua persen",                    0.012),
    ("32%",    "tiga puluhdua persen",                   0.32),
    ("48%",    "empat puluhdelapan persen",              0.48),
    ("80%",    "delapan puluhpersen",                    0.80),
    ("16%",    "enam belaspersen",                       0.16),
    ("30%",    "tiga puluhpersen",                       0.30),
    ("50%",    "lima puluhpersen",                       0.50),
    ("9,5%",   "sembilan koma limapersen",               0.095),
    ("4o/o",   "empatpersen",                            0.04),
    ("13,5%",  "tiga belaskoma lima persen",             0.135),
    ("6Vo",    "enampersen",                             0.06),
    ("19,5%",  "sembilan belas komalima persen",         0.195),

    # --- glyph corruption in the digit channel
    ("2Oo/o",  "dua puluh persen",                       0.20),
    ("lOVo",   "sepuluh persen",                         0.10),
    ("4Oo/o",  "empat puluh persen",                     0.40),
    ("2 57o",  "dua puluh lima persen",                  0.25),
    ("l0%",    "sepuluh persen",                         0.10),
    ("9Oo/o",  "sembilan puluh persen",                  0.90),
    ("1007o",  "seratus persen",                         1.00),
    ("15,57o", "lima belas koma lima persen",            0.155),
    ("3,6%o",  "tiga koma enam persen",                  0.036),

    # --- corruption in the word channel
    ("i 3o/o", "liga persen",                            0.03),
    ("2%o",    "dta persen",                             0.02),

    # --- both channels corrupted, independently
    ("l2%o",   "dta belas persen",                       0.12),

    # --- huruf markers must not be read as digits
    ("b. 10%", "sepuluh persen",                         0.10),
    ("i 75%",  "tujuh puluh lima persen",                0.75),

    # --- corrupted zero in front of an intact '%'
    # The 'o%' branch of PCT_TAIL used to consume the 'O' as part of a
    # corrupted percent sign, so the digit never reached GLYPH: '1O%' came
    # back as 1% and '6O%' as 6%, and only the word channel disagreeing
    # exposed it. Verified against the page images.
    ("1O%",    "sepuluh persen",                         0.10),   # PP 35/2023 Pasal 25(1)
    ("6O%",    "enam puluh persen",                      0.60),   # PP 35/2023 penjelasan; same string in Perda Mojokerto 7/2023, born-digital

    # --- rates above 100% are legitimate, not corruption
    # A tax-inclusive base is divided by 110% to recover the pre-tax figure;
    # a room-class tariff is capped at 125% of the class below. Both channels
    # agree on these, and the old ceiling of 100 discarded them as unparsed.
    ("110%",   "seratus sepuluh persen",                 1.10),   # Perwal Jogja 51/2024
    ("125%",   "seratus dua puluh lima persen",          1.25),   # Perda Tangerang 1/2025

    # --- clean baseline
    ("10%",    "sepuluh persen",                         0.10),
    ("30,5%",  "tiga puluh koma lima persen",            0.305),
    ("16%",    "enam belas persen",                      0.16),
]

# Segmentation must never invent a split for atomic 'se-' forms.
ATOMIC = [
    ("10%",  "sepuluh persen",  0.10),
    ("11%",  "sebelas persen",  0.11),
    ("100%", "seratus persen",  1.00),
]


# Durations, from real provisions. The unit sits outside the parenthetical
# here, which is why these need their own channel.
DURATIONS = [
    ("12", "dua belas",   "bulan",        12, "bulan"),
    ("3",  "tiga",        "hari kerja",    3, "hari_kerja"),
    ("30", "tiga puluh",  "hari",         30, "hari"),
    ("15", "lima belas",  "hari kalender", 15, "hari_kalender"),
    ("5",  "lima",        "tahun",         5, "tahun"),
    ("24", "dua puluh empat", "bulan",    24, "bulan"),
    # glyph damage reaches a deadline's digits the same way it reaches a rate's
    ("l2", "dua belas",   "bulan",        12, "bulan"),
    ("6O", "enam puluh",  "tahun",        60, "tahun"),
]


def run_durations():
    from ocr_numerals import recover_duration
    fails = []
    for numeral, words, unit, expected, expected_unit in DURATIONS:
        r = recover_duration(numeral, words, unit)
        if r["value"] != expected or r["unit"] != expected_unit:
            fails.append((numeral, words, unit, expected, r["value"], r["unit"]))
    print(f"durations: {len(DURATIONS) - len(fails)}/{len(DURATIONS)} passed")
    for n, w, u, e, g, gu in fails:
        print(f"  FAIL  {n} ({w}) {u}: expected {e} {u}, got {g} {gu}")
    return len(fails)


def run_invariants():
    """Properties that are not table-driven."""
    from ocr_numerals import (PAIR_DURATION, _snap, parse_words,
                              parse_words_count, scan)
    fails = []

    def check(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    # `liga` is one edit from both `lima` (5) and `tiga` (3). Repairing it is a
    # guess, and picking by set-iteration order made the guess depend on
    # PYTHONHASHSEED -- 0.05 on some runs, 0.03 on others.
    check("ambiguous repair refuses rather than guessing",
          _snap("liga") == (None, True) and parse_words("liga persen")[0] is None)
    check("unambiguous repair still works",
          _snap("empal") == ("empat", True))
    # `_int_from` skips tokens it does not know, so an unresolvable word must
    # fail the parse rather than drop out of the fold.
    check("unresolvable word does not silently drop",
          parse_words("empat zzzzzz persen")[0] is None)

    # The two shapes must not compete for the same text.
    check("a percentage is not read as a duration",
          PAIR_DURATION.search("sebesar 10% (sepuluh persen)") is None)
    check("hari kalender is not folded into hari",
          PAIR_DURATION.search("15 (lima belas) hari kalender").group(3).lower()
          == "hari kalender")
    check("a duration parenthetical with koma is refused",
          parse_words_count("satu koma lima") is None or
          parse_words_count("satu koma lima")[0] is None)

    # Perda Kupang 1/2024 lampiran: a tariff column between a number and the
    # parenthetical of the next line. Without a left anchor the digit class
    # started inside `1,500,000` and paired `000` with `lima`.
    check("a lampiran tariff column does not bleed into a duration",
          PAIR_DURATION.search(
              "               1,500,000\n         selama 5 (lima) hari"
          ).group(1).strip() == "5")
    # With re.IGNORECASE the `I` of the digit class matched the lowercase `i`
    # of the preceding word, capturing `i 12` and killing the digit channel on
    # 51 pairs -- a silent loss of half the redundancy, not a wrong value.
    m = PAIR_DURATION.search("berlaku lagi 12 (dua belas) bulan")
    check("a preceding lowercase i is not swallowed as a digit",
          m is not None and m.group(1).strip() == "12")
    # Both gaps wrap in the real corpus and both must survive.
    check("line break before the parenthetical",
          PAIR_DURATION.search("7\n      (tujuh) Hari") is not None)
    check("line break before the unit",
          PAIR_DURATION.search("24 (dua puluh empat)\n      bulan") is not None)

    # Reading order, so slot ids follow the page.
    hits = scan("paling lama 3 (tiga) bulan dan tarif 10% (sepuluh persen) "
                "serta 5 (lima) hari kerja")
    check("both channels found in one pass", len(hits) == 3)
    check("returned in reading order",
          [h["start"] for h in hits] == sorted(h["start"] for h in hits))
    check("units carried through",
          [h["unit"] for h in hits] == ["bulan", "fraction", "hari_kerja"])
    return len(fails)


def run(cases, label):
    fails = []
    for numeral, words, expected in cases:
        r = recover(numeral, words)
        got = r["value"]
        if got is None or abs(got - expected) > 1e-9:
            fails.append((numeral, words, expected, got, r["status"]))
    print(f"{label}: {len(cases) - len(fails)}/{len(cases)} passed")
    for n, w, e, g, st in fails:
        shown = f"{g:.4f}" if g is not None else "None"
        print(f"  FAIL  {n:<10} ({w})")
        print(f"        expected {e:.4f}  got {shown}  [{st}]")
    return len(fails)


if __name__ == "__main__":
    bad = run(CASES, "recovery") + run(ATOMIC, "atomic se- forms") + run_durations()
    print("\ninvariants:")
    bad += run_invariants()
    print("\nall passed" if bad == 0 else f"\n{bad} failing")
