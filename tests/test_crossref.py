#!/usr/bin/env python3
"""Regression tests for cross-reference resolution. Every fixture below is a
real excerpt from data/txt/, copied verbatim (only re-indented for
readability), not a constructed example."""

from crossref import (
    build_index, _tokenize, _canon, _unparen_repair, _read_targets, _match_external,
)

# --- real excerpt: PERDA_NO_1_TAHUN_2024.txt lines 1221-1231
JAKARTA_P44_P48 = """
                                Pasal 44

Objek PBJT merupakan penjualan, penyerahan, dan/atau konsumsi
Barang dan Jasa Tertentu yang meliputi:
a. Makanan dan/atau Minuman;
b. Tenaga Listrik;
c. Jasa Perhotelan;
d. Jasa Parkir; dan
e. Jasa Kesenian dan Hiburan.

                                Pasal 45

Objek Pajak lainnya.

                                Pasal 48

(1)   Jasa Parkir sebagaimana dimaksud dalam Pasal Pasal 44 huruf d
      meliputi:
      a. penyediaan atau penyelenggaraan tempat parkir; dan/atau
      b. penyediaan atau penyelenggaraan bangunan parkir.
"""

# --- real excerpt: UU_Nomor_1_Tahun_2022.txt lines 1747-1768
UU_P58 = """
                                   Pasal 58
                (1) TarifPBJT ditetapkan paling tinggi sebesar 10% (sepuluh
                   persen).
                (2) Khusus tarif PBJT atas jasa hiburan pada diskotek,
                    karaoke, kelab malam, bar, dan mandi uap/spa
                    ditetapkan paling rendah 4Oo/o lempat puluh persen) dan
                    paling tinggi 75% (tujuh puluh lima persen).
                (3) Khusus tarif PBJT atas Tenaga Listrik untuk:
                    a. konsumsi Tenaga Listrik dari sumber lain oleh
                        industri, pertambangan minyak bumi dan gas alam,
                        ditetapkan paling tinggi sebesar 3% (tiga persen); dan
                    b. konsumsi Tenaga Listrik yang dihasilkan sendiri,
                        ditetapkan paling tinggi 1,5% (satu koma lima
                       persen).
                (4) Tarif PBJT sebagaimana dimaksud pada ayat (l), ayat (2),
                    dan ayat (3) ditetapkan dengan Perda.

                                   Pasal 59
                (1) Besaran pokok PBJT yang terutang dihitung dengan cara
                   mengalikan dasar pengenaan PBJT sebagaimaha
                   dimaksud dalam Pasal 57 dengan tarif PBJT
                   sebagaimana dimaksud dalam Pasal 58 ayat (4).
"""

# --- PENJELASAN-boundary fixture: real heading text (line 2922) + real
# 'Cukup jelas.' stub style found in every document's elucidation appendix
PENJELASAN_FIXTURE = """
                                Pasal 1

Dalam Peraturan Daerah ini yang dimaksud dengan Daerah adalah Provinsi
Daerah Khusus Ibukota Jakarta.

                                Pasal 2

Ketentuan mengenai Pajak diatur lebih lanjut.

                                  PENJELASAN

                                      ATAS

                            NOMOR 1 TAHUN 2024

I.   UMUM

     Peraturan Daerah ini mengatur ketentuan pelaksanaan.

II. PASAL DEMI PASAL

Pasal 1
   Cukup jelas.
Pasal 2
   Cukup jelas.
"""


def check_index_basic():
    idx = build_index(JAKARTA_P44_P48)
    assert "44" in idx, "Pasal 44 missing from index"
    p44 = idx["44"]
    assert p44["ayat"] == {}, f"Pasal 44 should have no ayat, got {p44['ayat']!r}"
    assert set(p44["huruf"]) == set("abcde"), f"got {sorted(p44['huruf'])}"
    assert "Jasa Parkir" in p44["huruf"]["d"]["text"]
    assert "Jasa Kesenian dan Hiburan" in p44["huruf"]["e"]["text"]


def check_index_ayat_and_huruf():
    idx = build_index(UU_P58)
    assert "58" in idx and "59" in idx
    p58 = idx["58"]
    assert set(p58["ayat"]) == {"1", "2", "3", "4"}, sorted(p58["ayat"])
    assert p58["huruf"] == {}
    ayat3 = p58["ayat"]["3"]
    assert set(ayat3["huruf"]) == {"a", "b"}
    assert "3% (tiga persen)" in ayat3["huruf"]["a"]["text"]
    assert "1,5%" in ayat3["huruf"]["b"]["text"]


def check_index_stops_before_penjelasan():
    idx = build_index(PENJELASAN_FIXTURE)
    assert set(idx) == {"1", "2"}, f"PENJELASAN's Pasal 1/2 stubs leaked in: {sorted(idx)}"
    assert "Daerah Khusus Ibukota Jakarta" in idx["1"]["text"]
    assert "Cukup jelas" not in idx["1"]["text"]


def check_tokenize_paren_and_words():
    toks = _tokenize("dimaksud dalam Pasal 55 ayat (1) huruf l")
    assert toks == ["dimaksud", "dalam", "pasal", "55", "ayat", "(1)", "huruf", "l"], toks


def check_canon_repairs_real_keyword_typos():
    # 'ayal' for 'ayat' -- real corruption, Perda Surabaya 7/2023 line 4784
    assert _canon("ayal") == "ayat"
    # 'alat' for 'ayat' -- real corruption, UU 1/2022 (Dana Otonomi Khusus clause)
    assert _canon("alat") == "ayat"
    # unrelated real word must NOT be coerced
    assert _canon("pajak") == "pajak"


def check_canon_leaves_far_typos_alone():
    # 'hunrf' for 'huruf' -- real corruption, UU 1/2022 Pasal 55 (edit
    # distance 2, deliberately past the distance-1 threshold)
    assert _canon("hunrf") == "hunrf"


def check_unparen_repair():
    # '(l)' -- real corruption, UU 1/2022 Pasal 58(4) and PERDA_NO_1_TAHUN_2024 Pasal 80
    assert _unparen_repair("(l)") == "1"
    assert _unparen_repair("(2)") == "2"


def check_bare_ayat_list_same_pasal():
    # UU 1/2022 Pasal 58(4): 'ayat (l), ayat (2), dan ayat (3)' -- corrupted
    # first paren, no Pasal named, so every target defaults to current_pasal.
    words = _tokenize("pada ayat (l), ayat (2), dan ayat (3) ditetapkan")
    targets = _read_targets(words, current_pasal="58")
    assert targets == [
        {"pasal": "58", "ayat": "1", "huruf": None},
        {"pasal": "58", "ayat": "2", "huruf": None},
        {"pasal": "58", "ayat": "3", "huruf": None},
    ], targets


def check_cross_pasal_with_huruf():
    # PERDA_NO_1_TAHUN_2024 Pasal 80 citing Pasal 74 ayat (l) huruf f
    # (corrupted paren, real text).
    words = _tokenize("dalam Pasal 74 ayat (l) huruf f merupakan")
    targets = _read_targets(words, current_pasal="80")
    assert targets == [{"pasal": "74", "ayat": "1", "huruf": "f"}], targets


def check_bare_pasal_no_ayat():
    # UU 1/2022 Pasal 59(1) citing Pasal 57 (no ayat/huruf at all).
    words = _tokenize("dalam Pasal 57 dengan tarif")
    targets = _read_targets(words, current_pasal="59")
    assert targets == [{"pasal": "57", "ayat": None, "huruf": None}], targets


def check_pasal_direct_huruf_no_ayat():
    # UU 1/2022 Pasal 51(1) citing Pasal 50 huruf a (Pasal 50 has no ayat).
    words = _tokenize("dalam Pasal 50 huruf a meliputi")
    targets = _read_targets(words, current_pasal="51")
    assert targets == [{"pasal": "50", "ayat": None, "huruf": "a"}], targets


def check_doubled_pasal_keyword():
    # PERDA_NO_1_TAHUN_2024 Pasal 48(1) citing 'Pasal Pasal 44 huruf d'
    # (real doubled-word OCR artifact).
    words = _tokenize("dalam Pasal Pasal 44 huruf d meliputi")
    targets = _read_targets(words, current_pasal="48")
    assert targets == [{"pasal": "44", "ayat": None, "huruf": "d"}], targets


def check_ayat_keyword_typo_same_pasal():
    # Perda Surabaya 7/2023 Pasal 177(10) citing 'ayal (2) dan ayat (4)'
    # (real keyword typo, both same-Pasal).
    words = _tokenize("pada ayal (2) dan ayat (4) meliputi")
    targets = _read_targets(words, current_pasal="177")
    assert targets == [
        {"pasal": "177", "ayat": "2", "huruf": None},
        {"pasal": "177", "ayat": "4", "huruf": None},
    ], targets


def check_huruf_typo_degrades_to_bare_pasal():
    # UU 1/2022 Pasal 55(1) citing 'Pasal 50 hunrf e' -- 'hunrf' is distance
    # 2 from 'huruf', so the parser can't recognise the huruf keyword. It
    # should NOT drop the reference entirely: 'Pasal 50' was cleanly read
    # before the typo hit, so that much is flushed as a whole-Pasal target
    # -- graceful degradation rather than silence.
    words = _tokenize("dalam Pasal 50 hunrf e meliputi")
    targets = _read_targets(words, current_pasal="55")
    assert targets == [{"pasal": "50", "ayat": None, "huruf": None}], targets


def check_external_reference():
    note = _match_external("diatur dalam ketentuan peraturan perundang-undangan.")
    assert note is not None and "peraturan perundang-undangan" in note


def check_external_reference_none_for_citation():
    assert _match_external("dimaksud dalam Pasal 55 ayat (1) huruf l") is None


CHECKS = [
    check_index_basic, check_index_ayat_and_huruf, check_index_stops_before_penjelasan,
    check_tokenize_paren_and_words, check_canon_repairs_real_keyword_typos,
    check_canon_leaves_far_typos_alone, check_unparen_repair,
    check_bare_ayat_list_same_pasal, check_cross_pasal_with_huruf,
    check_bare_pasal_no_ayat, check_pasal_direct_huruf_no_ayat,
    check_doubled_pasal_keyword, check_ayat_keyword_typo_same_pasal,
    check_huruf_typo_degrades_to_bare_pasal, check_external_reference,
    check_external_reference_none_for_citation,
]


def run():
    passed = 0
    for fn in CHECKS:
        try:
            fn()
            passed += 1
            print(f"  ok    {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(CHECKS)} passed")
    return len(CHECKS) - passed


if __name__ == "__main__":
    import sys
    sys.exit(1 if run() else 0)
