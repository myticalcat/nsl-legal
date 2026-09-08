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
    bad = run(CASES, "recovery") + run(ATOMIC, "atomic se- forms")
    print("\nall passed" if bad == 0 else f"\n{bad} failing")
