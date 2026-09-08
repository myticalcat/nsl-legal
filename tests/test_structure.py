#!/usr/bin/env python3
"""Regression tests for structural segmentation. Every fixture below is real
text from the corpus, including its scan damage -- `4Oo/o lempat puluh persen)`
and `Pass} 1` are what the documents actually yield, not invented noise."""

import structure

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  -- {detail}" if detail else ""))
        FAILURES.append(name)


def citations(segmented):
    return [c for c, _ in structure.iter_units(segmented)]


# --- UU 1/2022 Pasal 58, verbatim including OCR damage -------------------
UU_58 = (
    "    Pasal 58\n"
    "                (1) TarifPBJT ditetapkan paling tinggi sebesar 10% (sepuluh\n"
    "                   persen).\n"
    "                (2) Khusus tarif PBJT atas jasa hiburan pada diskotek,\n"
    "                    karaoke, kelab malam, bar, dan mandi uap/spa\n"
    "                    ditetapkan paling rendah 4Oo/o lempat puluh persen) dan\n"
    "                    paling tinggi 75% (tujuh puluh lima persen).\n"
    "                (3) Khusus tarif PBJT atas Tenaga Listrik untuk:\n"
    "                    a. konsumsi Tenaga Listrik dari sumber lain oleh\n"
    "                       industri, ditetapkan paling tinggi 3% (tiga persen);\n"
    "                    b. konsumsi Tenaga Listrik yang dihasilkan sendiri,\n"
    "                       ditetapkan paling tinggi 1,5% (satu koma limapersen).\n"
    "                (4) Tarif PBJT sebagaimana dimaksud pada ayat (1)\n"
    "                    ditetapkan dengan Perda.\n"
)


def test_ayat_and_huruf():
    seg = structure.segment(UU_58)
    p = seg["pasal"][0]
    check("pasal 58 found", p["pasal"] == "58", p["pasal"])
    check("four ayat", len(p["ayat"]) == 4, len(p["ayat"]))
    ayat3 = [a for a in p["ayat"] if a["ayat"] == "3"][0]
    check("ayat (3) has two huruf", len(ayat3["huruf"]) == 2, len(ayat3["huruf"]))
    check("huruf citation is addressable",
          ayat3["huruf"][1]["citation"] == "Pasal 58 ayat (3) huruf b",
          ayat3["huruf"][1]["citation"])
    check("ayat (1) has no spurious huruf", not p["ayat"][0]["huruf"])
    # Offsets must point back at the source, so a span can be verified.
    check("offsets are faithful",
          UU_58[ayat3["huruf"][0]["start"]:ayat3["huruf"][0]["end"]]
          == ayat3["huruf"][0]["text"])
    # The deepest unit is what a norm cites; ayat (3) itself must not be
    # emitted alongside its huruf or its text would be counted twice.
    cites = citations(seg)
    check("deepest-level units only",
          "Pasal 58 ayat (3)" not in cites and "Pasal 58 ayat (3) huruf a" in cites)


# --- UU 1/2022 Pasal 55(1): the twelve statutory categories --------------
UU_55 = (
    "    Pasal 55\n"
    "        (1) Jasa Kesenian dan Hiburan meliputi:\n"
    "            a. tontonan film;\n"
    "            b. pergelaran kesenian;\n"
    "            c. kontes kecantikan;\n"
    "            d. kontes binaraga;\n"
    "            e. pameran;\n"
    "            f. pertunjukan sirkus;\n"
    "            g. pacuan kuda;\n"
    "            h. balap kendaraan bermotor;\n"
    "            i. permainan ketangkasan;\n"
    "            j. olahraga permainan;\n"
    "            k. panti pijat dan pijat refleksi; dan\n"
    "            l. diskotek, karaoke, kelab malam, bar, dan mandi uap/spa.\n"
)


def test_twelve_categories():
    seg = structure.segment(UU_55)
    ayat1 = seg["pasal"][0]["ayat"][0]
    check("twelve huruf recovered", len(ayat1["huruf"]) == 12, len(ayat1["huruf"]))
    by_letter = {h["huruf"]: " ".join(h["text"].split()) for h in ayat1["huruf"]}
    # The panti pijat conflict turns on k and l being separate items.
    check("huruf k is panti pijat",
          by_letter.get("k") == "panti pijat dan pijat refleksi; dan", by_letter.get("k"))
    check("huruf l is the hiburan list",
          by_letter.get("l", "").startswith("diskotek, karaoke"), by_letter.get("l"))


# --- pasal numbering: scan damage vs genuine suffix ----------------------
def test_o_for_zero_is_not_a_restart():
    # PP 35/2023 renders article 70 as `Pasal 7O`. Read naively this looks
    # like a jump from 69 back to 7 and split the document into nine pieces.
    text = "Pasal 69\nisi pasal 69.\nPasal 7O\nisi pasal 70.\nPasal 71\nisi pasal 71.\n"
    seg = structure.segment(text)
    check("7O does not open a section", len(seg["sections"]) == 1,
          [s["section"] for s in seg["sections"]])
    check("all three pasal kept", len(seg["pasal"]) == 3, len(seg["pasal"]))


def test_genuine_letter_suffix_survives():
    # `Pasal 12A` is how an amendment inserts an article. It must not be
    # repaired into 128, and B must not become 8 either.
    text = "Pasal 12\nisi.\nPasal 12A\nisi.\nPasal 12B\nisi.\nPasal 13\nisi.\n"
    seg = structure.segment(text)
    check("suffixed pasal preserved",
          [p["pasal"] for p in seg["pasal"]] == ["12", "12A", "12B", "13"],
          [p["pasal"] for p in seg["pasal"]])
    check("no section split on suffixes", len(seg["sections"]) == 1)


# --- sections -----------------------------------------------------------
def test_penjelasan_restart():
    text = ("Pasal 1\nisi operatif.\nPasal 2\nisi operatif.\n"
            "PENJELASAN\nATAS PERATURAN DAERAH\nI. UMUM\nnarasi umum.\n"
            "II. PASAL DEMI PASAL\nPasal 1\nCukup jelas.\nPasal 2\nCukup jelas.\n")
    seg = structure.segment(text)
    labels = [s["section"] for s in seg["sections"]]
    check("body then penjelasan", labels == ["body", "penjelasan"], labels)
    # Both copies of Pasal 1 survive; keying by number alone would drop one.
    ones = [p for p in seg["pasal"] if p["pasal"] == "1"]
    check("both Pasal 1 kept", len(ones) == 2, len(ones))
    check("sections distinguish them",
          sorted(p["section"] for p in ones) == ["body", "penjelasan"])
    check("umum narrative not operative",
          all("narasi umum" not in p["text"] for p in seg["pasal"] if p["section"] == "body"))


def test_penjelasan_only_file():
    # Gorontalo 1/2024 ships body, penjelasan and lampiran as three PDFs, so
    # a file can open directly in a penjelasan with no operative text at all.
    text = "PENJELASAN\nATAS PERATURAN DAERAH KOTA GORONTALO\nPasal 1\nCukup jelas.\n"
    seg = structure.segment(text)
    check("leading section labelled penjelasan",
          seg["sections"][0]["section"] == "penjelasan",
          seg["sections"][0]["section"])
    check("no operative pasal claimed",
          not [p for p in seg["pasal"] if p["section"] == "body"])


def test_mid_body_renumbering_is_a_defect_not_a_section():
    # Perda Bau-Bau 1/2024 numbers 18, 19, 20 and then, under `Bagian Keempat
    # PBJT`, numbers 18, 19, 20 a second time before carrying on at 21.
    text = ("Pasal 18\nsatu.\nPasal 19\ndua.\nPasal 20\ntiga.\n"
            "Bagian Keempat\nPBJT\nPasal 18\nempat.\nPasal 19\nlima.\n"
            "Pasal 20\nenam.\nPasal 21\ntujuh.\n")
    seg = structure.segment(text)
    check("stays one section", len(seg["sections"]) == 1,
          [s["section"] for s in seg["sections"]])
    check("every pasal kept", len(seg["pasal"]) == 7, len(seg["pasal"]))
    check("backwards numbering is reported",
          any(w["warning"] == "pasal_numbering_goes_backwards" for w in seg["warnings"]))
    check("duplicates are reported, not dropped",
          sum(1 for w in seg["warnings"]
              if w["warning"] == "duplicate_pasal_in_section") == 3,
          seg["warnings"])
    check("occurrence distinguishes the duplicates",
          [p["occurrence"] for p in seg["pasal"] if p["pasal"] == "18"] == [1, 2])


# --- sub-item runs ------------------------------------------------------
def test_penjelasan_citation_is_distinct_from_the_body():
    # `Pasal 32` in Perda Tangerang Selatan 10/2023 is a 25% reklame rate;
    # `Pasal 32` in its penjelasan is `Cukup jelas.` Emitting one string for
    # both made 741 of 1,328 corpus citation collisions.
    # The penjelasan opens on the same number the body closed with, so a
    # numbering restart never fires; the heading has to be a boundary itself.
    text = ("Pasal 31\nisi.\nPasal 32\nTarif Pajak Reklame sebesar 25%.\n"
            "PENJELASAN\nII. PASAL DEMI PASAL\nPasal 32\nCukup jelas.\n")
    seg = structure.segment(text)
    cites = citations(seg)
    check("body citation unqualified", "Pasal 32" in cites, cites)
    check("penjelasan citation qualified", "Penjelasan Pasal 32" in cites, cites)
    check("citations are unique", len(cites) == len(set(cites)), cites)


def test_duplicate_pasal_citations_are_distinguished():
    # Bau-Bau numbers 18 twice in one section; both need their own address.
    text = "Pasal 18\nsatu.\nPasal 19\ndua.\nPasal 18\ntiga.\n"
    seg = structure.segment(text)
    cites = [p["citation"] for p in seg["pasal"]]
    check("second occurrence marked", cites == ["Pasal 18", "Pasal 19", "Pasal 18 #2"],
          cites)


def test_page_furniture_does_not_break_a_provision():
    # A catchword, stamp and running header sit at the page break between
    # ayat (1) and ayat (2) in PP 35/2023, pushing `(2)` off the line start so
    # ayat (1) swallowed its siblings and their a./b./c. lists collapsed into
    # one citation. Furniture is per page, so this fixture is two pages.
    page1 = ("PRESIDEN\nREPUBLIK INDONESIA\n- 12 -\n"
             "Pasal 3\n"
             "(1) Jenis Pajak provinsi meliputi:\n"
             "    a. PKB;\n"
             "    b. BBNKB;\n"
             "    c. PAB.\n"
             "PAB . . .\nSK No 145757A\n")
    page2 = ("PRESIDEN\nREPUBLIK INDONESIA\n- 13 -\n"
             "(2) Jenis Pajak kabupaten/kota meliputi:\n"
             "    a. PBB-P2;\n"
             "    b. Pajak Reklame;\n"
             "    c. PAT.\n"
             "Pasal . . .\nSK No 145758 A\n")
    pages = [{"page": 1, "method": "text_layer", "text": page1},
             {"page": 2, "method": "text_layer", "text": page2}]
    joined, _ = structure.join_pages(pages)
    check("running header removed", "PRESIDEN" not in joined, joined[:110])
    check("catchword removed", ". . ." not in joined)
    check("stamp removed", "SK No" not in joined)
    check("provision text kept", "Jenis Pajak provinsi" in joined)

    seg = structure.segment(joined)
    p = seg["pasal"][0]
    check("both ayat recovered", [a["ayat"] for a in p["ayat"]] == ["1", "2"],
          [a["ayat"] for a in p["ayat"]])
    firsts = [" ".join(h["text"].split()).rstrip(";.") for a in p["ayat"]
              for h in a["huruf"] if h["huruf"] == "a"]
    check("each ayat keeps its own huruf a", firsts == ["PKB", "PBB-P2"], firsts)
    check("no multi-run warning once markers are visible",
          not [w for w in seg["warnings"] if "multiple" in w["warning"]],
          seg["warnings"])


def test_repeated_body_wording_is_not_treated_as_furniture():
    # `Cukup jelas.` occurs 245 times mid-page in PP 35/2023 and is real text.
    # Only the page edges are eligible, so frequency alone cannot delete it.
    pages = [{"page": i, "method": "text_layer",
              "text": (f"PRESIDEN\nREPUBLIK INDONESIA\nPasal {i}\n"
                       f"Cukup jelas.\nisi ketentuan {i}.\nlanjutan {i}.\n- {i} -\n")}
             for i in range(1, 9)]
    joined, _ = structure.join_pages(pages)
    check("header stripped", "PRESIDEN" not in joined)
    check("mid-page repetition kept", joined.count("Cukup jelas.") == 8,
          joined.count("Cukup jelas."))


def test_lampiran_is_not_absorbed_into_the_preceding_pasal():
    # A lampiran carries no pasal of its own, so without a boundary its rows
    # land inside whichever pasal precedes it and parse as ayat and huruf --
    # in Perda Semarang 4/2025 half a million characters of tariff table were
    # nested under one pasal, and 35% of citations across the corpus collided.
    text = ("Pasal 9\n"
            "(1) Tarif diatur dalam Lampiran.\n"
            "LAMPIRAN I\n"
            "TARIF RETRIBUSI\n"
            "1. Titip Darah 5.000 per kantong\n"
            "2. Gol. Darah ABO 15.000 per test\n"
            "a. Konsultasi Spesialis 50.000\n"
            "b. Konsultasi Ahli Gizi 25.000\n")
    seg = structure.segment(text)
    labels = [s["section"] for s in seg["sections"]]
    check("lampiran becomes its own section", labels == ["body", "lampiran"], labels)
    p = seg["pasal"][0]
    check("pasal text stops at the lampiran",
          "Titip Darah" not in p["text"], p["text"][:80])
    check("table rows are not huruf",
          not p["ayat"][0]["huruf"], p["ayat"][0]["huruf"])
    check("lampiran section is not a numbering restart",
          seg["sections"][1]["restart"] is False, seg["sections"][1])


def test_stray_marker_is_not_a_huruf():
    # A sentence ending in an initial, or a lone `b.`, must not open a list.
    text = "Pasal 3\nketentuan umum berlaku.\nb. bukan awal daftar apa pun.\n"
    seg = structure.segment(text)
    check("run must open at a", not seg["pasal"][0]["huruf"],
          seg["pasal"][0]["huruf"])


def test_angka_nested_under_huruf():
    text = ("Pasal 4\n"
            "(1) Objek meliputi:\n"
            "    a. jasa tertentu, yaitu:\n"
            "       1) hotel;\n"
            "       2) restoran;\n"
            "    b. barang tertentu.\n")
    seg = structure.segment(text)
    huruf = seg["pasal"][0]["ayat"][0]["huruf"]
    check("two huruf", len(huruf) == 2, len(huruf))
    check("angka nested under huruf a", len(huruf[0]["angka"]) == 2,
          len(huruf[0]["angka"]))
    check("angka citation is full",
          huruf[0]["angka"][0]["citation"] == "Pasal 4 ayat (1) huruf a angka 1",
          huruf[0]["angka"][0]["citation"])


def test_units_walk_ayat_with_angka_children():
    # An ayat whose children are angka with no huruf between. iter_units used
    # to probe for a child list, but an angka node stores its label under the
    # same key name a huruf node stores its children under, so the string was
    # iterated character by character.
    text = ("Pasal 7\n"
            "(1) Tarif ditetapkan sebagai berikut:\n"
            "    1. golongan A sebesar 10%;\n"
            "    2. golongan B sebesar 20%.\n"
            "(2) Ketentuan lain diatur dengan Perkada.\n")
    seg = structure.segment(text)
    cites = citations(seg)
    check("angka under ayat are addressable",
          "Pasal 7 ayat (1) angka 2" in cites, cites)
    check("ayat (1) not double-counted", "Pasal 7 ayat (1)" not in cites, cites)
    check("childless ayat still emitted", "Pasal 7 ayat (2)" in cites, cites)


def test_definitions_pasal_numbered_list():
    # Pasal 1 of every instrument is a numbered definition list with no ayat.
    text = ("Pasal 1\n"
            "Dalam Peraturan Daerah ini yang dimaksud dengan:\n"
            "1. Daerah adalah Kota Surabaya.\n"
            "2. Pemerintah Daerah adalah pemerintah Kota Surabaya.\n"
            "3. Pajak adalah kontribusi wajib kepada Daerah.\n")
    seg = structure.segment(text)
    p = seg["pasal"][0]
    check("no ayat claimed", not p["ayat"])
    check("three angka at pasal level", len(p["angka"]) == 3, len(p["angka"]))
    check("angka citation at pasal level",
          p["angka"][2]["citation"] == "Pasal 1 angka 3", p["angka"][2]["citation"])


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"\n{t.__name__}:")
        t()
    print("\n" + ("all passed" if not FAILURES else f"{len(FAILURES)} failing: {FAILURES}"))
    sys.exit(1 if FAILURES else 0)
