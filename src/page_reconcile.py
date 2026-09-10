#!/usr/bin/env python3
"""
Page-level reconciliation: the embedded text layer against a fresh re-OCR.

`ocr_numerals` reconciles two channels *within* one reading of the page --
digits against spelled-out words. This does the same thing one level up, across
two independent *readings* of the same page, because measurement showed neither
is reliable alone and they fail on disjoint figures:

    embedded text layer   corrupts whole-number percentages by glyph
                          confusion -- `40%` as `4Oo/o`, `10%` as `lOVo`
    tesseract re-OCR      reads those cleanly, and corrupts the percent sign
                          after a decimal comma -- `0,5%` as `0,54`,
                          `73,8%` as `73,84`

So neither replaces the other. Run both, align the pairs, and apply the rule
`recover` already uses: prefer the reading that needed no repair. Where both are
clean and they still disagree, that is a genuine `sources_disagree` and a human
reads the page -- the same terminal verdict the digits/words check produces, for
the same reason.

Only pages whose current reading yields a repaired or disputed pair are worth a
second opinion: 189 of 5,332 across the corpus. And only `text_layer` pages
give an *independent* second reading -- on a page already extracted by OCR both
readings are tesseract, so agreement proves nothing about the source.
"""

import argparse
import collections
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from ocr_numerals import scan

EXTRACTED = Path("data/extracted")
RAW = Path("data/raw")
DPI = 300
LANGS = "ind+eng"

# Intra-reading trust, worst first. A reading whose two channels agreed without
# repair outranks one that needed it, which is the same precedence `recover`
# applies between the digit and word channels.
TRUST = {"disagree": 0, "unparsed": 0, "single_channel": 1, "recovered": 2, "agree": 3}


def reocr_page(pdf, pageno, workdir):
    """Render one page and OCR it, at the DPI the pipeline already uses."""
    prefix = Path(workdir) / f"p{pageno}"
    r = subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-gray", "-png",
         "-f", str(pageno), "-l", str(pageno), str(pdf), str(prefix)],
        capture_output=True)
    if r.returncode != 0:
        return None
    imgs = sorted(Path(workdir).glob(f"p{pageno}*.png"))
    if not imgs:
        return None
    out = subprocess.run(["tesseract", str(imgs[0]), "stdout", "-l", LANGS],
                         capture_output=True)
    for i in imgs:
        i.unlink(missing_ok=True)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def pair_key(h):
    """What identifies the same figure across two readings of a page.

    The spelled-out words, not the digits: words are the error-detecting
    channel and survive both failure modes. They survive them *through repair*
    too -- the text layer's `dta persen` snaps to `dua` and keys against the
    re-OCR's clean `dua persen`, which is why three pairs that looked lost in
    the first comparison were the same provisions read correctly.
    """
    v = h["word_value"] if h["word_value"] is not None else h["digit_value"]
    return (h["unit"], v)


def align(a, b):
    """Match pairs between two readings. Returns (matched, a_only, b_only).

    Alignment is by key and then by order of occurrence, so a page stating 10%
    three times matches first-to-first. Both readings are of the same page, so
    the sequence is the same wherever both saw the figure.
    """
    bucket = collections.defaultdict(list)
    for h in b:
        bucket[pair_key(h)].append(h)
    matched, a_only = [], []
    for h in a:
        q = bucket.get(pair_key(h))
        if q:
            matched.append((h, q.pop(0)))
        else:
            a_only.append(h)
    b_only = [h for q in bucket.values() for h in q]
    return matched, a_only, b_only


def reconcile_pairs(layer, reocr):
    """Combine two readings of one page into per-figure records."""
    matched, layer_only, reocr_only = align(layer, reocr)
    out = []

    for a, b in matched:
        ta, tb = TRUST[a["status"]], TRUST[b["status"]]
        if a["value"] is not None and b["value"] is not None and a["value"] == b["value"]:
            status = "sources_agree" if a["status"] == b["status"] == "agree" \
                else "sources_agree_after_repair"
            chosen, value = ("text_layer" if ta >= tb else "reocr"), a["value"]
        elif ta > tb:
            status, chosen, value = "reocr_yields", "text_layer", a["value"]
        elif tb > ta:
            status, chosen, value = "text_layer_yields", "reocr", b["value"]
        else:
            status, chosen, value = "sources_disagree", None, None
        out.append({
            "status": status, "value": value, "chosen": chosen,
            "unit": a["unit"],
            "text_layer": {"numeral": a["source_numeral"], "words": a["source_words"],
                           "value": a["value"], "status": a["status"]},
            "reocr": {"numeral": b["source_numeral"], "words": b["source_words"],
                      "value": b["value"], "status": b["status"]},
        })

    for h, src in [(h, "text_layer") for h in layer_only] + \
                  [(h, "reocr") for h in reocr_only]:
        out.append({
            "status": "single_source", "value": h["value"], "chosen": src,
            "unit": h["unit"],
            src: {"numeral": h["source_numeral"], "words": h["source_words"],
                  "value": h["value"], "status": h["status"]},
        })
    return out


def candidate_pages(doc):
    """Pages worth a second reading: the current one already needed repair.

    Restricted to `text_layer` pages. On a page the pipeline already OCRed, a
    re-OCR is the same engine on the same image, so agreement is a determinism
    check and not evidence about the source.
    """
    out = []
    for pg in doc["pages"]:
        if pg["method"] != "text_layer":
            continue
        if any(h["ocr_recovered"] or h["needs_review"] for h in scan(pg["text"])):
            out.append(pg)
    return out


def reconcile_document(doc, limit=None):
    pdf = Path(doc["source_pdf"])
    if not pdf.exists():
        return None
    pages = candidate_pages(doc)
    if limit:
        pages = pages[:limit]
    results = []
    with tempfile.TemporaryDirectory() as work:
        for pg in pages:
            text = reocr_page(pdf, pg["page"], work)
            if text is None:
                continue
            results.append({
                "doc_id": doc["doc_id"], "page": pg["page"],
                "pairs": reconcile_pairs(scan(pg["text"]), scan(text)),
            })
    return results


def summarise(records):
    tally = collections.Counter()
    for r in records:
        for p in r["pairs"]:
            tally[p["status"]] += 1
    return tally


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", help="doc_id substring; default is every document")
    ap.add_argument("--limit", type=int, help="max pages per document")
    ap.add_argument("--out", type=Path, default=Path("out/page_reconcile.json"))
    ap.add_argument("--show", action="store_true", help="list every disputed figure")
    args = ap.parse_args()

    paths = sorted(p for p in EXTRACTED.glob("*.json") if p.name != "manifest.json")
    records = []
    for path in paths:
        doc = json.loads(path.read_text())
        if args.doc and args.doc.lower() not in doc["doc_id"].lower():
            continue
        n = len(candidate_pages(doc))
        if not n:
            continue
        print(f"  {doc['doc_id'][:46]:<46} {n:>3} candidate pages", flush=True)
        got = reconcile_document(doc, args.limit)
        if got:
            records.extend(got)

    tally = summarise(records)
    total = sum(tally.values())
    print(f"\n{'-'*64}\n{len(records)} pages reconciled, {total} figures\n")
    for k, v in tally.most_common():
        print(f"  {v:>5}  {k}")

    repaired = tally["sources_agree"] + tally["reocr_yields"] + tally["text_layer_yields"]
    print(f"\n  a second reading settled {repaired} figures that one reading "
          f"could not confirm alone")
    print(f"  {tally['sources_disagree']} remain genuinely disputed")

    if args.show:
        print("\ndisputed and single-source figures:")
        for r in records:
            for p in r["pairs"]:
                if p["status"] in ("sources_disagree", "single_source"):
                    tl = p.get("text_layer", {})
                    ro = p.get("reocr", {})
                    print(f"  {r['doc_id'][:30]:<30} p{r['page']:<4} {p['status']:<18} "
                          f"layer={tl.get('numeral','-')!r:<12} "
                          f"reocr={ro.get('numeral','-')!r:<12} -> {p['value']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"summary": dict(tally), "pages": records}, indent=1, ensure_ascii=False))
    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
