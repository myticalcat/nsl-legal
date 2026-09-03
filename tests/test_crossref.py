#!/usr/bin/env python3
"""Regression tests for cross-reference resolution. Every fixture below is a
real excerpt from data/txt/, copied verbatim (only re-indented for
readability), not a constructed example."""

from crossref import build_index

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


CHECKS = [check_index_basic, check_index_ayat_and_huruf, check_index_stops_before_penjelasan]


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
