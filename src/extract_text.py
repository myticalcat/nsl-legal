#!/usr/bin/env python3
"""
Page-level text extraction for the raw PDF corpus.

Two failure modes make a plain `pdftotext` pass insufficient. A page may carry
no text layer at all (a scan), or it may carry one that is confidently wrong --
a broken font/CMap remaps Latin glyphs into CJK and halfwidth ranges, so
`PAJAK DAERAH` extracts as `恥じAK DAERAH` while the page renders perfectly.
Both are recovered by rendering the page and running OCR over the image.

Corruption is detected by character-script anomaly, never by dictionary
hit-rate. Lampiran tariff tables and pages of `Cukup jelas.` boilerplate are
prose-free but entirely correct, and a stopword-frequency test rejects ~1,200
such pages against ~100 genuinely broken ones.

Every page records how its text was obtained, because an OCR'd page and a
text-layer page do not warrant equal trust downstream. Where OCR replaced a
corrupted text layer, the discarded text is kept: this pipeline does not
silently drop provenance.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/extracted")

OCR_LANGS = "ind+eng"
OCR_DPI = 300

# Below this many characters a page holds no recoverable text.
EMPTY_CHAR_THRESHOLD = 30
# Above this share of out-of-script characters the text layer is not Indonesian.
GARBAGE_RATIO_THRESHOLD = 0.02


def slugify(stem):
    """Match the naming already in data/txt: one underscore per non-alnum char.

    'Perda Jabar No. 9 Tahun 2023' -> 'Perda_Jabar_No__9_Tahun_2023'. Runs are
    not collapsed, so the period and the space after it each leave a mark.
    """
    return re.sub(r"[^A-Za-z0-9]", "_", stem)


def is_garbage_char(ch):
    """True for characters with no legitimate place in Indonesian legal text."""
    if ch == "�":
        return True
    if unicodedata.category(ch) == "Co":  # private use area
        return True
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF      # CJK unified ideographs
        or 0x3040 <= cp <= 0x30FF   # hiragana / katakana
        or 0xFF00 <= cp <= 0xFFEF   # halfwidth and fullwidth forms
    )


def classify(text):
    """Label a page's text: clean, corrupted, or empty."""
    stripped = text.strip()
    if len(stripped) < EMPTY_CHAR_THRESHOLD:
        return "empty", 0.0
    garbage_ratio = sum(is_garbage_char(c) for c in stripped) / len(stripped)
    if garbage_ratio > GARBAGE_RATIO_THRESHOLD:
        return "corrupted", garbage_ratio
    return "clean", garbage_ratio


def run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def text_layer_pages(pdf):
    """Extract the whole document once and split on the form feeds pdftotext emits."""
    proc = run(["pdftotext", "-layout", str(pdf), "-"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace")[:300])
    text = proc.stdout.decode("utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def ocr_page(pdf, pageno, workdir):
    """Render one page and OCR it. Returns text, or None if either step fails."""
    prefix = Path(workdir) / f"p{pageno}"
    render = run([
        "pdftoppm", "-r", str(OCR_DPI), "-gray", "-png",
        "-f", str(pageno), "-l", str(pageno),
        str(pdf), str(prefix),
    ])
    if render.returncode != 0:
        return None
    images = sorted(Path(workdir).glob(f"p{pageno}-*.png")) or sorted(
        Path(workdir).glob(f"p{pageno}.png")
    )
    if not images:
        return None
    ocr = run(["tesseract", str(images[0]), "stdout", "-l", OCR_LANGS])
    for img in images:
        img.unlink(missing_ok=True)
    if ocr.returncode != 0:
        return None
    return ocr.stdout.decode("utf-8", errors="replace")


def tool_versions():
    def first_line(cmd):
        try:
            proc = run(cmd, timeout=30)
            out = (proc.stdout or proc.stderr).decode(errors="replace")
            return out.strip().splitlines()[0]
        except Exception:
            return "unknown"

    return {
        "pdftotext": first_line(["pdftotext", "-v"]),
        "tesseract": first_line(["tesseract", "--version"]),
    }


def extract(pdf, tools):
    """Build the page-level record for one PDF."""
    layer_pages = text_layer_pages(pdf)
    pages = []

    with tempfile.TemporaryDirectory() as workdir:
        for index, layer_text in enumerate(layer_pages, start=1):
            label, garbage_ratio = classify(layer_text)
            page = {
                "page": index,
                "method": "text_layer",
                "classification": label,
                "garbage_ratio": round(garbage_ratio, 4),
                "text": layer_text,
            }

            if label != "clean":
                ocr_text = ocr_page(pdf, index, workdir)
                if ocr_text is None:
                    page["method"] = "ocr_failed"
                else:
                    ocr_label, ocr_garbage = classify(ocr_text)
                    page["method"] = "ocr"
                    page["classification"] = ocr_label
                    page["garbage_ratio"] = round(ocr_garbage, 4)
                    page["text"] = ocr_text
                    # Keep what OCR displaced, but only when it held content;
                    # an absent text layer has nothing to preserve.
                    if label == "corrupted":
                        page["replaced_text_layer"] = layer_text
                    page["replaced_classification"] = label

            page["char_count"] = len(page["text"].strip())
            pages.append(page)

    methods = {}
    classifications = {}
    for page in pages:
        methods[page["method"]] = methods.get(page["method"], 0) + 1
        classifications[page["classification"]] = (
            classifications.get(page["classification"], 0) + 1
        )

    return {
        "doc_id": slugify(pdf.stem),
        "source_pdf": str(pdf),
        "batch": pdf.parent.name,
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tools": tools,
        "ocr_langs": OCR_LANGS,
        "ocr_dpi": OCR_DPI,
        "n_pages": len(pages),
        "methods": methods,
        "classifications": classifications,
        "pages": pages,
    }


def find_pdfs(filter_substring=None):
    files = {p for p in RAW_DIR.rglob("*") if p.suffix.lower() == ".pdf"}
    files = {p for p in files if "Zone.Identifier" not in p.name}
    if filter_substring:
        needle = filter_substring.lower()
        files = {p for p in files if needle in str(p).lower()}
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filter", help="only process paths containing this substring")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    tools = tool_versions()

    manifest = []
    for pdf in find_pdfs(args.filter):
        rel = pdf.relative_to(RAW_DIR)
        if pdf.stat().st_size == 0:
            print(f"[skip]  {rel} -- zero-byte file, re-download needed", flush=True)
            manifest.append({"source_pdf": str(pdf), "error": "zero-byte file"})
            continue

        try:
            record = extract(pdf, tools)
        except Exception as exc:
            print(f"[fail]  {rel} -- {exc}", flush=True)
            manifest.append({"source_pdf": str(pdf), "error": str(exc)})
            continue

        out_path = args.out_dir / f"{record['doc_id']}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1))

        ocr_count = record["methods"].get("ocr", 0)
        failed = record["methods"].get("ocr_failed", 0)
        note = f"  ocr={ocr_count}" if ocr_count else ""
        note += f"  OCR_FAILED={failed}" if failed else ""
        still_bad = record["classifications"].get("corrupted", 0)
        note += f"  still_corrupted={still_bad}" if still_bad else ""
        print(f"[ok]    {rel}  pages={record['n_pages']}{note}", flush=True)

        manifest.append({
            "doc_id": record["doc_id"],
            "source_pdf": str(pdf),
            "batch": record["batch"],
            "n_pages": record["n_pages"],
            "methods": record["methods"],
            "classifications": record["classifications"],
            "output": str(out_path),
        })

    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tools": tools,
        "documents": manifest,
    }, ensure_ascii=False, indent=1))
    print(f"\nmanifest -> {manifest_path}")


if __name__ == "__main__":
    sys.exit(main())
