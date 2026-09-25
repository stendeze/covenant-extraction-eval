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

## The four corners rule

One principle decides more of this schema than any other, so it is stated once
here rather than re-argued at each field: **the agreement is the source. What
the company says about the agreement is not.**

It has now settled three fields independently, each time against an answer
that was more informative:

- `applicable_margin_bps` is `null` where a ratings grid defers its opening
  level, rather than the rate implied by the borrower's actual credit rating.
  The rating is real and public and it is not in the document.
- `aggregate_commitment` records Amentum's US$2,620,000,000 commitment, not the
  US$3,750,000,000 tranche outstanding on day one, because the larger figure
  appears nowhere in the agreement and so cannot carry a citation.
- `facility_type` records ANI's tranche as `term_loan_a` on its amortization,
  though the borrower's own 8-K and 10-Q call it a "delayed-draw term loan
  facility". The agreement never uses the phrase.

Each time, the rejected answer was the one a credit analyst would give. That is
the cost, and it is deliberate: this measures extraction from a document, and a
gold value that requires knowledge from outside it is not extractable — it is
recall, or inference, and a system scored against it would be rewarded for
knowing things rather than for reading. The citation requirement enforces this
mechanically, since a value with no supporting sentence in the document cannot
be cited.

Where the honest answer genuinely lives outside the document, the field says so
— that is what a deferral `null` is for — rather than importing it.

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

**"US corporate" means the borrower's domicile and the governing law — not the
currency.** The corpus has applied this test in both directions and the
distinction needs stating, because the two cases look similar from a distance.

- **Lamb Weston EX-10.1 is in**, and carries a €200,000,000 term loan to
  Lamb-Weston/Meijer v.o.f., a Dutch borrower. The agreement is a US
  agreement: US company, US law, Bank of America as agent, with one
  euro-denominated tranche to a foreign subsidiary. Foreign currency and a
  foreign co-borrower do not put a US agreement out of frame — and the schema
  expects them, since `aggregate_commitment` carries an ISO 4217 code and
  `interest_rate_benchmark` includes `euribor` and `cdor`.
- **Lithia Motors EX-10.2 is out.** The borrower is Lithia Master LP Company,
  LP, an Alberta limited partnership; the agreement is governed by the laws of
  Ontario, denominated in Canadian dollars, and priced off CDOR and Canadian
  Prime with no SOFR or LIBOR anywhere. A Canadian agreement with a Canadian
  borrower does not enter the frame because its parent files with the SEC.

The line is the **agreement's** nationality, not the registrant's and not the
tranche's. A US agreement may lend in any currency to a subsidiary anywhere; a
foreign-law agreement to a foreign borrower is out however familiar the parent
name on the 8-K. Stated because one corpus now contains both and a reader
comparing them would otherwise infer an inconsistency.

**The frame excludes by sector, not by structure — so asset-based facilities
are in.** This is a clarification of what the frame already said rather than an
amendment to it. An ABL revolver sizes availability off a borrowing base and
typically carries a single fixed-charge covenant springing on availability,
which looks unlike the leverage-and-coverage packages elsewhere in the corpus.
It is still a syndicated credit agreement made by a US corporate borrower with
an agent and a lender schedule, and nothing in the criteria above excludes it.
G-III Apparel qualifies on every stated test: $700M of commitments, JPMorgan
as agent, ten-plus lenders, a full amended and restated agreement. Avaya's ABL
was excluded on **size** — $128,125,000, below the floor — not on being an ABL.

The decisive point is that this schema anticipated these documents.
`springing_trigger` has defined `minimum_availability` and a `currency`
`threshold_unit` since before any document was labeled, and those values
describe an availability-based trigger, which is an ABL construction and
nothing else. Excluding ABLs would strand two enum values the schema
deliberately wrote.

> **The reasoning was checked against its own incentive, and a reader should
> be able to see that.** The question was raised while reading Avaya, where
> excluding ABLs cost nothing. It was settled while reading G-III, which
> supplies three enum values the corpus had recorded as never firing —
> `minimum_availability`, `currency` and `monthly`. Concluding "in frame" at
> exactly that moment is convenient, and convenience is not an argument. So
> the argument above rests only on what the frame says and on enum values
> fixed in advance; it would reach the same answer for an ABL that supplied
> nothing new. If it is wrong, it is wrong for reasons visible on this page.

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

### Changing a rule

The rules below are expected to move under contact with real documents; that
is the point of labeling in document order and committing as you go. When one
does, the change is **one commit with three parts**, naming the document that
forced it:

1. The rule changes here. This document governs.
2. **The corresponding instruction in [labeling-guide.md](labeling-guide.md)
   changes with it.** That file is what labeling is actually done from, and a
   rule that does not reach it keeps being applied in its old form at every
   document labeled afterward. This happened: the structured relative-maturity
   form was added here while the guide still described only `basis: stated`,
   and the next three documents were labeled with string-form maturities that
   had to be corrected one at a time. Each correction looked like labeler
   error and was a stale instruction.
3. The change is re-applied to everything already labeled, and the result is
   reported — including when it is empty, since empty-by-check and
   empty-by-assumption are different claims.

**Re-application that changes a recorded value is confirmed with the labeler
first, every time.** Most corrections are structural: a maturity string
becoming `{tenor_years, anchor}`, a null gaining `null_kind`. Those change how
a record is shaped, not what it says, and the right answer is already in the
label. A change like Roper's `other` → `debt_to_capitalization` is different
in kind — it changes what the gold record asserts about the document — and
gold data is the one thing in this repo that cannot be reconstructed from the
repo. It is put to the labeler before it is written, even when the rule makes
it mechanical and even when leaving it alone would be plainly wrong.

### When a field has accumulated too many rules

`facility_name` was cut on a standing instruction: a third adjudication rule
meant cutting the field rather than writing it. That instruction was right and
it bound. But a count is the wrong general test, because `maturity_date` now
carries five rules and is not in trouble.

**The test is what a new rule does, not how many there are.**

- A rule that **arbitrates between competing readings of the same
  construction** counts against the field. Each one is evidence the field is
  underdetermined — the document offered several answers and the schema had to
  invent a preference. `facility_name` accumulated three of these: which
  source ranks highest, what to do when only the cover page names the tranche,
  and how to choose when Article I names the tranche twice in two styles. The
  field was not getting better defined; the ambiguity was being papered over
  one document at a time.
- A rule that **extends coverage to a construction not previously seen** does
  not count. `maturity_date`'s five — which limb governs, springing provisos
  excluded, the structured relative form, hard dates winning, and basis decided
  by the definition alone — each address a different construction. None of them
  overrules another on the same facts. That is coverage accumulating, not
  ambiguity accumulating.

**When a field takes its second arbitrating rule, it gets a written warning
naming the third as fatal.** Applied retrospectively this cuts `facility_name`
at exactly the point it was cut, and leaves `maturity_date` alone.

> **On the exemption.** `maturity_date` is exempt under this test, not in spite
> of it, and the distinction matters more than the outcome. The
> `facility_name` cut is worth something only because the trigger bound when
> it was unwelcome — a rule that binds only when convenient is not a rule. So
> the exemption is stated with its reasoning on the page and a test a second
> reader can apply to the same facts, rather than asserted for the field that
> happens to be more interesting. If the reasoning is wrong, it is wrong
> visibly, which is the most that can be asked of it.

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

Eleven scored fields. Every one of them carries a citation (see
[Citations](#citations)), which is validated but scored separately.

---

## Facility fields

> **`facility_name` was cut on a pre-registered trigger.** It was the twelfth
> field: the tranche's own label, as a string. It carried a standing warning
> that if it required a third adjudication rule it should be cut rather than
> patched, and at Kontoor Brands it did. The full reasoning is in
> [labeling-notes.md](labeling-notes.md#facility_name--cut-not-patched). The
> short version is that an agreement can name the same tranche twice, in its
> own defined terms, in two incompatible styles — Kontoor defines the
> `Revolving Facility` in Article I and makes `Revolving Loans` under §2.6(a) —
> and the field has no principled way to choose. A field two careful readers
> answer differently is measuring phrasing, not extraction. `facility_type`
> carries the semantic weight and record alignment keys off it, so almost
> nothing is lost.

### 1. `facility_type`

**Type:** enum — `revolver`, `term_loan_a`, `term_loan_b`,
`delayed_draw_term_loan`, `bridge`, `other`.

**Where it lives:** the definitions in Article I ("Revolving Credit Facility",
"Term A Loans", "Initial Term Loans"); the commitment section, usually §2.01;
the cover page; the commitment schedule; and the
amortization schedule (a 1%/yr amortizing institutional tranche is a TLB; a
5–10%/yr amortizing pro rata tranche is a TLA).

**Correct when:** the enum value matches exactly. Adjudication rules:

- Where the agreement labels a tranche "Term A" / "Term B" explicitly, that
  label governs, even if the amortization profile is unusual.
- Where it says only "Term Loans" with no letter, classify by amortization:
  ≤1%/yr → `term_loan_b`, more → `term_loan_a`.
- **A bullet is 0%/yr, so an unlettered bullet term loan is `term_loan_b`.**
  A tranche repayable in full at maturity with no scheduled installments
  satisfies ≤1%/yr and needs no separate rule; this is stated only because the
  amortization test reads as though it assumes some amortization exists, and a
  labeler meeting a bullet should not have to re-derive it.

  **This will sometimes disagree with market usage, and the rule still
  governs.** Lamb Weston's €200M European Term Loan is a five-year bullet held
  by three relationship banks, priced off the revolver's own grid — every
  commercial instinct calls that a pro rata bank tranche, i.e. a TLA. It is
  recorded `term_loan_b`. The alternative test, classifying by lender base or
  by pricing, cannot be written mechanically: "relationship banks" and "pro
  rata pricing" are judgments a second labeler cannot reliably replicate, and
  a rule that requires taste is not one this schema can use. Flagged for the
  [blind relabel](#annotator-agreement) rather than resolved by preference.
- **Letter of credit and swingline sublimits are not facilities.** They are
  carve-outs of the revolving commitment and creating a separate record for
  them double-counts the commitment. No record.
- **Incremental / accordion / "Incremental Facilities" are not facilities.**
  They are an option to raise debt later, not a commitment made at signing. No
  record. This is the single most common source of an inflated commitment
  total, and excluding it is a deliberate choice, not an oversight.
- A delayed draw term loan *is* a facility — the commitment is made, only the
  funding is deferred.
- **`delayed_draw_term_loan` requires the agreement to say so**, either by
  labeling the tranche delayed-draw or by providing a multi-draw availability
  period. Both are things a second labeler can find by searching the document.
  A single-draw acquisition term loan, committed at signing and funded on the
  acquisition closing date, is classified by amortization like any other
  unlettered tranche — even where the borrower calls it delayed-draw
  elsewhere.

  ANI Pharmaceuticals is the case and it is not a close one commercially: the
  commitment is made at signing, funded in one draw at the acquisition close a
  month later, carries a ticking fee on the undrawn amount, and terminates on
  an Acquisition Outside Date. ANI's own 8-K and 10-Q call it a "delayed-draw
  term loan facility (the Term Loan A)". The agreement never uses the phrase,
  so the value is `term_loan_a`, on 2.5%/5%/7.5% amortization. See [The four
  corners rule](#the-four-corners-rule).

  **This makes `delayed_draw_term_loan` harder to fire, and it may not fire at
  all.** That is the accepted outcome, on the same basis as
  `debt_service_coverage`: an enum value that never fires costs nothing, and
  the alternative — admitting an external characterisation as evidence — costs
  the field's meaning.

### 2. `aggregate_commitment`

**Type:** object — `{amount: integer, currency: ISO 4217 code}`. Amount in
whole units of the currency, not millions. $500,000,000 is `500000000`.

**Where it lives:** §2.01; the defined term "Aggregate Commitments" / "Total
Revolving Commitment" / "Term Loan Commitment" in Article I; the lender-by-
lender commitment schedule; and the recitals, which often state the headline
size.

**Correct when:** amount and currency both match exactly. Adjudication rules:

- Record the commitment **at closing**, as stated in the document under
  review. Not as later amended, not net of any incremental capacity.
- **`null` where the exhibit defers the amount to a schedule it does not
  attach.** Peloton's `Revolving Commitment` definition gives no aggregate; it
  points to "the amount set forth opposite such Lender's name on Schedule
  2.01", and the exhibit ends "[Remainder of page intentionally left blank;
  signature pages intentionally removed]" with no schedules. The figure exists
  in the executed agreement and is absent from the filed document.

  This is the deferral rule already written for `applicable_margin_bps`,
  applied to a second field: the agreement states that the answer exists,
  names where it lives, and that place is outside the four corners. The
  citation is the pointer — the definition's reference to the unattached
  schedule — so the null stays falsifiable in the same way.

  The alternative was to take $100,000,000 from the 8-K body in the same
  accession. That would have been the first time this project sourced a gold
  value from outside the agreement, against [the four corners
  rule](#the-four-corners-rule), and it is the worse trade: a third nullable
  field costs less than a precedent for reading values off a press narrative.

  **Not to be confused with a schedule that is merely absent.** Six other
  documents in this corpus omit their commitment schedules and none produces a
  null, because in each the defined term states the aggregate itself and the
  schedule is only corroboration. The null applies where the amount appears
  nowhere in the exhibit.
- **Loans converted, rolled or assumed from another instrument at closing are
  not commitments under this agreement.** A tranche can be larger than its
  commitment: Amentum's `Initial Term Loans` are defined as the loans made
  under §2.01(a) *plus* US$1,130,000,000 of SpinCo Term Loans funded under a
  separate agreement of the same date, so US$3,750,000,000 is outstanding on
  day one against an `Initial Term Commitment` of US$2,620,000,000. Record the
  commitment — US$2,620,000,000 — and note the rollover in free text.

  The citation requirement is what makes this decisive rather than a
  preference. The combined figure appears nowhere in the document, so the
  alternative answer cannot carry a verbatim quote; a rule that forces an
  uncitable value is the wrong rule. A reviewer thinking in economic tranche
  size will expect the larger number, which is why the label notes it.
- Where the lender-by-lender schedule and the defined term disagree (it
  happens, usually a drafting error), the defined term governs and the
  discrepancy is noted in the label file.
- For a multicurrency facility, record the commitment in the currency the
  agreement uses to express the aggregate, which is nearly always USD with a
  sublimit expressed in the alternative currency. The sublimit is not a
  separate facility.

### 3. `maturity_date`

**Type:** object — `{value, basis}` where `basis` is `stated` or `relative`.

- `stated`: `value` is an ISO-8601 date — `"2028-06-25"`.
- `relative`: `value` is a **structured object**, `{tenor_years, anchor}` —
  `{"tenor_years": 5, "anchor": "Closing Date"}`. Use `tenor_months` instead
  where the agreement expresses a period in months.

**Where it lives:** the Article I definitions — "Maturity Date", "Revolving
Maturity Date", "Term Loan Maturity Date".

**Correct when:** `basis` matches and, for `stated`, the date matches exactly;
for `relative`, `tenor_years` (or `tenor_months`) and the normalized `anchor`
both match.

> **Why `relative` is structured rather than a verbatim string.** As a free
> string it would be scored under the normalization rules for text —
> lowercase, strip articles and punctuation, collapse whitespace — and "five
> years from the Closing Date", "the fifth anniversary of the Closing Date"
> and "such date that is five years from the Closing Date" would be three
> different answers to the same question. All three are substantively correct
> and two of them would score as misses. That is a false-negative mechanism
> built into the field, measuring phrasing rather than extraction. The
> structured form is machine-comparable and removes the guesswork.

Adjudication rules:

- **`basis` is decided by the Maturity Date definition alone.** If that
  definition names a calendar date, `stated` — even if it also describes the
  date as an anniversary ("June 25, 2028, being the fifth anniversary of the
  Closing Date"). If it names only a period, `relative`, **even where the
  anchor is separately hard-coded elsewhere in Article I**. Extreme Networks
  defines its Restatement Date as "June 22, 2023" and its maturity as the
  five-year anniversary of it; Amentum defines its Closing Date as "September
  27, 2024". Both are `relative`.

  This is a one-hop test — read one definition — and it is the rule rather
  than an arbitrary convention for a reason that shows up in this corpus.
  Amentum's term maturity resolves to 2031-09-27, a **Saturday**, and the
  definition carries a succeeding-Business-Day proviso that the limb rule
  above classifies as a mechanic to be disregarded. Resolving the date would
  force a choice this schema explicitly declines to make — 2031-09-27 or
  2031-09-29 — and two careful readers would split. The label file computed
  both.

  Resolving would also import date arithmetic into an extraction score: a
  system that correctly extracts both the period and the anchor could still
  miss on a leap-year or convention slip, which measures arithmetic rather
  than reading. Nothing is lost by declining, because `{tenor_years, anchor}`
  plus the anchor's own definition resolves the date at scoring time for any
  reader who wants it.
- **Record the limb that states a date or a period.** Maturity is nearly
  always defined as the earliest or latest of several limbs. Limbs referencing
  **termination, acceleration, or an extension option** are mechanics, not
  alternative maturities — they describe when the deal may end early or be
  prolonged, which is true of every facility ever written.

  This covers both common constructions without either being a special case,
  and it does not depend on limb order:

  - "the **earliest** of (i) June 25, 2028, (ii) termination in whole of the
    Commitments, (iii) the date the Loans are declared due and payable" →
    `{"value": "2028-06-25", "basis": "stated"}`. Limbs (ii) and (iii) are
    mechanics.
  - "the **later** of (a) such date that is five years from the Closing Date
    and (b) if extended pursuant to Section 2.14, such extended Maturity Date"
    → `{"value": {"tenor_years": 5, "anchor": "Closing Date"}, "basis":
    "relative"}`. Limb (b) is an extension option, i.e. a mechanic.

  Distinct from the springing-maturity case below, which turns on an
  instrument outside the document rather than on the parties' own termination
  or extension rights.
- **Business Day conventions are mechanics. Record the date the agreement
  states, unadjusted.** A definition that adds "if such date is not a Business
  Day, the Maturity Date shall be the next preceding Business Day" — or the
  succeeding one — is describing settlement mechanics, not an alternative
  maturity, and it applies to every facility ever written.

  This has arisen three times and was never written down: Amentum's term
  maturity resolves to a Saturday, Lamb Weston EX-10.2's Term A to a Sunday,
  and PureCycle's stated June 30, 2024 to a Sunday, rolling to Friday June 28.
  In each the stated date is recorded and the convention noted in free text.

  It is stated here because [the basis rule](#3-maturity_date) already relies
  on it: the argument for deciding `basis` from the Maturity Date definition
  alone is that resolving an anniversary would force a Business Day choice
  this schema declines to make. A rule that another rule depends on cannot
  live only in [labeling-guide.md](labeling-guide.md), which does not govern.
- **Springing maturity provisos are excluded from this field.** A clause like
  "or, if earlier, the date 91 days prior to the stated maturity of the Senior
  Notes" makes the actual maturity contingent on an instrument outside this
  document. Record the stated maturity; note the springing proviso in the
  label file's free-text notes. This is a known limitation and it is the right
  trade: resolving it correctly requires the notes indenture, which is not in
  the corpus.

### 4. `interest_rate_benchmark`

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

### 5. `applicable_margin_bps`

**Type:** number or `null` — basis points over the benchmark. Not an integer:
investment-grade grids routinely step in eighths of a percent, and 1.125% is
112.5 bps.

**Where it lives:** the Article I definition of "Applicable Margin" or
"Applicable Rate", which very often contains the pricing grid table inline.

**Correct when:** the number matches exactly, or `null` matches `null`.
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

  **A deferral `null` must carry a citation, and the quote is the deferral
  language itself.** The value alone cannot distinguish a system that read the
  deferral clause from one that simply declined; the citation can. A system
  that declines for the right reason can point at the sentence that made it
  decline — "Initially, the Applicable Rate shall be determined based upon the
  Debt Rating specified in the certificate delivered pursuant to Section
  4.01(a)(vii)" — and one that declines out of vagueness cannot. This makes
  `null` a falsifiable answer using the citation check that already exists.

  Note this is a *deferral* null, not an *absence* null. `springing_trigger`
  is `null` when no trigger exists, and absence has no sentence to quote, so
  no citation is required there. The distinction is whether the agreement says
  something the labeler is relying on.

  **Where this usually fires:** ratings-based grids, because the rating that
  sets the level is external by construction. But that is an observation about
  where to look, not the rule. The rule is deferral. A ratings grid that states
  its opening category yields an integer; a leverage grid that defers its
  opening level to a closing certificate yields `null`. Encoding "ratings grid
  → null" as the test would hardcode an empirical correlation into the
  labeling rule and mislabel the first document that breaks it.
- Record the margin for **benchmark loans**, not Base Rate loans. The Base
  Rate margin is mechanically the benchmark margin minus 100bps in nearly
  every agreement, so labeling it separately doubles the work for close to
  zero information. Deliberately not a field.
- Where the agreement expresses the margin as a percentage (2.25%), convert to
  bps (225).
- **Half basis points are kept, not rounded.** The field was typed as an
  integer until Mattel, whose ratings grid steps 1.125% / 1.250% / 1.375% /
  1.500% / 2.000% — 112.5 and 137.5 bps at Levels I and III. The same eighth-of-
  a-percent steps are printed in three other grids in this corpus: Advance
  Auto and Roper at 0.795%, Lamb Weston EX-10.1 at 1.125% and 1.375%. None
  happened to be an opening level, which is the only reason nothing had broken.

  This is different in kind from the [record-alignment
  defect](#record-alignment) that was deliberately left open. That construction
  appears nowhere in the corpus, so a rule for it would be written against a
  hypothetical. These values are printed in four of the corpus's own documents;
  the type was simply too narrow for the value space. Widening a type cannot
  change how anything is adjudicated, and no recorded value changes.

### 6. `has_margin_grid`

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
- **A margin that changes only with the passage of time is not a grid.**
  `false`, with the schedule recorded in free text. PureCycle's `Applicable
  Margin` escalates 5.00% → 10.00% → 12.50% → 15.00% → 17.50% on fixed
  calendar dates. It is emphatically not flat, and it is still `false`,
  because the field distinguishes **performance-linked pricing from
  predetermined pricing** — not varying from unvarying.

  Three things settle it. Every `true` case above turns on a condition that
  must be *observed* about the borrower — a leverage ratio, a rating, a
  utilization level — whereas a calendar is fully determined at signing and
  nothing the borrower does changes it. The one-time step-down that is `true`
  is triggered by a measured event, not a date. And decisively:
  `applicable_margin_bps` presupposes a measured grid, since its rules run
  "the rate in effect from the Closing Date until the first compliance
  certificate is delivered" and "where the agreement is silent, record the
  highest level" — PureCycle defines no Compliance Certificate at all, so
  reading it as a grid would make the two fields incoherent with each other.

  This extends the field to a construction it had not met, rather than
  arbitrating between readings of one it had, so it does not count against
  `has_margin_grid` under the [rule-accumulation
  test](#when-a-field-has-accumulated-too-many-rules).
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

### 7. `covenant_type`

**Type:** enum — `total_net_leverage`, `first_lien_net_leverage`,
`secured_net_leverage`, `total_leverage_gross`, `debt_to_capitalization`,
`interest_coverage`, `fixed_charge_coverage`, `debt_service_coverage`,
`minimum_liquidity`, `capex_limit`, `other`.

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
- **Classify by the denominator first, then by netting.** Every leverage value
  above divides debt by EBITDA and is unbounded, typically 3.00x to 7.00x.
  `debt_to_capitalization` divides debt by total capital — debt plus equity —
  and is therefore bounded near 1.00. **A threshold below 1.00 cannot be an
  EBITDA multiple**, which makes this a mechanical test rather than a judgment
  call: a covenant set at 0.65 to 1.00 is a capitalization test whatever it is
  labeled. Apply the denominator test before the netting test, since a
  capitalization ratio may also net cash and would otherwise be misread as a
  `net` leverage variant.
- Direction is **not a field**. It is fully determined by type: leverage
  covenants are maximums, coverage covenants and liquidity minimums are
  minimums. Adding a direction field would be a field that is right by
  construction and would inflate the accuracy number.
- **Coverage covenants are classified by what is in the denominator.**
  Interest alone → `interest_coverage`. Interest plus one or more recurring
  fixed obligations — rent, scheduled principal, taxes, preferred dividends —
  → `fixed_charge_coverage`. The numerator does not decide it; EBITDA, EBITDAR
  and Consolidated Net Income all appear over the same denominators.

  **Lease-adjusted constructions are `fixed_charge_coverage`.** EBITDAR over
  interest plus rent is the standard rent-adjusted form and is common in
  retail and restaurant credits, where capitalized rent is the largest fixed
  obligation on the page. It is named here so the shape does not have to be
  re-argued at each document that carries it.

  The narrower reading — that `fixed_charge_coverage` requires scheduled
  principal in the denominator — is rejected deliberately. Fixed charge
  denominators vary widely in practice, and requiring any particular
  component would push a large share of real fixed charge covenants into
  `other`, turning that value into the dumping ground the enum exists to
  prevent.
- Where a covenant runs for the benefit of revolving lenders only (the
  standard cov-lite structure), it is still recorded — it is a financial
  covenant in this agreement. The beneficiary is noted in free text.

#### `debt_to_capitalization` — added under Roper Technologies

**Trigger:** Roper Technologies, `0001193125-22-199694`.

Roper was selected as the corpus's covenant-free case and is not covenant-free.
§7.1, headed "Financial Condition Covenant", sets a Total Debt to Total Capital
Ratio at 0.65 to 1.00, tested on the last day of any Test Period of four
consecutive fiscal quarters. That is the standard investment-grade and utility
covenant, and before this change it had no home in the enum — it would have
been forced to `other`, which is the outcome the enum exists to avoid.

The gap was already on the record. [corpus.md](corpus.md#covenant-detection-false-negatives)
flagged `debt_to_capitalization` and `net_worth` as missing values after
reading the 21 documents the covenant regexes reported as empty, naming
Eversource Energy as a document that carries the first. Roper is the case that
forces it, so it is added now.

**`net_worth` is still not added.** Phillips 66 appears to carry a consolidated
net worth covenant, but no document in the corpus has been read that requires
the value, and enum values are added when a document forces them, not when one
is anticipated. The gap stays recorded here so that the next labeler who meets
a net worth covenant knows it was foreseen rather than missed.

`debt_service_coverage` will almost certainly never fire in this corpus. DSCR
is project and infrastructure finance; corporate syndicated credit uses
interest coverage or fixed charge coverage. The enum value stays because
removing it would force an `other` on the one deal that has it, but an empty
column for it is the expected result, not a labeling gap.

### 8. `initial_threshold`

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
- **Where the agreement expresses the level as a percentage, record the
  ratio, not the percentage number.** Boeing's "Consolidated Debt … more than
  60% of Total Capital" is `0.60`, not `60`.

  This is not the convention `springing_trigger` uses, and the difference is
  structural rather than arbitrary: that field carries a `threshold_unit`, so
  `35 / percent` says what it is, while `initial_threshold` carries no unit and
  a bare `60` is indistinguishable from a ratio of sixty times. The two
  documents that force this are the same covenant type — Roper's
  `debt_to_capitalization` at "0.65 to 1.00" and Boeing's at "60% of Total
  Capital" — and covenants align on `covenant_type`, so the records are meant
  to be directly comparable. Recorded either way, one of them would be wrong by
  a factor of a hundred.

  Two careful labelers did split on this, which is the condition this document
  exists to remove.
- Where there is a separate, higher level for an acquisition holiday
  (a "Covenant Holiday" or leverage step-up following a material acquisition),
  record the **non-holiday** level. The holiday is a conditional override, not
  the covenant level.
- **Any alternative level or schedule that applies only on a future condition
  is a conditional override. Record the level and schedule in effect at
  closing.** The acquisition holiday is one instance; it is not the only one,
  and it is not always looser.

  Mattel §7.05(b) carries two leverage schedules: (A) "Prior to the Fall-Away
  Date" and (B) "On and following the Fall-Away Date", where the Fall-Away Date
  is the first day the borrower holds BBB-/Baa3/BBB- ratings from two of three
  agencies with no Event of Default and has certified it. Schedule (B) is
  **tighter** — 4.00/3.75 against (A)'s 4.50/4.25/4.00. Schedule (A) is in
  effect at closing; it is the one recorded, as `initial_threshold` and as
  `step_down_schedule` both. Lamb Weston EX-10.1 had already met the same
  construction in a single level — a tighter 3.50x during an elective
  Collateral and Guarantee Suspension Period — and recorded the 5.00x in effect
  at closing *by analogy* to this rule. Mattel is the second document leaning
  on that analogy, which is the point at which it stops being an analogy and
  becomes the rule.

  The test is the one the benchmark field already uses: record what is in
  effect, not its successor. Whether the alternative is triggered by an
  acquisition, a ratings upgrade or an election, and whether it loosens or
  tightens, does not change the answer.

  Re-applied across all seven documents that carry a conditional override —
  Plains, Advance Auto, Kontoor, Extreme, ANI, MP Materials, Lamb Weston EX-10.1
  — and every one records the level in effect at closing. No label changes.

### 9. `step_down_schedule`

**Type:** array of `{effective_from, threshold: number}`, ordered by
`effective_from`. `effective_from` takes the same `{value, basis}` shape as
[`maturity_date`](#3-maturity_date), and means the same thing in both bases:
the **first fiscal period at the new level**.

- `stated`: `value` is an ISO-8601 date — the end date of that period, as the
  agreement states it. **Record the precision the agreement states**, which
  may be a month: `"2027-11"` is a legal value where the table says only "the
  Fiscal Quarter ending November 2027". See [Reduced
  precision](#reduced-precision-and-how-it-is-scored) below.
- `relative`: `value` is a **structured object**, `{quarters_after, anchor}` —
  `{"quarters_after": 5, "anchor": "Closing Date"}`. Use `months_after` where
  the agreement counts in months.

**Where it lives:** same table as `initial_threshold`.

**Correct when:** the arrays match as ordered sequences — same length, and
every pair matches on both keys. For `relative`, `quarters_after` (or
`months_after`) and the normalized `anchor` must both match. A partial match is
scored as a miss on this field; per-step credit is reported separately as a
diagnostic.

Adjudication rules:

- `[]` means the covenant level is flat for the life of the agreement.
  Confirmed flat, not unknown.
- The `initial_threshold` is **not** repeated as the first element. The array
  holds only changes from the initial level.
- Where the table's periods are described relative to fiscal quarters ("the
  fiscal quarter ending closest to June 30, 2026"), record the date the
  agreement itself states, `basis: stated`. Do not attempt to resolve a
  52/53-week fiscal calendar to a real date — the calendar is not in the
  document.
- **Where the agreement states no date at all, `basis` is `relative`.** A table
  keyed purely to a formula — "the fourth full Fiscal Quarter ending after the
  Closing Date" — has no date to record, and the Closing Date is itself defined
  by condition satisfaction. The two rules above were written for an agreement
  that names a date somewhere; this one does not.

  > **Why structured rather than the sentence verbatim.** The same reason
  > `maturity_date` is structured. "The first Test Period ending after the last
  > day of the fourth full Fiscal Quarter ending after the Closing Date" and
  > "after the fourth full fiscal quarter following the Closing Date" are one
  > answer and two strings, and under free-string normalization one of them
  > would score as a miss. This field already has a harsh scoring rule — the
  > whole array is a miss if any pair differs — so a phrasing-sensitive key
  > would compound.

- **Count to the first period at the new level, not the last at the old one.**
  This is where the mistake will be made, because the drafting says the
  opposite. Amentum §6.09 has two rows: 5.25x for Test Periods through the
  **fourth** full Fiscal Quarter after the Closing Date, then 5.00x "for any
  Test Period ending **thereafter**". "Thereafter" points backwards at the
  fourth; the value records the fifth —
  `{"quarters_after": 5, "anchor": "Closing Date"}` — because that is the first
  period actually tested at 5.00x.

  The convention is chosen so the two bases stay semantically identical: a
  `stated` `effective_from` has always meant the first period at the new level,
  and a `relative` one now means the same. A field name with two meanings
  depending on basis would be worse than either meaning.
- The final "and thereafter" row is a step-down like any other; the absence of
  an end date is expected.

#### Reduced precision, and how it is scored

A fiscal-period table can name a month without naming a day. Lamb Weston
§8.11(a) steps from 5.00x to 4.75x "on and after the last day of the Fiscal
Quarter ending November 2027", and the agreement's only calendar fact is that
the Fiscal Year ends on the last Sunday in May. The day is not derivable
without assuming a 13-week quarter, which this schema forbids.

So `stated` accepts **`YYYY-MM` as well as `YYYY-MM-DD`**, and the rule is:
record the precision the agreement states, never more.

**Comparison is exact on the string, and a prediction finer than gold is a
miss.** Gold `"2027-11"` against a predicted `"2027-11-28"` is **wrong**, not
approximately right and not a rounding question.

This is the intended behaviour rather than an artifact, and it is written down
so that a scorer implementation does not have to guess and inherit whatever a
date library happens to do. `"2027-11-28"` is a real claim: it asserts the
fiscal quarter ends on a specific Sunday, which the document does not say. A
system that produces it has resolved a calendar it was not given — the same
class of error as inventing a margin for a deferred opening level, and this
field's guard against it is the same one, refusing to reward a confident value
the document does not support. Scoring it as correct would teach exactly the
wrong thing.

The converse, gold `"2027-11-28"` against a predicted `"2027-11"`, is also a
miss: the document stated a day and the system dropped it. The rule is symmetric
because the target is fidelity to what the agreement says, in both directions.

### 10. `testing_frequency`

**Type:** enum — `continuous`, `weekly`, `quarterly`, `monthly`, `semiannual`,
`annual`, `event_driven`.

**Where it lives:** the lead-in to the covenants section — "as of the last day
of each fiscal quarter of the Borrower".

**Correct when:** the enum matches exactly.

`continuous` was added under Boeing, whose §4.2(b) covenant forbids the
borrower to "permit its Consolidated Debt … to be **at any time** more than
60% of Total Capital". There is no period-end lead-in anywhere in the section:
breach occurs the moment the ratio is exceeded, not at a quarter end. `annual`
was the nearest existing value and is wrong — it would record the §4.1(a)(2)
reporting cadence, and **this field is defined off the test date, not the
reporting date**. Common in investment-grade revolvers, where the covenant is
a continuous maintenance test and the certificate merely evidences it.

`weekly` was added under Peloton, whose minimum-liquidity covenant is tested
"as of the last Business Day of any week" whenever a Revolving Loan is
outstanding. That is periodic, not conditional, so `event_driven` would have
been wrong — the conditionality belongs in `springing_trigger`, which is
exactly the split the rule below insists on.

**Adjudication rule that matters:** `springing` is not a frequency. A springing
covenant is still tested quarterly; it is *conditional*, not *infrequent*.
Conditionality lives in `springing_trigger`. Conflating the two is the single
most common way this field gets labeled inconsistently by two careful people,
which is exactly why it is split.

### 11. `springing_trigger`

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
- **A one-time, irreversible condition that switches a covenant on — or off —
  permanently is not a springing trigger.** Record `null`, `null_kind`
  `absence`, and put the phase-in or sunset in free text.

  This field is for conditionality that is **re-evaluated every test date**: a
  covenant that bites this quarter because the revolver is drawn and does not
  bite next quarter because it is repaid. A permanent switch is a different
  thing. Once it fires the covenant is tested unconditionally in every period
  thereafter, which is exactly what `null` is defined to mean; before it fires
  the covenant does not exist to be triggered.

  **And the construction cannot be recorded faithfully anyway.** MP Materials'
  "Covenant Trigger Event" is the **earlier** of (a) a certificate showing
  Consolidated EBITDA ≥ $400,000,000 and (b) delivery of the financial
  statements for the quarter ending June 30, 2027. The limbs are not
  commensurable — one is an amount, one is a date — and limb (b) is a
  **certainty**: those statements will be delivered, so the covenants turn on
  by mid-2027 whatever EBITDA does. A `threshold` of `400000000` would record
  the limb that may never operate and silently drop the one that must. That is
  not an incomplete value, it is a false one.

  This is distinct from a [greater-of trigger](#12-springing_trigger), where
  both limbs measure the same quantity and choosing one is a documented
  convention. Here there is nothing to choose between.

  **The precedent for the shape of this answer is the springing-maturity
  exclusion.** `maturity_date` refuses a construction it cannot hold and sends
  it to free text rather than recording a distorted version. Same move, same
  reason.

  **The cost, stated:** `condition_type` `other` returns to never having
  fired, and the phase-in structure — the first in this corpus, and a real
  feature of a pre-revenue borrower's credit agreement — survives only as a
  note. A field that records a construction falsely is worse than a field that
  declines to record it, but the information is lost either way and that
  should be visible.
- The typical trigger is revolver utilization above a threshold (commonly 35%
  or 40% of commitments) measured on the last day of a fiscal quarter. Record
  the percentage as a number: 35% → `35`, unit `percent`.
- Where the trigger is expressed as minimum availability in dollars rather
  than utilization as a percentage, `condition_type` is `minimum_availability`
  and the unit is `currency`.
- **A trigger on *any* drawn revolver is `threshold: 0`, unit `currency`.**
  Peloton's covenants apply "solely to the extent any Revolving Loan is
  borrowed or outstanding". That is a threshold of zero dollars, not of zero
  percent: the document never expresses it as a proportion of commitments, and
  recording `percent` would invent a denominator it does not use. The same
  preference as the greater-of rule below — where the document fixes an
  amount, the currency limb is the one recorded.
- Where letters of credit are excluded from the utilization calculation (very
  common — undrawn LCs up to some amount do not count toward the trigger),
  that exclusion is noted in free text and does not change the threshold.
- **Where the trigger is a "greater of" or "lesser of" pairing a percentage
  with a dollar amount, record the currency limb.** G-III's covenant springs
  when Availability falls below "the greater of 10% of the Maximum Borrowing
  Amount and $52,500,000"; the recorded threshold is `52500000`, unit
  `currency`, and the percentage limb goes in free text.

  Two reasons, neither of which is that the other limb is unstated — `10` and
  `percent` would both be recordable. First, this field already pairs
  `minimum_availability` with `currency` in the rule above. Second, the dollar
  limb is a constant of the agreement, while the percentage limb floats with a
  borrowing base that is redetermined monthly and is not in the document, so
  only the currency limb has a level the document fixes.

  **The cost, stated because it is real: the recorded limb is usually the one
  that does not bind.** At G-III's $700M of commitments the 10% limb is $70M
  and governs whenever the borrowing base is $525M or more, so $52,500,000 is
  a floor that rarely operates. The rule takes a determinate value over an
  operative one, deliberately, and a reader should not discover that by
  working it out.

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
locating offsets across ~330 field instances is the most painful thing this
schema could ask for and it buys nothing the quote does not already buy. If a
quote matches at more than one offset the first is taken; ambiguity there is
irrelevant, since the check is whether the language exists in the document at
all.

Citation accuracy is scored and reported **separately** from field accuracy.
The two questions — did it get the number right, and can it show you where the
number came from — are different, and a system that is right for the wrong
reason should not be able to hide inside a single aggregate.

### `null_kind` — a gold annotation, not a schema field

Label files carry `null_kind` alongside any null value, taking `"deferral"` or
`"absence"`. It determines whether a citation is required: a deferral null
must quote the language that defers, an absence null has nothing to quote.

**It is deliberately not part of the extraction schema and is not scored.**
The model is never asked for it. The reason is the one that already excluded
covenant direction: `null_kind` is fully determined by field identity. On
`applicable_margin_bps` a null is essentially always a deferral; on
`springing_trigger` it is essentially always an absence. A model producing it
would be right by construction, and scoring it would inflate the headline
number with a field that cannot be got wrong.

The scorer reads `null_kind` from the gold record to decide whether to demand
a citation for that null. That preserves the machine-checkability without
asking the model for an answer it cannot fail.

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
> **Known limitation: all three facility tiebreakers can be exhausted.** Type,
> then `(type, currency)`, then commitment descending — an agreement with two
> facilities of the same type, in the same currency, at the same amount
> defeats every one of them, and the alignment becomes arbitrary. Lithia
> Motors is the demonstrated case: its Revolving Facility and Used Vehicle
> Flooring Facility are both CAD $100,000,000, so classifying both as
> `revolver` would have left no rule to align them by. That document was
> excluded for unrelated reasons, which means **this hole is unpatched and
> undemonstrated in the corpus** rather than fixed.
>
> It is recorded because it is a defect in the rule, not a fact about one
> document, and the next agreement with mirrored tranches will hit it. The
> obvious next tiebreaker is order of appearance in the commitment sections,
> which is mechanical and reproducible; it is deliberately **not** adopted
> here, because no document in the corpus forces it and a rule written against
> a hypothetical is the thing this schema keeps refusing to do.

- A predicted item with no gold match is a **spurious record** — every one of
  its fields counts against precision.
- A gold item with no predicted match is a **missed record** — every one of
  its fields counts against recall.

Reporting per-field F1 rather than raw accuracy follows CUAD and ContractEval,
which is the point: the methodology is borrowed so that the numbers are
comparable to published work, and the schema is the new part.

---

## Labeling budget

Eleven fields sounds small. It is not, because they are nested.

A two-tranche, two-covenant agreement — the modal deal in this frame — is:

```
6 facility fields  × 2 facilities =  12
5 covenant fields  × 2 covenants  =  10
                                    ---
                                     22 field instances
```

Each of those carries a section reference and a verbatim quote. At 15
documents that is **~330 labeled values and ~660 supporting citations**; at 20
it is ~440 and ~880. The figures were ~360 and ~720 when `facility_name` was
a field.

**Plan for 15.** Extend to 20 only if the first five go faster than expected.
A complete, carefully adjudicated 15 beats a rushed 20, and the held-out set
is the credibility of the whole project — it is the wrong place to be tired.

If the budget needs cutting further, the order is:

1. **`step_down_schedule`** is the most expensive single field — it is an
   array, and it requires reading a table carefully. But it is also one of the
   most interesting results, since it is where regex baselines fail hardest.
   Cut it only if the alternative is not finishing.

`facility_name` used to head this list and has already been cut, on its own
pre-registered trigger rather than for budget. See the note under [Facility
fields](#facility-fields).

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

**Report the instance count next to every per-field number.** Some fields will
not have enough instances to score at all, and the count is what lets a reader
see it rather than take an F1 on trust. `step_down_schedule` is the live case:
only a handful of covenant records carry a non-empty array, and just one —
Mattel's — has more than one step, so the multi-step sequence comparison rests
on a single real instance. For most of labeling it rested on none. A number
reported without its n invites exactly the reading it cannot support; the
generated table in [results.md](results.md) carries the current count. See
[labeling-notes.md](labeling-notes.md#step_down_schedule-one-multi-step-schedule-and-it-was-not-selected-for).

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

### One category of disagreement is worth more than the rate

Some labels are nominated in advance, with their reasoning recorded, because
they share a specific shape: **a rule fixed before labeling decides the case
cleanly, and trained market intuition says the opposite.** These are not close
calls or hard readings; the labeler knew the answer the rule gave, recorded it,
and wrote down that it felt wrong.

Two so far, both in [labeling-notes.md](labeling-notes.md#flagged-in-advance-for-the-blind-relabel):

- **Amentum `has_margin_grid`** — a flat margin with one one-way ratings
  step-down is `true` under the fixed-versus-variable rule, and nobody in the
  market would call it a grid.
- **Lamb Weston `facility_type`** — an unlettered euro bullet held by three
  relationship banks is `term_loan_b` under the amortization rule, and every
  commercial instinct says pro rata bank tranche.

If the blind pass reverses either, the finding is **not** that the document was
misread. It is that the rule and the domain disagree, and the rule is what a
model gets scored against. Reversing both would say something stronger still —
that the schema was written to be mechanical at the cost of being right, which
is a defensible trade but must be a stated one. Report this category
separately from the headline agreement rate; a disagreement here is a result,
not an error.

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
| Percentages | basis points where the field says bps, keeping half points (`1.125%` → `112.5`); otherwise number |
| Ratios | two decimals, `4.00:1.00` → `4.00`; a percentage level is a ratio, `60% of Total Capital` → `0.60` |
| Dates | ISO-8601 `YYYY-MM-DD` |
| Enums | exact match against the stated value set |
| Free strings | lowercase, strip articles and punctuation, collapse whitespace |

> **The free-string row currently governs nothing.** `facility_name` was the
> only free-string field and it was
> [cut](#facility-fields); every remaining scored field is an enum, a number, a
> date, a boolean or a structured object, all compared exactly. The row is kept
> because a v2 that reintroduces a string field will need it — and because
> anyone reading this table cold would otherwise assume it is live.
>
> **A known gap for that v2: it does not collapse plurals.** Lamb Weston names
> its tranches `Revolving A-2 Loan` in the §2.01 definition and `Revolving A-2
> Loans` in the subsection heading and the cover-page CUSIP label. Under this
> row those are different answers, so a system returning the heading's form
> would be scored wrong for a difference of one character that carries no
> meaning. Singularization is the obvious fix and it is not free — it has its
> own failure modes on defined terms that are plural by construction
> ("Commitments", "Obligations") — which is exactly why it should be decided
> before a string field returns, not after.

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
      "facility_type": "revolver",
      "aggregate_commitment": { "amount": 500000000, "currency": "USD" },
      "maturity_date": { "value": "2029-06-14", "basis": "stated" },
      "interest_rate_benchmark": "term_sofr",
      "applicable_margin_bps": 200,
      "has_margin_grid": true
    },
    {
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
        {
          "effective_from": { "value": "2026-06-30", "basis": "stated" },
          "threshold": 4.25
        },
        {
          "effective_from": { "value": "2027-06-30", "basis": "stated" },
          "threshold": 4.0
        }
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
