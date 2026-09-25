# covenant-extraction-eval

Structured extraction of financial covenants and key terms from SEC-filed credit agreements, with per-field accuracy against a hand-labeled set.

## Scope

Eleven fields per agreement: facility type, aggregate commitment, maturity, interest rate benchmark and margin, whether a margin grid exists, and — per financial covenant — type, initial threshold, step-down schedule, testing frequency, and springing trigger. Every extracted field carries a source citation. See [schema.md](schema.md) for types, where each field lives in an agreement, and the rule that decides whether an extracted value is correct.

**It was twelve. A field was cut on a trigger set before labeling began.** `facility_name` — the tranche's own label — carried a written instruction that if it ever required a third adjudication rule it should be cut rather than patched, because a field that keeps needing exceptions is not well defined. The third rule came due at the fourth document labeled, where an agreement names the same tranche twice in its own defined terms, in two incompatible styles, and the schema had no principled way to choose. It was cut.

This is worth stating plainly rather than leaving as a silent diff. A benchmark's credibility rests on its adjudication rules having been fixed in advance, and the way to demonstrate that is a rule that bound its author against his own preference at the moment it fired — not a schema in which every field happened to survive. The reasoning is in [labeling-notes.md](labeling-notes.md#facility_name--cut-not-patched); the cut itself is one commit, with the document that forced it named.

## Fields that test hallucination directly

Three fields are legitimately `null` on some agreements — `applicable_margin_bps`, `springing_trigger` and `aggregate_commitment` — and each is scored on null-vs-non-null before anything else.

This is deliberate, and it measures the failure mode that matters most for LLM extraction. Some credit agreements expressly defer a term to a document outside themselves: a ratings-based pricing grid whose opening level is set by a closing certificate not included in the exhibit states that the answer exists and declines to give it. The correct extraction is "the agreement does not state this." A model that confidently returns a plausible number is wrong, and wrong in the specific way that makes document AI dangerous in credit work — not by failing to find something, but by producing something that reads correctly and isn't.

Most extraction benchmarks score only whether the right value was found. This one also scores whether the system knows when there is no value to find. The guard is written into [schema.md](schema.md): `null` applies only where the agreement defers, never where the answer is merely buried or tedious to assemble — otherwise the field becomes an escape hatch and stops measuring anything.

**Deferral comes in two shapes, and they are not the same test.** One defers to an external *fact*: a ratings grid whose opening level depends on a credit rating that exists in the world and not in the document. The other defers to an *unattached exhibit*: a commitment amount that the agreement says is set out on a schedule the filer did not attach. Plains, Advance Auto and Roper are the first kind; Peloton is the second. A model declining on Peloton has noticed that a referenced part of the document is missing; a model declining on Advance Auto has recognised that the answer was never in the document at all. Both are correct and they are different capabilities, so they are reported separately rather than pooled into one null-detection number.

A `null` returned for a deferral must cite the deferral language itself. The value alone cannot distinguish a system that read the clause from one that declined out of vagueness; the citation can, and it does so through the citation check the harness already performs. Declining is only correct when the system can point at the sentence that made it decline.

**On few-shot examples:** any drawn for prompting come from documents outside the fifteen, and that is stated with the results. Examples taken from the held-out set would leak the answers the set exists to measure.

## Reporting

[results.md](results.md) fixes the shape results will be reported in, committed before any model was run. Every per-field number carries its instance count and **two baselines, which test different things**. The naive baseline is the majority-class guess — always answer the most common value, read nothing — and it asks whether reading the document helps at all; it is above 80% on `has_margin_grid`, `testing_frequency` and `step_down_schedule`. The regex baseline is the keyword extractor someone would build instead of an LLM, and it asks whether the expensive method beats the obvious one. A system can clear one and fail the other, so both appear beside every field score.

Results lead with `covenant_type`, because it is the field where a number means something without a caveat: eight of eleven enum values fired, no value dominates, and the naive baseline is roughly a quarter. On the skewed fields a high score is mostly the skew, which is why their baselines are printed next to them.

Every enum value appears in the table with `n = 0` where nothing fired, and the three values [schema.md](schema.md) pre-registered as possibly never firing are marked as such rather than pooled with the ones that simply did not come up. Pre-registered-and-empty and unexpectedly-empty are different claims.

The table is generated from the label files by `covenant-eval coverage`, not transcribed.

## Out of scope

**Baskets and mandatory prepayment triggers are deliberately excluded.** Both are real credit work — a covenant package without them is not a complete picture of a borrower's flexibility. Both are also miserable to label consistently: a basket is a network of cross-referenced defined terms, and two careful people reading the same restricted payments basket will disagree on what the right answer is. Ambiguous ground truth poisons a field-level accuracy metric, and that metric is this project's deliverable. Excluding them costs coverage and buys a number that means something.

Smaller exclusions, each argued at the field it belongs to in [schema.md](schema.md): Base Rate margins, covenant direction, incremental/accordion capacity, and springing maturity provisos.

## Prior art

[CUAD](https://www.atticusprojectai.org/cuad) — 510 EDGAR contracts expert-annotated across 41 clause categories — and the [ContractEval](https://arxiv.org/abs/2508.03080) benchmark supply the evaluation methodology used here: per-field F1 against a held-out set. CUAD's categories are legal clause types (governing law, renewal term, expiration). None of them are leverage ratios, pricing grids, or step-down schedules. There is no public benchmark for the financial terms of credit agreements, which is what the hand-labeled set in this repo is.

## Labeling notes

[labeling-notes.md](labeling-notes.md) records what labeling turns up: documented false-positive mechanisms for the baseline, found in real documents rather than hypothesized; schema changes made under contact with those documents, with the case that forced each one; and how disagreements between readers were resolved. The first agreement labeled produced all three.

**The baseline's errors are measured and directional, not assumed.** The comparison here is against a keyword/regex extractor, and a baseline whose failures nobody can articulate is not a fair comparison. Both directions are documented from real documents. The false positives are the interesting ones — template residue that asserts a margin is leverage-linked when the governing definition is flat. The false negatives are the larger ones: a keyword rule fires on the language it was written for and is silent on everything else, so it misses a debt-to-capitalization covenant sitting under a heading that reads "Financial Condition Covenant", and misses a five-level ratings grid because it was looking for the word "leverage". Measured against the documents read so far, the structure signal is right 3 of 6, and the grid signal 3 of 6 with every error a miss. Counting questions fail the other way: asked how many covenants an agreement has, the same approach answered four for an agreement with one, because three of the ratios it found are defined for incurrence tests and are not maintenance covenants at all. Existence questions under-report and counting questions over-report, and both produce a confident claim the document does not support.

That matters twice over, and the second time is uncomfortable: **this project used the same class of tool to help choose its own test set.** The selection signals in [corpus.md](corpus.md) came from that screen, so a document selected as "no grid" may have three. The defect is recoverable — selection signals are checkable by reading, and they are being re-checked by reading — but it is stated here rather than left for a reader to find, because a corpus rationale that inherited a tool's blind spot is exactly the kind of thing a benchmark should disclose about itself.

## Data

The hand-labeled set is committed to this repo. It is the part of the project that does not exist publicly, and a benchmark without its benchmark is not one.

The corpus is 15 syndicated credit agreements, $150M–$5B. Amendments are excluded — "Amendment No. 3 to Credit Agreement" is filed as EX-10.1 and contains none of these fields; amended and restated agreements are included and are the cleanest documents in the set. Accession numbers and the exact selection query are frozen in [corpus.md](corpus.md) before labeling begins, so the set is reconstructible rather than a pile of documents that happened to get picked. Full inclusion rule and sampling frame in [schema.md](schema.md).

**The corpus is stratified deliberately, not sampled at random.** A field whose gold value is constant across the set reports 100% accuracy and means nothing. Two fields were at risk, and the frame is built to prevent it: the date range straddles the LIBOR→SOFR transition so `interest_rate_benchmark` is a real classification rather than a constant, and the sample is stratified across revolver-only, revolver + TLA, and revolver + TLB structures so that `has_margin_grid` takes both values — institutional term loans are typically flat-priced, revolvers and pro rata tranches typically carry a grid — and so that cov-lite structures supply the empty-covenant-list case. Fifteen randomly drawn 2024 deals would be near-uniformly Term SOFR and would make the covenant fields look easier than they are.

Known limitation: banks, insurers, and REITs are excluded. Their covenant packages use a different taxonomy, which at this sample size would mean enum values appearing exactly once. The result therefore speaks to syndicated corporate credit agreements, not to credit agreements generally.

Sole annotator is the obvious objection. It is answered with a number rather than an assurance: five agreements are relabeled blind two weeks after the first pass, and intra-annotator agreement is reported per field.

Raw filings are not committed — they are large and re-downloadable from EDGAR full-text search, which covers every filing since 2001 including exhibits. Credit agreements are filed as EX-10 (Material Contracts) exhibits. Each label file records the accession number it was built from, so the corpus is reproducible from a clean checkout once the fetch script lands.

---

*Status: schema defined, nothing built yet.*
