# Labeling Guide

The operational companion to `schema.md`. That file says what each field
means and how to adjudicate it. This one says where to find it and in what
order to look.

`schema.md` governs. Where this guide and the adjudication rules disagree,
the rules win and this file is wrong.

---

## Before you start

**Article I definitions are alphabetical.** This is the single most useful
fact about credit agreements. Any defined term — "Applicable Rate",
"Maturity Date", "Eurocurrency Rate" — sits in alphabetical position inside
Section 1.01. You do not need to search; you can navigate.

**The table of contents tells you the section numbers.** They vary between
agreements. The financial covenant might be §6.12, §7.08, or §7.11. Read the
TOC first and write down three numbers: the commitments section (almost
always §2.01), the repayment/amortization section (usually §2.07), and the
financial covenant section.

**Search the term, not the quoted phrase.** Filings use typographic quotes
and inconsistent spacing, so `"Applicable Rate" means` often fails where
`Applicable Rate` succeeds. Search the bare term and look for the instance
in Article I — it will be bolded, quoted, or both.

---

## Search order

Eight steps, fixed sequence. Following the order matters: later steps depend
on what earlier ones return.

| # | Where | Yields |
|---|-------|--------|
| 1 | Table of contents | Section numbers for steps 2, 7, 8 |
| 2 | §2.01 | How many facilities, and what each one is |
| 3 | Commitment definitions (Art. I) | `aggregate_commitment` |
| 4 | "Maturity Date" definition (Art. I) | `maturity_date` |
| 5 | "Applicable Rate" / "Applicable Margin" (Art. I) | `applicable_margin_bps`, `has_margin_grid`, and what the margin attaches to |
| 6 | The attached rate's own definition (Art. I) | `interest_rate_benchmark` |
| 7 | §2.07 or the repayment section | `facility_type` (via amortization) |
| 8 | Financial covenant section | All five covenant fields |

---

## Facility fields

### Step 2 — §2.01: what facilities exist

§2.01 is where commitments are made. Each subsection is a facility: (a) the
term loan, (b) the revolver, and so on. This step tells you how many records
the agreement produces.

**The tranche names are not recorded.** `facility_name` was a field and was
cut, because an agreement can name the same tranche twice in its own defined
terms, in two incompatible styles — Kontoor Brands defines a `Revolving
Facility` in Article I and makes `Revolving Loans` under §2.6(a) — and the
rule had no principled way to choose. Read the names to orient yourself and
to find the amortization in step 7; `facility_type` is what gets recorded.

**Do not create a record for:**

- **Letter of credit sublimits.** Look for "part of, and not in addition to,
  the Revolving Credit Facility." That phrasing is the tell.
- **Swingline sublimits.** Same construction.
- **Incremental / accordion / New Term Facility.** An option to raise debt
  later, not a commitment made at signing.
- **Specified Refinancing Debt.** Same reason.

### Step 3 — commitment amounts

The amount is usually stated at the end of the commitment definition:
"The initial aggregate amount of the Initial Term Commitments is
$250,000,000." If the definition only points at Schedule 2.01, sum the
lender-by-lender column.

Where the schedule and the defined term disagree, the defined term governs.
Note the discrepancy in the label file.

**A tranche can be bigger than its commitment.** Watch for a loan definition
that folds in debt from somewhere else: "means (a) the term loans made by the
Initial Term Lenders pursuant to Section 2.01(a) **and (b) the SpinCo Term
Loans**". Amentum rolls $1.13B funded under a separate agreement into the
Initial Term Loan class at closing, so $3.75B is outstanding against a $2.62B
commitment. Record the commitment. Note the rollover.

The quick test is the citation: if the number you want to record does not
appear in the document, it is not the answer. $3.75B appears nowhere in
Amentum.

### Step 4 — maturity

One "Maturity Date" definition usually covers all facilities with lettered
clauses: "(a) with respect to the Revolving Credit Facility... (b) with
respect to the Initial Term Loans..."

**The "earliest of" construction is normal.** Nearly every agreement reads
"the earliest of (i) [date], (ii) the date of termination in whole of the
Commitments, (iii) the date the Loans are declared due and payable." Clauses
(ii) and (iii) are ordinary termination and acceleration language. So is a
"later of ... (b) if extended pursuant to Section 2.14" limb, and so is a
preceding-Business-Day proviso, which is a day-count adjustment. Record the
limb that states a date or a period; the rest are mechanics.

**Two bases, and the limb decides which.** If the limb you kept names a
calendar date, `basis: stated` and the value is that ISO date.

If it names a *period* — "the fifth anniversary of the Closing Date", "such
date that is five years from the Closing Date" — then `basis: relative`, and
the value is a **structured object**, never the sentence:

```json
{ "value": { "tenor_years": 5, "anchor": "Closing Date" }, "basis": "relative" }
```

**Do not resolve the anchor, even when you can.** Some agreements hard-code
it: Extreme Networks defines "Restatement Date" as June 22, 2023, Amentum
defines "Closing Date" as September 27, 2024. The maturity is still
`relative`, because the basis is decided by the Maturity Date definition
alone — one definition, one hop, no arithmetic. Amentum is why: its term
maturity lands on a Saturday, and resolving it would force you to decide
whether to apply a Business Day proviso you were told to ignore as a
mechanic. Note the resolved date in free text if it is useful; do not label
it.

Use `tenor_months` where the agreement counts in months. This is not
cosmetic: as free text, "five years from the Closing Date", "the fifth
anniversary of the Closing Date" and "such date that is five years from the
Closing Date" are three different strings for one answer, and two of them
would score as misses. Quote whichever phrasing the agreement uses in the
citation; the value is derived from it.

A springing maturity proviso is different and rarer: "or, if earlier, the
date 91 days prior to the stated maturity of the Senior Notes." That
references an instrument outside the document. Record the stated maturity and
note the proviso in free text.

### Step 5 — margin and grid

Find "Applicable Rate", "Applicable Margin", or "Applicable Percentage" in
Article I. This one definition yields three things: the margin, whether
there's a grid, and — critically — the name of the rate the margin attaches
to, which you need for step 6.

**Reading the margin:**

- Record the margin for benchmark loans, not Base Rate loans. Every agreement
  quotes both. The Base Rate margin is the benchmark margin minus 100bps in
  nearly every case.
- Convert percentages to bps: 3.25% → 325.
- Flat definition with no table → `has_margin_grid: false`.
- Table with pricing levels → `has_margin_grid: true`, and record the opening
  level.

**Grid types you will see:**

*Leverage grid* — levels keyed to a leverage ratio. Common in sponsor deals.
The opening level is usually stated: "Level III shall apply from the Closing
Date until the first Compliance Certificate is delivered."

*Ratings grid* — levels keyed to S&P / Moody's debt ratings. Common in
investment-grade revolvers. Frequently defers the opening level to a closing
certificate or to the rating in effect on any given day.

**The null rule.** `applicable_margin_bps` is `null` when the agreement
expressly defers determination to a document or fact outside its four
corners. Two forms seen so far:

> "Initially, the Applicable Rate shall be determined based upon the Debt
> Rating specified in the certificate delivered pursuant to Section
> 4.01(a)(vii)"

> "based upon the Ratings by S&P and Moody's ... applicable on such day"

Both defer. Neither states a number. Record `null` and cite the deferral
language itself — the citation is what distinguishes declining for the right
reason from declining out of vagueness.

Null does **not** apply when the answer is merely buried, only when the
agreement defers. If you find yourself reaching for null because a field is
annoying to locate, that is the wrong use.

**Commitment fee grids are not margin grids.** An agreement can have a flat
margin and a three-level commitment fee grid keyed to leverage. That is
`has_margin_grid: false`. The field is about the margin only.

### Step 6 — benchmark

Take the rate name from step 5 and find its definition in Article I. Follow
it until you hit an administrator.

| Definition resolves to | Enum |
|---|---|
| London interbank offered rate, ICE Benchmark Administration, Reuters LIBOR01/LIBOR02 | `libor` |
| Term SOFR Reference Rate, CME Term SOFR | `term_sofr` |
| Daily Simple SOFR | `daily_simple_sofr` |
| EURIBOR | `euribor` |
| Canadian Dollar Offered Rate, CDOR | `cdor` |

**Vocabulary.** "Eurocurrency Rate" and "Eurodollar Rate" mean LIBOR. "Term
Benchmark" means SOFR. These are the drafting conventions, not separate
rates.

**Ignore the Benchmark Replacement sections entirely.** Every LIBOR agreement
filed after mid-2021 defines Term SOFR, Daily Simple SOFR, Daily Compounded
SOFR, Benchmark Transition Event, and Benchmark Replacement. All of it is
conditional future language. The grammatical tell: fallback provisions read
"upon the occurrence of", pricing provisions read "means".

**Adjusted variants map to the unadjusted enum.** "Adjusted Term SOFR" is
`term_sofr`. The credit spread adjustment is not part of this field.

**Multi-currency limbs.** A definition can have two limbs — USD off LIBOR,
CAD off CDOR. Record the primary benchmark, the one the agreement expects to
be outstanding.

### Step 7 — facility type

If the agreement labels a tranche "Term A" or "Term B", that governs.

If it says only "Term Loans" or "Initial Term Loans" with no letter, go to
the repayment section and read the amortization:

| Amortization | Type |
|---|---|
| 0.25% quarterly (1.00%/yr) | `term_loan_b` |
| 1.25–2.5% quarterly (5–10%/yr) | `term_loan_a` |

A delayed draw term loan is a facility — the commitment is made, only the
funding is deferred.

---

## Covenant fields — step 8

Go to the financial covenant section from your TOC read. All five covenant
fields come from this one section plus the ratio's definition in Article I.

**An empty covenant list is a valid answer.** Genuinely cov-lite term loan Bs
have none. Record `[]`, not a guess.

### `covenant_type`

Classify by the ratio's own definition in Article I, not by its label. A
covenant labeled "Leverage Ratio" whose definition nets unrestricted cash and
counts only first lien debt is `first_lien_net_leverage`. The label is often
deliberately neutral — "Consolidated Coverage Ratio", "Financial Condition
Covenant" — and tells you nothing.

**Read the denominator first, then the netting.** Three questions in order:

1. *What is the ratio divided by?* Debt over EBITDA is the leverage family,
   unbounded, thresholds typically 3.00x–7.00x. Debt over total capital (debt
   plus equity) is `debt_to_capitalization`, bounded near 1.00. **A threshold
   below 1.00 cannot be an EBITDA multiple** — Roper's "0.65 to 1.00" is the
   tell, and it is mechanical, not a judgment. Take this step first, because a
   capitalization ratio may also net cash and would otherwise be misread as a
   `net` leverage variant.
2. *Does the debt definition subtract cash?* If yes, a `net` variant. If no,
   `total_leverage_gross`.
3. *Is it lien-limited?* First lien or secured debt only gives
   `first_lien_net_leverage` or `secured_net_leverage`. A senior unsecured
   facility has no lien-based variant.

**Coverage covenants are classified by the denominator too.** Interest alone
is `interest_coverage`. Interest plus one or more recurring fixed obligations
— rent, scheduled principal, taxes, preferred dividends — is
`fixed_charge_coverage`. The numerator does not decide it: EBITDA, EBITDAR and
Consolidated Net Income all appear over the same denominators.

Lease-adjusted constructions are `fixed_charge_coverage`. EBITDAR over
interest plus rent is the standard rent-adjusted form and is common in retail
credits; Advance Auto is the worked case. Do not reach for `other` because the
denominator lacks scheduled principal — that reading would push a large share
of real fixed charge covenants into the catch-all.

**Incurrence ratios are not covenants.** A First Lien Leverage Ratio defined
and used only to size incremental capacity or to gate ratio debt is not a
maintenance test and gets no record. Check what the defined term is actually
used for before recording it — Kontoor defines two such ratios and neither is
a covenant.

### `initial_threshold`

The level at the **first test date** — the top row of the table, not the
final level and not the "thereafter" row.

Normalize "6.50 to 1.00" and "6.50:1.00" to `6.50`.

Where a covenant holiday or acquisition step-up provides a temporarily higher
level, record the **non-holiday** level.

### `step_down_schedule`

`[]` means confirmed flat, not unknown.

Do not repeat `initial_threshold` as the first element. The array holds only
changes.

**`effective_from` has two bases, exactly like `maturity_date`.** In both, it
means the first fiscal period at the new level.

If the table names a date — "the fiscal quarter ending closest to June 30,
2026" — record it as the agreement states it:

```json
{ "effective_from": { "value": "2026-06-30", "basis": "stated" }, "threshold": 4.25 }
```

Do not resolve a 52/53-week fiscal calendar to a real date. The calendar is
not in the document.

If the table names no date at all — only a formula, "the fourth full Fiscal
Quarter ending after the Closing Date" — there is nothing to resolve, and the
basis is relative:

```json
{
  "effective_from": { "value": { "quarters_after": 5, "anchor": "Closing Date" },
                      "basis": "relative" },
  "threshold": 5.00
}
```

Use `months_after` where the agreement counts in months. Structured, not the
sentence, for the same reason as maturity: one answer must not depend on which
phrasing you copied.

**Count to the first period at the new level.** The drafting will point you
the other way. Amentum's table reads 5.25x through the *fourth* full Fiscal
Quarter after the Closing Date, then 5.00x "for any Test Period ending
thereafter" — and the value is `quarters_after: 5`, the first period actually
tested at 5.00x, not the fourth that "thereafter" refers back to. Whenever you
see "thereafter", add one.

### `testing_frequency`

From the lead-in: "as of the end of each fiscal quarter of Holdings" →
`quarterly`.

**Springing is not a frequency.** A springing covenant is still tested
quarterly; it is conditional, not infrequent. Conditionality goes in
`springing_trigger`.

### `springing_trigger`

`null` for an unconditionally tested covenant. This is the majority case.

The typical trigger is revolver utilization above a threshold, in a proviso
in the covenant section:

> "solely to the extent the aggregate amount of L/C Obligations and Revolving
> Credit Loans outstanding as of the end of such fiscal quarter ... exceeds
> 35.0% of the aggregate amount of all Revolving Credit Commitments"

Record `35`, unit `percent`, `condition_type: revolver_utilization`.

Where letters of credit are excluded from the utilization calculation — very
common — note it in free text. It does not change the threshold.

---

## Trap list

Consolidated, in the order they bite.

1. **L/C and swingline sublimits are not facilities.** Booking them inflates
   the commitment total.
2. **Incremental capacity is not a facility.** An option, not a commitment.
3. **The Base Rate margin is not the answer.** Every agreement quotes both.
4. **Benchmark Replacement sections mention SOFR in every LIBOR agreement.**
   Conditional, not operative.
5. **"Eurocurrency" and "Eurodollar" mean LIBOR.** Not separate benchmarks.
6. **The "earliest of" maturity construction is ordinary.** Record the stated
   date.
7. **Commitment fee grids are not margin grids.**
8. **Template residue.** Pro Forma Basis provisions sometimes assert the
   Applicable Rate is leverage-linked when it isn't — residue from a deal
   that had a margin grid. Verify against the Applicable Rate definition
   itself, never against a cross-reference.
9. **Deferred opening level → null, with the deferral quoted.** Not the
   highest level, not a looked-up rating.
10. **Covenant holiday levels are conditional overrides.** Record the
    non-holiday level.
11. **An empty covenant list is a real answer.**

---

## When a document doesn't fit

Stop and write down where you hesitated before resolving it. A field that
takes judgment is a field whose adjudication rule is underspecified, and the
hesitation is more valuable than the label.

Rule changes go in `schema.md` as their own commit, with the document that
forced them named in the message. Then re-apply to everything already
labeled.

**And update this file in that same commit.** This is the document labeling
is actually done from, so a schema change that does not reach it keeps being
applied in its old form — silently, and by construction, at every document
labeled afterward. That is not hypothetical: the structured relative-maturity
form landed in `schema.md` while step 4 here still described only `basis:
stated`, and the next three documents were all labeled with string-form
maturities that then had to be corrected one at a time. The conformance fixes
looked like labeler error and were a stale instruction.

So the protocol is three parts, not two: change the rule in `schema.md`,
change the instruction here, re-apply to everything already labeled — one
commit, naming the document that forced it.
