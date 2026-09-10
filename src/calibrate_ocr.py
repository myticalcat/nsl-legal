#!/usr/bin/env python3
"""
Two-page OCR calibration.

Before swapping the OCR engine on the scanned documents, establish that a
candidate transcribes what is on the page rather than what ought to be there.
A model that quietly repairs damage is worse than tesseract, not better: the
whole two-channel numeral design exists to detect damage, and an engine that
removes it deletes findings instead of reporting them.

The two gate pages are chosen because they pull in opposite directions, so no
uniformly-aggressive or uniformly-conservative engine can pass both.

  UU 1/2022 p17     the rendered glyphs read `6% (enam persen)`; the PDF's own
                    text layer says `60%`. A faithful transcription of the
                    image RESOLVES a standing disagreement -- both channels
                    land on 0.06. Confirmed against the page image 2026-09-08.

  Perwal Jogja p89  the rendered glyphs read `67% (enam puluh persen)` on a
                    clean, digitally-signed page. The provision contradicts
                    itself, and five other instruments carrying the same
                    sentence say 60%. A faithful transcription PRESERVES the
                    disagreement. An engine that returns `60%` here has
                    harmonised the enacted text and destroyed the finding.

Scoring runs the project's own `ocr_numerals.scan` over the transcription, so
the test is exactly the reconciliation the pipeline will apply downstream.

A third page is reported but not gated. Fidelity is necessary and not
sufficient: tesseract is already faithful on these two and still loses whole
provisions to column mis-ordering, which is the reason to consider replacing it
at all.

  Lhokseumawe p20   the twelve-item Pasal 55 list. tesseract keeps the
                    characters but collapses the markers `b.` to `i.` into one
                    line of noise (`PR mo 0`) and drops huruf l entirely --
                    `diskotek`, `karaoke` and `kelab malam` occur zero times in
                    the whole document. This measures recovery, not fidelity.

Usage:
    python3 src/calibrate_ocr.py --render          # write page images
    python3 src/calibrate_ocr.py --engine tesseract
    python3 src/calibrate_ocr.py --score out/calibration/candidate
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from ocr_numerals import scan

RAW = Path("data/raw")
OUT = Path("out/calibration")
DPI = 300
LANGS = "ind+eng"

GATE = [
    {
        "id": "uu_p17_text_layer_artifact",
        "pdf": RAW / "batch-a" / "UU Nomor 1 Tahun 2022.pdf",
        "page": 17,
        "match_words": "enam persen",
        "expect_value": 0.06,
        "expect_status": "agree",
        "wrong_value": 0.60,
        "why": "render says 6%; the text layer inserted a zero. A faithful "
               "transcription resolves the disagreement.",
    },
    {
        "id": "jogja_p89_enacted_defect",
        "pdf": RAW / "batch-a" / "Perwal Kota Jogja Nomor 51 Tahun 2024.pdf",
        "page": 89,
        "match_words": "enam puluh persen",
        "expect_value": None,
        "expect_status": "disagree",
        "wrong_value": 0.60,
        "why": "render says 67% against words saying enam puluh. The provision "
               "contradicts itself and the disagreement must survive.",
    },
]

PROBE = {
    "id": "lhokseumawe_p20_column_order",
    "pdf": RAW / "batch-c" / "Peraturan Daerah (PERDA) Kota Lhokseumawe Nomor 1 Tahun 2024.pdf",
    "page": 20,
    "want_markers": list("bcdefghi"),
    "want_terms": ["diskotek", "karaoke", "kelab malam", "bar", "mandi uap"],
    "why": "tesseract keeps the characters and loses the structure.",
}


def render(case):
    """One page to PNG, at the DPI the pipeline already uses."""
    OUT.mkdir(parents=True, exist_ok=True)
    prefix = OUT / case["id"]
    if not case["pdf"].exists():
        return None
    r = subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-gray", "-png",
         "-f", str(case["page"]), "-l", str(case["page"]),
         str(case["pdf"]), str(prefix)],
        capture_output=True)
    if r.returncode != 0:
        return None
    hits = sorted(OUT.glob(f"{case['id']}*.png"))
    return hits[0] if hits else None


def tesseract(image):
    r = subprocess.run(["tesseract", str(image), "stdout", "-l", LANGS],
                       capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def score_gate(case, text):
    """Judge a transcription with the pipeline's own reconciliation."""
    pairs = [h for h in scan(text)
             if case["match_words"] in " ".join(h["source_words"].split()).lower()]
    if not pairs:
        return False, "numeral pair not found in the transcription", None
    h = pairs[0]
    got = h["value"]
    detail = (f"{h['source_numeral']!r} / "
              f"{' '.join(h['source_words'].split())!r} "
              f"-> value={got} status={h['status']}")

    if h["status"] != case["expect_status"]:
        if case["wrong_value"] is not None and got == case["wrong_value"]:
            return False, f"SMOOTHED to {case['wrong_value']}: {detail}", h
        return False, f"expected status {case['expect_status']}: {detail}", h
    if case["expect_value"] is not None and got != case["expect_value"]:
        return False, f"expected value {case['expect_value']}: {detail}", h
    return True, detail, h


def score_probe(text):
    """Whole-word matching only.

    `bar` as a bare substring hits `barang`, `gambar` and `sebar`, which
    reported the huruf-l bracket as partly recovered when none of it was there.
    """
    # Scope to the list under test. The page carries other huruf lists -- a
    # `jasa tempat parkir` run above it and the Pasal 55(2) exclusions below --
    # and counting their markers reported b. and c. as recovered when the list
    # in question had lost every marker from b to i.
    low = text.lower()
    start = low.find("jasa kesenian dan hiburan")
    end = low.find("dikecualikan", start + 1) if start >= 0 else -1
    region = text[start:end if end > start else len(text)] if start >= 0 else ""
    markers = [m for m in PROBE["want_markers"]
               if re.search(rf"(?m)^\s*{m}[.)]\s", region)]
    terms = [t for t in PROBE["want_terms"]
             if re.search(rf"\b{re.escape(t)}\b", region.lower())]
    return markers, terms


def load(directory, case_id):
    for ext in (".txt", ".md", ".json"):
        p = Path(directory) / f"{case_id}{ext}"
        if p.exists():
            raw = p.read_text()
            if ext == ".json":
                return json.loads(raw).get("text", "")
            return raw
    return None


def report(transcriptions, label):
    print(f"\n=== OCR calibration: {label} ===\n")
    passed = 0
    for case in GATE:
        text = transcriptions.get(case["id"])
        if text is None:
            print(f"  SKIP  {case['id']}  (no transcription)")
            continue
        ok, detail, _ = score_gate(case, text)
        print(f"  {'PASS' if ok else 'FAIL'}  {case['id']}")
        print(f"        {detail}")
        print(f"        expected: {case['why']}")
        passed += ok

    text = transcriptions.get(PROBE["id"])
    if text is not None:
        markers, terms = score_probe(text)
        print(f"\n  PROBE {PROBE['id']}  (reported, not gated)")
        print(f"        huruf markers b-i recovered : {len(markers)}/8  {markers}")
        print(f"        huruf l terms recovered     : {len(terms)}/5  {terms}")

    print(f"\n  gate: {passed}/{len(GATE)} passed")
    if passed < len(GATE):
        print("  -> do not run this engine over the corpus.")
    return passed == len(GATE)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render", action="store_true",
                    help="write the page images for an external engine")
    ap.add_argument("--engine", choices=["tesseract"],
                    help="run a local engine and score it")
    ap.add_argument("--score", metavar="DIR",
                    help="score transcriptions in DIR, named <case_id>.txt")
    args = ap.parse_args()

    cases = GATE + [PROBE]

    if args.render or args.engine:
        images = {}
        for c in cases:
            img = render(c)
            if img is None:
                print(f"  could not render {c['id']} "
                      f"({'missing PDF' if not c['pdf'].exists() else 'pdftoppm failed'})")
                continue
            images[c["id"]] = img
            print(f"  rendered {c['id']:<34} -> {img}")
        if args.render:
            print(f"\nTranscribe each image and save as {OUT}/<engine>/<case_id>.txt,")
            print(f"then: python3 src/calibrate_ocr.py --score {OUT}/<engine>")
            print("\nAsk for a verbatim transcription, errors included. An engine "
                  "told to\n'clean up' the text will fail the gate by design.")
            return
        texts = {cid: tesseract(img) for cid, img in images.items()}
        texts = {k: v for k, v in texts.items() if v}
        (OUT / "tesseract").mkdir(parents=True, exist_ok=True)
        for cid, t in texts.items():
            (OUT / "tesseract" / f"{cid}.txt").write_text(t)
        sys.exit(0 if report(texts, "tesseract (baseline)") else 1)

    if args.score:
        texts = {c["id"]: load(args.score, c["id"]) for c in cases}
        texts = {k: v for k, v in texts.items() if v}
        if not texts:
            print(f"no transcriptions found in {args.score}")
            sys.exit(2)
        sys.exit(0 if report(texts, args.score) else 1)

    ap.print_help()


if __name__ == "__main__":
    main()
