#!/usr/bin/env python3
"""Regression tests for cross-reference resolution. Every fixture below is a
real excerpt from data/txt/, copied verbatim (only re-indented for
readability), not a constructed example."""

from crossref import (
    build_index, resolve_references, _tokenize, _canon, _unparen_repair,
    _read_targets, _match_external,
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

# --- real excerpt: PERDA_NO_1_TAHUN_2024.txt lines 1890-1929 and 2012-2017
JAKARTA_P74_P80 = """
                                  Pasal 74

(1)   Jenis penyediaan/pelayanan barang dan/atau jasa yang
      merupakan objek Retribusi Jasa Usaha sebagaimana dimaksud
      dalam Pasal 66 ayat (1) huruf b meliputi:
      a. penyediaan tempat kegiatan usaha berupa pasar grosir,
         pertokoan, dan tempat kegiatan usaha lainnya;
      b. penyediaan tempat pelelangan ikan, ternak, hasil bumi, dan
         hasil hutan termasuk fasilitas lainnya dalam lingkungan
         tempat pelelangan;
      c. penyediaan tempat khusus parkir di luar badan jalan;
      d. penyediaan tempat penginapan/pesanggrahan/vila;
      e. pelayanan rumah pemotongan hewan ternak;
      f. pelayanan jasa kepelabuhanan;
      g. pelayanan tempat rekreasi, pariwisata, dan olahraga;
      h. pelayanan penyeberangan orang atau barang dengan
         menggunakan kendaraan di air;
      i. penjualan hasil produksi usaha Pemerintah Provinsi DKI
         Jakarta; dan
      j. pemanfaatan aset Pemerintah Provinsi DKI Jakarta yang tidak
         mengganggu penyelenggaraan tugas dan fungsi Satuan Kerja
         Perangkat Daerah dan/atau optimalisasi aset Pemerintah
         Provinsi DKI Jakarta dengan tidak mengubah status
         kepemilikan sesuai dengan ketentuan peraturan perundang-
         undangan.

(2)   Rincian objek Retribusi Jasa Usaha sebagaimana dimaksud pada
      ayat (1) tercantum dalam Lampiran yang merupakan bagian tidak
      terpisahkan dalam Peraturan Daerah ini.

(3)   Penyediaan atau pelayanan sebagaimana dimaksud pada ayat (1)
      disediakan atau diberikan oleh Pemerintah Provinsi DKI Jakarta
      berdasarkan jasa atau pelayanan yang diberikan dan kewenangan
      Provinsi DKI Jakarta sebagaimana diatur dalam ketentuan
      peraturan perundang-undangan.

(4)   Pelayanan sebagaimana dimaksud pada ayat (3) termasuk
      pelayanan yang diberikan oleh BLUD.

                                Pasal 80

Pelayanan jasa kepelabuhanan sebagaimana dimaksud dalam Pasal 74
ayat (l) huruf f merupakan pelayanan kepelabuhanan pada pelabuhan
yang disediakan, dimiliki, dan/atau dikelola oleh Pemerintah Provinsi
DKI Jakarta.
"""

# --- real excerpt: Perda Surabaya 7/2023 lines 4726-4794 (trimmed)
SURABAYA_P177 = """
                                Pasal 177

(1) Walikota dapat memberikan kemudahan perpajakan Daerah
    kepada Wajib Pajak, berupa :
   a. perpanjangan batas waktu pembayaran atau pelaporan
      Pajak; dan/atau
   b. pemberian fasilitas angsuran atau penundaan
      pembayaran Pajak terutang atau Utang Pajak.
(2) Perpanjangan batas waktu pembayaran atau pelaporan Pajak
    sebagaimana dimaksud pada ayat (1) huruf a, diberikan
    kepada Wajib Pajak yang mengalami keadaan kahar.
(3) Perpanjangan batas waktu pembayaran atau pelaporan Pajak
    sebagaimana dimaksud pada ayat (1) huruf a dapat diberikan
    Walikota secara jabatan.
(4) Pemberian fasilitas angsuran atau penundaan pembayaran
    Pajak terutang atau Utang Pajak sebagaimana dimaksud
    pada ayat (1) huruf b dilakukan dalam hal Wajib Pajak
    mengalami kesulitan likuiditas.
    (10) Keadaan kahar sebagaimana dimaksud pada ayal (2) dan
         ayat (4) meliputi:
        a. bencana alam;
        b. kebakaran.
"""

# --- real excerpt: UU_Nomor_1_Tahun_2022.txt (Pasal 199 area, line 4574)
AMENDMENT_FIXTURE = """
                                  Pasal 199

Undang-Undang Nomor 21 Tahun 2001 tentang Otonomi Khusus Provinsi Papua
sebagaimana telah beberapa kali diubah, terakhir dengan Undang-Undang
Nomor 2 Tahun 2021 tetap berlaku.
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
    assert _canon("ayal") == "ayat"
    assert _canon("alat") == "ayat"
    assert _canon("pajak") == "pajak"


def check_canon_leaves_far_typos_alone():
    assert _canon("hunrf") == "hunrf"


def check_unparen_repair():
    assert _unparen_repair("(l)") == "1"
    assert _unparen_repair("(2)") == "2"


def check_bare_ayat_list_same_pasal():
    words = _tokenize("pada ayat (l), ayat (2), dan ayat (3) ditetapkan")
    targets = _read_targets(words, current_pasal="58")
    assert targets == [
        {"pasal": "58", "ayat": "1", "huruf": None},
        {"pasal": "58", "ayat": "2", "huruf": None},
        {"pasal": "58", "ayat": "3", "huruf": None},
    ], targets


def check_cross_pasal_with_huruf():
    words = _tokenize("dalam Pasal 74 ayat (l) huruf f merupakan")
    targets = _read_targets(words, current_pasal="80")
    assert targets == [{"pasal": "74", "ayat": "1", "huruf": "f"}], targets


def check_bare_pasal_no_ayat():
    words = _tokenize("dalam Pasal 57 dengan tarif")
    targets = _read_targets(words, current_pasal="59")
    assert targets == [{"pasal": "57", "ayat": None, "huruf": None}], targets


def check_pasal_direct_huruf_no_ayat():
    words = _tokenize("dalam Pasal 50 huruf a meliputi")
    targets = _read_targets(words, current_pasal="51")
    assert targets == [{"pasal": "50", "ayat": None, "huruf": "a"}], targets


def check_doubled_pasal_keyword():
    words = _tokenize("dalam Pasal Pasal 44 huruf d meliputi")
    targets = _read_targets(words, current_pasal="48")
    assert targets == [{"pasal": "44", "ayat": None, "huruf": "d"}], targets


def check_ayat_keyword_typo_same_pasal():
    words = _tokenize("pada ayal (2) dan ayat (4) meliputi")
    targets = _read_targets(words, current_pasal="177")
    assert targets == [
        {"pasal": "177", "ayat": "2", "huruf": None},
        {"pasal": "177", "ayat": "4", "huruf": None},
    ], targets


def check_huruf_typo_degrades_to_bare_pasal():
    words = _tokenize("dalam Pasal 50 hunrf e meliputi")
    targets = _read_targets(words, current_pasal="55")
    assert targets == [{"pasal": "50", "ayat": None, "huruf": None}], targets


def check_external_reference():
    note = _match_external("diatur dalam ketentuan peraturan perundang-undangan.")
    assert note is not None and "peraturan perundang-undangan" in note


def check_external_reference_none_for_citation():
    assert _match_external("dimaksud dalam Pasal 55 ayat (1) huruf l") is None


def check_resolve_same_pasal_multi_target():
    idx = build_index(UU_P58)
    refs = resolve_references(idx["58"]["text"], idx, current_pasal="58")
    hits = [r for r in refs if r["status"] == "same_pasal"]
    assert len(hits) == 1, [r["status"] for r in refs]
    r = hits[0]
    assert [t["ayat"] for t in r["targets"]] == ["1", "2", "3"]
    assert all(t["pasal"] == "58" for t in r["targets"])
    assert all(t["text"] is None for t in r["targets"])
    assert r["needs_review"] is False


def check_resolve_cross_pasal_fetches_text():
    idx = build_index(UU_P58)
    refs = resolve_references(idx["59"]["text"], idx, current_pasal="59")
    cross = [r for r in refs if r["status"] == "cross_pasal"]
    assert len(cross) == 1, [r["status"] for r in refs]
    r = cross[0]
    assert r["targets"][0]["pasal"] == "58"
    assert r["targets"][0]["ayat"] == "4"
    assert "ditetapkan dengan Perda" in r["targets"][0]["text"]
    assert r["needs_review"] is False


def check_resolve_cross_pasal_with_corrupted_paren():
    idx = build_index(JAKARTA_P74_P80)
    refs = resolve_references(idx["80"]["text"], idx, current_pasal="80")
    cross = [r for r in refs if r["status"] == "cross_pasal"]
    assert len(cross) == 1, [r["status"] for r in refs]
    t = cross[0]["targets"][0]
    assert t["pasal"] == "74" and t["ayat"] == "1" and t["huruf"] == "f"
    assert "pelayanan jasa kepelabuhanan" in t["text"]


def check_resolve_external():
    idx = build_index(JAKARTA_P74_P80)
    refs = resolve_references(idx["74"]["ayat"]["3"]["text"], idx, current_pasal="74")
    ext = [r for r in refs if r["status"] == "external"]
    assert len(ext) == 1, [r["status"] for r in refs]
    assert "peraturan perundang-undangan" in ext[0]["note"]
    assert ext[0]["targets"] == []


def check_resolve_citation_before_external_not_swallowed():
    # Regression: Pasal 74 ayat (2)'s citation ('... ayat (1) tercantum
    # dalam Lampiran ...') names a real same-Pasal target BEFORE
    # mentioning something external in the same sentence. The external
    # check must not run until the citation parser has already come up
    # empty, or this same-Pasal ayat (1) reference gets swallowed as
    # "external" just because "Lampiran" appears later in the sentence.
    idx = build_index(JAKARTA_P74_P80)
    refs = resolve_references(idx["74"]["ayat"]["2"]["text"], idx, current_pasal="74")
    assert len(refs) == 1, [r["status"] for r in refs]
    assert refs[0]["status"] == "same_pasal"
    assert refs[0]["targets"] == [{"pasal": "74", "ayat": "1", "huruf": None, "text": None}]


def check_resolve_amendment_history():
    idx = build_index(AMENDMENT_FIXTURE)
    refs = resolve_references(idx["199"]["text"], idx, current_pasal="199")
    amend = [r for r in refs if r["status"] == "amendment_history"]
    assert len(amend) == 1, [r["status"] for r in refs]
    assert amend[0]["targets"] == []
    assert amend[0]["needs_review"] is False


def check_resolve_unfound_cross_pasal_needs_review():
    idx = build_index(UU_P58)
    refs = resolve_references(
        "Tarif ini sebagaimana dimaksud dalam Pasal 999 ayat (1) berlaku.",
        idx, current_pasal="58",
    )
    r = refs[0]
    assert r["targets"][0]["text"] is None
    assert r["needs_review"] is True


def check_resolve_surabaya_ayal_typo_same_pasal():
    idx = build_index(SURABAYA_P177)
    refs = resolve_references(idx["177"]["ayat"]["10"]["text"], idx, current_pasal="177")
    hits = [r for r in refs if r["status"] == "same_pasal"]
    assert len(hits) == 1, [r["status"] for r in refs]
    assert [t["ayat"] for t in hits[0]["targets"]] == ["2", "4"]


CHECKS = [
    check_index_basic, check_index_ayat_and_huruf, check_index_stops_before_penjelasan,
    check_tokenize_paren_and_words, check_canon_repairs_real_keyword_typos,
    check_canon_leaves_far_typos_alone, check_unparen_repair,
    check_bare_ayat_list_same_pasal, check_cross_pasal_with_huruf,
    check_bare_pasal_no_ayat, check_pasal_direct_huruf_no_ayat,
    check_doubled_pasal_keyword, check_ayat_keyword_typo_same_pasal,
    check_huruf_typo_degrades_to_bare_pasal, check_external_reference,
    check_external_reference_none_for_citation,
    check_resolve_same_pasal_multi_target, check_resolve_cross_pasal_fetches_text,
    check_resolve_cross_pasal_with_corrupted_paren, check_resolve_external,
    check_resolve_citation_before_external_not_swallowed,
    check_resolve_amendment_history, check_resolve_unfound_cross_pasal_needs_review,
    check_resolve_surabaya_ayal_typo_same_pasal,
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
