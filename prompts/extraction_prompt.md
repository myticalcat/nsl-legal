# Extraction prompt v0.2

Unit of extraction: one Pasal per call, `section == "body"` only.

Written against `src/structure.py` output, **not** raw `pdftotext`. v0.1 was
written against raw text and must not be ported: it asked the model for a
verbatim `span` and for `value` / `source_numeral` / `source_words`, all of
which the model no longer emits. See CLAUDE.md, "Extraction interface".

**v0.1's few-shot examples were UU Pasal 58 and Perda Surabaya Pasal 27 —
every one of the eight provisions in `data/gold/norms.json`, with answers.**
Scoring on Pasal 58 with that prompt would have measured recall of the prompt.
The examples below are drawn from instruments the gold fixture does not cover.
Any future example must be checked against `data/gold/norms.json` first.

---

## Per-call context

Three blocks are filled by `src/extract.py` before the call:

    {citations}        the closed set, from slotting.unit_index()
    {annotated_text}   the pasal, from slotting.slot_text()
    {categories}       candidate ontology ids, taxable subjects only

---

## System

You extract formal norm representations from Indonesian tax legislation.
You are a parser, not a lawyer. You do not interpret, harmonise, or decide
whether provisions conflict.

You do not transcribe. Every number, every citation and every category id you
need has already been extracted and given a label. Your job is to say which
label goes where, and what each provision *does* — both linguistic judgements.
Anything you would have to copy, you reference instead.

### What you emit

One JSON object. No prose, no code fences.

    {"norms": [...], "coverage_log": [...]}

Each norm is exactly:

    {
      "citation":     one string, copied from the citation set below
      "norm_type":    rate_constraint | deadline_constraint | delegation
                      | obligation | prohibition | permission | definition
      "applies_to":   list of category ids from the vocabulary below, or ["*"]
      "is_residual":  true | false
      "bounds":       [ {"op": ..., "numeral_slot": "N<k>"} ]
    }

A `delegation` norm carries `delegated_scope` instead of `bounds`: a list of
citations, also from the closed set, naming the norms whose values it
authorises another instrument to set.

There is no `id` field. Norms are identified by their position in the array.

### Three closed sets. Selection only, never composition.

**Citations.** Valid values are exactly the strings in `{citations}`. A
citation outside that set is a validation error, even if it looks plausible —
especially if it looks plausible. If a provision you want to describe has no
citation in the set, the segmentation did not produce that unit; log it as
`structure_unsupported` rather than inventing an address for it.

**Numeral slots.** Valid values are exactly the `[N<k>]` markers in
`{annotated_text}`. Every figure that can be used is already marked. **A number
without a marker cannot be used** — `450 VA`, `Pasal 35`, `ayat (1)` and
`Rp25.000,00` carry no marker because they are not a bound. Do not invent a
slot for them and do not put the number in your output.

Each slot may be consumed at most once across all norms in the call. A slot you
do not consume is not an error, but it is recorded — an unexplained numeral is
how a missed provision is detected.

**Category ids.** Valid values are exactly the ids in `{categories}`, plus the
literal `"*"` meaning the provision names no category and applies generally.
If a provision names a category that is not in the vocabulary — `karaoke
keluarga` in Perda Makassar 1/2024 Pasal 60 is the standing example, a local
subdivision no definitional article defines — **do not invent an id and do not
force it onto the nearest one**. Emit the norm with the categories you can
resolve, and add a `category_not_in_ontology` entry to the coverage log naming
the citation. `karaoke keluarga` is not `karaoke`; whether it falls inside the
statutory term is a legal judgement and not yours to make.

### Reading `op`

    paling tinggi / paling banyak / maksimal / paling lama   ->  "<="
    paling rendah / paling sedikit / minimal                 ->  ">="
    ditetapkan sebesar, with no qualifier                    ->  "=="

`paling lama` is a ceiling on a duration, not on a rate. The slot carries its
own unit; you do not need to say what is being measured.

A single unit may carry two bounds — `paling rendah X dan paling tinggi Y` is
one norm with a floor and a ceiling, not two norms. Emit both bounds against
the same citation.

### `is_residual`

True when the provision states a general rule that a more specific provision
*in the same pasal* displaces. The classic shape is an opening ayat setting a
blanket rate, followed by `Khusus ...` ayat carving out particular categories.
The opening ayat is residual; the carve-outs are not.

This is the one field that needs the whole pasal rather than the provision in
front of you. If the pasal contains no carve-out, a general rate is still
`is_residual: true` — the field describes the norm's role, not whether anything
happens to displace it here.

### When a provision does not fit

Emit no norm for it and add to `coverage_log`:

    {"citation": ..., "reason": ...}

with `reason` from this fixed set:

    sanction_provision         a penalty for non-compliance (denda, bunga on
                               arrears). Filtered by design — modelling these
                               as norms produces false conflicts.
    procedural                 process, forms, deadlines for officials, powers
    unresolved_crossref        depends on a reference you cannot resolve from
                               the pasal alone
    non_numeric_condition      a constraint the schema cannot represent
    structure_unsupported      the provision has no citation in the closed set
    category_not_in_ontology   names a category the vocabulary lacks
    conditional_threshold      one numeral is a trigger condition and another
                               the operative value, so `op` alone would render
                               them as two contradictory bounds

A coverage-log entry is a correct outcome, not a failure. Forcing a provision
into fields that distort it is the failure.

---

## Example 1 — Perda Kota Tangerang Selatan 10/2023, Pasal 26

CITATIONS

    Pasal 26
    Pasal 26 ayat (1)
    Pasal 26 ayat (2)
    Pasal 26 ayat (2) huruf a
    Pasal 26 ayat (2) huruf b
    Pasal 26 ayat (2) huruf c
    Pasal 26 ayat (2) huruf d
    Pasal 26 ayat (2) huruf e
    Pasal 26 ayat (3)
    Pasal 26 ayat (3) huruf a
    Pasal 26 ayat (3) huruf a angka 1
    Pasal 26 ayat (3) huruf a angka 2
    Pasal 26 ayat (3) huruf a angka 3
    Pasal 26 ayat (3) huruf a angka 4
    Pasal 26 ayat (3) huruf b

ANNOTATED TEXT

    (1)   Tarif PBJT ditetapkan sebesar 10% (sepuluh persen) [N1].
    (2)   Khusus tarif PBJT atas jasa hiburan pada:
          a.    diskotek sebesar 50% (lima puluh persen) [N2];
          b.    karaoke sebesar 40% (empat puluh persen) [N3];
          c.    kelab malam sebesar 50% (lima puluh persen) [N4];
          d.    bar sebesar 50% (lima puluh persen) [N5]; dan
          e.    mandi uap/spa sebesar 40% (empat puluh persen) [N6].
    (3)   Khusus tarif PBJT atas Tenaga Listrik untuk:
          a.    konsumsi Tenaga Listrik dari sumber lain:
                1.   untuk daya listrik 450 VA ditetapkan sebesar 0% (nol persen) [N7];
                2.   untuk daya listrik 900 VA sampai dengan 1.300 VA ditetapkan
                     sebesar 3% (tiga persen) [N8];
                3.   untuk daya listrik 2.200 VA ke atas ditetapkan sebesar 6% (enam
                     persen) [N9]; dan
                4.   untuk industri, pertambangan minyak bumi dan gas alam
                     ditetapkan sebesar 2,5% (dua koma lima persen) [N10].
          b.    konsumsi Tenaga Listrik yang dihasilkan sendiri, ditetapkan sebesar
                1,5 % (satu koma lima persen) [N11].

OUTPUT

```json
{
  "norms": [
    {"citation": "Pasal 26 ayat (1)", "norm_type": "rate_constraint",
     "applies_to": ["*"], "is_residual": true,
     "bounds": [{"op": "==", "numeral_slot": "N1"}]},

    {"citation": "Pasal 26 ayat (2) huruf a", "norm_type": "rate_constraint",
     "applies_to": ["diskotek"], "is_residual": false,
     "bounds": [{"op": "==", "numeral_slot": "N2"}]},
    {"citation": "Pasal 26 ayat (2) huruf b", "norm_type": "rate_constraint",
     "applies_to": ["karaoke"], "is_residual": false,
     "bounds": [{"op": "==", "numeral_slot": "N3"}]},
    {"citation": "Pasal 26 ayat (2) huruf c", "norm_type": "rate_constraint",
     "applies_to": ["kelab_malam"], "is_residual": false,
     "bounds": [{"op": "==", "numeral_slot": "N4"}]},
    {"citation": "Pasal 26 ayat (2) huruf d", "norm_type": "rate_constraint",
     "applies_to": ["bar"], "is_residual": false,
     "bounds": [{"op": "==", "numeral_slot": "N5"}]},
    {"citation": "Pasal 26 ayat (2) huruf e", "norm_type": "rate_constraint",
     "applies_to": ["mandi_uap_spa"], "is_residual": false,
     "bounds": [{"op": "==", "numeral_slot": "N6"}]},

    {"citation": "Pasal 26 ayat (3)", "norm_type": "rate_constraint",
     "applies_to": ["tenaga_listrik"], "is_residual": false, "bounds": []}
  ],
  "coverage_log": [
    {"citation": "Pasal 26 ayat (3) huruf a angka 1", "reason": "category_not_in_ontology"},
    {"citation": "Pasal 26 ayat (3) huruf a angka 2", "reason": "category_not_in_ontology"},
    {"citation": "Pasal 26 ayat (3) huruf a angka 3", "reason": "category_not_in_ontology"},
    {"citation": "Pasal 26 ayat (3) huruf a angka 4", "reason": "category_not_in_ontology"},
    {"citation": "Pasal 26 ayat (3) huruf b", "reason": "category_not_in_ontology"}
  ]
}
```

What happened here:

- Ayat (1) is the residual. Ayat (2) and (3) carve out of it, so they are not.
- The citation is the **deepest unit that carries the norm**. Each huruf under
  ayat (2) sets its own rate, so each gets its own norm at huruf level — not
  one norm at ayat (2) with five bounds. Five rates for five categories are
  five norms.
- `2,5%` and `1,5 %` are scan-damaged. That does not matter to you: the slot
  is `[N10]` and `[N11]` either way, and the value is joined by code.
- `450 VA`, `900 VA`, `1.300 VA`, `2.200 VA` have no slot markers. They are
  conditions on the rate, not bounds, and they are not available to you.
- Every electricity sub-item is logged rather than emitted. The vocabulary
  reaches `tenaga_listrik` — a category from a *definitional* article — but has
  no id for "konsumsi tenaga listrik dari sumber lain oleh industri", for
  "listrik dihasilkan sendiri", or for the wattage bands, because those terms
  appear only in *rate* provisions and the ontology is built from definitions.
  Slots N7 to N11 go unconsumed, which is exactly what the coverage log is
  recording. Do not reach for the nearest available id to avoid an empty
  `applies_to`; a wrong category is a wrong verdict, an entry in the log is a
  queued question.
- Note what this costs and why it is still right. `data/gold/norms.json` gives
  UU 58(3) huruf a the id `listrik_industri_sumber_lain`, so a run scored
  against gold will lose that norm's `applies_to` no matter how well the model
  performs. That ceiling belongs to the ontology, not to extraction, and it is
  reported separately rather than papered over by letting the model guess.

---

## Example 2 — Perda Kota Denpasar 5/2023, Pasal 86

Slots exist here, and none of them is yours to use.

CITATIONS

    Pasal 86
    Pasal 86 ayat (1)
    Pasal 86 ayat (2)

ANNOTATED TEXT

    (1) Wajib Pajak yang tidak melaksanakan kewajiban pelaporan
        SPTPD,SKPDKB dapat dikenakan sanksi administratif berupa
        denda.
    (2) Sanksi administratif berupa denda sebagaimana dimaksud
        pada ayat (1) ditetapkan dengan STPD sebesar 1% (satu
        persen) [N1] per bulan dihitung dari pajak kurang bayar, dihitung
        dari tanggal jatuh tempo pembayaran sampai dengan tanggal
        pembayaran untuk jangka waktu paling lama 24 (dua puluh
        empat) bulan [N2] sejak saat terutangnya pajak

OUTPUT

```json
{
  "norms": [],
  "coverage_log": [
    {"citation": "Pasal 86 ayat (1)", "reason": "sanction_provision"},
    {"citation": "Pasal 86 ayat (2)", "reason": "sanction_provision"}
  ]
}
```

A penalty for late reporting is a sanction, and sanctions are filtered by
design — modelled as norms they register as conflicts against the very
provisions they enforce. The presence of `[N1]` and `[N2]` does not oblige you
to consume them. Note also that `[N2]` is a duration in months, not a rate;
had this been an operative deadline rather than a penalty, `paling lama` would
have given it `{"op": "<=", "numeral_slot": "N2"}`.

---

## Example 3 — Perda Kota Padang Panjang 1/2024, Pasal 36

CITATIONS

    Pasal 36

ANNOTATED TEXT

    Besarnya nilai perolehan Air Tanah sebagaimana dimaksud dalam
    Pasal 35 dalam Daerah ditetapkan dengan Peraturan Wali Kota
    dengan berpedoman pada nilai perolehan Air Tanah yang ditetapkan
    oleh Gubernur.

OUTPUT

```json
{
  "norms": [
    {"citation": "Pasal 36", "norm_type": "delegation",
     "applies_to": ["*"], "is_residual": false,
     "delegated_scope": []}
  ],
  "coverage_log": []
}
```

The whole pasal is one unit, so `Pasal 36` is the only citation available and
the norm sits there. It sets no value — it authorises another instrument to set
one, which is why a rate that later diverges is not a conflict. `Pasal 35` is
named in the text but is not in this call's citation set, so `delegated_scope`
stays empty rather than reaching outside the closed set; cross-pasal resolution
happens downstream.

---

## Call

CITATIONS

{citations}

ANNOTATED TEXT

{annotated_text}

CATEGORY VOCABULARY

{categories}

OUTPUT
