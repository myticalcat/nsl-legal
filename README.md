# Setup

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

Put source PDFs in `data/raw/`, then:

    for f in data/raw/*.pdf; do
      pdftotext -layout "$f" "data/txt/$(basename "${f%.pdf}").txt"
    done

# Run

    python tests/test_ocr_numerals.py                       # regression suite
    python src/ocr_numerals.py data/txt/UU_Nomor_1_Tahun_2022.txt
    python src/slotting.py                                  # slotting demo
    python src/detect.py                                    # conflict detection

See CLAUDE.md for architecture, decisions, and open work.
