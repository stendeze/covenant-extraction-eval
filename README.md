# covenant-extraction-eval

Structured extraction of financial covenants and key terms from SEC-filed credit agreements, with per-field accuracy against a hand-labeled set.

## Scope

Twelve fields per agreement: facility name and type, aggregate commitment, maturity, interest rate benchmark and margin, whether a margin grid exists, and — per financial covenant — type, initial threshold, step-down schedule, testing frequency, and springing trigger. Every extracted field carries a source citation. See [schema.md](schema.md) for types, where each field lives in an agreement, and the rule that decides whether an extracted value is correct.

## Fields that test hallucination directly

Two fields are legitimately `null` on some agreements — `applicable_margin_bps` and `springing_trigger` — and both are scored on null-vs-non-null before anything else.

This is deliberate, and it measures the failure mode that matters most for LLM extraction. Some credit agreements expressly defer a term to a document outside themselves: a ratings-based pricing grid whose opening level is set by a closing certificate not included in the exhibit states that the answer exists and declines to give it. The correct extraction is "the agreement does not state this." A model that confidently returns a plausible number is wrong, and wrong in the specific way that makes document AI dangerous in credit work — not by failing to find something, but by producing something that reads correctly and isn't.

Most extraction benchmarks score only whether the right value was found. This one also scores whether the system knows when there is no value to find. The guard is written into [schema.md](schema.md): `null` applies only where the agreement defers, never where the answer is merely buried or tedious to assemble — otherwise the field becomes an escape hatch and stops measuring anything.

## Out of scope

**Baskets and mandatory prepayment triggers are deliberately excluded.** Both are real credit work — a covenant package without them is not a complete picture of a borrower's flexibility. Both are also miserable to label consistently: a basket is a network of cross-referenced defined terms, and two careful people reading the same restricted payments basket will disagree on what the right answer is. Ambiguous ground truth poisons a field-level accuracy metric, and that metric is this project's deliverable. Excluding them costs coverage and buys a number that means something.

Smaller exclusions, each argued at the field it belongs to in [schema.md](schema.md): Base Rate margins, covenant direction, incremental/accordion capacity, and springing maturity provisos.

## Prior art

[CUAD](https://www.atticusprojectai.org/cuad) — 510 EDGAR contracts expert-annotated across 41 clause categories — and the [ContractEval](https://arxiv.org/abs/2508.03080) benchmark supply the evaluation methodology used here: per-field F1 against a held-out set. CUAD's categories are legal clause types (governing law, renewal term, expiration). None of them are leverage ratios, pricing grids, or step-down schedules. There is no public benchmark for the financial terms of credit agreements, which is what the hand-labeled set in this repo is.

## Labeling notes

[labeling-notes.md](labeling-notes.md) records what labeling turns up: documented false-positive mechanisms for the baseline, found in real documents rather than hypothesized; schema changes made under contact with those documents, with the case that forced each one; and how disagreements between readers were resolved. The first agreement labeled produced all three.

## Data

The hand-labeled set is committed to this repo. It is the part of the project that does not exist publicly, and a benchmark without its benchmark is not one.

The corpus is 15 syndicated credit agreements, $150M–$5B. Amendments are excluded — "Amendment No. 3 to Credit Agreement" is filed as EX-10.1 and contains none of these fields; amended and restated agreements are included and are the cleanest documents in the set. Accession numbers and the exact selection query are frozen in [corpus.md](corpus.md) before labeling begins, so the set is reconstructible rather than a pile of documents that happened to get picked. Full inclusion rule and sampling frame in [schema.md](schema.md).

**The corpus is stratified deliberately, not sampled at random.** A field whose gold value is constant across the set reports 100% accuracy and means nothing. Two fields were at risk, and the frame is built to prevent it: the date range straddles the LIBOR→SOFR transition so `interest_rate_benchmark` is a real classification rather than a constant, and the sample is stratified across revolver-only, revolver + TLA, and revolver + TLB structures so that `has_margin_grid` takes both values — institutional term loans are typically flat-priced, revolvers and pro rata tranches typically carry a grid — and so that cov-lite structures supply the empty-covenant-list case. Fifteen randomly drawn 2024 deals would be near-uniformly Term SOFR and would make the covenant fields look easier than they are.

Known limitation: banks, insurers, and REITs are excluded. Their covenant packages use a different taxonomy, which at this sample size would mean enum values appearing exactly once. The result therefore speaks to syndicated corporate credit agreements, not to credit agreements generally.

Sole annotator is the obvious objection. It is answered with a number rather than an assurance: five agreements are relabeled blind two weeks after the first pass, and intra-annotator agreement is reported per field.

Raw filings are not committed — they are large and re-downloadable from EDGAR full-text search, which covers every filing since 2001 including exhibits. Credit agreements are filed as EX-10 (Material Contracts) exhibits. Each label file records the accession number it was built from, so the corpus is reproducible from a clean checkout once the fetch script lands.

---

*Status: schema defined, nothing built yet.*
