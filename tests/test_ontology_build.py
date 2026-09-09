#!/usr/bin/env python3
"""Regression tests for the ontology builder. Fixtures are real provisions."""

import structure
from ontology_build import (distributive_head, harvest_document, split_services,
                            subject_of, trim_label, instrument_rank, chapeau_of)

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  -- {detail}" if detail else ""))
        FAILURES.append(name)


# UU 1/2022 Pasal 55, scan damage included: `hunrf` for `huruf`,
# `permainanketangkasan` glued, `perlengkaphn` for `perlengkapan`. The huruf run
# has to be complete: `structure.py` accepts a sub-item list only as a run
# opening at `a` and advancing by one, so an abridged fixture jumping a,b,c,k,l
# silently keeps only a,b,c and the tail is swallowed into huruf c.
PASAL_55 = (
    "Pasal 55\n"
    "                 (1) Jasa Kesenian dan Hiburan sebagaimana dimaksud\n"
    "                      dalam Pasal 50 hunrf e meliputi:\n"
    "                      a. tontonan film atau bentuk tontonan audio visual\n"
    "                         lainnya yang dipertontonkan secara langsung di\n"
    "                          suatu lokasi tertentu;\n"
    "                     b. pergelaran kesenian, musik, tari, dan/atau busana;\n"
    "                     c. kontes kecantikan;\n"
    "                     d. kontes binaraga;\n"
    "                     e. pameran;\n"
    "                     f. pertunjukan sirkus, akrobat, dan sulap;\n"
    "                     g. pacuan kuda dan perlombaan kendaraan bermotor;\n"
    "                     h. permainanketangkasan;\n"
    "                     i. olahraga permainan dengan menggunakan\n"
    "                         tempat/ruang dan/atau peralatan dan perlengkaphn\n"
    "                         untuk olahraga dan kebugaran;\n"
    "                     j. rekreasi wahana air, wahana ekologi, wahana\n"
    "                         pendidikan, wahana budaya, wahana salju, wahana\n"
    "                         permainan, pemancingan, agrowisata, dan kebun\n"
    "                         binatang;\n"
    "                     k. panti pijat dan pijat refleksi; dan\n"
    "                     l. diskotek, karaoke, kelab malam, bar, dan mandi\n"
    "                         uap/spa.\n"
    "                 (2) Yang dikecualikan dari Jasa Kesenian dan Hiburan\n"
    "                     sebagaimana dimaksud pada ayat (1) adalah Jasa\n"
    "                     Kesenian dan Hiburan yang semata-mata untuk:\n"
    "                     a. promosi budaya tradisional dengan tidak dipungut\n"
    "                         bayaran;\n"
    "                     b. kegiatan layanan masyarakat dengan tidak dipungut\n"
    "                         bayaran; dan/atau\n"
    "                     c. bentuk kesenian dan hiburan lainnya yang diatur\n"
    "                         dengan Perda.\n")


def harvest():
    doc = structure.segment(PASAL_55)
    doc["doc_id"] = "UU_Nomor_1_Tahun_2022"
    return harvest_document(doc)


def test_splitting_a_huruf():
    # The comma matches before ` dan `, so the last member arrives with its
    # conjunction attached unless it is stripped per member.
    members, _ = split_services("diskotek, karaoke, kelab malam, bar, dan mandi uap/spa")
    check("conjunction stripped from the final member",
          members == ["diskotek", "karaoke", "kelab malam", "bar", "mandi uap/spa"],
          members)
    check("dan/atau stripped too",
          split_services("pergelaran kesenian, musik, tari, dan/atau busana")[0]
          == ["pergelaran kesenian", "musik", "tari", "busana"])
    check("two-member list splits",
          split_services("panti pijat dan pijat refleksi")[0]
          == ["panti pijat", "pijat refleksi"])
    # A qualified noun phrase is one concept; splitting it invents categories.
    members, reason = split_services(
        "tontonan film atau bentuk tontonan audio visual lainnya yang "
        "dipertontonkan secara langsung di suatu lokasi tertentu")
    check("a subordinate clause blocks the split", members is None, members)
    check("and says why", reason == "qualified_by_subordinate_clause", reason)
    check("a single term is not split",
          split_services("kontes kecantikan")[0] is None)


def test_distributive_head_is_flagged_not_resolved():
    # `pergelaran kesenian, musik, tari` means pergelaran musik, not musik.
    # 3 of the 5 splits in Pasal 55(1) do this.
    check("head detected",
          distributive_head(["pergelaran kesenian", "musik", "tari", "busana"])
          == "pergelaran")
    check("also for pertunjukan",
          distributive_head(["pertunjukan sirkus", "akrobat", "sulap"])
          == "pertunjukan")
    # A flat list of equals has no distributive head.
    check("flat list is not flagged",
          distributive_head(["diskotek", "karaoke", "kelab malam", "bar",
                             "mandi uap/spa"]) is None)


def test_exclusion_list_is_not_harvested():
    cats, notes = harvest()
    ids = {c["id"] for c in cats}
    # Pasal 55(2) enumerates what is NOT taxable. Harvesting it would create
    # categories that are by definition outside the tax.
    check("exclusions absent from categories",
          not any("promosi_budaya" in i for i in ids), sorted(ids))
    check("and logged with a reason",
          any(n["reason"] == "exclusion_list_not_a_category" for n in notes), notes)


def test_pasal_55_recovers_the_statutory_categories():
    cats, _ = harvest()
    ids = {c["id"] for c in cats}
    for expected in ["panti_pijat", "pijat_refleksi", "diskotek", "karaoke",
                     "kelab_malam", "bar", "mandi_uap_spa", "kontes_kecantikan"]:
        check(f"recovered {expected}", expected in ids, sorted(ids))
    check("the subject becomes the root",
          "jasa_kesenian_dan_hiburan" in ids)
    check("subject is tagged taxable",
          next(c for c in cats if c["id"] == "jasa_kesenian_dan_hiburan")
          ["taxable_subject"] is True)


def test_heading_bleed_is_trimmed():
    # A swallowed section heading, from the ~89 known segmentation leaks.
    lab, bled = trim_label("Pajak Sarang Burung Walet. Bagian Kedua Rincian Objek")
    check("heading removed", lab == "Pajak Sarang Burung Walet", lab)
    check("and the leak is reported", bled is True)
    lab, bled = trim_label("panti pijat dan pijat refleksi; dan")
    check("ordinary label untouched", lab == "panti pijat dan pijat refleksi", lab)
    check("no false leak", bled is False)


def test_rank_drives_the_live_pending_split():
    check("UU is national", instrument_rank("UU_Nomor_1_Tahun_2022") == "national")
    check("PP is national", instrument_rank("PP_Nomor_35_Tahun_2023") == "national")
    check("Perda is not",
          instrument_rank("Peraturan_Daerah__Perda__Kota_Cirebon") == "perda")
    # The Perwal tier spells itself four ways; all of them must be caught.
    for name in ["Perwal_Kota_Jogja_Nomor_51", "Perwali_Kota_Surabaya_No_26",
                 "Peraturan_Walikota_Surabaya_Nomor_10"]:
        check(f"{name[:22]} is perwal", instrument_rank(name) == "perwal")


if __name__ == "__main__":
    import sys
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            print(f"\n{name}:")
            fn()
    print("\n" + ("all passed" if not FAILURES else f"{len(FAILURES)} failing: {FAILURES}"))
    sys.exit(1 if FAILURES else 0)
