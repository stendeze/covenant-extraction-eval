You are extracting structured terms from one credit agreement filed with the SEC.

The rules below are the adjudication rules a human labeler applied to build the reference answers for this task. They were written for the labeler: where they say "record", "label", "label file" or "labeler", read "your output" and "you". Worked examples drawn from particular agreements have been removed; the rules stand on their own.

Your output is one JSON object in the schema you are given. It has the record shape described below, with two differences from a label file: it has no `null_kind` — you are never asked to classify a null — and no `facility_name`. Where a rule sends a fact to free text, put it in `notes`.

Every non-null value carries a citation: the section it comes from, and a quote copied verbatim from the agreement — the exact characters of a sentence or clause that supports the value. A null that the agreement itself defers to a document or fact outside it carries a citation quoting the deferring language. A null meaning the thing does not exist carries no citation.

# The rules

## The four corners rule

One principle decides more of this schema than any other, so it is stated once here rather than re-argued at each field: **the agreement is the source. What the company says about the agreement is not.**

It has now settled three fields independently, each time against an answer that was more informative:

- `applicable_margin_bps` is `null` where a ratings grid defers its opening level, rather than the rate implied by the borrower's actual credit rating. The rating is real and public and it is not in the document.

Each time, the rejected answer was the one a credit analyst would give. That is the cost, and it is deliberate: this measures extraction from a document, and a gold value that requires knowledge from outside it is not extractable — it is recall, or inference, and a system scored against it would be rewarded for knowing things rather than for reading. The citation requirement enforces this mechanically, since a value with no supporting sentence in the document cannot be cited.

Where the honest answer genuinely lives outside the document, the field says so — that is what a deferral `null` is for — rather than importing it.

## Record shape

One agreement produces one record. Facilities and financial covenants are lists, because a single credit agreement routinely has a revolver plus one or more term tranches, and two or three financial covenants tested against the same borrower.

```
Agreement
├── source            (provenance, not scored)
├── facilities[]      (7 scored fields each)
└── financial_covenants[]  (5 scored fields each)
```

Financial covenants sit at the agreement level, not inside a facility. In a real capital structure they are tested against the consolidated borrower, not against a tranche. The common exception — a cov-lite term loan B where the leverage covenant runs for the benefit of the revolving lenders only — is captured in the covenant's own adjudication rule rather than as a separate field.

## Field summary

| # | Field | Level | Type |
|---|-------|-------|------|
| 1 | `facility_type` | facility | enum |
| 2 | `aggregate_commitment` | facility | {amount: integer, currency: ISO 4217} |
| 3 | `maturity_date` | facility | {value: date \| string, basis: enum} |
| 4 | `interest_rate_benchmark` | facility | enum |
| 5 | `applicable_margin_bps` | facility | number |
| 6 | `has_margin_grid` | facility | boolean |
| 7 | `covenant_type` | covenant | enum |
| 8 | `initial_threshold` | covenant | number |
| 9 | `step_down_schedule` | covenant | array of {effective_from, threshold} |
| 10 | `testing_frequency` | covenant | enum |
| 11 | `springing_trigger` | covenant | object \| null |

Eleven scored fields. Every one of them carries a citation (see [Citations](#citations)), which is validated but scored separately.

## Facility fields

### 1. `facility_type`

**Type:** enum — `revolver`, `term_loan_a`, `term_loan_b`, `delayed_draw_term_loan`, `bridge`, `other`.

**Where it lives:** the definitions in Article I ("Revolving Credit Facility", "Term A Loans", "Initial Term Loans"); the commitment section, usually §2.01; the cover page; the commitment schedule; and the amortization schedule (a 1%/yr amortizing institutional tranche is a TLB; a 5–10%/yr amortizing pro rata tranche is a TLA).

**Correct when:** the enum value matches exactly. Adjudication rules:

- Where the agreement labels a tranche "Term A" / "Term B" explicitly, that label governs, even if the amortization profile is unusual.
- Where it says only "Term Loans" with no letter, classify by amortization: ≤1%/yr → `term_loan_b`, more → `term_loan_a`.
- **A bullet is 0%/yr, so an unlettered bullet term loan is `term_loan_b`.** A tranche repayable in full at maturity with no scheduled installments satisfies ≤1%/yr and needs no separate rule; this is stated only because the amortization test reads as though it assumes some amortization exists, and a labeler meeting a bullet should not have to re-derive it.

  **This will sometimes disagree with market usage, and the rule still governs.**
- **A term tranche lettered other than A or B is `other`, whatever its amortization.** The letter is the agreement's own classification of the tranche, and the amortization test is for tranches with no letter.
- **Letter of credit and swingline sublimits are not facilities.** They are carve-outs of the revolving commitment and creating a separate record for them double-counts the commitment. No record.
- **Incremental / accordion / "Incremental Facilities" are not facilities.** They are an option to raise debt later, not a commitment made at signing. No record. This is the single most common source of an inflated commitment total, and excluding it is a deliberate choice, not an oversight.
- A delayed draw term loan *is* a facility — the commitment is made, only the funding is deferred.
- **`delayed_draw_term_loan` requires the agreement to say so**, either by labeling the tranche delayed-draw or by providing a multi-draw availability period. Both are things a second labeler can find by searching the document. A single-draw acquisition term loan, committed at signing and funded on the acquisition closing date, is classified by amortization like any other unlettered tranche — even where the borrower calls it delayed-draw elsewhere.

### 2. `aggregate_commitment`

**Type:** object — `{amount: integer, currency: ISO 4217 code}`. Amount in whole units of the currency, not millions. $500,000,000 is `500000000`.

**Where it lives:** §2.01; the defined term "Aggregate Commitments" / "Total Revolving Commitment" / "Term Loan Commitment" in Article I; the lender-by- lender commitment schedule; and the recitals, which often state the headline size.

**Correct when:** amount and currency both match exactly. Adjudication rules:

- Record the commitment **at closing**, as stated in the document under review. Not as later amended, not net of any incremental capacity.
- **`null` where the exhibit defers the amount to a schedule it does not attach.**
- **Loans converted, rolled or assumed from another instrument at closing are not commitments under this agreement.**
- Where the lender-by-lender schedule and the defined term disagree (it happens, usually a drafting error), the defined term governs and the discrepancy is noted in the label file.
- For a multicurrency facility, record the commitment in the currency the agreement uses to express the aggregate, which is nearly always USD with a sublimit expressed in the alternative currency. The sublimit is not a separate facility.

### 3. `maturity_date`

**Type:** object — `{value, basis}` where `basis` is `stated` or `relative`.
- `relative`: `value` is a **structured object**, `{tenor_years, anchor}` — `{"tenor_years": 5, "anchor": "Closing Date"}`. Use `tenor_months` instead where the agreement expresses a period in months.

**Where it lives:** the Article I definitions — "Maturity Date", "Revolving Maturity Date", "Term Loan Maturity Date".

**Correct when:** `basis` matches and, for `stated`, the date matches exactly; for `relative`, the tenor and the normalized `anchor` both match.

- **The tenor is compared in months.** `{"tenor_years": 5}` and `{"tenor_months": 60}` are the same answer: both count calendar time from the same day, and which key a reader chose says nothing about whether they read the definition. The key records how the agreement phrases the period; the comparison does not depend on it.
- **The anchor is the defined term the Maturity Date definition counts from, normalized as an [anchor](#normalization-applied-before-comparison).** `Closing Date`, `the Closing Date` and `closing date` match. Different defined terms do not, even where the agreement defines them as the same day: equating them means reading a second definition, which is the hop the basis rule below declines to take.

Adjudication rules:

- **`basis` is decided by the Maturity Date definition alone.** If it names only a period, `relative`, **even where the anchor is separately hard-coded elsewhere in Article I**.
- **Record the limb that states a date or a period.** Maturity is nearly always defined as the earliest or latest of several limbs. Limbs referencing **termination, acceleration, or an extension option** are mechanics, not alternative maturities — they describe when the deal may end early or be prolonged, which is true of every facility ever written.

  This covers both common constructions without either being a special case, and it does not depend on limb order:

  - Limbs (ii) and (iii) are mechanics.
  - "the **later** of (a) such date that is five years from the Closing Date and (b) if extended pursuant to Section 2.14, such extended Maturity Date" → `{"value": {"tenor_years": 5, "anchor": "Closing Date"}, "basis": "relative"}`. Limb (b) is an extension option, i.e. a mechanic.

  Distinct from the springing-maturity case below, which turns on an instrument outside the document rather than on the parties' own termination or extension rights.
- **Business Day conventions are mechanics. Record the date the agreement states, unadjusted.**
- **Springing maturity provisos are excluded from this field.** A clause like "or, if earlier, the date 91 days prior to the stated maturity of the Senior Notes" makes the actual maturity contingent on an instrument outside this document. Record the stated maturity; note the springing proviso in the label file's free-text notes.

### 4. `interest_rate_benchmark`

**Type:** enum — `term_sofr`, `daily_simple_sofr`, `libor`, `euribor`, `cdor`, `base_rate`, `prime`, `other`.

**Where it lives:** the Article I definitions of "Term SOFR", "Adjusted Term SOFR", "Benchmark", "Base Rate" / "ABR"; and the interest section in Article II.

**Correct when:** the enum matches exactly. Adjudication rules:

- Record the **primary floating benchmark**, i.e. the one applicable to the borrowings the agreement expects to be outstanding. Essentially every US agreement also permits Base Rate borrowings as an alternative; that alternative is not the answer.
- Post-2022 agreements are almost entirely Term SOFR. Pre-2022 agreements are LIBOR and typically contain benchmark replacement language; the benchmark replacement provision does **not** change the answer, which is `libor` — the field records the benchmark in effect, not its successor.
- `adjusted` variants (Adjusted Term SOFR, i.e. Term SOFR plus a credit spread adjustment) map to the unadjusted enum value. The CSA is not part of this field.
- **Multicurrency facilities still get one value.** A "Eurocurrency Rate" whose definition prices Dollar borrowings off LIBOR and Canadian Dollar borrowings off CDOR is `libor` — the alternative-currency limb is not the primary benchmark. `cdor` exists for the agreement whose primary borrowings are in Canadian Dollars.

### 5. `applicable_margin_bps`

**Type:** number or `null` — basis points over the benchmark. Not an integer: investment-grade grids routinely step in eighths of a percent, and 1.125% is 112.5 bps.

**Where it lives:** the Article I definition of "Applicable Margin" or "Applicable Rate", which very often contains the pricing grid table inline.

**Correct when:** the number matches exactly, or `null` matches `null`. Adjudication rules:

- Record the **opening margin**: the rate in effect from the Closing Date until the first compliance certificate is delivered. Most agreements state this explicitly ("Level III shall apply from the Closing Date until...").
- Where the agreement is **silent** on the opening level, record the highest (most expensive) level in the grid, and flag the label. This is the conservative reading and it is applied consistently, which matters more than which convention is chosen.
- **Where the agreement expressly defers determination to a document or fact outside its four corners, the value is `null`.** The distinction from the rule above is between an agreement that is *silent* and one that is *explicit that the answer is elsewhere*.
- Record the margin for **benchmark loans**, not Base Rate loans. The Base Rate margin is mechanically the benchmark margin minus 100bps in nearly every agreement, so labeling it separately doubles the work for close to zero information. Deliberately not a field.
- Where the agreement expresses the margin as a percentage (2.25%), convert to bps (225).
- **Half basis points are kept, not rounded.**

### 6. `has_margin_grid`

**Type:** boolean.

**Where it lives:** same definition as `applicable_margin_bps`; sometimes a standalone "Pricing Grid" schedule.

**Correct when:** the boolean matches. Adjudication rules:

- `true` when **the applicable margin** varies with a measured condition — a leverage ratio, a total net leverage ratio, a ratings grid, or a utilization grid.
- `false` when the margin is flat for the life of the facility.
- A **single step-down on a one-time event** (a leverage-based step-down at first test date only, or an IPO step-down) is `true`. The distinction the field draws is fixed-vs-variable pricing, not the number of rows in the table.
- **A margin that changes only with the passage of time is not a grid.** `false`, with the schedule recorded in free text.
- MFN / most-favored-nation provisions and pricing that changes only on default are not grids. `false`.

#### Margin grids vs. fee grids

**A grid on the commitment fee is not a margin grid.** `false` is correct for an agreement whose interest margin is flat even when its undrawn commitment fee steps with leverage.

This is not hypothetical.

Hence the rename: the field name now asks the question the rule answers.

## Covenant fields

If an agreement has no financial covenants at all — a genuinely cov-lite term loan B — the gold list is empty. That is a real and correct answer, not a labeling failure, and a model that invents a covenant there is penalized exactly as it should be.

### 7. `covenant_type`

**Type:** enum — `total_net_leverage`, `first_lien_net_leverage`, `secured_net_leverage`, `total_leverage_gross`, `debt_to_capitalization`, `interest_coverage`, `fixed_charge_coverage`, `debt_service_coverage`, `minimum_liquidity`, `capex_limit`, `other`.

**Where it lives:** the financial covenants section — Article VI or VII, the section number varies (§6.12, §7.11, §6.10 are all common); and the Article I definitions of the ratio itself ("Consolidated Total Net Leverage Ratio") and its inputs ("Consolidated EBITDA", "Consolidated Total Debt").

**Correct when:** the enum matches exactly. Adjudication rules:

- Classify by the **defined ratio's own definition**, not by its label. A covenant labeled "Leverage Ratio" whose definition nets unrestricted cash and counts only first lien debt is `first_lien_net_leverage`.
- Netting is determined by whether the debt definition subtracts cash. If it does, it is a `net` variant; if not, `total_leverage_gross`.
- **Classify by the denominator first, then by netting.** Every leverage value above divides debt by EBITDA and is unbounded, typically 3.00x to 7.00x. `debt_to_capitalization` divides debt by total capital — debt plus equity — and is therefore bounded near 1.00. Apply the denominator test before the netting test, since a capitalization ratio may also net cash and would otherwise be misread as a `net` leverage variant.
- Direction is **not a field**. It is fully determined by type: leverage covenants are maximums, coverage covenants and liquidity minimums are minimums. Adding a direction field would be a field that is right by construction and would inflate the accuracy number.
- **Coverage covenants are classified by what is in the denominator.** Interest alone → `interest_coverage`. Interest plus one or more recurring fixed obligations — rent, scheduled principal, taxes, preferred dividends — → `fixed_charge_coverage`. The numerator does not decide it; EBITDA, EBITDAR and Consolidated Net Income all appear over the same denominators.

  **Lease-adjusted constructions are `fixed_charge_coverage`.** EBITDAR over interest plus rent is the standard rent-adjusted form and is common in retail and restaurant credits, where capitalized rent is the largest fixed obligation on the page. It is named here so the shape does not have to be re-argued at each document that carries it.

  The narrower reading — that `fixed_charge_coverage` requires scheduled principal in the denominator — is rejected deliberately. Fixed charge denominators vary widely in practice, and requiring any particular component would push a large share of real fixed charge covenants into `other`, turning that value into the dumping ground the enum exists to prevent.
- Where a covenant runs for the benefit of revolving lenders only (the standard cov-lite structure), it is still recorded — it is a financial covenant in this agreement. The beneficiary is noted in free text.

### 8. `initial_threshold`

**Type:** number — the level applicable at the first test date. Ratios to two decimals (`4.00`); dollar thresholds as integers in whole currency units.

**Where it lives:** the financial covenants section, frequently as a table of fiscal periods against levels.

**Correct when:** the number matches exactly after normalization. Adjudication rules:

- Record the level at the **first test date**, which is the top row of the step-down table — not the final level, and not the level "thereafter".
- **Where the level repeats on a cycle within the year — set by fiscal quarter or month of the year rather than by a dated or counted schedule — record the most restrictive level in the cycle:** the highest minimum, or the lowest maximum.
- Where the agreement expresses the ratio as "4.00:1.00" or "4.00 to 1.00", normalize to `4.00`.
- **Where the agreement expresses the level as a percentage, record the ratio, not the percentage number.**
- Where there is a separate, higher level for an acquisition holiday (a "Covenant Holiday" or leverage step-up following a material acquisition), record the **non-holiday** level. The holiday is a conditional override, not the covenant level.
- **Any alternative level or schedule that applies only on a future condition is a conditional override. Record the level and schedule in effect at closing.** The acquisition holiday is one instance; it is not the only one, and it is not always looser.

### 9. `step_down_schedule`

**Type:** array of `{effective_from, threshold: number}`, ordered by `effective_from`. `effective_from` takes the same `{value, basis}` shape as [`maturity_date`](#3-maturity_date), and means the same thing in both bases: the **first fiscal period at the new level**.

- `stated`: `value` is an ISO-8601 date — the end date of that period, as the agreement states it. See [Reduced precision](#reduced-precision-and-how-it-is-scored) below.
- `relative`: `value` is a **structured object**, `{quarters_after, anchor}` — `{"quarters_after": 5, "anchor": "Closing Date"}`. Use `months_after` where the agreement counts in months.

**Where it lives:** same table as `initial_threshold`.

**Correct when:** the arrays match as ordered sequences — same length, and every pair matches on both keys. For `relative`, the count, its unit and the normalized `anchor` must all match. A partial match is scored as a miss on this field; per-step credit is reported separately as a diagnostic.

- **`quarters_after` and `months_after` are not interchangeable**, unlike the maturity tenor. "The fifth full Fiscal Quarter ending after the Closing Date" counts fiscal periods, and where it lands depends on where the anchor falls inside a quarter; fifteen months after the same day is a different date. Choosing the unit is reading the table, so the unit is compared.
- **The per-step diagnostic** counts a gold step as recovered when the prediction contains a step with the same `effective_from` and `threshold`, wherever it sits in the array. Recall is recovered gold steps over gold steps; precision is matching predicted steps over predicted steps. It is computed over every aligned pair where either side has a step, reported beside the field, and never changes the field's score.

Adjudication rules:

- `[]` means the covenant level is flat for the life of the agreement. Confirmed flat, not unknown.
- **A level that repeats on a cycle within the year is not a step-down schedule, and the field's type cannot hold it.** `[]` would assert the level is flat, which is false, and a dated array would hold dates the labeler computed, which this field forbids. Record `null` with `null_kind` [`unrepresentable`](#null_kind--a-gold-annotation-not-a-schema-field), cite the construction, and put the cycle in free text. The field is excluded from scoring for that covenant.
- The `initial_threshold` is **not** repeated as the first element. The array holds only changes from the initial level.
- Where the table's periods are described relative to fiscal quarters ("the fiscal quarter ending closest to June 30, 2026"), record the date the agreement itself states, `basis: stated`. Do not attempt to resolve a 52/53-week fiscal calendar to a real date — the calendar is not in the document.
- **Where the agreement states no date at all, `basis` is `relative`.**

- **Count to the first period at the new level, not the last at the old one.** This is where the mistake will be made, because the drafting says the opposite.
- The final "and thereafter" row is a step-down like any other; the absence of an end date is expected.

#### Reduced precision, and how it is scored

A fiscal-period table can name a month without naming a day.

So `stated` accepts **`YYYY-MM` as well as `YYYY-MM-DD`**, and the rule is: record the precision the agreement states, never more.

**Comparison is exact on the string, and a prediction finer than gold is a miss.**

This is the intended behaviour rather than an artifact, and it is written down so that a scorer implementation does not have to guess and inherit whatever a date library happens to do. A system that produces it has resolved a calendar it was not given — the same class of error as inventing a margin for a deferred opening level, and this field's guard against it is the same one, refusing to reward a confident value the document does not support. Scoring it as correct would teach exactly the wrong thing.

The rule is symmetric because the target is fidelity to what the agreement says, in both directions.

### 10. `testing_frequency`

**Type:** enum — `continuous`, `weekly`, `quarterly`, `monthly`, `semiannual`, `annual`, `event_driven`.

**Where it lives:** the lead-in to the covenants section — "as of the last day of each fiscal quarter of the Borrower".

**Correct when:** the enum matches exactly.

**Adjudication rule that matters:** `springing` is not a frequency. A springing covenant is still tested quarterly; it is *conditional*, not *infrequent*. Conditionality lives in `springing_trigger`. Conflating the two is the single most common way this field gets labeled inconsistently by two careful people, which is exactly why it is split.

### 11. `springing_trigger`

**Type:** object or `null`. When non-null: `{condition_type: enum, threshold: number, threshold_unit: enum, quote: string}` where `condition_type` is `revolver_utilization`, `minimum_availability`, or `other`, and `threshold_unit` is `percent` or `currency`.

**Where it lives:** the proviso in the covenants section, or a defined term — "Covenant Trigger Event", "Financial Covenant Test Period", "Testing Period".

**Correct when:** null-vs-non-null is correct, and where non-null, `condition_type`, `threshold` and `threshold_unit` all match.

The unit is part of the threshold. 35 percent of commitments and $35 are different triggers, and the any-drawn rule below records `0` in `currency` precisely so that the unit carries meaning. The `quote` carried inside the value is checked like any other citation and scored with [citation accuracy](#citations), not here.

Adjudication rules:

- `null` means the covenant is tested unconditionally every period. This is the majority case and it is cheap to label, which is what keeps this field affordable.
- **A one-time, irreversible condition that switches a covenant on — or off — permanently is not a springing trigger.** Record `null`, `null_kind` `absence`, and put the phase-in or sunset in free text.

  This field is for conditionality that is **re-evaluated every test date**: a covenant that bites this quarter because the revolver is drawn and does not bite next quarter because it is repaid. A permanent switch is a different thing.
- The typical trigger is revolver utilization above a threshold (commonly 35% or 40% of commitments) measured on the last day of a fiscal quarter. Record the percentage as a number: 35% → `35`, unit `percent`.
- Where the trigger is expressed as minimum availability in dollars rather than utilization as a percentage, `condition_type` is `minimum_availability` and the unit is `currency`.
- **A trigger on *any* drawn revolver is `threshold: 0`, unit `currency`.**
- Where letters of credit are excluded from the utilization calculation (very common — undrawn LCs up to some amount do not count toward the trigger), that exclusion is noted in free text and does not change the threshold.
- **Where the trigger is a "greater of" or "lesser of" pairing a percentage with a dollar amount, record the currency limb.**

## Citations

The `quote` must appear **verbatim** in the source document. That is mechanically checkable without any human labeling, which makes it a free hallucination guardrail: a citation that does not appear in the text is an automatic failure regardless of whether the extracted value happened to be right.

**Character offsets are not labeled by hand.** The span is derived programmatically from the quote by substring search at scoring time. Hand- locating offsets across ~330 field instances is the most painful thing this schema could ask for and it buys nothing the quote does not already buy. If a quote matches at more than one offset the first is taken; ambiguity there is irrelevant, since the check is whether the language exists in the document at all.

Citation accuracy is scored and reported **separately** from field accuracy. The two questions — did it get the number right, and can it show you where the number came from — are different, and a system that is right for the wrong reason should not be able to hide inside a single aggregate.

### `null_kind` — a gold annotation, not a schema field

Label files carry `null_kind` alongside any null value, taking `"deferral"`, `"absence"` or `"unrepresentable"`. It determines whether a citation is required, and whether the field is scored at all. The three are told apart by where the value is:

- **`deferral`** — the value exists outside the document. The agreement says so, and the null must quote the language that defers.
- **`absence`** — the value does not exist. There is nothing to quote.
- **`unrepresentable`** — the value exists in the document, and the field's type cannot express it. The null must quote the construction, and the field is **excluded from scoring** for that record: neither a hit nor a miss, and not counted among the field's instances.

**Guard against overuse — the same guard the deferral null carries.** `unrepresentable` applies only where the field's type cannot hold the construction the document states, never where a value is merely hard to extract, buried, cross-referenced within the document, or tedious to assemble. It must cite the construction, and it is sanctioned only where a rule in this document names the construction; today there is one, the seasonal covenant cycle under [`step_down_schedule`](#9-step_down_schedule). Without that limit it becomes the escape hatch the deferral rule was written to prevent, and a worse one: a field excluded from scoring cannot even be scored wrong.

**It is deliberately not part of the extraction schema and is not scored.** The model is never asked for it. The reason is the one that already excluded covenant direction: `null_kind` is fully determined by field identity. On `applicable_margin_bps` a null is essentially always a deferral; on `springing_trigger` it is essentially always an absence; on `step_down_schedule` it is only ever unrepresentable. A model producing it would be right by construction, and scoring it would inflate the headline number with a field that cannot be got wrong.

The scorer reads `null_kind` from the gold record to decide whether to demand a citation for that null, and whether to score the field at all. That preserves the machine-checkability without asking the model for an answer it cannot fail.

## Normalization applied before comparison

| Kind | Rule |
|------|------|
| Currency amounts | integer, whole units, no separators |
| Percentages | basis points where the field says bps, keeping half points (`1.125%` → `112.5`); otherwise number |
| Dates | ISO-8601 `YYYY-MM-DD` |
| Enums | exact match against the stated value set |
| Free strings | lowercase, strip articles and punctuation, collapse whitespace |
| Anchors | the `anchor` of a `relative` maturity or `effective_from`: casefold, strip one leading "the", surrounding quotation marks and trailing punctuation, collapse whitespace — nothing else |

## Out of scope

**Baskets** and **mandatory prepayment triggers**. Both are real credit work and both are miserable to label consistently. A basket is a network of cross-referenced defined terms — a restricted payments basket routes through the builder basket, which routes through Consolidated Net Income, which has its own add-back stack — and two careful people will disagree on what the right answer is. Ambiguous ground truth poisons the number, and the number is the deliverable.

# Your task

Read the whole agreement that follows. Return the one JSON object for it: every facility and every financial covenant the rules call for, each field decided by its rule, each value with its citation.
