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

## Layout

    src/ocr_numerals.py   two-channel numeral recovery (digits + words)
    src/slotting.py       numeral slotting; the join between OCR and LLM
    src/detect.py         IR → Z3 compiler and conflict detection
    data/gold/norms.json  hand-written gold IR (8 norms, UU 58 + Perda 27)
    data/gold/ontology.json  category subsumption taxonomy
    prompts/              extraction prompt with real few-shot examples
    schema/schema.md      IR field documentation, each justified by a provision
    tests/                regression suite, all cases from real scanned text

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
- **Schema does not self-modify.** Unrepresentable provisions go to a coverage
  log with a reason code. The ontology may grow, but new subsumption edges land
  in `pending_review` before going live.

## Findings so far

**OCR.** UU 1/2022 is a Canon scan. Digits corrupt (`l0%`, `2Oo/o`, `4Oo/o`);
so do words (`liga persen` for `tiga`, glued tokens like `duabelas`). Indonesian
drafting writes every figure twice, so two independent channels can be
reconciled. 100 pairs found, 61 agree, 38 recovered, 1 disagreement.

The disagreement is Pasal 10(1)(b): `60% (enam persen)`. Both channels are
internally clean and they contradict. Internal evidence (the 1,2%→2% and
6%→10% parallel with Pasal 10(2)) says the true value is 6% and the digits
gained a zero. **Needs confirmation against an official copy.**

**A candidate real conflict.** UU Pasal 55(1) lists `panti pijat dan pijat
refleksi` at huruf k, separately from `diskotek, karaoke, kelab malam, bar,
mandi uap/spa` at huruf l. Pasal 58(2)'s 40–75% band applies only to the
huruf-l list, so panti pijat falls back to the 10% general cap in 58(1).
Perda Surabaya 7/2023 Pasal 27(3) taxes panti pijat at 50%.

Four-hop reasoning. This is the paper's worked example. **Needs verification
by a lawyer, and check whether Pasal 58 has been amended** — the entertainment
tax band was contentious in early 2024 and may have been challenged.

## Open work

1. Cross-reference resolution (`sebagaimana dimaksud pada ayat (1)`) — not yet
   built, and it is upstream of everything.
2. Extraction runner: prompt → API → validate → repair loop. Not written.
3. JSON Schema file + validation on load. Currently only prose docs.
4. Coverage log with a fixed failure taxonomy.
5. Perturbation engine for synthetic data (operators listed in docs).
6. Held-out real test set: ~60 pairs from Mahkamah Agung hak uji materiil
   decisions, hand-annotated, never tuned on.
7. Ablation table: LLM end-to-end / LLM+IR+LLM reasoning / full pipeline /
   gold IR + Z3.

## Corpus notes

- UU 1/2022 (national, scanned, noisy) — the only OCR-damaged source.
- Perda DKI Jakarta 1/2024 — DKI levies both province and city taxes, so it is
  the most productive single document.
- Perda Jawa Barat 9/2023 — 628 pages, mostly lampiran. Strip appendices.
- Perda Surabaya 7/2023 — city level, has PBJT.

Province and city levy **disjoint** tax types under HKPD. Jabar and Surabaya
are never comparable to each other. Pairing must be tier-aware.

## Conventions

- Run tests before and after any change to `ocr_numerals.py`. Every test case
  is a real string from a scanned statute.
- New corruption patterns get a regression test, not just a fix.
- Keep legal terms in Indonesian. Do not translate `pasal`, `ayat`, `tarif`.
- Verdicts must cite provisions. `assert_and_track` everywhere in Z3, so unsat
  cores name pasal rather than anonymous constraints.
