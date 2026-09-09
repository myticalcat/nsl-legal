#!/usr/bin/env python3
"""
Numeral slotting: the join between deterministic OCR recovery and LLM extraction.

The model never sees a number it has to transcribe. Before extraction, every
recovered numeral pair in the Pasal is tagged with a slot id. The model's only
job for numbers is to say which slot belongs to which bound, and what the
operator is -- both linguistic judgements. After extraction, values are joined
in from the slot table.

This buys three things:
  - the model cannot silently "correct" 4Oo/o to 40% and destroy provenance
  - a hallucinated slot id is a validation error, not a plausible wrong number
  - unconsumed slots are a coverage signal: a numeral nobody accounted for

Provenance is structural, not quoted. RESOLVED 2026-09-09, see CLAUDE.md: the
model emits no text at all, so there is no span to verify. It selects a
`citation` from the closed set of units in the pasal and a `numeral_slot` from
the table, and both are checkable against `src/structure.py` offsets. The
replacement check is stronger than the substring test it retires: a slot must
lie inside the unit its norm cites, which catches a bound filed under the wrong
ayat. Measured over the whole body corpus, 857 of 857 slots fall inside exactly
one addressable unit, none crossing a boundary, so the assertion is safe to
make hard.
"""

import re

from ocr_numerals import scan

SLOT_RE = re.compile(r"\[(N\d+)\]")


def slot_text(pasal_text):
    """Annotate a Pasal with numeral slot ids. Returns (annotated, slot_table).

    Offsets in the table are relative to `pasal_text`, which is
    `structure.py`'s `pasal["text"]`; add `pasal["start"]` to compare them
    against a unit's absolute `start`/`end`.
    """
    hits = scan(pasal_text)
    table, out, cursor = {}, [], 0
    for i, h in enumerate(hits, 1):
        sid = f"N{i}"
        table[sid] = {
            "value": h["value"],
            "status": h["status"],
            "source_numeral": h["source_numeral"],
            "source_words": h["source_words"],
            "ocr_recovered": h["ocr_recovered"],
            "needs_review": h["needs_review"],
            "unit": h["unit"],
            "start": h["start"],
            "end": h["end"],
        }
        out.append(pasal_text[cursor:h["end"]])
        out.append(f" [{sid}]")
        cursor = h["end"]
    out.append(pasal_text[cursor:])
    return "".join(out), table


# `pdftotext -layout` keeps the page's ragged indentation and line wraps, so a
# provision reads `sebesar 10% (sepuluh\n                   persen).` and a
# category label reads `perundang-\n     undangan`. Text lifted out of a unit
# for downstream use -- an ontology label, a review-queue excerpt -- has to
# have the layout collapsed first or the same phrase gets two different forms
# depending on where the line broke.
#
# Layout only, never content. Whitespace, a break inside a hyphenated compound
# and a soft hyphen carry no legal meaning, so removing them is lossless.
# Furniture stripping deliberately does NOT belong here: this function must
# leave `TarifPBJT` and `4Oo/o` exactly as the page had them, because a caller
# comparing two normalised strings needs the difference between them to be
# real. This is a normaliser, not a verifier -- it has no opinion about whether
# its input is genuine, and the span check that once used it is retired.
SOFT_HYPHEN = "­"
WRAPPED_HYPHEN = re.compile(r"-\s*\n\s*")
WHITESPACE = re.compile(r"\s+")


def canonical(text):
    """Collapse what the page layout inserted, and nothing else.

    The hyphen is kept when a line breaks inside a compound: all 314 such
    breaks in the corpus are real Indonesian compounds -- `perundang-undangan`,
    `semata-mata`, `PBB-P2` -- and none is a word the typesetter split, so
    joining without the hyphen would corrupt every one of them.
    """
    text = text.replace(SOFT_HYPHEN, "")
    text = WRAPPED_HYPHEN.sub("-", text)
    return WHITESPACE.sub(" ", text).strip()


def unit_index(pasal):
    """Every addressable unit in a pasal, as {citation: (start, end, level)}.

    This is the closed set a norm's `citation` is selected from, and the
    boundaries a slot is checked against. Every level is included, not just
    the leaves: a numeral often sits in an ayat's chapeau above a huruf list
    (128 slots resolve to a bare pasal and 379 to an ayat that has huruf
    children), and that chapeau is a real unit with a real citation.
    """
    index = {pasal["citation"]: (pasal["start"], pasal["end"], "pasal")}

    def add(unit, level):
        index[unit["citation"]] = (unit["start"], unit["end"], level)

    def add_angka(items):
        for g in items or []:
            add(g, "angka")

    def add_huruf(items):
        for h in items or []:
            add(h, "huruf")
            add_angka(h.get("angka"))

    for a in pasal.get("ayat") or []:
        add(a, "ayat")
        add_huruf(a.get("huruf"))
        add_angka(a.get("angka"))
    add_huruf(pasal.get("huruf"))
    add_angka(pasal.get("angka"))
    return index


def resolve(norms, table, pasal):
    """
    Join recovered values into the model's output and validate.

    The model supplies `citation`, `op` and `numeral_slot`. Everything numeric
    comes from the slot table and every offset from `pasal`; neither is ever
    read back from the model.

    `applies_to` is not checked here -- it needs the ontology, and that
    validation lives in the extraction runner.
    """
    errors, used = [], set()
    units = unit_index(pasal)
    base = pasal["start"]

    for n in norms:
        cite = n.get("citation")
        unit = units.get(cite)
        if unit is None:
            errors.append({"norm": n["id"], "error": "citation_not_in_pasal",
                           "citation": cite})

        for b in n.get("bounds", []):
            sid = b.get("numeral_slot")
            if sid not in table:
                errors.append({"norm": n["id"], "error": "unknown_slot", "slot": sid})
                continue
            if sid in used:
                errors.append({"norm": n["id"], "error": "slot_reused", "slot": sid})
            used.add(sid)
            slot = table[sid]

            # Structural provenance, replacing the retired span check. A model
            # that files Pasal 58 ayat (2)'s floor under ayat (1) fails here;
            # a substring test never could, since the text is a real substring
            # of the pasal either way.
            if unit is not None:
                if not (unit[0] <= base + slot["start"] and
                        base + slot["end"] <= unit[1]):
                    errors.append({"norm": n["id"], "error": "slot_outside_cited_unit",
                                   "slot": sid, "citation": cite})

            b.update({k: slot[k] for k in
                      ("value", "source_numeral", "source_words", "ocr_recovered",
                       "unit")})
            if slot["needs_review"]:
                errors.append({"norm": n["id"], "error": "slot_needs_review", "slot": sid})
            if "value" in b and b["value"] is None:
                errors.append({"norm": n["id"], "error": "slot_unresolved", "slot": sid})

        ops = [b.get("op") for b in n.get("bounds", [])]
        if ">=" in ops and "<=" in ops:
            floor = next(b for b in n["bounds"] if b["op"] == ">=")
            ceil = next(b for b in n["bounds"] if b["op"] == "<=")
            lo, hi = floor.get("value"), ceil.get("value")
            # Never compare across units. `hari kerja`, `hari kalender` and
            # bare `hari` are three different measures and the ratio between
            # them depends on a holiday calendar, so a norm whose floor and
            # ceiling disagree about the unit is reported, not converted.
            if floor.get("unit") != ceil.get("unit"):
                errors.append({"norm": n["id"], "error": "bounds_unit_mismatch",
                               "units": [floor.get("unit"), ceil.get("unit")]})
            elif lo is not None and hi is not None and lo > hi:
                errors.append({"norm": n["id"], "error": "floor_above_ceiling"})

    orphans = sorted(set(table) - used)
    return norms, errors, orphans


if __name__ == "__main__":
    import structure

    pasal_text = (
        "\n"
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
    # Segment it the way the pipeline does, so the demo exercises the real
    # closed citation set rather than a hand-written one.
    pasal = structure.segment("Pasal 58\n" + pasal_text)["pasal"][0]

    annotated, table = slot_text(pasal["text"])
    print("=== what the model is shown ===")
    print(annotated)
    print("=== closed citation set (the model selects from these) ===")
    for cite, (s, e, lvl) in unit_index(pasal).items():
        print(f"  {cite:<28} {lvl:<6} [{s}:{e}]")
    print("=== slot table (model never sees this) ===")
    for sid, s in table.items():
        v = f"{s['value']:.3%}" if s["value"] is not None else "REVIEW"
        flag = " ~recovered" if s["ocr_recovered"] else ""
        print(f"  {sid}: {v:>9}  {s['source_numeral']} ({s['source_words']}){flag}")

    # what a correct model response looks like: citations, operators and slots.
    # No numbers, no quoted text, nothing the model had to copy.
    llm_output = [
        {"id": "UU-58-1", "citation": "Pasal 58 ayat (1)", "is_residual": True,
         "norm_type": "rate_constraint", "applies_to": ["*"],
         "bounds": [{"op": "<=", "numeral_slot": "N1"}]},
        {"id": "UU-58-2", "citation": "Pasal 58 ayat (2)", "is_residual": False,
         "norm_type": "rate_constraint",
         "applies_to": ["diskotek", "karaoke", "kelab_malam", "bar", "mandi_uap_spa"],
         "bounds": [{"op": ">=", "numeral_slot": "N2"},
                    {"op": "<=", "numeral_slot": "N3"}]},
        {"id": "UU-58-3b", "citation": "Pasal 58 ayat (3) huruf b", "is_residual": False,
         "norm_type": "rate_constraint", "applies_to": ["listrik_dihasilkan_sendiri"],
         "bounds": [{"op": "<=", "numeral_slot": "N5"}]},
    ]

    resolved, errors, orphans = resolve(llm_output, table, pasal)
    print("\n=== after join ===")
    for n in resolved:
        bs = ", ".join(
            f"{b['op']} {b['value']:.1%}" if b.get("value") is not None
            else f"{b['op']} <unresolved>"
            for b in n["bounds"])
        print(f"  {n['id']:<10} {n['citation']:<28} {bs}")
    print(f"\nerrors: {errors or 'none'}")
    print(f"orphan slots: {orphans or 'none'}  "
          f"(Pasal 58 ayat (3) huruf a was not extracted, so its slot is unconsumed)")
