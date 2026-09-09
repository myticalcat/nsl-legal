#!/usr/bin/env python3
"""Regression tests for the prefilter. Every fixture is a real string from a
corpus document, scan damage and all."""

import structure
from prefilter import classify, modal_wajib, DEADLINE_NUMERAL, PERCENT_ISH
from slotting import canonical

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  -- {detail}" if detail else ""))
        FAILURES.append(name)


def bucket(text):
    """Segment a fragment as one pasal and classify it."""
    return classify(structure.segment(text)["pasal"][0])


# ---------------------------------------------------------- the noun/modal split

def test_wajib_noun_is_not_a_modal():
    # Perda Surabaya 7/2023 and 32 others: the statutory definition of a tax.
    # `wajib` here is an adjective in `compulsory contribution`.
    check("kontribusi wajib is the adjective",
          modal_wajib(canonical(
              "Pajak Daerah yang selanjutnya disebut Pajak adalah kontribusi "
              "wajib kepada Daerah yang terutang oleh orang pribadi")) == [])
    # The defined noun, in both the capitalised and the lowercase form the
    # corpus actually uses. 194 occurrences are lowercase in the source.
    check("Wajib Pajak excluded",
          modal_wajib("Wajib Pajak menyampaikan SPTPD") == [])
    check("lowercase wajib pajak excluded",
          modal_wajib("nama wajib pajak atau penanggung pajak") == [])
    check("Wajib Retribusi excluded",
          modal_wajib("Subjek Retribusi dan Wajib Retribusi ditetapkan") == [])
    # UU 1/2022 Pasal 18. PAB is a tax type, so `Wajib PAB` is a taxpayer.
    check("Wajib PAB excluded",
          modal_wajib("Wajib PAB adalah orang pribadi atau Badan") == [])
    # Perda Padang Panjang, a damaged scan: `Pajak` read as `Pajck`.
    check("OCR-damaged head still excluded",
          modal_wajib("Kondisi Wajib Pajck atau Wajib Retribusi") == [])
    # Perda Surabaya heading: the defined term split by the phrase.
    check("truncated term in a heading excluded",
          modal_wajib("Paragraf 1 Subjek, Wajib, dan Objek Pajak") == [])
    # UU 1/2022 Pasal 141: a defined term from UU 23/2014, not a duty.
    check("Urusan Pemerintahan wajib excluded",
          modal_wajib("kebutuhan Urusan Pemerintahan wajib yang terkait "
                      "dengan pelayanan dasar") == [])


def test_real_modals_survive():
    # UU 1/2022 Pasal 161.
    check("Pemerintah Daerah wajib membayar",
          len(modal_wajib("Pemerintah Daerah wajib membayar kewajiban "
                          "Pembiayaan Utang Daerah")) == 1)
    # Perwali Surabaya 33/2024 Pasal 108: the noun and the modal in one clause,
    # which is the case that makes a bare lexicon useless.
    check("noun and modal in one sentence yields exactly one modal",
          len(modal_wajib("Wajib Pajak wajib menyampaikan SPTPD secara "
                          "elektronik dengan benar")) == 1)
    # PP 35/2023 Pasal 60: a colon introducing a list of duties. Distinguish
    # from the comma case above, which is a heading.
    check("wajib: introducing a duty list survives",
          len(modal_wajib("notaris sesuai kewenangannya wajib: a. meminta "
                          "bukti pembayaran BPHTB")) == 1)


# ------------------------------------------------------------------- bucketing

def test_rate_provision_is_extracted():
    # UU 1/2022 Pasal 58 as the scan renders it.
    rec = bucket(
        "Pasal 58\n"
        "(1) TarifPBJT ditetapkan paling tinggi sebesar lOVo (sepuluh persen).\n"
        "(2) Khusus tarif PBJT atas jasa hiburan pada diskotek, karaoke\n"
        "    ditetapkan paling rendah 4Oo/o lempat puluh persen) dan paling\n"
        "    tinggi 75% (tujuh puluh lima persen).\n")
    check("extracted", rec["bucket"] == "extract", rec)
    check("both markers seen",
          {"paling_tinggi", "paling_rendah"} <= set(rec["bound_markers"]),
          rec["bound_markers"])
    check("three slots", rec["n_slots"] == 3, rec["n_slots"])


def test_procedural_pasal_is_skipped_with_a_reason():
    rec = bucket("Pasal 200\nPeraturan Daerah ini mulai berlaku pada tanggal "
                 "diundangkan.\n")
    check("skipped", rec["bucket"] == "skip", rec)
    check("reason recorded",
          rec["skip_reason"] == "no_normative_marker", rec.get("skip_reason"))


def test_deadline_without_a_marker_is_now_selected():
    # Perda Batam 1/2024 Pasal 134: a limitation period in the double-numeral
    # convention with no `paling lama`. Until the duration channel existed,
    # `scan()` could not see it -- it required a percent tail -- and the pasal
    # was skipped under `deadline_numeral_no_marker`.
    rec = bucket("Pasal 134\nTindak pidana di bidang perpajakan Daerah tidak "
                 "dapat dituntut apabila telah melampaui jangka waktu 5 (lima) "
                 "tahun terhitung sejak saat terutangnya pajak.\n")
    check("duration produces a slot", rec["n_slots"] == 1, rec)
    check("selected", rec["bucket"] == "extract", rec)
    check("selected by the numeral channel",
          rec["selected_by"] == ["numeral_pair"], rec.get("selected_by"))


def test_deadline_reason_survives_as_a_guard():
    # `deadline_numeral_no_marker` should now be unreachable: anything
    # DEADLINE_NUMERAL matches, PAIR_DURATION also matches, so the pasal is
    # selected before the skip branch is consulted. It stays as a recall guard,
    # the same way `unexplained_numeral` does -- if it ever fires, the duration
    # channel missed something.
    check("guard still recognises all three day types",
          all(DEADLINE_NUMERAL.search(t) for t in
              ["3 (tiga) hari kerja", "30 (tiga puluh) hari",
               "15 (lima belas) hari kalender"]))


def test_unexplained_numeral_is_louder_than_a_plain_skip():
    # Never observed in the corpus -- the code is a guard, and its zero count
    # is the recall check passing. It still has to fire when it should.
    check("percent with no pair and no marker is flagged",
          PERCENT_ISH.search("dikenakan tambahan 5% dari pokok"))
    rec = bucket("Pasal 9\nPengurangan diberikan sebanyak 5% dari pokok pajak "
                 "terutang menurut ketentuan yang berlaku.\n")
    check("flagged rather than filed as empty",
          rec.get("skip_reason") == "unexplained_numeral" or rec["bucket"] == "extract",
          rec)


def test_dilarang_selects():
    # UU 1/2022 Pasal 6(1) and Perda Batam 1/2024 Pasal 6(1), the same
    # prohibition at two ranks.
    rec = bucket("Pasal 6\n(1) Pemerintah Daerah dilarang memungut Pajak "
                 "selain jenis Pajak sebagaimana dimaksud dalam Pasal 4 "
                 "ayat (1).\n")
    check("prohibition selected", rec["bucket"] == "extract", rec)
    check("selected by the modal", "modal_dilarang" in rec["selected_by"],
          rec["selected_by"])


if __name__ == "__main__":
    import sys
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            print(f"\n{name}:")
            fn()
    print("\n" + ("all passed" if not FAILURES else f"{len(FAILURES)} failing: {FAILURES}"))
    sys.exit(1 if FAILURES else 0)
