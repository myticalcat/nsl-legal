#!/usr/bin/env python3
"""
Neurosymbolic legal conflict detection - symbolic layer prototype.

Reads hand-written gold IR (norms.json) + a subsumption taxonomy (ontology.json),
compiles applicable norms into Z3 constraints per taxable category, and reports
one of three verdicts:

    CONFLICT   - no rate satisfies both instruments (UNSAT); unsat core cites the pasal
    COMPLIANT  - a satisfying rate exists (SAT); the model is the witness
    ABSTAIN    - an open-textured term makes the applicability question undecidable

The neural layer's only job is producing norms.json from raw text. Everything
below is deterministic, so extraction accuracy and reasoning accuracy can be
measured separately.
"""

import json
import os
from z3 import Real, Solver, Bool, sat, unsat

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "..", "data", "gold", "ontology.json")) as f:
    ONTO = json.load(f)
with open(os.path.join(HERE, "..", "data", "gold", "norms.json")) as f:
    IR = json.load(f)

CATS = ONTO["categories"]
OPEN_TEXTURED = ONTO["open_textured"]
INSTRUMENTS = IR["instruments"]
NORMS = IR["norms"]


# ---------------------------------------------------------------- subsumption

def ancestors(cat):
    """cat and all its transitive parents. karaoke_keluarga -> {karaoke_keluarga, karaoke, jasa_hiburan}"""
    chain, cur = [], cat
    while cur is not None and cur in CATS:
        chain.append(cur)
        cur = CATS[cur]["parent"]
    return chain


def norm_applies(norm, cat):
    """A norm applies to cat if it names cat or any of cat's ancestors. '*' = residual, handled separately."""
    if norm.get("applies_to") == ["*"]:
        return False  # residual; only used as fallback
    return any(a in norm["applies_to"] for a in ancestors(cat))


def applicable(cat, instrument):
    """
    Norms from `instrument` governing `cat`, after lex specialis.
    A residual norm (Pasal 58(1): the general cap) is displaced whenever a
    specific norm reaches the category. This is the step that makes the
    panti pijat case work: no specific national norm reaches it, so the
    residual 10% cap springs back.
    """
    pool = [n for n in NORMS
            if n["instrument"] == instrument and n["norm_type"] == "rate_constraint"]
    specific = [n for n in pool if norm_applies(n, cat)]
    if specific:
        return specific, False
    residual = [n for n in pool if n.get("is_residual")]
    return residual, True


def delegation_covers(cat, norm_ids):
    """Is divergence from the statutory figure authorised by an express delegation?"""
    for n in NORMS:
        if n["norm_type"] != "delegation":
            continue
        if any(nid in n.get("delegated_scope", []) for nid in norm_ids):
            return n
    return None


# ------------------------------------------------------------------ compiler

OPS = {
    "<=": lambda v, k: v <= k,
    ">=": lambda v, k: v >= k,
    "==": lambda v, k: v == k,
    "<":  lambda v, k: v < k,
    ">":  lambda v, k: v > k,
}


def check(cat):
    """Compile the applicable norms for one category and ask Z3 for a witness."""
    nat, nat_residual = applicable(cat, "UU_1_2022")
    loc, _ = applicable(cat, "PERDA_SBY_7_2023")

    if not nat or not loc:
        return {"category": cat, "verdict": "NO_PAIR"}

    # An open-textured tail ("dan sejenisnya") does NOT undermine the verdict for a
    # category the drafter enumerated by name. It only leaves the norm's outer
    # boundary undetermined. So we record it as a coverage caveat here and raise a
    # separate ABSTAIN for the unenumerated extension itself (see main()).
    tail_terms = sorted({t for n in loc
                         for t in n.get("open_textured_terms", [])
                         if cat not in n["applies_to"]})
    caveat_terms = sorted({t for n in loc for t in n.get("open_textured_terms", [])})

    rate = Real(f"tarif_{cat}")
    s = Solver()
    s.set(unsat_core=True)
    labels = {}

    for n in nat + loc:
        for i, b in enumerate(n["bounds"]):
            tag = f"{n['id']}#{i}"
            p = Bool(tag)
            labels[tag] = (n, b)
            s.assert_and_track(OPS[b["op"]](rate, b["value"]), p)

    # a tax rate is a real proportion
    s.add(rate >= 0, rate <= 1)

    result = s.check()
    out = {
        "category": cat,
        "label": CATS[cat]["label"],
        "national": [n["id"] for n in nat],
        "national_via_residual": nat_residual,
        "local": [n["id"] for n in loc],
        "tail_terms": tail_terms,
        "caveat_terms": caveat_terms,
    }

    if result == unsat:
        core = [str(c) for c in s.unsat_core()]
        out["verdict"] = "CONFLICT"
        out["core"] = [
            {
                "norm": labels[t][0]["id"],
                "instrument": INSTRUMENTS[labels[t][0]["instrument"]]["title"].split(" tentang")[0],
                "citation": labels[t][0]["citation"],
                "constraint": f"tarif {labels[t][1]['op']} {labels[t][1]['value']:.0%}",
                "rank": INSTRUMENTS[labels[t][0]["instrument"]]["rank"],
            }
            for t in core
        ]
        ranks = {c["rank"] for c in out["core"]}
        if len(ranks) > 1:
            out["resolution"] = "lex superior: the lower-ranked instrument yields"
    elif result == sat:
        m = s.model()
        out["verdict"] = "COMPLIANT"
        out["witness_rate"] = float(m[rate].as_fraction())
        deleg = delegation_covers(cat, out["national"])
        if deleg:
            out["authorised_by"] = f"{deleg['citation']} ({deleg['id']})"

    if tail_terms:
        # reached only through an open-textured extension -> we cannot decide applicability
        out["verdict"] = "ABSTAIN"
        out["abstain_note"] = (
            "category reached only via "
            + ", ".join(OPEN_TEXTURED[t]["label"] for t in tail_terms)
        )
    elif caveat_terms:
        out["caveat"] = (
            "norm also extends via "
            + ", ".join(OPEN_TEXTURED[t]["label"] for t in caveat_terms)
            + "; this verdict covers the enumerated category only"
        )
    return out


# -------------------------------------------------------------------- report

def main():
    local_cats = sorted({c
                         for n in NORMS
                         if n["instrument"] == "PERDA_SBY_7_2023"
                         for c in n["applies_to"] if c != "*"})

    print("=" * 78)
    print("PBJT rate conflict check - UU 1/2022 Pasal 58  vs  Perda Surabaya 7/2023 Pasal 27")
    print("=" * 78)

    tally = {}
    for cat in local_cats:
        r = check(cat)
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
        icon = {"CONFLICT": "[X]", "COMPLIANT": "[ok]", "ABSTAIN": "[?]"}.get(r["verdict"], "[-]")
        print(f"\n{icon} {r['label']}  ->  {r['verdict']}")
        via = "  (via residual/general cap)" if r.get("national_via_residual") else ""
        print(f"    national: {', '.join(r['national'])}{via}")
        print(f"    local:    {', '.join(r['local'])}")

        if r["verdict"] == "CONFLICT":
            print("    unsat core:")
            for c in r["core"]:
                print(f"      - {c['citation']:<22} {c['constraint']:<16} [rank {c['rank']}]")
            print(f"    -> {r.get('resolution', '')}")
        elif "witness_rate" in r:
            print(f"    witness: a rate of {r['witness_rate']:.1%} satisfies both")
            if "authorised_by" in r:
                print(f"    divergence authorised by {r['authorised_by']}")
        if "abstain_note" in r:
            print(f"    note: {r['abstain_note']}")
        if "caveat" in r:
            print(f"    caveat: {r['caveat']}")

    # unresolved open-textured extensions, reported once, not per category
    gaps = {t: n for n in NORMS for t in n.get("open_textured_terms", [])}
    if gaps:
        print("\n[?] COVERAGE GAPS (referred for human review)")
        for t, n in gaps.items():
            print(f"    {n['citation']}: '{OPEN_TEXTURED[t]['label']}' - {OPEN_TEXTURED[t]['reason']}")
            tally["ABSTAIN"] = tally.get("ABSTAIN", 0) + 1

    print("\n" + "-" * 78)
    print("  ".join(f"{k}: {v}" for k, v in sorted(tally.items())))


if __name__ == "__main__":
    main()
