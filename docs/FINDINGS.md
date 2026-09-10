# Findings

Lab notebook for the neurosymbolic legal conflict detection project. Results,
measurements, and dead ends, in the order they were established. CLAUDE.md
holds the decisions these findings produced; this file holds the evidence.

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

**A drafting defect inside one provision.** Perwal Jogja 51/2024 **Pasal 198
ayat (4), page 89** reads `67% (enam puluh persen)` in the enacted,
digitally-signed text — the page is `text_layer` and classified `clean`, so
this is not scan damage. Both channels extracted it faithfully; the provision
contradicts itself. Ayat (3) directly above sets 30% for a *keberatan*, and the
scheme pairs a 30% objection with a 60% appeal, so the words are right and `67`
is the typo. Left as `disagree`; do not auto-repair it.

**Confirmed 2026-09-09 against five other instruments.** The provision is a
near-verbatim copy of PP 35/2023 Pasal 96 ayat (4), down to the ayat structure
(imbalan bunga, the computation window, the 30% waiver, the appeal denda). Six
instruments in the corpus carry that text:

    PP 35/2023                  Pasal 96    60%  (enam puluh persen)
    Perda Pekalongan 8/2023     Pasal 182   60%  (enam puluh persen)
    Perda Tangerang Sel 10/2023 Pasal 89    60%  (enam puluh persen)
    Perda Cilegon 1/2024        Pasal 130   60%  (enam puluh persen)
    Perda Surabaya 7/2023       Pasal 172   60%  (enam puluh persen)
    Perwal Jogja 51/2024        Pasal 198   67%  (enam puluh persen)   <-- outlier

Five witnesses agree with Jogja's own word channel. The `67` has essentially no
remaining defence, and the enacted text still says it, which is the point.

Two things this changes. First, the earlier note that this was "found without
any cross-instrument reasoning" holds for *detection* but not for
*confirmation*: the two-channel check found it inside one provision, and
verbatim text reuse across instruments settled it. Those are separable
mechanisms and the paper can show both on one example. Second, it makes
CLAUDE.md's observation about PP 35/2023 text recurring across instruments
operational rather than incidental — a provision copied into six documents is
a six-way redundancy code, and an outlier in one copy is a detectable defect
even when both of that copy's own channels are clean.

Note what would happen if the digits were taken at face value: a Perwal
imposing 67% where the national PP sets 60% is a rank conflict. It would not
surface as one, because sanction provisions are deliberately excluded from the
IR. The numeral channel catches it instead, which is a useful argument that the
two mechanisms are complementary rather than redundant.

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

  Running headers still leak into about 89 units, all in enacting and closing
  boilerplate rather than rate provisions, e.g. `Agar REPUBLIK ]NOONESIA Agar
  setiap orang mengetahuinya` in UU 1/2022 Pasal 193. **Edit-distance
  clustering of page-edge lines does not fix this -- tried and reverted,
  2026-09-08.** The cause is not spelling variance: `REPUBLIK INDONESIA` is
  furniture at line 1 of most pages *and* legitimate text elsewhere in the
  same document (`UNDANG-UNDANG REPUBLIK INDONESIA` on the title page,
  `DEWAN PERWAKILAN RAKYAT REPUBLIK INDONESIA` mid-page), so the "never
  mid-page" rule correctly refuses to delete it. Clustering changed the output
  by exactly nothing: its apparent gain was page numbers, which `PAGE_NUMBER`
  already strips. Separating these needs a rule that strips by position
  regardless of wording, which would eat the title page. Left alone
  deliberately.

  `PASAL_HEADER` requires `Pasal N` alone on a line, so the ~492 inline
  `Pasal N <text>` forms are not headers. Right for operative text, wrong for
  the penjelasan, where `Pasal 22 Cukup jelas.` sits on one line -- which is
  why Kupang's penjelasan appears to start at Pasal 22 and Cilegon's at Pasal 2
  (its `Pasal 1` was scanned as `Pass} 1`). The penjelasan is non-normative, so
  this has not been chased. Do not widen the regex without care: it would start
  matching citations mid-sentence.

  401 of 6,411 pasal touch at least one OCR'd page and carry the reading-order
  caveat. `extraction_methods` on each pasal says which.


**Spans vs offsets, surveyed before deciding (2026-09-09).** The question was
whether the model must ever name a sub-clause *within* an ayat, which is the
only thing a quoted span buys over a citation plus offsets.

Numeral pairs per body leaf unit, all 34 documents, 19,901 units: 19,153 carry
none, 714 carry one, 29 carry two, 5 carry three or more. Of the 29 two-pair
units, 24 are the *same provision* — `ditetapkan paling rendah 20% (dua puluh
persen) dan paling tinggi 100% (seratus persen)`, the PBB-P2 assessment base,
reproduced near-verbatim across 22 Perda and PP 35/2023 — joined by UU 58(2)
itself. One norm, two bounds, which `bounds`-as-a-list already covers; `op`
tells the floor from the ceiling and no span is needed.

Every remaining multi-numeral unit is a segmentation defect, not drafting.
PP 35/2023 Pasal 23(1)(a) reads `l. soy" ... 2. 8Oo/o`, so the angka run never
opens at `1` and two sub-items collapse into the huruf. Lhokseumawe Pasal 6 has
no surviving ayat markers at all. Sibolga Pasal 7(1)(b) and Pasal 25 huruf c
carry a migrated `(1) (2) (1) (5) (6)` marker block — the OCR reading-order
caveat, exactly where it was predicted. Perwali Surabaya 43/2024 Pasal 104(2)
opens its huruf run at `c.`, so the validated-run rule rejects it. UU 1/2022
Pasal 40(4) absorbed ayat (5) behind a `REPUBLIK INOONESIA` header. In each
case the sub-clause a model would be asked to quote sits inside a unit whose
boundaries are already wrong, so a span would verify a quotation against a
mis-segmented parent and pass. The span check cannot see the defect that
produced the case for having it.

**Slot containment: 857/857.** Every numeral slot in body text falls inside
exactly one addressable unit. Zero cross a boundary; zero are orphaned. The
deepest containing unit is an ayat for 379, a huruf for 293, a bare pasal for
128, an angka for 57. This makes "the slot named in `bounds` lies inside the
unit named in `citation`" safe to assert as a hard error, and it catches a
class the retired substring test could not: a bound filed under the wrong ayat
quotes text that is a real substring of the pasal either way.

One correction worth recording, because the first measurement was wrong in an
instructive direction. A leaf-only containment test reported 58 slots outside
every unit. They are not outside anything — they sit in an ayat's *chapeau*,
the introductory clause above a huruf list, as in PP 35/2023 Pasal 25(5). The
chapeau is a real unit with a real citation. Containment must be checked
against the deepest *containing* unit, never the deepest leaf, and citing the
parent of a slot's unit is valid; only citing a sibling is an error.

**A two-slot norm that is not a span problem.** Perwali Surabaya 33/2024
Pasal 93(2)(c)(1): an NJOP that `meningkat lebih dari 50% (lima puluh persen)`
may be given `pengurangan sebesar 50% (lima puluh persen)`. Both numerals are
real, both belong to one norm, and they have different roles — a trigger
threshold and a relief value — which `op` alone renders as two contradictory
bounds. A span would not have disambiguated them either. One occurrence in 857
slots, logged as `conditional_threshold` rather than given a schema field.

**Prefilter, all 34 documents (2026-09-09).** 3,614 body pasal, 1,137 selected
(31%), 2,477 skipped. Selection channels, counted per pasal and overlapping:
979 bound marker, 368 numeral pair, 178 modal `wajib`, 32 `dilarang`. As the
*sole* reason for selection: 583 bound marker, 100 modal `wajib`, 33 numeral
pair, 25 `dilarang`. Skip reasons: 2,275 `no_normative_marker`, 202
`deadline_numeral_no_marker`, 0 `unexplained_numeral`.

**The bound-marker counts in CLAUDE.md were a slight undercount, and the cause
is worth keeping.** They read 51/185 for UU 1/2022 and 55/197 for Perda
Surabaya. Matching with a literal single space over unjoined text reproduces
those two figures exactly; matching `\s+` over layout-collapsed text gives
52 and 59. The difference is markers split across a line break -- `paling\n
tinggi` -- which the original regex could not see. One in the UU, four in
Surabaya. The corrected corpus-wide figure is 979 of 3,614, or 27.1%, which is
still the ~28% the decision rests on.

**`wajib` is more noun than CLAUDE.md recorded, because the denominator was
wrong.** The file reports Surabaya 326 occurrences of which 221 are the noun,
and UU 105 of which 50. Those totals are *substring* counts: 326 includes 24
`kewajiban`, 12 `diwajibkan` and 1 `kewajibannya`, and 105 includes 20
`kewajiban`, 2 `kewajibannya`, 2 `diwajibkan` and 1 `mewajibkan`. Against the
word `wajib`, Surabaya is 225 of 289 and UU is 50 of 80. Over body pasal
corpus-wide with the full head list it is 3,514 of 3,796 -- 93%, not two
thirds. The decision is unaffected and in fact strengthened; only the numbers
change.

Four exclusions are needed, not one. Beyond `Wajib Pajak` / `Wajib Retribusi`:
the tax-type heads (`Wajib PAB`, `Wajib PBB-P2`, `Wajib PAT`, `Wajib PKB`,
`Wajib PBJT`, `Wajib BBNKB`); `kontribusi wajib kepada Daerah`, the adjective
in the statutory definition of a tax, which opens Pasal 1 of nearly every
instrument (26 occurrences); `Urusan Pemerintahan wajib`, a defined term from
UU 23/2014 (5); and `wajib` followed immediately by a comma, which is the
heading `Subjek, Wajib, dan Objek Pajak` splitting the defined term (12).
A colon is the opposite case and must be kept -- `sesuai kewenangannya wajib:
a. meminta ...` introduces a list of duties, 27 occurrences. Applying all four
takes modal `wajib` from 282 to 231.

Matching on capitalisation instead of a head list is worse, and was measured:
194 noun occurrences are lowercase in the source, against only 7 capitalised
occurrences whose head is outside the list.

**Fuzzy marker matching is a dead end, measured not assumed.** At edit distance
1 from the marker words, `lama` collides with `lima` (467), `sama` (325) and
`nama` (246), and `ditetapkan` collides with `diterapkan` (22), a real word
meaning "applied". That is 1,108 near-miss tokens against roughly ten genuinely
damaged markers (`ditctapkan`, `diletapkan`, `ditecapkan`, `diietapkan`,
`dcngan`, `denoan`, `rcndah`, `tinngi`, `ebesar`). Tolerance is unnecessary as
well as harmful: a provision stating a rate states the figure twice, so every
damaged-marker pasal is selected by the numeral channel regardless. Strict
matching, deliberately.

**No skipped pasal contains an unclaimed percentage.** Zero of 2,477. Every
`%` and every `persen` in body text is either inside a recovered pair or inside
a pasal a bound marker already selected. This is the recall check CLAUDE.md
asks for, and it passes; the `unexplained_numeral` reason code stays as a guard
that currently never fires.

**The numeral recogniser does not see deadlines, and CLAUDE.md implies it
does.** Open work item 5 says `paling lama 12 (dua belas) bulan` "uses the same
double-numeral convention the recovery module already handles". The convention
is the same; the module is not. `ocr_numerals.PAIR` requires a percent-like
tail, so `scan("paling lama 12 (dua belas) bulan")` returns nothing. Measured
over body pasal: 1,102 double-numeral time constructions -- 560 `bulan`, 327
`tahun`, 157 `hari kerja`, 58 `hari` -- across 628 pasal. 426 of those pasal
reach the extract bucket through some other channel, overwhelmingly `paling
lama`; 202 would be skipped with no trace. They are still skipped, because
extracting norms the compiler does not consume is 202 wasted calls, but they
now carry `deadline_numeral_no_marker` so the work item arrives pre-costed.
The `hari kerja` / `hari` split CLAUDE.md insists on is real and sizeable --
157 against 58 -- not a hypothetical.

**`dilarang` is no longer purely a confidentiality duty.** CLAUDE.md records 9
occurrences across the original four documents, every one a duty on officials
not to disclose taxpayer data. Across all 34 documents there are 32, in four
classes: 21 confidentiality (21 documents), 6 `Pemungutan Pajak dilarang
diborongkan` (tax collection may not be subcontracted), 2 `Pemerintah Daerah
dilarang memungut Pajak selain jenis Pajak sebagaimana dimaksud dalam Pasal 4
ayat (1)`, and 3 fiscal-discipline rules on Daerah (`dilarang melakukan
Pembiayaan langsung`, `dilarang memberikan jaminan atas Pembiayaan utang`,
`dilarang mendirikan Bangunan`).

The two-occurrence class is the interesting one: it appears in UU 1/2022
Pasal 6(1) and again, copied, in Perda Batam 1/2024 Pasal 6(1). It is a
prohibition on a *government* rather than a taxpayer, it has a national
counterpart at a higher rank, and it is decidable against a closed list -- the
permitted tax types in UU Pasal 4(1) -- with no numerals at all. So the claim
that strict O/F conflicts are "essentially absent in this domain" holds as an
order of magnitude (32 against 979 rate-marker pasal) but is not literally
true, and the paper should not say every instance is a confidentiality duty.

**The word channel is error-detecting; the digit channel is not (2026-09-09).**
The intuition that words survive scanning better is right, but the mechanism is
not frequency. Enumerating every single-character substitution, deletion and
insertion: **281 of 359 digit corruptions (78.3%) parse to a valid but
different number**, while **0 of 1,274 corruptions of a numeral word land on
another vocabulary word.** The Indonesian numeral vocabulary has a minimum
pairwise edit distance of 2, so any single-character corruption of `empat`
produces a non-word the parser can see, whereas `40` corrupts to `4O`, `10` and
`80` — all perfectly valid. That is the real asymmetry, and it is why a
repaired channel yields to an unrepaired one.

It is not a reason to prefer words unconditionally. Repair can still be
ambiguous: `liga` sits one edit from both `lima` (5) and `tiga` (3). Measured,
4 of 1,924 single-character word corruptions are ambiguous in this sense, all
of them the lima/tiga pair via `tima` and `liga`. In the one real corpus
occurrence the digits are clean (`3o/o`) and the existing "prefer the channel
that needed no repair" rule gets it right, where "always prefer words" would
have returned 5%.

**`_snap` was nondeterministic across processes.** It picked the nearest
vocabulary word by iterating `VOCAB`, a `set`, whose iteration order follows
string hashing and is randomised per process. `_snap('liga')` returned `lima`
under PYTHONHASHSEED 0, 1, 2 and `tiga` under 3, 4, 5 — so `parse_words('liga
persen')` was 0.05 or 0.03 depending on the run, and the reconciliation totals
below were not reproducible. Fixed by iterating a sorted tuple. `_segment` had
the same exposure. Any measurement in this file taken before 2026-09-09 that
touched an ambiguous repair should be treated as one sample of two.

An ambiguous repair now returns None rather than picking, so the token fails to
parse and the other channel or a human decides. `_int_from` also silently
skipped tokens it did not recognise, which meant an unresolvable word dropped
out of the fold and produced a confident wrong number (`empat <noise> persen`
as 4); `parse_words` now refuses instead.

**The duration channel.** `PAIR` requires a percent-like tail, so no deadline
ever produced a slot. Deadlines write the figure twice exactly as rates do but
put the unit *outside* the parenthetical — `12 (dua belas) bulan` against
`10% (sepuluh persen)` — so this needed a second pattern rather than a wider
one. Corpus after widening: **2,104 pairs, 1,790 agree, 311 recovered, 1
single_channel, 2 disagree.** By unit: fraction 923, bulan 594, tahun 364,
hari kerja 157, hari 58, hari kalender 8. The fraction count is unchanged at
923, which is the check that the percentage path was not disturbed. The two
disagreements are still the two real ones.

**There are three day types, not two.** `hari kerja` (157), `hari` (58) and
`hari kalender` (8). CLAUDE.md asked for `hari kerja` and `hari` to stay
distinct; `hari kalender` is a third and the alternation must list the longer
forms first, or `15 (lima belas) hari kalender` silently becomes a `hari`.
Nothing is converted: `slotting.resolve` reports `bounds_unit_mismatch` when a
norm's floor and ceiling disagree about the unit rather than picking a ratio.
Largest values observed: 60 tahun, 24 bulan, 30 hari, 20 hari kerja,
15 hari kalender.

**Two bugs the duration pattern hit, both caught by the redundancy itself.**
`re.IGNORECASE` on the whole pattern made the `I` in the digit class match the
lowercase `i` of a preceding word, so `... lagi 12 (dua belas) bulan` captured
`i 12`, which does not parse as an integer. That did not produce a wrong value
— it silently dropped the digit channel on 51 pairs, which is worse, because
half the redundancy disappeared invisibly. The fix is to case-fold only the
unit alternation, inline. This is the same trap `PAIR`'s own comment warns
about, hit again.

The second: with no `%` to anchor its left edge, the digit class started inside
a larger number and a lampiran tariff column bled across lines —
`1,500,000\n     (lima) hari` in Perda Kupang matched `000` against `lima`,
and was correctly flagged `disagree` rather than silently taken. Forbidding
newlines fixes it but costs 235 of 1,181 real matches (113 wrap before the
parenthetical, 122 before the unit), because `pdftotext -layout` breaks the
line at both gaps. A `(?<![\d.,])` lookbehind fixes it at the source instead
and costs exactly one match corpus-wide — the artifact itself.

**Prefilter, after the widening.** 1,340 of 3,614 body pasal selected (37%,
up from 31%). Selection channels: 979 bound marker, 886 numeral pair (up from
368), 178 modal `wajib`, 32 `dilarang`. Sole reason: 324 bound marker, 236
numeral pair, 81 modal `wajib`, 24 `dilarang`. `deadline_numeral_no_marker`
is now 0 — everything it caught, the duration channel catches first — and it
stays as a recall guard alongside `unexplained_numeral`, also 0.

**`disagree` is overloaded: two causes, one code (2026-09-09).** The two
disagreements in the corpus have opposite meanings.

    UU 1/2022 Pasal 10(1)(b)    `60% (enam persen)`        the page renders 6%
    Perwal Jogja Pasal 198(4)   `67% (enam puluh persen)`  the page renders 67%

In the first, the source is correct and our reading of it is wrong -- the
scan's text layer inserted a zero the glyphs do not have. Opening the page
*resolves* it. In the second, the enacted instrument contradicts itself, and
opening the page *confirms* the contradiction rather than settling it. The
first is a pipeline defect; the second is a finding about the law and belongs
in the output, not the error log.

**They are indistinguishable on every signal currently recorded.** Both pages
are `method=text_layer`, `classification=clean`, `garbage_ratio=0.0`, and in
both cases each channel parsed without repair. Page provenance does not
separate them, which kills the obvious triage rule. Two things could:

*Re-render the disputed page and OCR the numeral.* A third channel, consulted
only where the first two disagree. If the rendered glyphs contradict the text
layer it is an extraction artifact; if they agree it is an enacted defect. This
is what a human already does -- FINDINGS records that every `disagree` was
settled by opening the page -- so the value is in making it reproducible, not
in new capability. Cost is negligible: 2 pages in 5,332.

*Cross-instrument corroboration*, surveyed below.

**Cross-instrument numeral outliers: the mechanism works, the evidence is
thin.** Group every numeral by a fingerprint of its surrounding text with the
numeral itself masked, then compare copies. 31 provision groups in this corpus
are shared by 3 or more instruments. Two groups disagree, and the method
independently surfaces the Jogja case without using the two-channel check at
all. Nothing new turned up beyond it.

Three implementation details that were each wrong on the first attempt and are
worth not rediscovering:

  Mask the matched numeral *span*, not the digits by regex. PP 35/2023's
  scan-damaged `607o` otherwise reduces to `#o #` where Jogja's `67%` reduces
  to `# #`, and the two copies never group.

  Fingerprint a window around the numeral, not the containing unit. Trailing
  section headings bleed into a unit and differ between instruments -- Jogja's
  ayat carries `Bagian Kesebelas` and PP 35's carries `Bagian Ketujuh Belas` --
  which alone was enough to hide the group. Trim the first and last token, or
  the fixed-width window cuts words differently in each copy.

  Compare only within a matching unit. Grouping `paling lama 1 tahun` with
  `paling lama 6 bulan` produced a confident nonsense outlier. Same rule as
  `hari kerja` against `hari`, hit from a different direction.

**The method cannot run on raw text, and that is the real result.** It has no
way to tell a defect from authorised variation. Perda Malang 4/2023 Pasal 25(2)
sets the entertainment floor at 50% where five instruments copying the same
sentence say 40% -- that is not an error, it is UU 58(4) delegation working
exactly as designed, and it is the false positive the whole `delegation` norm
type exists to prevent. Perda Semarang's 2-year implementing deadline against
three instruments' 1 year is the same story. At a 3-instrument threshold the
precision for *defects* is 1 in 2.

So outlier detection belongs downstream of the IR, where `norm_type:
delegation` and the delegated band say whether divergence is authorised, rather
than as a text-level pass. Read the other way, the corpus's verbatim copying is
a real signal -- a provision reproduced in six instruments is a six-way
redundancy code, and it catches defects that both of a copy's own channels
agree on, which the two-channel check structurally cannot.

**Ontology builder, all 34 documents (2026-09-09).** The scoreable check first:
UU 1/2022 Pasal 55(1) enumerates twelve huruf and the builder recovers
**12/12**, splitting them into 25 service-level categories. Against the gold
fixture's eight Pasal 55 categories: 7 matched by id, 1 matched by label
(`jasa_hiburan` in the fixture is the hand-shortened form of the statute's
`Jasa Kesenian dan Hiburan`, which slugifies to `jasa_kesenian_dan_hiburan`),
**0 missed**. 31 extras, which is the expected direction -- CLAUDE.md records
that the fixture was drawn from rate provisions and only ever saw huruf k and
huruf l, so the ten other statutory huruf are new.

Corpus totals: 284 national categories (253 unique ids), of which 163 sit under
a subject tagged taxable; 3,951 local categories (1,432 unique ids), 2,225
taxable; 1,776 proposed alignments, 1,637 `same_as` and 139 `subclass_of`;
2,871 coverage-log entries.

**Only about 45% of definitional lists define a taxable thing.** `Keadaan kahar
meliputi:` and `Wewenang penyidik meliputi:` are the same drafting move applied
to procedure. Of 38 national subject nodes, roughly 17 are tax objects -- `Jenis
Pajak`, `Objek PBJT`, `Jasa Kesenian dan Hiburan`, `Jasa Parkir`, `Jenis
Retribusi` and the three Retribusi object classes -- and the rest are
procedural. They are tagged, not dropped: `applies_to` should resolve against
`taxable_subject` nodes, and the untagged ones stay in the file so a later pass
need not re-harvest. Tagging also cut the alignment queue from 2,507 to 1,776
by not proposing `keadaan kahar` alignments across thirty Perda.

**A distributive head is common and must not be resolved automatically.**
`pergelaran kesenian, musik, tari, dan/atau busana` does not name a category
`musik`; it names `pergelaran musik`. Three of the five splits in Pasal 55(1)
do this -- huruf b (`pergelaran`), f (`pertunjukan`), j (`rekreasi`) -- and 74
cases occur corpus-wide. Distributing the head is a reading of the provision
and getting it wrong invents categories, so the split is emitted as found and
flagged `distributive_head_suspected`. Note the downstream cost: a Perda naming
`pergelaran musik` will not align with a category called `musik`, because
neither is a prefix of the other.

**Exclusion lists look identical to definitions and mean the opposite.** UU
Pasal 55(2) enumerates what is *not* Jasa Kesenian dan Hiburan; harvesting it
would create three categories that are by definition outside the tax. 246 such
lists corpus-wide. The exclusion test must run *before* the opener test:
Pasal 55(2) opens with `... yang semata-mata untuk:`, which is not one of the
recognised enumeration openers, so gating on the opener first drops it silently
instead of recording the refusal.

**Splitting a huruf needs a subordination test, not a comma count.** `diskotek,
karaoke, kelab malam, bar, dan mandi uap/spa` is five categories; `tontonan
film atau bentuk tontonan audio visual lainnya yang dipertontonkan secara
langsung di suatu lokasi tertentu` is one, and splitting it on commas would
invent several. Presence of `yang`, `dengan`, `untuk`, `lainnya` and similar
blocks the split; 2,332 huruf corpus-wide are left unsplit with the reason
recorded. One detail worth keeping: the comma alternative matches before
` dan `, so the final member of a list arrives as `dan mandi uap/spa` unless
the conjunction is stripped per member. That single bug cost `mandi_uap_spa` in
the first gold comparison.

**Some categories are never defined -- they are introduced by being taxed.**
`karaoke keluarga` and `karaoke dewasa` occur three times in the whole corpus,
all of them in *rate* provisions: Perda Surabaya 7/2023 Pasal 27(2) and 27(3),
and Perda Padang Panjang Pasal 60. Neither appears in any definitional article
in any instrument, including Surabaya's own Pasal 25, which copies the
statutory list verbatim and therefore stops at `karaoke`.

This is a real problem for the ordering CLAUDE.md fixes. "The ontology builder
must run before the norm extractor, because `applies_to` can only reference ids
that already exist" holds for statutory categories and fails for local
subdivisions: the extractor will meet `karaoke keluarga` in Pasal 27(2) and
find no id to reference. It is also the gold fixture's own worked example, so
this is not an edge case.

The ordering is still right -- definitions genuinely do precede rates for
everything the statute names -- but it needs a second pass. The extractor
should emit `category_not_in_ontology` rather than inventing an id, and those
become `pending_review` proposals. Harvesting category mentions out of rate
provisions directly is possible (the drafting is regular: the list sits between
`atas jasa hiburan pada` and `ditetapkan sebesar`) but it makes the ontology
depend on rate provisions again, which is the mistake that lost ten of the
twelve statutory categories in the first place.

**How good is the ontology builder, measured (2026-09-10).** The corpus is its
own replicate set: 24 of the 34 documents reproduce UU Pasal 55(1)'s twelve-item
list in their own definitional article, so recall can be measured without new
annotation. Result: **240/279 items, 86%**, with 19 of 24 documents at 100%.

    Gorontalo 1/2024        7/12   58%
    Lubuk Linggau 12/2023   7/11   64%
    Lhokseumawe 1/2024      0/11    0%
    Sibolga 1/2024          0/12    0%
    Perwali Surabaya 33     1/8    12%
    all others (19)                100%

**Every failure is upstream input damage or nesting, not category logic.**
Lhokseumawe (85/85 pages OCR'd) and Sibolga (102/139) lost their huruf markers
to OCR: the list arrives as one run-on huruf with commas and colons where
`b.` `c.` `d.` should be, and `structure.py` correctly refuses to invent a
validated run from it. Gorontalo and Lubuk Linggau are the same failure,
milder. Perwali Surabaya 33 is different -- its list is not the statutory
categories at all but the payment components of each, nested a level deeper.

**Two builder bugs found by this measurement, both fixed.** `chapeau_of`
stripped only a trailing *letter* marker, so an angka list's chapeau read
`... meliputi: 1.` and, because the opener regex is anchored at `$`, every
angka-level enumeration was silently rejected. And `containers()` looked only
at pasal- and ayat-level huruf, so a list nested at `ayat -> huruf -> angka`
was never reached. Together these hid Perwali Surabaya 33/2024 Pasal 103
entirely. Fixing both added 201 local categories and 160 coverage-log entries;
the Pasal 55 check is unchanged at 12/12 and 8/8.

**Precision is not measured and should not be quoted.** The `taxable_subject`
tag is a regex over the subject phrase, validated against nothing. Of 38
national subject nodes roughly 17 look like tax objects by inspection, but that
is an eyeball, not an evaluation. Recall has a replicate set; precision would
need annotation.

**Where a model would and would not help.** The failures that exist are
concentrated in OCR-flattened lists, and that is precisely where an LLM would
win -- `tontonan film ..., pergelaran kesenian, musik, tari, ..., kontes
kecantikan, ...` is recognisably a twelve-item enumeration even with the
markers gone, and the boundary of the first item's `yang` clause is not
recoverable by any rule that does not already know the list. The distributive
head (74 cases) and the taxable/procedural split are also semantic and a model
would beat the current regexes on both.

Three reasons not to reach for one first. The ontology is the vocabulary that
`applies_to` is *scored against*, so building it neurally makes the extraction
metric circular. A hallucinated category is worse than a missing one: a missing
category fails loudly as `category_not_in_ontology`, while an invented id
silently participates in subsumption and can only produce wrong verdicts. And
it costs the one-neural-stage property, which is the paper's measurement story.

And there is a deterministic path that targets the actual failures. 19 of 24
documents yield the twelve-item list cleanly and UU 1/2022 yields it perfectly,
so the damaged copies can be recovered by *aligning* their flattened text
against the already-recovered statutory list -- the same cross-instrument
redundancy that settled the Perwal Jogja `67%`. That is verifiable, needs no
model, and would address 4 of the 5 failing documents. Try it before adding a
second neural stage.

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

