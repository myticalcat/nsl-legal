#!/usr/bin/env python3
"""
Prefilter: decide which body pasal are worth an API call.

Only about a quarter of body pasal carry anything a norm extractor can use.
The rest are procedure, definitions, institutional plumbing and closing
formulae. Across 6,411 pasal that difference is the whole feasibility of a
run, so the filter runs before the model, never after.

Two buckets, and the skip bucket is the point. A pasal is never silently
dropped: every skip carries a reason code, and the reason codes are a recall
check rather than bookkeeping. In particular a skipped pasal that still
contains an unexplained numeral is a bug -- either the numeral recogniser
missed a pair or the segmentation put it somewhere strange -- and it is
reported as `unexplained_numeral` rather than being quietly filed under "no
marker".

Selection is deliberately generous. A false positive costs one API call; a
false negative loses a provision permanently and invisibly.
"""

import argparse
import collections
import json
import re
from pathlib import Path

from ocr_numerals import scan
from slotting import canonical

# ------------------------------------------------------------ bound markers

# The seven forms that introduce a numeric bound in this drafting tradition.
# Measured across the corpus: 979 of 3,614 body pasal carry at least one.
#
# These are matched strictly, with only whitespace flexibility. Fuzzy matching
# was measured and rejected: at edit distance 1, `lama` collides with `lima`,
# `sama` and `nama` for 1,038 false hits, and `ditetapkan` collides with
# `diterapkan`, a real word that occurs 22 times. The genuine damage is about
# ten occurrences corpus-wide (`ditctapkan`, `dcngan`, `rcndah`, `tinngi`), and
# every one of them sits in a pasal that the numeral channel selects anyway --
# a provision stating a rate states the figure twice, and the words survive.
# So tolerance here would buy nothing and cost a thousand false positives.
BOUND_MARKERS = {
    "paling_tinggi": r"paling\s+tinggi",
    "paling_rendah": r"paling\s+rendah",
    "paling_lama": r"paling\s+lama",
    "paling_sedikit": r"paling\s+sedikit",
    "paling_banyak": r"paling\s+banyak",
    "ditetapkan_sebesar": r"ditetapkan\s+sebesar",
    "ditetapkan_dengan": r"ditetapkan\s+dengan",
}
BOUND_RE = {k: re.compile(v, re.I) for k, v in BOUND_MARKERS.items()}

# ------------------------------------------------------------------- modals

WAJIB = re.compile(r"\bwajib\b", re.I)
DILARANG = re.compile(r"\bdilarang\b", re.I)

# `Wajib Pajak` and `Wajib Retribusi` are defined nouns meaning "taxpayer",
# not the modal "must". Measured on the word `wajib` (not the substring, which
# also catches `kewajiban` and `diwajibkan`): 225 of 289 occurrences in Perda
# Surabaya and 50 of 80 in UU 1/2022 are the noun. Over body pasal across the
# whole corpus it is 3,512 of 3,796. A lexicon matching bare `wajib` invents
# obligations by the hundred.
#
# The head is a closed list because the tax types are: HKPD enumerates them.
# Matching on capitalisation instead was measured and is worse -- 194 of the
# noun occurrences are lowercase in the source, because drafters and OCR both
# fail to capitalise a defined term consistently, while only 7 capitalised
# occurrences have a head outside this list.
# The head tail is left loose (`paj\w*`, `re\w*busi`) because the scans damage
# it: `Wajib Pajck`, `wajib rertibusi`. That is safe in a way general fuzzy
# matching is not, because a genuine modal is followed by a verb, and
# Indonesian verbs in this position carry a me-/di-/ber-/ter- prefix that
# neither pattern can reach.
NOUN_HEAD = re.compile(
    r"\s+(?:paj\w*|re\w*busi\w*|pungut\w*|"
    r"pbb-?p2|pbb|pab|pat|pkb|pbjt|bbnkb|pbbkb|mblb|bphtb|pap|opsen)\b", re.I)

# `wajib` is also an adjective, and two boilerplate phrases carry it. `Pajak
# adalah kontribusi wajib kepada Daerah` -- a *compulsory contribution* -- is
# the statutory definition of a tax and opens Pasal 1 of almost every
# instrument in the corpus (26 occurrences). `Urusan Pemerintahan wajib` is a
# defined term from UU 23/2014, mandatory governmental affairs (5). Neither
# imposes a duty on anyone.
ADJECTIVE_CONTEXT = re.compile(r"\b(?:kontribusi|pemerintahan)\s+$", re.I)

# A modal needs a verb after it, so `wajib` followed immediately by a comma is
# not one. All 12 occurrences are the heading `Subjek, Wajib, dan Objek Pajak`,
# where the defined term `Wajib Pajak` has been split across the phrase. A
# colon is the opposite case and stays: `sesuai kewenangannya wajib: a. meminta
# ...` introduces a list of duties, and there are 27 of those.
TRUNCATED_TERM = re.compile(r",")


def modal_wajib(text):
    """Occurrences of `wajib` used as a modal.

    Excludes the defined noun (`Wajib Pajak`), the adjective (`kontribusi
    wajib`), and the term truncated by a heading. Measured over body pasal:
    3,796 occurrences of the word, of which 3,514 are the noun and 231 survive
    as modals.
    """
    out = []
    for m in WAJIB.finditer(text):
        if NOUN_HEAD.match(text, m.end()):
            continue
        if ADJECTIVE_CONTEXT.search(text[max(0, m.start() - 24):m.start()]):
            continue
        if TRUNCATED_TERM.match(text, m.end()):
            continue
        out.append(m)
    return out


# ------------------------------------------------------- unexplained numeral

# A percentage the pair recogniser did not claim. `scan()` needs digits *and*
# a spelled-out parenthetical; a bare `10%` with no words, or words whose
# parenthesis did not survive the scan, produces no slot. In a pasal that is
# being skipped that is a recall failure worth seeing, so it gets its own
# reason code instead of being filed under "nothing here".
PERCENT_ISH = re.compile(r"\d\s*(?:%|[VY]o|o/o|7o|o%|%o|Zo)|\bpersen\b", re.I)

# The double-numeral convention is not exclusive to percentages: `12 (dua
# belas) bulan` writes the figure twice the same way `10% (sepuluh persen)`
# does. `ocr_numerals.PAIR` does not see these -- it requires a percent tail --
# so a deadline produces no slot and reaches the extract bucket only when it
# also carries `paling lama`. Measured over body pasal: 1,102 such
# constructions (560 bulan, 327 tahun, 157 hari kerja, 58 hari) in 628 pasal,
# of which 426 are selected by some other channel and 202 would be skipped
# silently.
#
# They are still skipped, because `deadline_constraint` is not implemented and
# extracting norms nothing consumes is 202 wasted calls. But they get their own
# reason code so the bucket is already costed when that work starts, and so
# this does not have to be surveyed twice.
DEADLINE_NUMERAL = re.compile(
    r"\b\d+\s*\(\s*[a-zA-Z][a-zA-Z ]{2,30}?\)\s*(?:hari kerja|hari|bulan|tahun)\b", re.I)


def classify(pasal):
    """Bucket one pasal. Returns a record; `bucket` is 'extract' or 'skip'."""
    text = canonical(pasal["text"])
    slots = scan(pasal["text"])
    markers = sorted(k for k, rx in BOUND_RE.items() if rx.search(text))
    modals = [m.group(0) for m in modal_wajib(text)]
    forbids = DILARANG.findall(text)

    record = {
        "doc_id": pasal.get("doc_id"),
        "citation": pasal["citation"],
        "pasal": pasal["pasal"],
        "occurrence": pasal["occurrence"],
        "bound_markers": markers,
        "n_slots": len(slots),
        "n_modal_wajib": len(modals),
        "n_dilarang": len(forbids),
        "extraction_methods": pasal.get("extraction_methods", []),
    }

    reasons = []
    if markers:
        reasons.append("bound_marker")
    if slots:
        reasons.append("numeral_pair")
    if modals:
        reasons.append("modal_wajib")
    if forbids:
        reasons.append("modal_dilarang")

    if reasons:
        record["bucket"] = "extract"
        record["selected_by"] = reasons
    else:
        record["bucket"] = "skip"
        if PERCENT_ISH.search(text):
            # A rate the pair recogniser did not claim. Should never happen --
            # measured at 0 across the corpus -- and if it does, it is a recall
            # bug in `scan` or in the segmentation, not a quiet skip.
            record["skip_reason"] = "unexplained_numeral"
        elif DEADLINE_NUMERAL.search(text):
            record["skip_reason"] = "deadline_numeral_no_marker"
        else:
            record["skip_reason"] = "no_normative_marker"
    return record


def prefilter_document(doc):
    """Classify every body pasal in one `src/structure.py` document."""
    out = []
    for p in doc["pasal"]:
        if p["section"] != "body":
            continue
        rec = classify(p)
        rec["doc_id"] = doc["doc_id"]
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--structured", type=Path, default=Path("data/structured"))
    ap.add_argument("--out", type=Path, default=Path("out/prefilter.json"))
    ap.add_argument("--verbose", action="store_true",
                    help="list every unexplained_numeral skip")
    args = ap.parse_args()

    records, per_doc = [], []
    for path in sorted(args.structured.glob("*.json")):
        if path.name == "manifest.json":
            continue
        doc = json.loads(path.read_text())
        recs = prefilter_document(doc)
        records.extend(recs)
        n_ex = sum(1 for r in recs if r["bucket"] == "extract")
        per_doc.append({
            "doc_id": doc["doc_id"], "body_pasal": len(recs), "extract": n_ex,
            "skip": len(recs) - n_ex,
            "skip_reasons": dict(collections.Counter(
                r["skip_reason"] for r in recs if r["bucket"] == "skip")),
            "selected_by": dict(collections.Counter(
                k for r in recs if r["bucket"] == "extract" for k in r["selected_by"])),
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"per_document": per_doc, "pasal": records}, indent=1, ensure_ascii=False))

    print(f"{'document':<52} {'body':>5} {'extr':>5} {'skip':>5}   share")
    for d in per_doc:
        share = d["extract"] / d["body_pasal"] if d["body_pasal"] else 0
        print(f"{d['doc_id'][:52]:<52} {d['body_pasal']:>5} {d['extract']:>5} "
              f"{d['skip']:>5}   {share:>5.0%}")

    body = sum(d["body_pasal"] for d in per_doc)
    extract = sum(d["extract"] for d in per_doc)
    print(f"\n{'TOTAL':<52} {body:>5} {extract:>5} {body - extract:>5}   "
          f"{extract / body:>5.0%}")

    print("\nselected by (a pasal may be selected by more than one):")
    for k, c in collections.Counter(
            k for r in records if r["bucket"] == "extract"
            for k in r["selected_by"]).most_common():
        print(f"  {c:>5}  {k}")
    print("\nsole reason for selection:")
    for k, c in collections.Counter(
            r["selected_by"][0] for r in records
            if r["bucket"] == "extract" and len(r["selected_by"]) == 1).most_common():
        print(f"  {c:>5}  {k}")
    print("\nskip reasons:")
    for k, c in collections.Counter(
            r["skip_reason"] for r in records if r["bucket"] == "skip").most_common():
        print(f"  {c:>5}  {k}")

    if args.verbose:
        print("\nunexplained numerals in skipped pasal:")
        for r in records:
            if r.get("skip_reason") == "unexplained_numeral":
                print(f"  [{r['doc_id'][:38]}] {r['citation']}")

    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
