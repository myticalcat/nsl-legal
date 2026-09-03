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
"""

import re
from ocr_numerals import scan

SLOT_RE = re.compile(r"\[(N\d+)\]")


def slot_text(pasal_text):
    """Annotate a Pasal with numeral slot ids. Returns (annotated, slot_table)."""
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
        }
        out.append(pasal_text[cursor:h["end"]])
        out.append(f" [{sid}]")
        cursor = h["end"]
    out.append(pasal_text[cursor:])
    return "".join(out), table


def strip_slots(s):
    """Remove slot markers so a span can be checked against the original text."""
    return re.sub(r"\s*\[N\d+\]", "", s)


def resolve(norms, table, source_text):
    """
    Join recovered values into the model's output and validate.

    The model supplies `op` and `numeral_slot` per bound. Everything numeric
    comes from the slot table, never from the model.
    """
    errors, used = [], set()

    for n in norms:
        span = strip_slots(n.get("span", ""))
        if span and span not in source_text:
            errors.append({"norm": n["id"], "error": "span_not_verbatim"})

        for b in n.get("bounds", []):
            sid = b.get("numeral_slot")
            if sid not in table:
                errors.append({"norm": n["id"], "error": "unknown_slot", "slot": sid})
                continue
            if sid in used:
                errors.append({"norm": n["id"], "error": "slot_reused", "slot": sid})
            used.add(sid)
            slot = table[sid]
            b.update({k: slot[k] for k in
                      ("value", "source_numeral", "source_words", "ocr_recovered")})
            if slot["needs_review"]:
                errors.append({"norm": n["id"], "error": "slot_needs_review", "slot": sid})
            if "value" in b and b["value"] is None:
                errors.append({"norm": n["id"], "error": "slot_unresolved", "slot": sid})

        ops = [b.get("op") for b in n.get("bounds", [])]
        if ">=" in ops and "<=" in ops:
            lo = next(b["value"] for b in n["bounds"] if b["op"] == ">=")
            hi = next(b["value"] for b in n["bounds"] if b["op"] == "<=")
            if lo is not None and hi is not None and lo > hi:
                errors.append({"norm": n["id"], "error": "floor_above_ceiling"})

    orphans = sorted(set(table) - used)
    return norms, errors, orphans


if __name__ == "__main__":
    pasal = (
        "Pasal 58\n"
        "(1) TarifPBJT ditetapkan paling tinggi sebesar lOVo (sepuluh persen).\n"
        "(2) Khusus tarif PBJT atas jasa hiburan pada diskotek, karaoke, kelab\n"
        "    malam, bar, dan mandi uap/spa ditetapkan paling rendah 4Oo/o\n"
        "    (empat puluh persen) dan paling tinggi 75% (tujuh puluh lima persen).\n"
        "(3) Khusus tarif PBJT atas Tenaga Listrik untuk konsumsi Tenaga Listrik\n"
        "    yang dihasilkan sendiri, ditetapkan paling tinggi 1,5% (satu koma\n"
        "    limapersen).\n"
    )

    annotated, table = slot_text(pasal)
    print("=== what the model is shown ===")
    print(annotated)
    print("=== slot table (model never sees this) ===")
    for sid, s in table.items():
        v = f"{s['value']:.3%}" if s["value"] is not None else "REVIEW"
        flag = " ~recovered" if s["ocr_recovered"] else ""
        print(f"  {sid}: {v:>9}  {s['source_numeral']} ({s['source_words']}){flag}")

    # what a correct model response looks like: operators and slots, no numbers
    llm_output = [
        {"id": "UU-58-1", "citation": "Pasal 58 ayat (1)", "is_residual": True,
         "span": "TarifPBJT ditetapkan paling tinggi sebesar lOVo (sepuluh persen).",
         "applies_to": ["*"],
         "bounds": [{"op": "<=", "numeral_slot": "N1"}]},
        {"id": "UU-58-2", "citation": "Pasal 58 ayat (2)", "is_residual": False,
         "span": "ditetapkan paling rendah 4Oo/o",
         "applies_to": ["diskotek", "karaoke", "kelab_malam", "bar", "mandi_uap_spa"],
         "bounds": [{"op": ">=", "numeral_slot": "N2"},
                    {"op": "<=", "numeral_slot": "N3"}]},
        {"id": "UU-58-3b", "citation": "Pasal 58 ayat (3) huruf b", "is_residual": False,
         "span": "ditetapkan paling tinggi 1,5% (satu koma",
         "applies_to": ["listrik_dihasilkan_sendiri"],
         "bounds": [{"op": "<=", "numeral_slot": "N4"}]},
    ]

    resolved, errors, orphans = resolve(llm_output, table, pasal)
    print("\n=== after join ===")
    for n in resolved:
        bs = ", ".join(
            f"{b['op']} {b['value']:.1%}" if b.get("value") is not None
            else f"{b['op']} <unresolved>"
            for b in n["bounds"])
        print(f"  {n['id']:<10} {bs}")
    print(f"\nerrors: {errors or 'none'}")
    print(f"orphan slots: {orphans or 'none'}")
