# Neurosymbolic legal conflict detection — Indonesian regulatory hierarchy

Detect conflicts between national law (UU) and regional regulation (Perda) by
extracting deontic norms with an LLM and reasoning over them with Z3.

Target: conference paper (JURIX / NLLP / ICAIL). ~8 week runway.

## Architecture

    PDF → OCR numeral recovery → slotting → LLM extraction → norm IR
        → ontology grounding → Z3 → {CONFLICT, COMPLIANT, ABSTAIN}

Exactly one stage is neural (extraction). Everything downstream is
deterministic. This is deliberate: it lets extraction accuracy and reasoning
accuracy be measured separately. **Do not move logic into the LLM stage.**

## Status — read before assuming anything works

| Component | State |
|---|---|
| `src/ocr_numerals.py` | working, tested against real scanned text |
| `src/extract_text.py` | working, run over all 34 raw PDFs |
| `src/structure.py` | working, 6,411 pasal, 8/8 gold citations resolve |
| `src/slotting.py` | working, demo only, not wired to an API |
| `src/detect.py` | working, 21 categories, 2 conflicts found |
| `data/gold/norms.json` | **hand-written fixture**, 8 norms |
| `data/gold/ontology.json` | **hand-written fixture**, 23 categories |
| `prompts/extraction_prompt.md` | written, **never executed** |
| ontology builder | does not exist |
| extraction runner | does not exist |
| cross-reference resolver | does not exist |
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

## Decisions already made — do not relitigate

- **IR is an intermediate representation**, not information retrieval. JSON norm
  objects. The LLM never emits SMT-LIB.
- **Extraction unit is one Pasal**, not one ayat. `is_residual` cannot be set
  correctly without sibling context.
- **The model never transcribes numbers.** It emits `{op, numeral_slot}`;
  values are joined from the slot table. An LLM shown `4Oo/o` will silently
  "correct" it to `40%` and destroy provenance.
- **`bounds` is a list.** UU Pasal 58(2) carries a floor and a ceiling in one
  sentence.
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
- **Only `rate_constraint` is implemented.** `obligation`, `prohibition`, and
  `permission` are declared in the schema and ignored by the compiler. Note
  that the *applicability* reasoning is already general — subsumption, lex
  specialis, and delegation are not numeric. Only the constraint language is.
  Extending to strict O/F conflicts is a second constraint kind (booleans plus
  `Not(And(Obliged, Forbidden))`), reusing `applicable()` unchanged. The real
  cost is agent/action alignment (`pelaku usaha` vs `setiap orang`), not the
  encoding. Before building it, grep the corpus for `wajib`/`dilarang` pairs
  with a national counterpart — if genuine cross-tier contradictions are rare,
  that finding justifies the numeric focus better than any design argument.
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

## Findings so far

**OCR.** UU 1/2022 is a Canon scan. Digits corrupt (`l0%`, `2Oo/o`, `4Oo/o`);
so do words (`liga persen` for `tiga`, glued tokens like `duabelas`). Indonesian
drafting writes every figure twice, so two independent channels can be
reconciled. 100 pairs found, 61 agree, 38 recovered, 1 disagreement.

The disagreement is Pasal 10(1)(b): `60% (enam persen)`. Both channels are
internally clean and they contradict. Internal evidence (the 1,2%→2% and
6%→10% parallel with Pasal 10(2)) says the true value is 6% and the digits
gained a zero. **Resolved 2026-09-08: the page image reads `6% (enam
persen)`.** The scan's own text layer inserted the zero; the word channel was
right. Reconciliation cannot repair this class — both channels parse cleanly,
so `disagree` is the correct terminal verdict and a human reads the page.
The record stays flagged rather than silently corrected.

**Reading the page image is part of verification, not a last resort.** Text
agreement is inference about the source; the render is the source. Every
`disagree` and `unparsed` case below was settled by opening the page, and
three of the five turned out to be a parser bug rather than a real conflict.
Route these to a page image, not to a guess.

**Corpus expansion (`data/raw/batch-a|b|c`, 34 usable PDFs, 5,332 pages).**
Text-layer survey: 5,132 pages clean, 106 corrupted, 94 empty. Nearly
everything yields to `pdftotext -layout`, which reproduces the existing
`data/txt/` files byte-for-byte. Only two documents need real OCR — Perda
Lhokseumawe 1/2024 (85/85 pages, no text layer at all) and Perda Sibolga
1/2024 (101/139 pages, broken CMap remapping Latin glyphs into CJK: `恥じAK
DAERAH` for `PAJAK DAERAH`). Perda Balikpapan 8/2023 is a 0-byte download and
needs re-fetching. Do not classify pages by dictionary hit-rate: lampiran
tariff tables and pages of `Cukup jelas.` boilerplate are prose-free but
perfectly correct, and a stopword-frequency test flags 1,222 pages instead of
106. Character-script anomaly is the signal that actually separates the two.

Reconciliation over `data/extracted/`: 923 pairs, 657 agree, 264 recovered,
2 disagree, 0 unparsed. The two disagreements are the real ones below; every
other pair reconciles. OCR recovered numerals that did not previously exist as
text at all — Lhokseumawe went from 0 pairs to 30, Sibolga from 26 garbage-
derived pairs to 32 clean ones — and the OCR'd documents produced no
disagreements, which is decent evidence the OCR is sound on the values that
matter. Note why cross-channel agreement still means something on an OCR'd
page: the two channels are different encodings in different parts of the line
(digits vs. spelled-out words), so one engine misreading `60` as `80` would not
also turn `enam puluh` into `delapan puluh`. The independence is in the source,
not the reader.

**Glyph confusion is not scan-exclusive.** `6O%` (letter O for zero) appears
in Perda Mojokerto 7/2023 at page 67 — a born-digital, BSrE-signed document
that was never scanned, apparently copied from the identical illustrative
passage in PP 35/2023. So the two-channel check earns its keep on clean
digital sources too, and "this PDF is not a scan" is not a reason to skip it.

**A drafting defect inside one provision.** Perwal Jogja 51/2024 Pasal 198(4)
reads `67% (enam puluh persen)` in the enacted, digitally-signed text. Both
channels extracted it faithfully; the provision contradicts itself. Ayat (3)
directly above sets 30% for a rejected *keberatan*, and the national scheme
pairs 30% objection with 60% appeal, so the words are right and `67` is the
typo. This is a distinct conflict class from panti pijat — numeral-level,
intra-provision, and found without any cross-instrument reasoning. Left as
`disagree`; do not auto-repair it.

**Structure, as segmented (`data/structured/`).** 6,411 pasal, 9,053 ayat,
9,481 huruf, 2,889 angka, 22,915 addressable units, 80 warnings. The pasal
count equals the raw `^Pasal N$` marker count exactly, so nothing is dropped.

Page furniture is stripped before segmenting, and it mattered more than
expected: a catchword, stamp and running header at a page break push the
following `(2)` off the line start, so the preceding ayat absorbs its siblings
and their `a./b./c.` lists collapse into one citation. Removing it recovered
125 previously-swallowed ayat. Identify furniture by *position*, never by
wording or frequency alone: `PRESIDEN` occurs 102 times in PP 35/2023 and every
one is a page's first line, while `Cukup jelas.` occurs 245 times mid-page and
is real text. The rule is "recurs at the page edges and never once in the
middle", with the edge zone shrinking on a short page so a middle always
exists.

Citations are qualified by section and occurrence, because `Pasal 32` (a 25%
reklame rate in Perda Tangerang Selatan 10/2023) and `Penjelasan Pasal 32`
(`Cukup jelas.`) are different provisions. That plus furniture stripping took
colliding citations from 1,328 to 510 (6.0% to 2.23%).

Ayat markers are read tolerantly, because they are scan-damaged too: `(2)`
arrives as `(21` 94 times, the closing paren read as a `1`, and `(5)` as `(s)`.
A strict `\(\d+\)` drops those, the ayat is lost, and its parent absorbs it.
Tolerance is safe only because runs are validated -- `(21` is ayat 21 after
ayat 20 and ayat 2 after ayat 1, and continuity decides, never the glyph. A
run of one is accepted only when it needed no repair. This recovered 416 ayat
(8,637 to 9,053) and fixed PP 35/2023 Pasal 3, which had collapsed four ayat
of tax types into one.

`python3 src/structure.py --verify-gold` checks the segmentation against the
hand-annotated fixture: all 8 gold citations resolve to exactly one unit each.
This is the only check here that is not the segmenter agreeing with itself, so
run it after touching this module.

**Do not add a parenthesised-letter level.** `(a)`, `(b)`, `(c)` look like a
missing fifth level, but 1,375 of their 1,406 occurrences are inside lampiran
tariff tables, and all 31 in operative text are `(l)` -- a scan-damaged `(1)`,
not a letter at all. Measured before building; there is nothing to build.

The remaining 510 collisions (2.23%) are flagged, not hidden: 73 warnings
report a container holding more than one list opening, which proves a parent
marker was missed. Known residue:

  Running headers survive when OCR spells them differently on each page --
  `PRESIOEN`, `REPIJBLIK`, `REPLIBLIK`, `]NOONESIA` -- so no single variant
  clears the repeat threshold. About 75 leaks, all in enacting and closing
  boilerplate rather than rate provisions, e.g. `Agar REPUBLIK ]NOONESIA Agar
  setiap orang mengetahuinya` in UU 1/2022 Pasal 193. Fuzzy clustering of edge
  lines would fix it; the payoff is small.

  `PASAL_HEADER` requires `Pasal N` alone on a line, so the ~492 inline
  `Pasal N <text>` forms are not headers. Right for operative text, wrong for
  the penjelasan, where `Pasal 22 Cukup jelas.` sits on one line -- which is
  why Kupang's penjelasan appears to start at Pasal 22 and Cilegon's at Pasal 2
  (its `Pasal 1` was scanned as `Pass} 1`). The penjelasan is non-normative, so
  this has not been chased. Do not widen the regex without care: it would start
  matching citations mid-sentence.

  401 of 6,411 pasal touch at least one OCR'd page and carry the reading-order
  caveat. `extraction_methods` on each pasal says which.

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

1. **Ontology builder.** Extract enumerated lists from definitional articles
   (`a. ... ; b. ... ; dan c. ...` is highly regular drafting). Emit
   `{id, label, parent, origin}`. Cross-instrument alignment goes to
   `pending_review`, never auto-merged: `karaoke_keluarga ⊑ karaoke` is a legal
   judgement. Immediate check available — it should recover the same 12
   statutory categories currently in the gold fixture.
2. **Cross-reference resolution** (`sebagaimana dimaksud pada ayat (1)`).
   Survey the distinct reference forms and their counts before building the
   resolver. First fix `crossref.build_index`: it keys pasal by number and so
   loses 94 of 232 in Sibolga and 74 of 181 in Lubuk Linggau, which means
   `resolve_references` today can resolve a citation to penjelasan text
   instead of the operative pasal. `src/structure.py` already produces the
   correct segmentation; point the resolver at that rather than fixing the
   same problem twice.
3. **Extraction runner.** Prompt → API → validate → repair (two attempts, then
   human queue). Test on UU Pasal 58 first, since gold exists for it.
4. JSON Schema file + validation on load.
5. Coverage log with a fixed failure taxonomy.
6. Perturbation engine for synthetic data.
7. Held-out real test set: ~60 pairs from Mahkamah Agung hak uji materiil
   decisions, hand-annotated, never tuned on.
8. Ablation table: LLM end-to-end / LLM+IR+LLM reasoning / full pipeline /
   gold IR + Z3. Row 2 is the one reviewers care about — it isolates whether
   the solver helps or merely the structuring.

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
9/2023) are not in `data/raw/` at all and still come only from `data/txt/`. Two are national — UU 1/2022 and PP
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