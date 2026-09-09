#!/usr/bin/env python3
"""Regression tests for numeral slotting and structural provenance. Every
fixture is real text from the corpus, ragged indentation and scan damage
included.

The span check these tests once covered is retired (see CLAUDE.md, spans vs
offsets, resolved 2026-09-09). `canonical` survives as a normaliser for text
lifted out of a unit, so its tests survive with it; provenance is now the
assertion that a slot lies inside the unit its norm cites.
"""

import structure
from slotting import canonical, resolve, slot_text, unit_index

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  -- {detail}" if detail else ""))
        FAILURES.append(name)


# UU 1/2022 Pasal 58 ayat (1), exactly as pdftotext -layout yields it.
WRAPPED = ("TarifPBJT ditetapkan paling tinggi sebesar 10% (sepuluh\n"
           "                   persen).")

# UU 1/2022 Pasal 149 ayat (1): a compound broken across a line.
HYPHEN_WRAP = ("penggunaannya berdasarkan peraturan perundang-\n"
               "                    undangan pada tahun anggaran")

# Perda Cilegon 1/2024 carries literal soft hyphens from the scan.
SOFT = "- 4 ­\n\n\n\n\n9.     Wajib    Pajak    adalah"

# UU 1/2022 Pasal 58 as the scan actually renders it: `10%` degraded to `lOVo`,
# `40%` to `4Oo/o`, and the opening paren of `(empat` read as an `l`. Three of
# the five numerals here need OCR recovery, and ayat (3) carries a huruf list
# so the pasal exercises every level of the citation set.
PASAL_58 = (
    "Pasal 58\n"
    "                (1) TarifPBJT ditetapkan paling tinggi sebesar lOVo\n"
    "                   (sepuluh persen).\n"
    "                (2) Khusus tarif PBJT atas jasa hiburan pada diskotek,\n"
    "                    karaoke, kelab malam, bar, dan mandi uap/spa\n"
    "                    ditetapkan paling rendah 4Oo/o lempat puluh persen) dan\n"
    "                    paling tinggi 75% (tujuh puluh lima persen).\n"
    "                (3) Khusus tarif PBJT atas Tenaga Listrik untuk:\n"
    "                    a. konsumsi Tenaga Listrik dari sumber lain oleh\n"
    "                        industri, pertambangan minyak bumi dan gas alam,\n"
    "                        ditetapkan paling tinggi sebesar 3% (tiga persen); dan\n"
    "                    b. konsumsi Tenaga Listrik yang dihasilkan sendiri,\n"
    "                        ditetapkan paling tinggi 1,5% (satu koma lima\n"
    "                       persen).\n"
)


def pasal_58():
    return structure.segment(PASAL_58)["pasal"][0]


def test_canonical_collapses_layout_only():
    check("wrapped line joins",
          canonical(WRAPPED)
          == "TarifPBJT ditetapkan paling tinggi sebesar 10% (sepuluh persen).",
          canonical(WRAPPED))
    # All 314 hyphen-at-break cases in the corpus are real compounds, so the
    # hyphen must survive the join.
    check("hyphenated compound keeps its hyphen",
          "perundang-undangan" in canonical(HYPHEN_WRAP), canonical(HYPHEN_WRAP))
    check("soft hyphen removed", "­" not in canonical(SOFT), canonical(SOFT))
    check("runs of spaces collapse",
          canonical(SOFT) == "- 4 9. Wajib Pajak adalah", canonical(SOFT))
    check("content is untouched",
          canonical("  4Oo/o  (empat  puluh persen) ") == "4Oo/o (empat puluh persen)")


def test_unit_index_is_the_closed_citation_set():
    index = unit_index(pasal_58())
    check("every level present", set(index) == {
        "Pasal 58", "Pasal 58 ayat (1)", "Pasal 58 ayat (2)",
        "Pasal 58 ayat (3)", "Pasal 58 ayat (3) huruf a",
        "Pasal 58 ayat (3) huruf b"}, sorted(index))
    # The chapeau of ayat (3) is a unit in its own right even though it has
    # huruf children; 379 slots corpus-wide resolve to a unit of this shape.
    check("parent of a huruf list is still citable",
          index["Pasal 58 ayat (3)"][2] == "ayat", index["Pasal 58 ayat (3)"])


def test_slots_join_and_leave_a_coverage_trail():
    pasal = pasal_58()
    annotated, table = slot_text(pasal["text"])
    check("five numerals found", len(table) == 5, sorted(table))
    check("markers land in the annotated text", "[N1]" in annotated and "[N5]" in annotated)
    check("lOVo recovered to 10%", table["N1"]["value"] == 0.10, table["N1"])
    check("4Oo/o recovered to 40%", table["N2"]["value"] == 0.40, table["N2"])
    check("recovery is flagged", table["N2"]["ocr_recovered"] is True)

    norms = [
        {"id": "UU-58-1", "citation": "Pasal 58 ayat (1)",
         "bounds": [{"op": "<=", "numeral_slot": "N1"}]},
        {"id": "UU-58-2", "citation": "Pasal 58 ayat (2)",
         "bounds": [{"op": ">=", "numeral_slot": "N2"},
                    {"op": "<=", "numeral_slot": "N3"}]},
    ]
    resolved, errors, orphans = resolve(norms, table, pasal)
    check("correct output validates", not errors, errors)
    check("value joined from the table",
          resolved[0]["bounds"][0]["value"] == 0.10, resolved[0]["bounds"][0])
    check("provenance joined too",
          resolved[1]["bounds"][0]["source_numeral"] == "4Oo/o", resolved[1]["bounds"][0])
    # Nobody extracted ayat (3); its two numerals are unaccounted for, and that
    # is the cheapest recall check in the pipeline.
    check("unextracted numerals surface as orphans",
          orphans == ["N4", "N5"], orphans)


def test_slot_must_lie_inside_the_cited_unit():
    # The check the span test used to do, done structurally. N3 is ayat (2)'s
    # ceiling; filing it under ayat (1) is exactly the mislocation a substring
    # test could never catch, since the text is a real substring of the pasal
    # either way.
    pasal = pasal_58()
    _, table = slot_text(pasal["text"])
    norms = [{"id": "WRONG", "citation": "Pasal 58 ayat (1)",
              "bounds": [{"op": "<=", "numeral_slot": "N3"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("misfiled slot is rejected",
          any(e["error"] == "slot_outside_cited_unit" for e in errors), errors)

    # A huruf's slot is inside its parent ayat as well, so citing the chapeau
    # is not an error -- only citing a sibling is.
    norms = [{"id": "PARENT", "citation": "Pasal 58 ayat (3)",
              "bounds": [{"op": "<=", "numeral_slot": "N4"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("citing the parent of the slot's unit is allowed", not errors, errors)

    norms = [{"id": "SIBLING", "citation": "Pasal 58 ayat (3) huruf a",
              "bounds": [{"op": "<=", "numeral_slot": "N5"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("citing a sibling huruf is rejected",
          any(e["error"] == "slot_outside_cited_unit" for e in errors), errors)


def test_composed_citation_is_rejected():
    # The model selects from the closed set; it never composes. `ayat (5)` does
    # not exist in this pasal, and a plausible-looking citation is the failure
    # mode that motivated closing the set in the first place.
    pasal = pasal_58()
    _, table = slot_text(pasal["text"])
    norms = [{"id": "INVENTED", "citation": "Pasal 58 ayat (5)",
              "bounds": [{"op": "<=", "numeral_slot": "N1"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("citation outside the closed set is rejected",
          any(e["error"] == "citation_not_in_pasal" for e in errors), errors)


def test_slot_hygiene():
    pasal = pasal_58()
    _, table = slot_text(pasal["text"])

    norms = [{"id": "A", "citation": "Pasal 58 ayat (2)",
              "bounds": [{"op": ">=", "numeral_slot": "N2"},
                         {"op": "<=", "numeral_slot": "N2"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("a slot cannot serve two bounds",
          any(e["error"] == "slot_reused" for e in errors), errors)

    norms = [{"id": "B", "citation": "Pasal 58 ayat (2)",
              "bounds": [{"op": ">=", "numeral_slot": "N9"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("a hallucinated slot is rejected",
          any(e["error"] == "unknown_slot" for e in errors), errors)

    # 75% as the floor and 40% as the ceiling: both slots are real and both are
    # inside ayat (2), so only the ordering check catches this.
    norms = [{"id": "C", "citation": "Pasal 58 ayat (2)",
              "bounds": [{"op": ">=", "numeral_slot": "N3"},
                         {"op": "<=", "numeral_slot": "N2"}]}]
    _, errors, _ = resolve(norms, table, pasal)
    check("floor above ceiling is rejected",
          any(e["error"] == "floor_above_ceiling" for e in errors), errors)


if __name__ == "__main__":
    import sys
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            print(f"\n{name}:")
            fn()
    print("\n" + ("all passed" if not FAILURES else f"{len(FAILURES)} failing: {FAILURES}"))
    sys.exit(1 if FAILURES else 0)
