# Neurosymbolic legal conflict detection — Indonesian regulatory hierarchy

Detect conflicts between national law (UU) and regional regulation (Perda) by
extracting deontic norms with an LLM and reasoning over them with Z3.

Target: conference paper (JURIX / NLLP / ICAIL). ~8 week runway.

## Architecture

    PDF → text extraction (per-page method recorded)
        → deterministic structural segmentation (pasal/ayat/huruf/angka)
        → prefilter → OCR numeral recovery → slotting
        → LLM extraction → norm IR
        → ontology grounding → Z3 → {CONFLICT, COMPLIANT, ABSTAIN}

Exactly one stage is neural (extraction). Everything downstream is
deterministic, and everything upstream is too. This is deliberate: it lets
extraction accuracy and reasoning accuracy be measured separately. **Do not
move logic into the LLM stage.**

Findings, measurements and dead ends live in `docs/FINDINGS.md`. This file
holds decisions, status, and what to do next.

## Status — read before assuming anything works

| Component | State |
|---|---|
| `src/ocr_numerals.py` | working, tested; rates and durations, 2,104 pairs corpus-wide |
| `src/extract_text.py` | working, run over all 34 raw PDFs |
| `src/structure.py` | working, 6,411 pasal, 8/8 gold citations resolve |
| `src/slotting.py` | working, demo runs through real segmentation, not wired to an API |
| `src/detect.py` | working, 21 categories, 2 conflicts found |
| `src/calibrate_ocr.py` | working, tesseract baseline passes the 2-page gate |
| `data/gold/norms.json` | **hand-written fixture**, 8 norms |
| `data/gold/ontology.json` | **hand-written fixture**, 23 categories |
| `prompts/extraction_prompt.md` | written, **never executed** |
| `src/ontology_build.py` | working, 12/12 on UU Pasal 55, 8/8 gold; 86% cross-instrument recall |
| `src/prefilter.py` | working, run over all 34 documents; 1,340/3,614 body pasal selected |
| extraction runner | does not exist |
| cross-reference resolver | exists but broken; see open work 2 |
| coverage log | does not exist |
| JSON Schema + load validation | does not exist |

The entire neural half is currently a human reading PDFs. Everything
downstream of extraction is real and tested. The pipeline has never run end to
end on an unseen document.

## Gold fixtures vs generated output — do not confuse these

    data/gold/norms.json      hand-written, FROZEN, never overwrite
    data/gold/ontology.json   hand-written, FROZEN, never overwrite
    out/norms.json            extractor output, regenerated each run
    out/ontology.json         builder output, regenerated each run

The two files are structurally identical, so only the directory distinguishes
them. Evaluation compares `out/` against `data/gold/`. If a pipeline stage
writes into `data/gold/`, the ground truth is destroyed and the comparison
silently becomes "does the extractor agree with itself", which always passes.

`data/extracted/` is also regenerated, despite living under `data/` — it is
derived from `data/raw/` by `src/extract_text.py` and can be rebuilt at any
time. It sits under `data/` because it is corpus input to the pipeline, not an
artefact scored against gold. Nothing in `data/` except `data/gold/` is frozen.

`data/raw/`, `data/extracted/` and `data/structured/` are all gitignored, so a
fresh clone has none of them. After restoring `data/raw/`, run
`python3 src/extract_text.py` (~10 min, most of it OCR) then
`python3 src/structure.py` (seconds).

The ontology is a special case: it legitimately grows, because each new Perda
introduces local subdivisions (`karaoke_keluarga`) absent from earlier
documents. Split it — the twelve statutory categories from UU Pasal 55 are
frozen and scoreable; new local categories land in `pending_review` for human
confirmation. Score the builder on statutory recovery only.

## Layout

    src/                  pipeline modules
    data/raw/             source PDFs, batch-a|b|c
    data/txt/             pdftotext -layout output for the original four documents
    data/extracted/       src/extract_text.py output, one JSON per PDF
    data/structured/      src/structure.py output, pasal/ayat/huruf/angka tree
    data/gold/            frozen hand-annotated ground truth
    prompts/              extraction prompt with real few-shot examples
    schema/schema.md      IR field documentation, each field justified by a provision
    tests/                regression suite, every case a real string from a scan
    docs/FINDINGS.md      lab notebook: measurements, results, dead ends
    out/                  all pipeline output, regenerated

## Decisions already made — do not relitigate

- **IR is an intermediate representation**, not information retrieval. JSON norm
  objects. The LLM never emits SMT-LIB.
- **Extraction unit is one Pasal**, not one ayat. `is_residual` cannot be set
  correctly without sibling context.
- **The model never transcribes numbers, citations, or text.** It emits
  `{citation, norm_type, applies_to, is_residual, op, numeral_slot}` and
  nothing else. Values join from the slot table; citations are *selected* from
  the closed set present in the pasal object; offsets are copied from the unit
  by code. An LLM shown `4Oo/o` will silently "correct" it to `40%` and destroy
  provenance, and one shown a citation will happily compose a plausible one
  that does not exist. Anything the model can only copy, it should instead
  reference.
- **Spans are retired; provenance is structural. Resolved 2026-09-09.** The
  model emits no text at all. It selects a `citation` from the closed set of
  units in the pasal and a `numeral_slot` from the table, and code checks that
  the slot lies inside the cited unit. This replaces the literal span check and
  is strictly stronger: a bound filed under the wrong ayat fails it, where a
  substring test passes, because the text is a real substring of the pasal
  either way. Surveyed before deciding — **857 of 857 numeral slots in body
  text fall inside exactly one addressable unit, none crossing a boundary**, so
  the assertion is safe to make hard. No provision in the corpus needs a
  sub-clause named *within* an ayat: of 19,901 body leaf units only 34 carry
  more than one numeral pair, 24 of those are the single recurring PBB-P2 base
  provision (one norm, two bounds), and every apparent multi-norm unit is a
  segmentation defect whose boundaries a span could not have fixed anyway.
  `span_not_verbatim` and `slotting.strip_slots` are gone; the new reason code
  is `slot_outside_cited_unit`. `slotting.canonical` **survives** with a
  different job — see below.
- **Containment is against the deepest *containing* unit, not the deepest
  leaf.** A numeral often sits in an ayat's chapeau above a huruf list: 379 of
  the 857 slots resolve to an ayat that has huruf children, and 128 to a bare
  pasal. Checking leaves only would report 58 of them as orphaned when they are
  correctly placed. `slotting.unit_index` therefore returns every level, and
  citing a parent of the slot's unit is valid; only citing a sibling is an
  error.
- **One norm can carry two slots in different roles, and it is not a span
  problem.** Perwali Surabaya 33/2024 Pasal 93(2)(c)(1): NJOP that
  `meningkat lebih dari 50%` may be given `pengurangan sebesar 50%`. The first
  numeral is a trigger threshold, the second the relief value, and `op` alone
  makes them look like two contradictory bounds. One occurrence in 857 slots,
  so it goes to the coverage log as `conditional_threshold` rather than
  earning a schema field. Revisit if the full run turns up more.
- **`bounds` is a list.** UU Pasal 58(2) carries a floor and a ceiling in one
  sentence.
- **The two channels are not equally reliable, and the reason is structural.**
  78.3% of single-character digit corruptions parse to a valid but *different*
  number; 0 of 1,274 word corruptions land on another vocabulary word, because
  the numeral vocabulary has minimum pairwise edit distance 2. The spelled-out
  channel is error-detecting and the digit channel is not. This justifies
  "prefer the channel that needed no repair" — but **not** "always prefer
  words": `liga` is one edit from both `lima` (5) and `tiga` (3), and in the
  one real occurrence the digits are clean and right. An ambiguous repair
  returns None and lets the other channel decide.
- **Iterate `VOCAB_ORDER`, never `VOCAB`.** Fixed 2026-09-09: `_snap` and
  `_segment` iterated a `set`, so the winner depended on per-process string
  hashing — `_snap('liga')` gave `lima` or `tiga` by PYTHONHASHSEED, making
  `parse_words` and every corpus total irreproducible. Sorted tuple. Anything
  iterating the vocabulary must use it.
- **A percentage may exceed 100.** Corrected 2026-09-08: `parse_digits` and
  `parse_words` rejected anything over 100 as a mangled `%`, which was true of
  the original four documents and false of the corpus. A tax-inclusive base is
  divided by `110%` to recover the pre-tax figure (Perwal Jogja 51/2024), and a
  room-class tariff is capped at `125%` of the class below (Perda Tangerang
  1/2025). Both channels agree on these; the guard was discarding correct data.
  `CEILING` is now a backstop against glued digits, not a claim about rates.
- **`op` matters more than `value`.** UU 58(1) `<= 10%` and Perda 27(1)
  `== 10%` are the same number and compliant precisely because one is a cap.
- **`is_residual` implements lex specialis.** A general norm is displaced
  wherever a specific one reaches the category. This is what produces the
  panti pijat conflict.
- **Delegation is a norm type.** UU 58(4) authorises Perda to set rates, so
  divergence within bounds is not a conflict. Without this, every rate is a
  false positive.
- **Abstain is a first-class verdict**, not a failure. Open-textured terms
  (`dan sejenisnya`) are referred, not guessed. Note the semantics: a vague
  tail does not undermine categories the drafter named explicitly; it only
  leaves the norm's outer boundary undetermined.
- **Pipeline ordering: definitions before rates.** Categories live in
  definitional articles (UU Pasal 55, Perda Pasal 25); constraints live in rate
  articles (Pasal 58, Pasal 27). The ontology builder must run before the norm
  extractor, because `applies_to` can only reference ids that already exist.
  This was learned the hard way: the hand-built ontology was drawn from rate
  provisions alone and silently missed ten of the twelve statutory categories.
- **Only `rate_constraint` is implemented, and the corpus justifies that.**
  `obligation`, `prohibition`, and `permission` are declared in the schema and
  ignored by the compiler. `dilarang` occurs 9 times across the original four
  documents (~1,100 pages), every one a confidentiality duty on officials.
  **Corrected 2026-09-09 on the full corpus: 32 occurrences across 34
  documents, in four classes** — 21 confidentiality, 6 `Pemungutan Pajak
  dilarang diborongkan`, 3 fiscal-discipline rules on Daerah, and 2 of
  `Pemerintah Daerah dilarang memungut Pajak selain jenis Pajak sebagaimana
  dimaksud dalam Pasal 4 ayat (1)`. So the order of magnitude holds — 32
  against 979 rate-marker pasal, and the numeric focus is still justified — but
  **do not write that every instance is a confidentiality duty.** The last
  class is a genuine counterexample: it is in UU 1/2022 Pasal 6(1) and copied
  into Perda Batam 1/2024 Pasal 6(1), so it is a prohibition with a national
  counterpart at a higher rank, and it is decidable against the closed list of
  permitted tax types in UU Pasal 4(1) with no numerals at all. Worth one
  sentence in the paper as the shape a non-numeric conflict would take.

  Note the *applicability* reasoning is already general: subsumption, lex
  specialis, and delegation are not numeric. Only the constraint language is.
  Extending to O/F is a second constraint kind (booleans plus
  `Not(And(Obliged, Forbidden))`) reusing `applicable()` unchanged; the real
  cost is agent/action alignment (`pelaku usaha` vs `setiap orang`), not the
  encoding.
- **`wajib` is overwhelmingly noun, not modal.** *Wajib Pajak* and *Wajib
  Retribusi* are defined terms meaning "taxpayer". Corrected 2026-09-09: this
  read "two thirds", from Surabaya 221/326 and UU 50/105, but those
  denominators were substring counts that also caught `kewajiban`,
  `diwajibkan` and `mewajibkan`. Against the word `wajib` it is Surabaya
  225/289 and UU 50/80; over body pasal corpus-wide, **3,514 of 3,796, or 93%**.
  A deontic lexicon matching bare `wajib` produces thousands of phantom
  obligations. The exclusion is mandatory in both the prefilter and the
  extraction prompt, and it needs four rules, not one:
  the defined-term heads including every tax type (`Wajib PAB`, `Wajib PBB-P2`,
  `Wajib PAT`, `Wajib PKB`, `Wajib PBJT`, `Wajib BBNKB`); `kontribusi wajib`,
  the adjective in the statutory definition of a tax, which opens Pasal 1 of
  nearly every instrument; `Urusan Pemerintahan wajib`, a defined term from
  UU 23/2014; and `wajib` followed immediately by a comma, which is the heading
  `Subjek, Wajib, dan Objek Pajak` splitting the term. A colon is the opposite
  case and must be kept — `wajib: a. meminta ...` introduces a list of duties.
  Matching on capitalisation instead was measured and is worse: 194 noun
  occurrences are lowercase in the source, against 7 capitalised ones with a
  head outside the list.
- **`slotting.canonical` is a normaliser, not a verifier.** It was built to
  make span checking survive layout artifacts; spans are gone, but the function
  is kept because text lifted *out* of a unit still has to have the page layout
  collapsed. An ontology label wrapped as `perundang-\n     undangan` and a
  review-queue excerpt broken mid-sentence otherwise get two different forms
  depending on where the line broke. It collapses whitespace, joins a line
  break inside a hyphenated compound, and drops soft hyphens (157 in the
  corpus). The hyphen itself is kept: all 314 hyphen-at-break cases are real
  compounds (`perundang-undangan`, `semata-mata`, `PBB-P2`) and none is a
  typeset word split, so dropping it would corrupt every one. Do not fold
  furniture stripping into this function -- a caller comparing two normalised
  strings needs the difference between them to be real, and `TarifPBJT` and
  `4Oo/o` must survive exactly as the page had them.
- **Residual page furniture is the extractor's problem, not the segmenter's.**
  Furniture that changes the tree shape must die before segmentation: the
  catchword and stamp between `Pasal 3 ayat (1)` and `ayat (2)` in PP 35/2023
  cost 416 ayat corpus-wide until stripped, and by IR time the provision is
  simply absent. Furniture that merely sits inside a correctly segmented unit
  is different -- the extraction stage is already neural and already tolerates
  `TarifPBJT` and `4Oo/o`, so the ~89 remaining boilerplate leaks are noise it
  can absorb. Strip what breaks structure; defer what only adds noise. This
  keeps the one-neural-stage property intact rather than spending a second
  model on 89 occurrences. The original plan was for this to surface as
  `span_not_verbatim`; with spans retired it does not, and the survey shows the
  guard was watching the wrong door anyway. Embedded furniture does not
  manifest as a quotation mismatch -- it manifests as *boundary* damage, as in
  UU 1/2022 Pasal 40(4) where `REPUBLIK INOONESIA` pushed `(5)` off the line
  start and ayat (4) absorbed its sibling. That is caught by the
  unexplained-numeral recall check and by the parser warnings, both of which
  are louder and closer to the actual defect.
- **Prefilter before the API, always.** Only 27% of body pasal carry a bound
  marker (`paling tinggi`, `paling rendah`, `paling lama`, `paling sedikit`,
  `paling banyak`, `ditetapkan sebesar`, `ditetapkan dengan`) — 979 of 3,614.
  Corrected 2026-09-09: the per-document figures here read 51/185 in UU 1/2022
  and 55/197 in Perda Surabaya, measured with a literal single space. Matching
  `\s+` over layout-collapsed text gives 52 and 59; the extra five are markers
  split across a line break, which the old regex could not see. Adding numeral
  pairs and modals brings the full extract bucket to 1,137 of 3,614, or 31%.
  Skipped pasal are **logged with a reason, never silently dropped** — the skip
  log is a recall check, and an unexplained numeral in a skipped pasal is a bug.
  Measured: zero of 2,477 skipped pasal contain an unclaimed percentage, so
  that guard currently never fires, which is the check passing.
- **Match markers strictly. Fuzzy matching is a measured dead end.** At edit
  distance 1, `lama` collides with `lima`, `sama` and `nama` for 1,038 false
  hits and `ditetapkan` with `diterapkan` (22, a real word), against roughly
  ten genuinely damaged markers corpus-wide. Tolerance is also unnecessary: a
  provision stating a rate states the figure twice, so a damaged-marker pasal
  is selected by the numeral channel anyway. Same lesson as the edit-distance
  page-edge clustering — do not re-try it.
- **Schema does not self-modify.** Unrepresentable provisions go to a coverage
  log with a reason code. The ontology may grow, but new subsumption edges land
  in `pending_review` before going live.
- **Structure is segmented deterministically, and it is a list.** Pasal
  occurrences are never keyed by number: an instrument states `Pasal 1` in its
  operative text and again in its penjelasan, and `crossref.build_index` keys
  by number, so it silently drops one -- 94 of 232 pasal in Perda Sibolga
  1/2024, 74 of 181 in Lubuk Linggau. `src/structure.py` records duplicates
  with an occurrence index and a warning. Three rules earn their keep:
  sections come from *pasal-numbering restart*, not heading text, because
  `PENJELASAN` does not survive OCR in those same two documents; a sub-item
  list is accepted only as a *validated run* opening at `a` or `1`; and a
  `LAMPIRAN` heading always ends a pasal, because a lampiran has no pasal of
  its own and its tariff rows otherwise nest inside the pasal above it. That
  last rule alone cut spurious units from 40,404 to 22,315 and colliding
  citations from 35% to 6%, with the pasal count unchanged at 6,411.
- **A backwards jump in pasal numbering is not automatically a new section.**
  Section restarts in this corpus drop by 122 or more; genuine drafting
  defects drop by 2. Perda Bau-Bau 1/2024 numbers 18, 19, 20 and then numbers
  18, 19, 20 again under `Bagian Keempat PBJT`; Perda Pekalongan 8/2023 goes
  176 to 174. Those are the document's defects and are reported, not smoothed.
- **The O-for-zero corruption reaches pasal numbers, not just rates.** PP
  35/2023 renders article 70 as `Pasal 7O`, which reads as a jump from 69 back
  to 7 and split that document into nine sections. Repair the suffix to a
  digit only when it restores an ascending sequence -- never by glyph alone,
  because `Pasal 12A` is a real amendment insertion and `B` would become 8.
- **A replacement OCR engine must pass `src/calibrate_ocr.py` first.** Two
  pages, chosen to pull in opposite directions: UU 1/2022 p17, where a faithful
  read of the image *resolves* a disagreement (the text layer inserted a zero),
  and Perwal Jogja p89, where a faithful read *preserves* one (the enacted text
  contradicts itself). An engine that returns `60%` for the second has
  harmonised the statute and deleted a finding — that is a failure, however
  clean the output looks. Scoring reuses `ocr_numerals.scan`, so the gate is
  the pipeline's own reconciliation. tesseract passes 2/2 and is the baseline
  to beat. Fidelity is necessary and not sufficient: the same harness probes
  Lhokseumawe p20, where tesseract keeps the characters and loses 8 of 8 huruf
  markers, so a candidate must beat that *without* failing the gate.
- **Text extraction records its own method, per page.** `text_layer` and `ocr`
  pages do not warrant equal trust and must stay distinguishable downstream; a
  page whose corrupted text layer was replaced also keeps the discarded string.
  Detect corruption by character-script anomaly, never by dictionary hit-rate —
  tariff tables and `Cukup jelas.` pages are prose-free and correct, and a
  stopword test flags ~1,200 of them against ~100 real failures.
  Strip page furniture before segmenting, and verify against the gold
  fixture after: `src/structure.py --verify-gold` is the only check that is
  not the segmenter agreeing with itself.
  Caveat on OCR'd pages: tesseract does not preserve reading order the way
  `pdftotext -layout` does. Marginal labels (`Menimbang`, `Mengingat`) migrate
  to the top of the page, so pasal segmentation over an OCR'd page cannot
  assume source order. Character accuracy is good; sequence is not.

## Extraction interface — the structured corpus changes it

`src/structure.py` output is not raw text. Each unit carries a `citation` and
character offsets, so the old `prompts/extraction_prompt.md` (written against
`pdftotext` output) **must not be ported unmodified**.

- **Citations are a closed set per call.** Extracting Pasal 58, the valid
  citations are exactly those in that pasal object. The model selects; it never
  composes. A citation outside the set is a validation error, the same class as
  an unknown numeral slot.
- **Filter on `section`.** Only `body` is normative. 136 `lampiran` sections
  across the corpus — skip. `penjelasan` is non-normative but useful for a
  later pass: it often states whether a list is exhaustive, which may convert
  `dan sejenisnya` abstains into decidable verdicts.
- **Key on `(doc_id, section, pasal, occurrence)`.** Never on pasal number
  alone; numbers repeat across body and penjelasan.
- **Parser warnings are a confidence signal.** 40 `multiple_huruf_runs_in_ayat`,
  33 `multiple_huruf_runs_in_pasal`, 5 `duplicate_pasal_in_section`, 2
  `pasal_numbering_goes_backwards`. Units named in a warning get reduced
  `extraction_confidence` and go to the front of the review queue.
- **Slot-to-unit assignment is derivable, so assert it.** `scan()` returns char
  offsets and unit boundaries are known, so every numeral slot must fall inside
  the unit its norm cites. Measured: 857/857 do, none crossing a boundary, so a
  crossing means the parse is wrong — flag it, do not resolve it. Then every
  `%` and every numeral parenthetical in an extracted pasal should either
  produce a slot or appear in the skip log. Unexplained numerals are the
  cheapest recall check available.
- **The model's entire output per norm is
  `{citation, norm_type, applies_to, is_residual, bounds:[{op, numeral_slot}]}`.**
  No numbers, no composed citations, no copied text — the last of that went
  with spans. `unmapped` goes too: the ontology builder runs first and mints
  ids for local categories, so `applies_to` is selection from a closed set as
  well. That leaves one gap to log rather than guess: a rate article naming a
  category no definitional article defined gets `category_not_in_ontology` and
  a review-queue entry. The model must never invent an id to fill it.

## The worked example

**A candidate real conflict.** UU Pasal 55(1) lists `panti pijat dan pijat
refleksi` at huruf k, separately from `diskotek, karaoke, kelab malam, bar,
mandi uap/spa` at huruf l. Pasal 58(2)'s 40–75% band applies only to the
huruf-l list, so panti pijat falls back to the 10% general cap in 58(1).
Perda Surabaya 7/2023 Pasal 27(3) taxes panti pijat at 50%.

**The Perda also contradicts itself.** Surabaya's own Pasal 25 copies the
statutory list verbatim, including `k. panti pijat dan pijat refleksi` as an
item separate from `l. diskotek, karaoke, ...`. So the Perda defines panti
pijat as a huruf-k service and then taxes it at the huruf-l rate. This is
stronger evidence than the cross-instrument conflict, because it does not
depend on any interpretive choice — the drafter's own definitional article
settles which bracket applies. Lead with this.

Four-hop reasoning. This is the paper's worked example. **Needs verification
by a lawyer, and check whether Pasal 58 has been amended** — the entertainment
tax band was contentious in early 2024 and may have been challenged.

**The residual path is not trigger-happy.** Of 21 categories checked, 12 reach
the national rule via the residual general cap. Ten of those are COMPLIANT and
two CONFLICT. Categories Surabaya sets no special rate for take Pasal 27(1)'s
flat 10%, exactly at the national ceiling. Use this when someone suspects the
mechanism just flags everything it touches.

## Open work — in dependency order

1. ~~**Prefilter** (`src/prefilter.py`).~~ **Done 2026-09-09.** 1,340 of 3,614
   body pasal selected (37%); the only skip reason still reached is
   `no_normative_marker` (2,274). `deadline_numeral_no_marker` and
   `unexplained_numeral` are both 0 and stay as recall guards. Output in
   `out/prefilter.json`.
2. ~~**Ontology builder.**~~ **Done 2026-09-09** (`src/ontology_build.py`,
   output `out/ontology.json`). 12/12 huruf recovered from UU Pasal 55(1),
   8/8 gold categories recovered (7 by id, 1 by label), 0 missed. National
   categories are live; everything a Perda or Perwal introduces is a proposal.
   **Open follow-up: not every category is defined before it is taxed.**
   `karaoke keluarga` and `karaoke dewasa` — the gold fixture's own worked
   example — appear only in rate provisions, never in a definitional article,
   so no definitional pass can mint their ids. The extractor must emit
   `category_not_in_ontology` and feed a second ontology pass rather than
   invent one. Do not solve this by harvesting categories from rate provisions:
   that is exactly what lost ten of the twelve statutory categories.
3. **Cross-reference resolution** (`sebagaimana dimaksud pada ayat (1)`).
   Survey the distinct reference forms and their counts before building the
   resolver. First fix `crossref.build_index`: it keys pasal by number and so
   loses 94 of 232 in Sibolga and 74 of 181 in Lubuk Linggau, which means
   `resolve_references` today can resolve a citation to penjelasan text
   instead of the operative pasal. `src/structure.py` already produces the
   correct segmentation; point the resolver at that rather than fixing the
   same problem twice.
4. **Extraction runner.** Prompt → API → validate → repair (two attempts on the
   failing norm only, not the whole pasal, then human queue). Test on UU Pasal
   58 first, since gold exists for it. Score element-wise — `applies_to` F1, `bounds` accuracy,
   `is_residual` accuracy, `norm_type` accuracy — reported separately, not as
   exact-match. Prediction worth testing: `is_residual` will be the weakest
   field, because it needs sibling context rather than the provision alone.
5. **`deadline_constraint`.** Recognition is **done 2026-09-09**; the compiler
   is not. `ocr_numerals.PAIR_DURATION` reads `12 (dua belas) bulan` alongside
   `10% (sepuluh persen)` — a separate pattern, because a duration puts its
   unit outside the parenthetical — and `scan` now returns 1,181 durations
   beside the 923 percentages, every slot carrying a `unit`. What remains is
   the Z3 side: `bounds` already carries `{op, value, unit}` and `applicable()`
   does not care what the variable measures, so this is a compiler case, not
   new machinery. **Three day types, not two** — `hari kerja` 157, `hari` 58,
   `hari kalender` 8 — and none is converted into another;
   `slotting.resolve` raises `bounds_unit_mismatch` rather than assuming a
   ratio. `bounds` already carries `{op, value, unit}` and
   `applicable()` does not care what the variable measures, so this is a second
   conflict class from machinery already built and tested. **Model `hari kerja`
   and `hari` as distinct units** — do not silently normalise; if two norms use
   different day types, flag it rather than assuming a conversion.
6. JSON Schema file + validation on load.
7. Coverage log with a fixed failure taxonomy.
8. Perturbation engine for synthetic data. Labels are solver-verified by
   construction, so this set is unaffected by the annotation question below.
   Development and diagnostics only — never the test set.
9. **Held-out test set: ~40–60 pairs, two independent annotators, report
   Cohen's κ.** Mahkamah Agung *hak uji materiil* decisions were the original
   plan and were abandoned — too hard to locate, and they skew toward genuine
   conflicts since nobody litigates a compliant Perda. What they provided was
   labels produced by someone other than the system's author, and a second
   annotator provides the same thing under our own control. Threshold conflicts
   need no legal training to annotate ("is 50% within a 10% cap" is not a
   judgement call); reserve expert input for the interpretive minority. Costs
   about two days across two people. **Do not leave this to week 6.** In
   Limitations: labels are expert-annotated rather than judicially derived, and
   validation against authoritative review outcomes is future work.
   Kemendagri's 2016 Perda cancellations are a possible supplementary external
   source, but their legal status is contested after the Constitutional Court
   limited that power, and they predate HKPD — verify before relying on them.
10. Ablation table: LLM end-to-end / LLM+IR+LLM reasoning / full pipeline /
    gold IR + Z3. Row 2 is the one reviewers care about — it isolates whether
    the solver helps or merely the structuring. Row 4 is cheap and gives the
    ceiling: remaining error is then attributable to extraction.

## Corpus notes

- UU 1/2022 (national, scanned, noisy) — the noisiest source of the original
  four, but no longer the only damaged one; see the batch corpus below.
- Perda DKI Jakarta 1/2024 — DKI levies both province and city taxes, so it is
  the most productive single document.
- Perda Jawa Barat 9/2023 — 628 pages, mostly lampiran. Strip appendices.
- Perda Surabaya 7/2023 — city level, has PBJT.

Province and city levy **disjoint** tax types under HKPD. Jabar and Surabaya
are never comparable to each other. Pairing must be tier-aware.

**Instrument names are not uniform — do not key patterns on `Perda` or
`Daerah`.** Lhokseumawe 1/2024 is an Aceh **Qanun**, and its enacting clause
reads `QANUN KOTA LHOKSEUMAWE TENTANG PAJAK KOTA DAN RETRIBUSI KOTA` — `Pajak
Kota` and `Retribusi Kota` where every other document in the corpus says
`Pajak Daerah` and `Retribusi Daerah`. A matcher looking for the Perda wording
silently skips the whole document. The Perwal/Perwali tier varies in spelling
too (`Perwal`, `Perwali`, `Peraturan Walikota`, `Peraturan Wali Kota`).

`data/raw/batch-a|b|c` holds 34 usable PDFs (35 files; Balikpapan 8/2023 is
0 bytes and must be re-downloaded). Two duplicate originals — UU 1/2022 and
Perda Surabaya 7/2023 — extract byte-identically to their `data/txt/` copies,
so 32 instruments are new. The other two originals (DKI Jakarta 1/2024, Jabar
9/2023) are not in `data/raw/` at all and still come only from `data/txt/`.

Two are national — UU 1/2022 and PP
35/2023, the latter carrying the implementing detail the UU delegates. The
rest are city-level Perda plus Perwal/Perwali implementing regulations across
~25 kota. Two useful properties: batch-b gives Surabaya at four instrument
levels, which lets intra-city delegation chains be tested without crossing
tiers, and PP 35/2023's penjelasan examples are copied nearly verbatim into
several Perda, so the same provision text recurs across instruments with
independent typos. Note the Perwal/Perwali tier is not in the HKPD pairing
model yet — a Perwal implements its own city's Perda, so it is a third rung,
not a peer of the Perda.

## Conventions

- **Never write to `data/gold/`.** It is frozen ground truth. Pipeline output
  goes to `out/`. The files are chmod 444; if a write fails there, that is the
  guard working, not a bug to route around.
- Run tests before and after any change to `ocr_numerals.py`. Every test case
  is a real string from a scanned statute.
- New corruption patterns get a regression test, not just a fix.
- Survey real data before designing against imagined data. This habit found the
  OCR corruption, the line-wrapped parentheticals (which had been silently
  dropping half the numerals in the statute), and the ten missing categories.
- Keep legal terms in Indonesian. Do not translate `pasal`, `ayat`, `tarif`.
- Verdicts must cite provisions. `assert_and_track` everywhere in Z3, so unsat
  cores name pasal rather than anonymous constraints.
- Update this file when a decision changes. The `dan sejenisnya` abstain
  semantics were corrected once already; undocumented corrections revert.
- Measurements go in `docs/FINDINGS.md`; decisions go here. The test for this
  file: would a fresh session do the wrong thing without this line? If not, it
  is a finding.
- A dead end is worth recording. Edit-distance clustering of page-edge lines
  and the parenthesised-letter level were both tried or measured and rejected;
  both entries exist so nobody spends the day again.