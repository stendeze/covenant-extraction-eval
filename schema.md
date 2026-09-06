# Extraction Schema and Labeling Protocol

The target schema for structured extraction from credit agreements, the rule
for which documents enter the corpus, the adjudication rules that decide
whether an extracted value is correct, and the labeling budget those rules
imply.

The adjudication rules are the load-bearing part of this document. "Leverage
covenant" sounds unambiguous until you hit an agreement with a springing
covenant, three step-downs, and a different level for the first four quarters.
Every rule below exists because a specific real case would otherwise produce
two defensible answers, and a field with two defensible answers cannot be
scored.

---

## Corpus selection

"20 credit agreements" is not a reproducible test set. This section is the
inclusion rule and the sampling frame, and it is frozen before labeling
begins.

### What counts as a credit agreement

EX-10 is the Material Contracts category generally, so a naive full-text pull
returns employment agreements, leases, security agreements, and — the trap —
amendments.

**Included:**

- Credit agreements, term loan agreements, and revolving credit agreements.
- **Amended and Restated agreements.** These are in scope and are in practice
  the cleanest documents in the corpus: a full restatement carries the whole
  covenant package inline rather than by reference.

**Excluded:**

- **Amendments that are not restatements.** "Amendment No. 3 to Credit
  Agreement" is filed as EX-10.1 and contains none of these fields. It says
  *"Section 6.12(a) is hereby amended by replacing '4.50' with '4.25'."* The
  fields exist only in the agreement being amended. Detection rule: the
  document has no Article I definitions section and no §2.01 commitment
  section, or its title matches `amendment|waiver|consent|joinder` without
  also matching `amended and restated`.
- Security agreements, pledge agreements, guarantees, and intercreditor
  agreements — liens and priority, not economic terms.
- Commitment letters and fee letters — not binding facility documentation.
- Note purchase agreements and indentures — bonds, different covenant grammar.
- Documents under ~30 pages, which are almost never full agreements.

### Sampling frame

| Dimension | Frame | Why |
|-----------|-------|-----|
| Filing date | 2021-06-01 to present | Straddles the LIBOR→SOFR transition deliberately, see below |
| Aggregate commitments | $150M – $5B | Below is bilateral/middle-market with idiosyncratic drafting; above is mega-cap with bespoke structures |
| Syndication | Syndicated only — an Administrative Agent and ≥3 lenders on the commitment schedule | Bilateral agreements have no margin grid and often no agent, which degenerates two fields |
| Borrower | US corporate, English language | — |
| Borrower sector | Excludes banks, insurers, and REITs | See limitation below |

**The sector exclusion is a limitation, not a design win.** Banks, insurers,
and REITs are excluded because their covenant packages use a different
taxonomy — unencumbered asset tests, regulatory capital ratios, fixed charge
coverage defined off funds from operations — which at fifteen documents would
mean enum values that appear exactly once and cannot be scored. That is the
right call for a set this size, and it narrows what the result generalizes to.
The honest claim is field-level accuracy on syndicated corporate credit
agreements, not on credit agreements.

### Class balance

A field whose gold value is constant across the corpus cannot be scored
meaningfully. 100% accuracy on `interest_rate_benchmark` proves nothing if
every document in the set is Term SOFR. Two fields are at risk and the frame
is set to avoid it:

- **`interest_rate_benchmark`** — the date range starts pre-transition so that
  roughly 3 of 15 agreements are LIBOR. Without them the field is degenerate.
- **`has_margin_grid`** — stratify to get both. Institutional TLBs are
  typically flat-priced; revolvers and pro rata TLAs typically have a grid, so
  structural variety supplies this for free.

Stratify the sample across three facility structures: revolver-only,
revolver + TLA (pro rata), and revolver + TLB (institutional). The covenant
fields behave differently across them — cov-lite TLBs yield an empty covenant
list, and springing covenants cluster in revolver-only and TLB structures. A
corpus of fifteen pro rata deals would make the covenant fields look easier
than they are.

### Freezing

The accession numbers are selected, listed, and committed **before** labeling
starts and before any model output is looked at. A corpus chosen after seeing
which documents the system handles well is not a held-out set. If a document
turns out to be unlabelable — truncated exhibit, scanned image, wrong document
type that passed the filter — it is replaced and the replacement is recorded
in the corpus file with the reason.

---

## Record shape

One agreement produces one record. Facilities and financial covenants are
lists, because a single credit agreement routinely has a revolver plus one or
more term tranches, and two or three financial covenants tested against the
same borrower.

```
Agreement
├── source            (provenance, not scored)
├── facilities[]      (7 scored fields each)
└── financial_covenants[]  (5 scored fields each)
```

Financial covenants sit at the agreement level, not inside a facility. In a
real capital structure they are tested against the consolidated borrower, not
against a tranche. The common exception — a cov-lite term loan B where the
leverage covenant runs for the benefit of the revolving lenders only — is
captured in the covenant's own adjudication rule rather than as a separate
field.

---

## Field summary

| # | Field | Level | Type |
|---|-------|-------|------|
| 1 | `facility_name` | facility | string |
| 2 | `facility_type` | facility | enum |
| 3 | `aggregate_commitment` | facility | {amount: integer, currency: ISO 4217} |
| 4 | `maturity_date` | facility | {value: date \| string, basis: enum} |
| 5 | `interest_rate_benchmark` | facility | enum |
| 6 | `applicable_margin_bps` | facility | integer |
| 7 | `has_margin_grid` | facility | boolean |
| 8 | `covenant_type` | covenant | enum |
| 9 | `initial_threshold` | covenant | number |
| 10 | `step_down_schedule` | covenant | array of {effective_from, threshold} |
| 11 | `testing_frequency` | covenant | enum |
| 12 | `springing_trigger` | covenant | object \| null |

Twelve scored fields. Every one of them carries a citation (see
[Citations](#citations)), which is validated but scored separately.

---

## Facility fields

### 1. `facility_name`

**Type:** string — the borrower's own label for the tranche.

**Where it lives:** the definitions in Article I ("Revolving Credit Facility",
"Term A Loans", "Initial Term Loans"); the commitment section, usually §2.01;
the cover page; and the commitment schedule, usually Schedule 1.01 or 2.01.

**Correct when:** the string matches gold after normalization — lowercase,
strip leading articles, strip punctuation, collapse whitespace. So "the
Revolving Credit Facility" and "Revolving Credit Facility" match; "Revolving
Facility" and "Revolving Credit Facility" do not.

This is the weakest-signal field in the schema and it is reported separately
from the headline number. It exists because it is what a human reviewer keys
off, and because a model that cannot name the tranche it just extracted is
telling you something. `facility_type` carries the semantic weight.

### 2. `facility_type`

**Type:** enum — `revolver`, `term_loan_a`, `term_loan_b`,
`delayed_draw_term_loan`, `bridge`, `other`.

**Where it lives:** inferred from the same places as `facility_name`, plus the
amortization schedule (a 1%/yr amortizing institutional tranche is a TLB; a
5–10%/yr amortizing pro rata tranche is a TLA).

**Correct when:** the enum value matches exactly. Adjudication rules:

- Where the agreement labels a tranche "Term A" / "Term B" explicitly, that
  label governs, even if the amortization profile is unusual.
- Where it says only "Term Loans" with no letter, classify by amortization:
  ≤1%/yr → `term_loan_b`, more → `term_loan_a`.
- **Letter of credit and swingline sublimits are not facilities.** They are
  carve-outs of the revolving commitment and creating a separate record for
  them double-counts the commitment. No record.
- **Incremental / accordion / "Incremental Facilities" are not facilities.**
  They are an option to raise debt later, not a commitment made at signing. No
  record. This is the single most common source of an inflated commitment
  total, and excluding it is a deliberate choice, not an oversight.
- A delayed draw term loan *is* a facility — the commitment is made, only the
  funding is deferred.

### 3. `aggregate_commitment`

**Type:** object — `{amount: integer, currency: ISO 4217 code}`. Amount in
whole units of the currency, not millions. $500,000,000 is `500000000`.

**Where it lives:** §2.01; the defined term "Aggregate Commitments" / "Total
Revolving Commitment" / "Term Loan Commitment" in Article I; the lender-by-
lender commitment schedule; and the recitals, which often state the headline
size.

**Correct when:** amount and currency both match exactly. Adjudication rules:

- Record the commitment **at closing**, as stated in the document under
  review. Not as later amended, not net of any incremental capacity.
- Where the lender-by-lender schedule and the defined term disagree (it
  happens, usually a drafting error), the defined term governs and the
  discrepancy is noted in the label file.
- For a multicurrency facility, record the commitment in the currency the
  agreement uses to express the aggregate, which is nearly always USD with a
  sublimit expressed in the alternative currency. The sublimit is not a
  separate facility.

### 4. `maturity_date`

**Type:** object — `{value, basis}` where `basis` is `stated` (value is an
ISO-8601 date) or `relative` (value is the verbatim formulation, e.g. "the
fifth anniversary of the Closing Date").

**Where it lives:** the Article I definitions — "Maturity Date", "Revolving
Maturity Date", "Term Loan Maturity Date".

**Correct when:** `basis` matches and, for `stated`, the date matches exactly;
for `relative`, the normalized string matches. Adjudication rules:

- Where the agreement gives a hard date, `basis` is `stated` even if it also
  describes the date as an anniversary.
- **The "earliest of" construction is ordinary and does not change the
  answer.** Nearly every agreement defines maturity as the earliest of (i) a
  stated calendar date, (ii) the date the commitments are terminated in whole,
  and (iii) the date the loans are declared due and payable on acceleration.
  Limbs (ii) and (iii) are termination and acceleration mechanics, not
  alternative maturities — they describe what happens when the deal ends
  early, which is true of every facility ever written. Record the stated
  calendar date from limb (i). This is distinct from the springing-maturity
  case below, which turns on an instrument outside the document rather than on
  the parties' own termination rights.
- **Springing maturity provisos are excluded from this field.** A clause like
  "or, if earlier, the date 91 days prior to the stated maturity of the Senior
  Notes" makes the actual maturity contingent on an instrument outside this
  document. Record the stated maturity; note the springing proviso in the
  label file's free-text notes. This is a known limitation and it is the right
  trade: resolving it correctly requires the notes indenture, which is not in
  the corpus.

### 5. `interest_rate_benchmark`

**Type:** enum — `term_sofr`, `daily_simple_sofr`, `libor`, `euribor`, `cdor`,
`base_rate`, `prime`, `other`.

**Where it lives:** the Article I definitions of "Term SOFR", "Adjusted Term
SOFR", "Benchmark", "Base Rate" / "ABR"; and the interest section in Article
II.

**Correct when:** the enum matches exactly. Adjudication rules:

- Record the **primary floating benchmark**, i.e. the one applicable to the
  borrowings the agreement expects to be outstanding. Essentially every US
  agreement also permits Base Rate borrowings as an alternative; that
  alternative is not the answer.
- Post-2022 agreements are almost entirely Term SOFR. Pre-2022 agreements are
  LIBOR and typically contain benchmark replacement language; the benchmark
  replacement provision does **not** change the answer, which is `libor` — the
  field records the benchmark in effect, not its successor.
- `adjusted` variants (Adjusted Term SOFR, i.e. Term SOFR plus a credit spread
  adjustment) map to the unadjusted enum value. The CSA is not part of this
  field.
- **Multicurrency facilities still get one value.** A "Eurocurrency Rate" whose
  definition prices Dollar borrowings off LIBOR and Canadian Dollar borrowings
  off CDOR is `libor` — the alternative-currency limb is not the primary
  benchmark. `cdor` exists for the agreement whose primary borrowings are in
  Canadian Dollars. Like `debt_service_coverage`, it may never fire; an unused
  enum value costs nothing, and the alternative is forcing `other` on the one
  agreement that needs it mid-labeling.

### 6. `applicable_margin_bps`

**Type:** integer or `null` — basis points over the benchmark.

**Where it lives:** the Article I definition of "Applicable Margin" or
"Applicable Rate", which very often contains the pricing grid table inline.

**Correct when:** the integer matches exactly, or `null` matches `null`.
Adjudication rules:

- Record the **opening margin**: the rate in effect from the Closing Date
  until the first compliance certificate is delivered. Most agreements state
  this explicitly ("Level III shall apply from the Closing Date until...").
- Where the agreement is **silent** on the opening level, record the highest
  (most expensive) level in the grid, and flag the label. This is the
  conservative reading and it is applied consistently, which matters more than
  which convention is chosen.
- **Where the agreement expressly defers determination to a document or fact
  outside its four corners, the value is `null`.** The distinction from the
  rule above is between an agreement that is *silent* and one that is
  *explicit that the answer is elsewhere*. A ratings grid that says "Initially,
  the Applicable Rate shall be determined based upon the Debt Rating specified
  in the certificate delivered pursuant to Section 4.01(a)(vii)" is the second
  case: the opening level exists, the agreement knows it exists, and the
  agreement declines to state it.

  Applying the silence fallback there would record the most expensive level for
  an investment-grade borrower — a number that is wrong, and wrong in a way
  that penalizes a model for correctly declining to invent one. Resolving it
  from external ratings data would measure whether the model memorized credit
  ratings rather than whether it can extract from a document.

  **Guard against overuse.** `null` applies only where the agreement defers,
  not where the answer is merely buried, cross-referenced within the document,
  or tedious to assemble. An answer that requires reading three definitions in
  this agreement is an integer, not a `null`. Without this limit the field
  becomes an escape hatch for anything hard, which would make it worthless as
  a measurement.

  Scored as null-vs-non-null first, then on the integer where both are
  non-null — the same pattern `springing_trigger` already uses, so this adds
  no new scoring machinery.
- Record the margin for **benchmark loans**, not Base Rate loans. The Base
  Rate margin is mechanically the benchmark margin minus 100bps in nearly
  every agreement, so labeling it separately doubles the work for close to
  zero information. Deliberately not a field.
- Where the agreement expresses the margin as a percentage (2.25%), convert to
  bps (225).

### 7. `has_margin_grid`

**Type:** boolean.

> Renamed from `has_pricing_grid` after labeling document one. The old name
> asked a broader question than the rule answered — see
> [Margin grids vs. fee grids](#margin-grids-vs-fee-grids) below.

**Where it lives:** same definition as `applicable_margin_bps`; sometimes a
standalone "Pricing Grid" schedule.

**Correct when:** the boolean matches. Adjudication rules:

- `true` when **the applicable margin** varies with a measured condition — a
  leverage ratio, a total net leverage ratio, a ratings grid, or a utilization
  grid.
- `false` when the margin is flat for the life of the facility.
- A **single step-down on a one-time event** (a leverage-based step-down at
  first test date only, or an IPO step-down) is `true`. The distinction the
  field draws is fixed-vs-variable pricing, not the number of rows in the
  table.
- MFN / most-favored-nation provisions and pricing that changes only on
  default are not grids. `false`.

#### Margin grids vs. fee grids

**A grid on the commitment fee is not a margin grid.** `false` is correct for
an agreement whose interest margin is flat even when its undrawn commitment
fee steps with leverage.

This is not hypothetical. The first agreement labeled — Paya Holdings,
June 2021 — prices both tranches at a flat 3.25% over the Eurocurrency Rate
with no levels at all, and carries a full three-level grid on the
`Applicable Commitment Fee`, keyed to the same First Lien Net Leverage Ratio
that would key a margin grid (0.500% above 3.75x, 0.375% between 3.25x and
3.75x, 0.250% below), complete with "Pricing Level" labels and a
compliance-certificate reset. Asked "does this agreement have a pricing
grid?", two careful readers answer differently. Asked "does the margin vary?",
they do not.

Hence the rename: the field name now asks the question the rule answers.

If commitment-fee grids turn out to be common across the corpus, a separate
`has_commitment_fee_grid` field is a candidate for v2. It is deliberately not
added now — adding a field mid-labeling would mean relabeling everything
already done, for a term that is not among the ones this schema claims to
extract.

---

## Covenant fields

If an agreement has no financial covenants at all — a genuinely cov-lite term
loan B — the gold list is empty. That is a real and correct answer, not a
labeling failure, and a model that invents a covenant there is penalized
exactly as it should be.

### 8. `covenant_type`

**Type:** enum — `total_net_leverage`, `first_lien_net_leverage`,
`secured_net_leverage`, `total_leverage_gross`, `interest_coverage`,
`fixed_charge_coverage`, `debt_service_coverage`, `minimum_liquidity`,
`capex_limit`, `other`.

**Where it lives:** the financial covenants section — Article VI or VII, the
section number varies (§6.12, §7.11, §6.10 are all common); and the Article I
definitions of the ratio itself ("Consolidated Total Net Leverage Ratio") and
its inputs ("Consolidated EBITDA", "Consolidated Total Debt").

**Correct when:** the enum matches exactly. Adjudication rules:

- Classify by the **defined ratio's own definition**, not by its label. A
  covenant labeled "Leverage Ratio" whose definition nets unrestricted cash
  and counts only first lien debt is `first_lien_net_leverage`.
- Netting is determined by whether the debt definition subtracts cash. If it
  does, it is a `net` variant; if not, `total_leverage_gross`.
- Direction is **not a field**. It is fully determined by type: leverage
  covenants are maximums, coverage covenants and liquidity minimums are
  minimums. Adding a direction field would be a field that is right by
  construction and would inflate the accuracy number.
- Where a covenant runs for the benefit of revolving lenders only (the
  standard cov-lite structure), it is still recorded — it is a financial
  covenant in this agreement. The beneficiary is noted in free text.

`debt_service_coverage` will almost certainly never fire in this corpus. DSCR
is project and infrastructure finance; corporate syndicated credit uses
interest coverage or fixed charge coverage. The enum value stays because
removing it would force an `other` on the one deal that has it, but an empty
column for it is the expected result, not a labeling gap.

### 9. `initial_threshold`

**Type:** number — the level applicable at the first test date. Ratios to two
decimals (`4.00`); dollar thresholds as integers in whole currency units.

**Where it lives:** the financial covenants section, frequently as a table of
fiscal periods against levels.

**Correct when:** the number matches exactly after normalization. Adjudication
rules:

- Record the level at the **first test date**, which is the top row of the
  step-down table — not the final level, and not the level "thereafter".
- Where the agreement expresses the ratio as "4.00:1.00" or "4.00 to 1.00",
  normalize to `4.00`.
- Where there is a separate, higher level for an acquisition holiday
  (a "Covenant Holiday" or leverage step-up following a material acquisition),
  record the **non-holiday** level. The holiday is a conditional override, not
  the covenant level.

### 10. `step_down_schedule`

**Type:** array of `{effective_from: date, threshold: number}`, ordered by
`effective_from`. `effective_from` is the ISO-8601 **end date of the first
fiscal period at the new level**.

**Where it lives:** same table as `initial_threshold`.

**Correct when:** the arrays match as ordered sequences — same length, and
every pair matches on both keys. A partial match is scored as a miss on this
field; per-step credit is reported separately as a diagnostic.

Adjudication rules:

- `[]` means the covenant level is flat for the life of the agreement.
  Confirmed flat, not unknown.
- The `initial_threshold` is **not** repeated as the first element. The array
  holds only changes from the initial level.
- Where the table's periods are described relative to fiscal quarters ("the
  fiscal quarter ending closest to June 30, 2026"), record the date the
  agreement itself states. Do not attempt to resolve a 52/53-week fiscal
  calendar to a real date — the calendar is not in the document.
- The final "and thereafter" row is a step-down like any other; the absence of
  an end date is expected.

### 11. `testing_frequency`

**Type:** enum — `quarterly`, `monthly`, `semiannual`, `annual`,
`event_driven`.

**Where it lives:** the lead-in to the covenants section — "as of the last day
of each fiscal quarter of the Borrower".

**Correct when:** the enum matches exactly.

**Adjudication rule that matters:** `springing` is not a frequency. A springing
covenant is still tested quarterly; it is *conditional*, not *infrequent*.
Conditionality lives in `springing_trigger`. Conflating the two is the single
most common way this field gets labeled inconsistently by two careful people,
which is exactly why it is split.

### 12. `springing_trigger`

**Type:** object or `null`. When non-null:
`{condition_type: enum, threshold: number, threshold_unit: enum, quote: string}`
where `condition_type` is `revolver_utilization`, `minimum_availability`, or
`other`, and `threshold_unit` is `percent` or `currency`.

**Where it lives:** the proviso in the covenants section, or a defined term —
"Covenant Trigger Event", "Financial Covenant Test Period", "Testing Period".

**Correct when:** null-vs-non-null is correct, and where non-null,
`condition_type` and `threshold` both match.

Adjudication rules:

- `null` means the covenant is tested unconditionally every period. This is
  the majority case and it is cheap to label, which is what keeps this field
  affordable.
- The typical trigger is revolver utilization above a threshold (commonly 35%
  or 40% of commitments) measured on the last day of a fiscal quarter. Record
  the percentage as a number: 35% → `35`, unit `percent`.
- Where the trigger is expressed as minimum availability in dollars rather
  than utilization as a percentage, `condition_type` is `minimum_availability`
  and the unit is `currency`.
- Where letters of credit are excluded from the utilization calculation (very
  common — undrawn LCs up to some amount do not count toward the trigger),
  that exclusion is noted in free text and does not change the threshold.

---

## Citations

Every scored field carries a citation:

```json
{
  "value": 200,
  "citation": {
    "section": "1.01 (definition of \"Applicable Margin\")",
    "quote": "2.00% per annum in the case of Term Benchmark Loans"
  }
}
```

The `quote` must appear **verbatim** in the source document. That is
mechanically checkable without any human labeling, which makes it a free
hallucination guardrail: a citation that does not appear in the text is an
automatic failure regardless of whether the extracted value happened to be
right.

**Character offsets are not labeled by hand.** The span is derived
programmatically from the quote by substring search at scoring time. Hand-
locating offsets across ~360 field instances is the most painful thing this
schema could ask for and it buys nothing the quote does not already buy. If a
quote matches at more than one offset the first is taken; ambiguity there is
irrelevant, since the check is whether the language exists in the document at
all.

Citation accuracy is scored and reported **separately** from field accuracy.
The two questions — did it get the number right, and can it show you where the
number came from — are different, and a system that is right for the wrong
reason should not be able to hide inside a single aggregate.

---

## Record alignment

Facilities and covenants are lists, so predicted items must be aligned to gold
items before any field can be scored. Without a stated alignment rule, the
accuracy number is not reproducible.

- **Facilities** align on `facility_type`. Where an agreement has two tranches
  of the same type (two TLBs, or a USD and a EUR revolver), align on
  `(facility_type, aggregate_commitment.currency)`, then on commitment amount
  descending.
- **Covenants** align on `covenant_type`.
- A predicted item with no gold match is a **spurious record** — every one of
  its fields counts against precision.
- A gold item with no predicted match is a **missed record** — every one of
  its fields counts against recall.

Reporting per-field F1 rather than raw accuracy follows CUAD and ContractEval,
which is the point: the methodology is borrowed so that the numbers are
comparable to published work, and the schema is the new part.

---

## Labeling budget

Twelve fields sounds small. It is not, because they are nested.

A two-tranche, two-covenant agreement — the modal deal in this frame — is:

```
7 facility fields  × 2 facilities =  14
5 covenant fields  × 2 covenants  =  10
                                    ---
                                     24 field instances
```

Each of those carries a section reference and a verbatim quote. At 15
documents that is **~360 labeled values and ~720 supporting citations**; at 20
it is ~480 and ~960.

**Plan for 15.** Extend to 20 only if the first five go faster than expected.
A complete, carefully adjudicated 15 beats a rushed 20, and the held-out set
is the credibility of the whole project — it is the wrong place to be tired.

If the budget needs cutting further, the order is:

1. **`facility_name`** goes first. It is already argued above as the weakest
   signal and already reported separately from the headline number, so
   dropping it costs the least. That removes 1 instance per facility.
2. **`step_down_schedule`** is the most expensive single field — it is an
   array, and it requires reading a table carefully. But it is also one of the
   most interesting results, since it is where regex baselines fail hardest.
   Cut it only if the alternative is not finishing.

Do not cut the corpus below 15. Fewer documents means every per-field number
is computed over a handful of instances and the confidence intervals swallow
the result.

### What this sample size can support

Fifteen documents is the right trade for three weeks, and it constrains what
can honestly be claimed. Per-field F1 computed over ~15 instances carries
intervals wide enough that small differences between ablation arms are not
distinguishable from noise.

The consequence is a design constraint, not a caveat to bury in a footnote:
**the ablation must be built to show large effects or none.** Compare
conditions expected to differ substantially — retrieval versus a context
window truncated hard enough to actually drop the covenant section, schema-
enforced output versus free text — rather than conditions expected to differ
by a few points.

And when a gap is small, the finding is **"no measurable difference at this
sample size."** That sentence is stronger than a four-point improvement the
data cannot support, and an interviewer who knows how to read an evaluation
will treat it as such. The failure mode this project is exposed to is not a
disappointing result; it is a confident one that does not survive a question
about n.

---

## Annotator agreement

Sole annotator is the obvious attack on this entire project, and it is worth
answering with a measurement rather than an assurance.

**Protocol:** two weeks after the initial pass, relabel **five agreements
blind** — original labels not consulted, ideally not even opened — and report
the agreement rate between the two passes, per field.

This costs a couple of hours. It converts "I labeled these myself" from an
unmeasured weakness into a stated limitation with a number attached, and it
does something more useful besides: any field where you disagree with yourself
is a field whose adjudication rule is underspecified. Intra-annotator
agreement doubles as a test of this document.

Published benchmarks report inter-annotator agreement. A single annotator
cannot, but intra-annotator agreement is the honest available substitute and
reporting it is strictly better than reporting nothing. Disagreements found
this way are resolved by tightening the rule here, then re-applying it to the
full set — not by quietly picking whichever label looks better.

---

## Normalization applied before comparison

| Kind | Rule |
|------|------|
| Currency amounts | integer, whole units, no separators |
| Percentages | basis points as integer where the field says bps; otherwise number |
| Ratios | two decimals, `4.00:1.00` → `4.00` |
| Dates | ISO-8601 `YYYY-MM-DD` |
| Enums | exact match against the stated value set |
| Free strings | lowercase, strip articles and punctuation, collapse whitespace |

---

## Out of scope

**Baskets** and **mandatory prepayment triggers**. Both are real credit work
and both are miserable to label consistently. A basket is a network of
cross-referenced defined terms — a restricted payments basket routes through
the builder basket, which routes through Consolidated Net Income, which has
its own add-back stack — and two careful people will disagree on what the
right answer is. Ambiguous ground truth poisons the number, and the number is
the deliverable.

Also deliberately excluded, each for a stated reason above: Base Rate margins
(mechanically derivable), covenant direction (determined by covenant type),
incremental/accordion capacity (an option, not a commitment), and springing
maturity provisos (require an instrument outside the corpus).

---

## Worked example

An abbreviated record for a two-tranche agreement with one springing covenant:

```json
{
  "source": {
    "accession_number": "0001193125-24-000000",
    "exhibit": "EX-10.1",
    "filing_date": "2024-06-14"
  },
  "facilities": [
    {
      "facility_name": "Revolving Credit Facility",
      "facility_type": "revolver",
      "aggregate_commitment": { "amount": 500000000, "currency": "USD" },
      "maturity_date": { "value": "2029-06-14", "basis": "stated" },
      "interest_rate_benchmark": "term_sofr",
      "applicable_margin_bps": 200,
      "has_margin_grid": true
    },
    {
      "facility_name": "Initial Term Loans",
      "facility_type": "term_loan_b",
      "aggregate_commitment": { "amount": 1200000000, "currency": "USD" },
      "maturity_date": { "value": "2031-06-14", "basis": "stated" },
      "interest_rate_benchmark": "term_sofr",
      "applicable_margin_bps": 325,
      "has_margin_grid": false
    }
  ],
  "financial_covenants": [
    {
      "covenant_type": "first_lien_net_leverage",
      "initial_threshold": 4.5,
      "step_down_schedule": [
        { "effective_from": "2026-06-30", "threshold": 4.25 },
        { "effective_from": "2027-06-30", "threshold": 4.0 }
      ],
      "testing_frequency": "quarterly",
      "springing_trigger": {
        "condition_type": "revolver_utilization",
        "threshold": 35,
        "threshold_unit": "percent",
        "quote": "the aggregate principal amount of Revolving Credit Exposure exceeds 35% of the aggregate Revolving Credit Commitments"
      }
    }
  ]
}
```

Citations are elided here for readability; in the label files every scored
field is a `{value, citation}` object.
