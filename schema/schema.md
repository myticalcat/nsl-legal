# Deontic IR schema v0.1

Intermediate representation between Indonesian legal text and Z3. The neural
layer produces this; a deterministic compiler consumes it. That split is what
lets you report extraction accuracy and reasoning accuracy separately.

Every field below exists because a real provision in UU 1/2022 or Perda
Surabaya 7/2023 broke a simpler schema. Nothing here is speculative.

## Instrument

| Field | Purpose |
|---|---|
| `rank` | Position in the UU 12/2011 Pasal 7 hierarchy. UU = 3, Perda Prov = 6, Perda Kab/Kota = 7. Drives *lex superior*. |
| `jurisdiction` | Blocks nonsense pairings. Surabaya (kota) and Jabar (provinsi) levy disjoint tax types under HKPD, so they are never comparable to each other. |
| `in_force_from` | Prevents flagging repealed text. Minimal temporal handling; anything richer is out of scope. |

## Norm

### `norm_type`
`rate_constraint` | `obligation` | `prohibition` | `permission` | `delegation` | `definition`

Only `rate_constraint` and `delegation` are implemented. The others are
declared so the schema doesn't need breaking changes later.

### `bounds` — a **list**, not a scalar

Forced by **UU Pasal 58(2)**, which carries a floor and a ceiling in one
sentence: `paling rendah 40% ... dan paling tinggi 75%`. A single
`{op, value}` cannot represent it.

```json
"bounds": [
  {"op": ">=", "value": 0.40, "source_numeral": "4Oo/o", "source_words": "empat puluh persen", "ocr_recovered": true},
  {"op": "<=", "value": 0.75, "source_numeral": "75%",   "source_words": "tujuh puluh lima persen"}
]
```

`op` distinguishes ceiling / floor / exact. This is the single most important
field in the schema: **UU 58(1) `<= 10%` and Surabaya 27(1) `== 10%` are the
same number and are compliant precisely because one is a cap.** A system that
stores bare numbers cannot tell compliance from coincidence.

`source_numeral` + `source_words` implement the OCR recovery. Indonesian legal
drafting writes every figure twice — digits, then spelled out in parentheses.
The scanned UU corrupts `40%` into `4Oo/o`, but `empat puluh persen` survives
because it is words. Parse the parenthetical as authoritative, use the digits
as a checksum, flag mismatches. `ocr_recovered: true` marks where this fired.

### `applies_to` + `is_residual`

`applies_to` holds ontology category ids, resolved by **subsumption, not string
equality**. Forced by Surabaya 27(2)/(3), which split the statutory term
`karaoke` into `karaoke keluarga` and `karaoke dewasa`. Neither string appears
in the UU. Equality matching finds no overlap and silently reports no conflict.

`is_residual: true` marks a general fallback (UU 58(1), Surabaya 27(1)) that
applies only where no specific norm reaches the category. This is *lex
specialis* made machine-checkable, and it is the mechanism that produces the
panti pijat conflict: no specific national norm covers `panti_pijat`, so the
residual 10% cap springs back and collides with Surabaya's 50%.

### `delegation` / `delegated_scope`

Forced by **UU Pasal 58(4)**: `Tarif PBJT ... ditetapkan dengan Perda`.
Without this, the system flags every Perda rate that differs from a statutory
figure — which is every rate, since setting them is the Perda's job. This field
is what makes authorised divergence a first-class non-conflict rather than a
false positive. In evaluation these are your hard negatives.

### `open_textured_terms`

Forced by `dan sejenisnya` in Surabaya 27(3). Semantics matter here and the
first implementation got them wrong:

- An open-textured **tail does not undermine** the verdict for a category the
  drafter enumerated by name. `diskotek` is `diskotek`.
- It leaves the norm's **outer boundary** undetermined. That produces one
  `ABSTAIN` for the extension itself, referred to human review.

So the term attaches a `caveat` to enumerated categories and an `ABSTAIN`
only to categories reached solely through the extension.

### `extraction_confidence`

Populated by the neural layer. Routes low-confidence norms to review and lets
you report precision at varying coverage.

## Verdicts

| Verdict | Z3 result | Meaning |
|---|---|---|
| `CONFLICT` | UNSAT | No rate satisfies both. Unsat core cites the specific pasal. |
| `COMPLIANT` | SAT | A satisfying rate exists; the model is a concrete witness. |
| `ABSTAIN` | — | Applicability undecidable from text. Human review. |

`assert_and_track` is used throughout so the unsat core names provisions rather
than anonymous constraints. That is the explainability claim: the system does
not say "conflict detected", it says *Pasal 27(3) `== 50%` against Pasal 58(1)
`<= 10%`, and rank 7 yields to rank 3.*

## Known gaps (Limitations section material)

- Sanction provisions (`dikenai denda`) are filtered out, not modelled.
  Contrary-to-duty structures would otherwise register as false conflicts.
- Temporal reasoning is in-force / repealed only.
- Priority is a static rank; no defeasible derogation reasoning.
- The subsumption ontology is hand-built for one tax type.
