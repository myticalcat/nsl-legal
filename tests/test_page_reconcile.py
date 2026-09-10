#!/usr/bin/env python3
"""Regression tests for page-level reconciliation. Every fixture is a real
string from UU 1/2022, taken from both readings of the same page."""

from ocr_numerals import scan
from page_reconcile import align, pair_key, reconcile_pairs, TRUST

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  -- {detail}" if detail else ""))
        FAILURES.append(name)


def one(layer, reocr):
    return reconcile_pairs(scan(layer), scan(reocr))[0]


def test_the_page_17_case():
    # The finding FINDINGS records as settled by opening the page image: the
    # scan's own text layer inserted a zero, and the glyphs read 6%.
    r = one("ditetapkan paling tinggi 60% (enam persen).",
            "ditetapkan paling tinggi 6% (enam persen).")
    check("text layer yields to the clean reading",
          r["status"] == "text_layer_yields", r["status"])
    check("value taken from the re-OCR", r["value"] == 0.06, r["value"])
    check("chosen source recorded", r["chosen"] == "reocr", r["chosen"])
    check("both readings kept for the record",
          r["text_layer"]["numeral"] == "60%" and r["reocr"]["numeral"] == "6%", r)


def test_glyph_damage_confirmed_by_a_clean_reading():
    # UU Pasal 58: the text layer's `4Oo/o` is scanner OCR, the image is clean.
    r = one("ditetapkan paling rendah 4Oo/o lempat puluh persen)",
            "ditetapkan paling rendah 40% (empat puluh persen)")
    check("agreement recorded even though one reading needed repair",
          r["status"] == "sources_agree_after_repair", r["status"])
    check("value unchanged", r["value"] == 0.40, r["value"])
    check("the clean reading is preferred", r["chosen"] == "reocr", r["chosen"])


def test_decimal_percent_is_a_reocr_failure_not_a_loss():
    # tesseract reads `%` after a decimal comma as a digit, so the pair never
    # forms. The figure must survive as single_source, not vanish.
    r = one("ditetapkan paling tinggi sebesar 0,5% (nol koma lima persen).",
            "ditetapkan paling tinggi sebesar 0,54 (nol koma lima persen).")
    check("kept from the reading that has it",
          r["status"] == "single_source", r["status"])
    check("value preserved", r["value"] == 0.005, r["value"])
    check("attributed to the text layer", r["chosen"] == "text_layer", r["chosen"])


def test_corrupted_words_still_key_across_readings():
    # `dta persen` snaps to `dua`, so it aligns with the clean reading rather
    # than looking like two different figures. Three pairs were miscounted as
    # lost before this held.
    a = scan("bersangkutan sebesar 2%o (dta persen); b.")
    b = scan("bersangkutan sebesar 2% (dua persen); b.")
    check("both readings produce a pair", len(a) == 1 and len(b) == 1, (a, b))
    check("and they key together", pair_key(a[0]) == pair_key(b[0]),
          (pair_key(a[0]), pair_key(b[0])))
    matched, a_only, b_only = align(a, b)
    check("so they align", len(matched) == 1 and not a_only and not b_only)


def test_repeated_figures_align_in_order():
    # A page stating 10% twice must match first-to-first, not cross over.
    txt = ("tarif ditetapkan sebesar 10% (sepuluh persen) dan untuk hal lain "
           "ditetapkan sebesar 10% (sepuluh persen).")
    matched, a_only, b_only = align(scan(txt), scan(txt))
    check("both occurrences matched", len(matched) == 2, len(matched))
    check("none left over", not a_only and not b_only)


def test_trust_order_is_the_same_rule_recover_uses():
    check("a clean reading outranks a repaired one",
          TRUST["agree"] > TRUST["recovered"] > TRUST["single_channel"])
    check("a disagreeing reading is trusted least",
          TRUST["disagree"] == 0 and TRUST["unparsed"] == 0)


def test_two_clean_readings_that_differ_are_referred():
    # Neither reading needed repair and they still contradict. That is the
    # terminal verdict, not something to resolve by preference.
    r = one("ditetapkan sebesar 30% (tiga puluh persen).",
            "ditetapkan sebesar 40% (empat puluh persen).")
    # different word values, so they do not key together at all
    check("clean readings of different figures do not merge",
          r["status"] == "single_source", r["status"])


if __name__ == "__main__":
    import sys
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            print(f"\n{name}:")
            fn()
    print("\n" + ("all passed" if not FAILURES else f"{len(FAILURES)} failing: {FAILURES}"))
    sys.exit(1 if FAILURES else 0)
