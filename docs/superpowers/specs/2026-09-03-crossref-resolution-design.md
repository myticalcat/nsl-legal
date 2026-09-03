# Cross-reference resolution — design spec

Date: 2026-09-03
Status: approved for implementation
Module: `src/crossref.py` (new)

## Problem

Indonesian legal drafting is saturated with internal citations —
`sebagaimana dimaksud pada ayat (1)`, `sebagaimana dimaksud dalam Pasal 55
ayat (1) huruf l`, `sebagaimana diatur dalam Peraturan Daerah ini` — and a
norm extracted from a single Pasal in isolation is often meaningless without
resolving them. CLAUDE.md lists this as open-work item #1 and "upstream of
everything": the extraction unit is one Pasal, but a norm's `applies_to`
categories are sometimes only nameable by reading a *different* Pasal that
the current one cites by reference (the panti pijat case: Pasal 58 only
makes sense against the enumeration in Pasal 55).

## Survey findings that shaped this design

A corpus-wide survey (before this spec) found:

- `sebagaimana` occurs 1,297 times across the four documents. Five shapes —
  bare `ayat (N)`, `Pasal N ayat (M)`, `Pasal N ayat (M) huruf X`, bare
  `ayat (N) huruf X`, bare `Pasal N` — cover 92% of occurrences.
- `kecuali sebagaimana diatur dalam Pasal N` does **not** occur anywhere in
  this corpus. Every `kecuali` (38 total, manually checked) introduces a
  substantive exception, never a citation. Exception clauses are out of
  scope for this module.
- Structural markers (`Pasal`/`ayat`/`huruf` numbers) suffer the same
  scanner-glyph corruption `ocr_numerals.py` already handles for
  percentages — `Pasal L4`, `Pasa1 47`, `ayat (21`, `ayal (2)`, doubled
  words (`Pasal Pasal 44`, `pada pada ayat (7)`) — and this corruption
  appears in **all four** documents, not just UU 1/2022 as CLAUDE.md's
  corpus notes currently claim. That note should be revisited separately;
  this spec does not change CLAUDE.md.
- All four documents end with a `PENJELASAN` (elucidation) appendix that
  repeats every Pasal number as a stub (`Pasal 1 Cukup jelas. Pasal 2 Cukup
  jelas...`). Any structural index must stop before this section or the
  stubs silently overwrite the real operative-text spans.
- No cross-instrument internal citation exists anywhere in the corpus
  (a Perda never cites a UU by internal Pasal number, only by statute
  name) — resolution is single-instrument scoped.
- `sebagaimana telah diubah` (and variants) is amendment-history framing,
  not a provision citation, and is classified separately.

## Decisions made in brainstorming

1. **Pipeline placement: pre-extraction context injection.** `crossref.py`
   runs before a Pasal is handed to the LLM. It resolves cross-Pasal
   citations and hands their text to the (not-yet-built) extraction runner
   as extra prompt context — this is what lets the LLM correctly determine
   `applies_to`/`is_residual` for a norm whose applicability is defined
   elsewhere. Post-extraction norm-ID linking (e.g. auto-populating
   `delegated_scope`) is explicitly deferred — not built in this pass.
2. **`crossref.py` owns structural segmentation.** Nothing else in the
   codebase splits a document into Pasal/ayat/huruf spans; building that
   index is the resolver's own prerequisite, not a separate module.
3. **Every reference is fully resolved, but text is only fetched for
   cross-Pasal targets.** A bare `ayat (2)` still resolves to an explicit
   `{pasal: <current>, ayat: "2"}` target — nothing is left implicit — but
   no text is fetched for it, since the LLM already sees the whole current
   Pasal and fetching would just duplicate it.
4. **Reuse `ocr_numerals.py`'s `GLYPH` table** for digit repair in
   structural markers, rather than building a second glyph-confusion table
   for the same underlying phenomenon.
5. **Citation grammar parsed with an anchor regex + small token parser**,
   not a growing regex alternation. The survey's regex-cascade approach
   plateaued at 47 shapes and still missed real cases; a token parser over
   a bounded span handles arbitrary-depth `dan`/`atau` lists and is the
   natural place to hook in digit repair.

## Public API

```python
def build_index(document_text: str) -> DocIndex:
    """Walk one document's operative text (stopping before any PENJELASAN /
    'PASAL DEMI PASAL' appendix) and return a Pasal -> ayat -> huruf lookup
    of text spans. Single-instrument scoped: one index per document."""

def resolve_references(pasal_text: str, index: DocIndex, current_pasal: str) -> list[Reference]:
    """Find every 'sebagaimana ...' occurrence in one Pasal's text and
    resolve each to a classified target. Cross-Pasal targets are looked up
    against `index` and have their text attached; same-Pasal targets are
    resolved but left without fetched text."""
```

### `DocIndex` shape

```python
{
  "58": {
    "start": int, "end": int, "text": str,
    "ayat": {
      "1": {
        "start": int, "end": int, "text": str,
        "huruf": {"a": {"start": int, "end": int, "text": str}, ...}
      },
      ...
    }
  },
  ...
}
```
Keyed by Pasal number as a string (post-repair, so a corrupted marker and
its citations agree on the same key even if that key isn't the "true"
number — consistency between index and citation matters more than
recovering ground truth when both sides go through the same repair).

### `Reference` shape

```python
{
  "phrase": str,             # the matched 'sebagaimana ...' span, verbatim
  "start": int, "end": int,  # offsets into pasal_text
  "verb": "dimaksud" | "diatur" | "tercantum" | "ditetapkan" | "dimaksudkan",
  "status": "same_pasal" | "cross_pasal" | "external" | "unresolved" | "amendment_history",
  "targets": [
    {"pasal": str, "ayat": str | None, "huruf": str | None, "text": str | None}
  ],
  "needs_review": bool,
  "note": str | None,        # human-readable reason for external/unresolved
}
```

`targets` has more than one entry for `dan`/`atau` lists (e.g. `ayat (1),
ayat (2), dan ayat (3)`). Only `cross_pasal` targets carry non-`None`
`text`.

## Parsing approach

1. A regex locates each `sebagaimana <verb>` occurrence and captures a
   bounded span following it (up to the next sentence-ish boundary).
2. A small hand-written token parser walks that span's words (`Pasal`,
   `ayat`, `huruf`, `angka`, numbers, `dan`/`atau`), building the target
   list. Numbers pass through `ocr_numerals.py`'s `GLYPH.translate()`
   before being read.
3. A digit run inside `(` is accepted as the ayat/huruf number up to any
   clause boundary (whitespace, comma, `dan`, `huruf`) **without requiring
   a literal closing `)`** — this tolerates the observed
   `ayat (21` / `ayat (2\` corruption without having to guess whether the
   trailing character is corruption or a genuine second digit.
4. `verb == "diubah"` classifies as `amendment_history` and is not resolved
   further, regardless of what follows it (bare, or naming an amending
   regulation) — the survey found no case of `diubah` citing a
   Pasal/ayat/huruf target in this corpus.
5. Named external targets (`Undang-Undang Dasar`, `ketentuan peraturan
   perundang-undangan`, `peraturan perundang-undangan`, a differently-named
   statute) classify as `external`, `targets: []`, with `note` naming what
   was cited.
6. Anything left — verb present, no parseable target, not external, not
   amendment-history — classifies as `unresolved`, `needs_review: True`,
   `note` holding the raw phrase. This is a deliberate ABSTAIN-style
   fallback: never guess a target that isn't there.

## Error handling

- **PENJELASAN boundary**: `build_index` stops at the first line matching
  a heading pattern for the elucidation appendix, so its repeated Pasal
  stubs never overwrite operative-text spans.
- **Corrupted structural markers**: handled by GLYPH-table digit repair
  (§ Parsing approach, step 2) and tolerant paren-matching (step 3). When
  repair still leaves an ambiguous or unfindable target (e.g. the named
  Pasal doesn't exist in the index), the reference becomes `unresolved`,
  never a best-guess.
- **Doubled words** (`Pasal Pasal 44`, `pada pada ayat (7)`): the token
  parser skips a repeated keyword rather than treating it as a second,
  nonsensical target.

## Out of scope for this pass

- Post-extraction norm-ID linking (auto-populating `delegated_scope` or
  similar fields from resolved references) — deferred; `resolve_references`
  produces citation targets, not norm IDs.
- Exception-clause (`kecuali ...`) modeling — no such citation form exists
  in this corpus.
- Cross-instrument citation resolution — no evidence any exists.
- The extraction runner itself (open-work #2) — this module only provides
  what that runner will consume; assembling the augmented prompt is that
  runner's job, not `crossref.py`'s.
- Revising CLAUDE.md's corpus notes about which documents are
  OCR-damaged — flagged as a finding, not addressed here.

## Testing plan

New `tests/test_crossref.py`, following the existing suite's convention:
real strings pulled from the corpus, run as a plain script (not pytest),
each case a `(input, expected)` pair. Planned cases:

- `UU-58-4`'s multi-target same-Pasal list (`ayat (1), ayat (2), dan ayat
  (3)`) → three targets, all `status: same_pasal`, current Pasal = 58.
- A genuine cross-Pasal citation (`Pasal N ayat (M) huruf X` naming a
  different Pasal than current) → `status: cross_pasal`, `text` populated
  from a `build_index` fixture.
- Corrupted markers: `ayat (21`, `Pasal L4`, `ayal (2)` → correctly
  repaired and resolved.
- Doubled words: `Pasal Pasal 44`, `dimaksud pada pada ayat (7)`.
- An external reference (`ketentuan peraturan perundang-undangan`) →
  `status: external`, `targets: []`.
- An amendment-history phrase (`sebagaimana telah diubah beberapa kali`) →
  `status: amendment_history`.
- A `PENJELASAN`-boundary regression: a Pasal appearing both in the
  operative text and again in the elucidation appendix must resolve to the
  operative-text span, not the `Cukup jelas` stub.

## Note on environment

This project directory is not a git repository (verified: `git status`
reports `fatal: not a git repository`), so this spec is saved to disk only
and has not been committed.
