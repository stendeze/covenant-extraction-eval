# Labeling Notes

A running log of what labeling actually turns up: traps the baseline will fall
into, schema ambiguities found by hitting them, and how disagreements were
resolved.

Kept separate from [schema.md](schema.md) because that document states the
rules and this one records the evidence that produced them. When a note here
changes a rule, the rule moves to schema.md and the note stays as the reason.

---

## Baseline false-positive mechanisms

Documented failure modes for the keyword/regex baseline, found in real
documents rather than hypothesized. These matter because the headline number
is extraction accuracy *against a baseline* — a baseline that fails for
reasons nobody can articulate is not a fair comparison, and one whose failures
are characterized is.

### Template residue links a flat margin to a leverage ratio

**Found in:** Paya Holdings, 2021-06-25 (`0001213900-21-034493`)
**Affects:** `has_margin_grid`
**Baseline verdict:** `true` · **Correct verdict:** `false`

The Pro Forma Basis provision reads:

> when calculating the Consolidated First Lien Net Leverage Ratio for purposes
> of determining (i) the Applicable Rate, (ii) the Applicable Commitment Fee
> and (iii) actual compliance ... with the Financial Covenant

That sentence asserts the Applicable Rate is determined by reference to a
leverage ratio. It is not. The `Applicable Rate` definition in the same
document is two flat percentages — 3.25% for Eurocurrency Rate Loans and 2.25%
for Base Rate Loans, identical across both tranches, with no levels and no
step-downs. The leverage ratio genuinely drives the *commitment fee* grid; the
reference to the Applicable Rate is residue from a template drafted for a deal
that had a margin grid.

Any baseline matching `Applicable Rate` within a window of `Leverage Ratio`
scores `true` here and is wrong. So does one keyed on "Pricing Level", which
appears in this document exclusively in the commitment-fee grid.

**Why this is not a fixable baseline bug.** The distinguishing evidence is the
*absence* of levels inside one definition, while a nearly identical
construction with levels sits elsewhere in the same document. Resolving it
requires reading the definition that governs, not matching a pattern near it.
That is the gap the extraction system is supposed to close, and this is a
measured instance of it rather than an assertion.

### Eurocurrency usage is not a LIBOR tell after 2023

**Affects:** `interest_rate_benchmark`, and corpus selection

Counting "Eurodollar"/"Eurocurrency" separates LIBOR-priced from SOFR-priced
agreements only for filings up to roughly mid-2022. In later agreements the
same words appear as ordinary multicurrency terminology: Federal Signal
(2025), Altice USA (2025) and Vertex (2024) all show heavy Eurocurrency usage
with no LIBOR pricing anywhere. Used as a ranking signal for corpus selection,
not as a label.

---

## Schema changes made under contact

### `has_pricing_grid` → `has_margin_grid`

**Trigger:** document one, Paya Holdings.

The rule always said `true` when *the applicable margin* varies. The field
*name* asked a broader question — "is there a pricing grid?" — and Paya has a
three-level grid on the `Applicable Commitment Fee` while its margin is flat.
Both readings were defensible under the old name; only one is under the new
one.

Renaming was preferred to tightening the rule text, because the ambiguity
would otherwise have to be re-resolved at every document, and fifteen
independent resolutions of the same ambiguity is exactly how a single
annotator becomes inconsistent with themselves.

A `has_commitment_fee_grid` field is a v2 candidate if fee grids prove common.
Deliberately not added mid-labeling: it would invalidate work already done for
a term the schema does not claim to extract.

### `applicable_margin_bps` — nullable when the agreement defers

**Trigger:** document two, Plains GP Holdings.

The opening-margin rule assumed a leverage grid keyed to compliance
certificates, where "no opening level stated" means the agreement is silent and
the conservative reading is the most expensive level. Plains is not silent. Its
ratings grid says *"Initially, the Applicable Rate shall be determined based
upon the Debt Rating specified in the certificate delivered pursuant to Section
4.01(a)(vii)"* — a certificate not in the exhibit. The agreement knows the
answer exists and declines to state it.

Applying the silence fallback would have recorded 175bps, the Level 5 rate for
a `BB+ / Ba1 or lower` borrower, for an investment-grade MLP actually pricing
three or four levels tighter. Resolving it from external ratings data would
have measured whether the model memorized Plains' August 2021 credit rating.

The field is now nullable, scored null-vs-non-null first, with an explicit
guard that `null` applies only where the agreement defers — not where the
answer is buried, cross-referenced or tedious. Without that limit the field
becomes an escape hatch for anything hard.

This is an improvement to the eval rather than a concession. Hallucination
under uncertainty is the central failure mode of LLM extraction, and there is
now a field class that tests it directly: a model that declines is right, one
that produces a confident 175 is wrong.

### `interest_rate_benchmark` — added `cdor`

**Trigger:** document two, Plains GP Holdings.

Plains' `Eurocurrency Rate` definition has two limbs — Dollar borrowings price
off LIBOR, Canadian Dollar borrowings off CDOR. The existing "primary
benchmark" rule already resolves this document to `libor`, so no label changed.
`cdor` was added anyway, on the same reasoning that kept
`debt_service_coverage`: a purely additive enum value cannot alter an existing
label, and the alternative is forcing `other` on the first CAD-primary
agreement to appear mid-labeling.

### `maturity_date` — the "earliest of" construction

**Trigger:** document one, Paya Holdings.

The springing-maturity rule covered provisos referencing an external
instrument. It did not cover the near-universal "earliest of (i) a stated
date, (ii) termination in whole, (iii) acceleration" construction, which is
termination mechanics rather than an alternative maturity. Every agreement in
the corpus will have some version of it, so the rule now says explicitly to
record limb (i).

---

## Disagreements and how they resolved

### Paya Holdings — `has_margin_grid`

Two readers labeled this document independently and disagreed on one field.
One searched for a margin grid, found the `Applicable Rate` flat, and recorded
`false`. The other found the commitment-fee grid and argued the field as named
could reasonably be read `true`.

**Resolution:** read the governing definitions rather than argue from the
field name. The margin is flat; the fee grid is real; both readings were
faithful to the document and the field name was the thing at fault. The label
did not change — **the schema did**.

This is worth recording for what it demonstrates about method, not about this
document. The intra-annotator agreement check in
[schema.md](schema.md#annotator-agreement) exists because a sole annotator
cannot report inter-annotator agreement. Here that process ran early, with a
second party, before the corpus was labeled — and it did what it is supposed
to do: a field where two careful readers disagree is a field whose
adjudication rule is underspecified. The disagreement was resolved by
tightening the schema and re-applying it, not by picking the better-looking
label.

It also sets the expectation for the formal check. Disagreements found there
should be handled the same way: fix the rule, re-apply it to the full set,
report the rate as measured rather than as repaired.

---

## Per-document observations

### Plains GP Holdings / All American Pipeline, L.P. — 2021-08-20 — `0001104659-21-109833`

- **Benchmark is LIBOR**, in two hops rather than Paya's three: `Applicable
  Rate` attaches to Eurocurrency Rate Loans, and `Eurocurrency Rate` names the
  rate outright — "the London Interbank Offered Rate ("LIBOR"), as published on
  the applicable Reuters Screen page ... 11:00 a.m., London time". No
  intermediate `Screen Rate` definition. All 14 SOFR mentions are Benchmark
  Replacement machinery, one of which states it plainly: "if the then-current
  Benchmark is LIBOR, the Benchmark Replacement will replace such Benchmark."
- **`has_margin_grid` is true** — five levels keyed to S&P/Moody's Debt Rating,
  1.000% to 1.750% on Eurocurrency loans, with the commitment fee in the same
  table.
- **A useful contrast with Paya on exactly that field.** Paya has a grid table
  that is *not* a margin grid; Plains has one that is. A labeler who learned
  "grid table means margin grid" from this document would get Paya wrong, and
  vice versa. The two documents together are why the field was renamed rather
  than merely re-described.
- **`applicable_margin_bps` is null** — see the schema change above.
- **Multicurrency**: CAD borrowings price off CDOR, USD off LIBOR. Resolved to
  `libor` by the primary-benchmark rule; `cdor` added to the enum against a
  future CAD-primary agreement.

### Paya Holdings III, LLC — 2021-06-25 — `0001213900-21-034493`

- **Benchmark is LIBOR**, resolved in three hops: `Applicable Rate` attaches to
  Eurocurrency Rate Loans → `Eurocurrency Rate` is the `Screen Rate` at 10:00
  a.m. London time → `Screen Rate` is "the London interbank offered rate as
  administered by ICE Benchmark Administration ... pages LIBOR01 or LIBOR02 of
  the Reuters screen". All sixteen SOFR mentions in the document sit inside
  Benchmark Replacement machinery — the successor, not the rate in effect.
- **Same 325bps margin on both the $45M revolver and the $250M TLB**, which is
  unusual; revolvers normally price tighter. Read as a small revolver treated
  as an accommodation alongside the institutional tranche rather than
  separately negotiated.
- **Initial Term Loans carry a 0.75% LIBOR floor.** Not a schema field, but it
  means `applicable_margin_bps` alone understates the effective pricing.
- **`facility_type` came from amortization, not the name.** Labeled "Initial
  Term Loans" with no letter; §2.07(a) sets quarterly installments at 0.25% of
  original principal — 1.00% per annum — so `term_loan_b`.
- **The L/C sublimit exclusion did real work.** The $10,000,000 Letter of
  Credit Sublimit is "part of, and not in addition to, the Revolving Credit
  Facility". Booking it as a facility would have reported $55M of revolver
  against an actual $45M.
- **Covenant is springing but not expressly for revolving lenders.** §7.08
  tests First Lien Net Leverage at 6.50:1.00 only when revolver utilization
  exceeds 35.0%, excluding cash-collateralized and undrawn letters of credit.
  A search for an express "benefit of the Revolving Credit Lenders" carve-out
  or a revolver-only waiver right found none. The protection here is economic
  — the covenant only bites when the revolver is drawn — rather than a stated
  beneficiary restriction, and the free-text note should say that rather than
  imply the latter. Not exhaustively verified against §10.01.
