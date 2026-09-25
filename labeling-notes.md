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

### One agreement, two facilities, and both grid heuristics wrong at once

**Found in:** Peloton Interactive, 2024-05-30 (`0001193125-24-150397`)
**Affects:** `has_margin_grid`
**Correct verdict:** `false` on the revolver, `true` on the term loan

Paya taught that a pricing-grid table can exist without the *margin* being
gridded. Peloton is the harder case: the grid is real, it governs one facility,
and it does not govern the other. The `Applicable Rate` proviso reads

> with respect to clauses (a) and (b)(iii) **only** … the Applicable Rate for
> ABR Loans and Term Benchmark Loans and the Commitment Fee shall be based on
> the First Lien Net Leverage Ratio

Clause (a) is the Initial Term Loan margin; clause (b)(iii) is the revolver's
*Commitment Fee*. The revolver's own interest margin, in (b)(i)–(ii), sits
outside the proviso and is flat for the life of the facility.

**Both obvious heuristics fail, in opposite directions, on the same document.**
A rule keyed to the defined term `Applicable Margin` reads this agreement as
having no grid at all — the phrase is not a defined term here and appears only
as the grid table's two column headers. A rule keyed to the presence of a
pricing-grid table reads it as fully gridded. One is wrong about the term loan,
the other about the revolver, and no single facility-blind answer is right.

**And there is a check that does not depend on parsing the word "only".** The
revolver's stated margins are 5.00% Term Benchmark and 4.00% ABR. The grid's
columns are 5.500/6.000 and 4.500/5.000. The revolver's numbers appear in
neither column, so the grid cannot be governing them. Meanwhile the term
loan's 6.00%/5.00% and the fee's 0.50% each equal the ≥ 5.00x row exactly —
the set the proviso names. Arithmetic confirms what the cross-reference says,
which is the kind of independent confirmation worth having when the deciding
word is a single "only" buried in a 92,000-word definition.

This is also the modal pattern inverted: the institutional TLB carries the
leverage grid and the revolver is flat-priced, where
[schema.md](schema.md#class-balance) assumes the reverse.

### Keyword heuristics under-detect, and the corpus rationales inherited it

**Affects:** the baseline, and `corpus.md`'s selection rationales.

The false-positive mechanisms below are the ones a keyword baseline will fall
into. This is the other half, and it is larger: the same heuristics **miss**
constructions systematically, and because `screen.py`'s signals were used to
write the selection rationales in [corpus.md](corpus.md), documents were
selected for properties they do not have.

Three independent instances, in the order they surfaced:

1. **Covenant detection.** The regexes match `Leverage Ratio`, `Interest
   Coverage Ratio`, `Fixed Charge Coverage` and `First Lien Leverage`. Reading
   the 21 documents they reported as covenant-free turned up debt-to-
   capitalization, consolidated net worth, and interest coverage written as a
   ratio of components — none matched. Roper is the costly case: it was
   selected as the corpus's covenant-free document and has a Total Debt to
   Total Capital Ratio at 0.65 to 1.00 in §7.1, under a heading reading
   "Financial Condition Covenant" inside an article headed NEGATIVE COVENANTS.
   A phrase search for "financial covenant" never sees it.
2. **The re-read that was supposed to catch it.** Two documents were then
   cleared by hand as genuinely covenant-free, Roper and PPG Industries. Roper
   was wrong. PPG was cleared by the same reader applying the same method in
   the same pass, so its status is unverified rather than confirmed — the
   check and the thing it was checking failed together.
3. **Structure and grid signals, measured.** Comparing `screened.jsonl`
   against the labels: `structure` is correct 3 of 6 and `pricing_grid_hint`
   3 of 6 over the first six documents read, **with every grid error a false
   negative**. It scored `false` on Plains and Advance Auto, both of which
   carry five-level ratings grids, and on Lamb Weston, which carries three
   tiered grids. `structure` reported `revolver_plus_tla` for a term-only
   agreement and confused TLA with TLB twice.

4. **Covenant counts, in both directions.** The rationales also quote covenant
   counts, and the signal that produced them matches *defined ratio
   vocabulary* rather than identifying maintenance tests. Against the labels:
   Amentum predicted four covenant types and has **one** — the other three
   ratios are defined and used only for incurrence tests. Kontoor predicted
   three and has two, for the same reason. Advance Auto predicted one and has
   two, because its second covenant is labeled "Consolidated Coverage Ratio",
   a neutral name no pattern matches. Two of five exact.

**The errors are systematic, not random, but they are not all misses.** A
keyword rule fires on the language it was written for and is silent on
everything else, so anything asking *does this exist* — covenant presence,
grid presence — fails as a miss, and every `pricing_grid_hint` error measured
so far is a false negative. But anything asking *how many* over-counts
instead, because a defined term that looks like a covenant is counted whether
or not it is one. Both directions produce the same end state: a corpus
rationale that asserts something the document does not support.
[corpus.md](corpus.md) row 7 selected Lamb Weston for "Lettered TLA with no
grid"; that accession holds two agreements, neither matching, and both carry
grids. Row 12 selected G-III Apparel for "3 covenants with **no** grid" from
the same signal; it has since been read and is a revolver-only ABL with one
covenant and an availability grid. Both documents chosen to supply
`has_margin_grid: false` supply `true`.

**Why this belongs with the baseline rather than only in the corpus file.**
The baseline this project scores against is a keyword/regex extractor. These
are measured instances of its failure mode, on real documents, with the
correct answer established by reading — which is exactly what makes the
comparison fair rather than a strawman. The headline result is extraction
accuracy against that baseline, and a reader is entitled to know the baseline's
errors are characterized and directional rather than hand-waved. Stated in
[README.md](README.md) for that reason.

The uncomfortable corollary is that this project used the same class of tool to
choose its own test set. That is recoverable — selection signals are checkable
by reading, and reading is what the grid audit does — but it has to be said
plainly rather than discovered by a reader.

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

### `maturity_date` — `relative` values are structured, not verbatim strings

**Trigger:** document two, Plains GP Holdings — the first `relative` maturity.

Plains states no calendar maturity anywhere: the definition is "the later of
(a) such date that is five years from the Closing Date...". As a verbatim
string that value would be scored under the text normalization rules, where
"five years from the Closing Date", "the fifth anniversary of the Closing
Date" and "such date that is five years from the Closing Date" are three
different answers to one question. All three are substantively correct and two
would score as misses.

That is a false-negative mechanism built into the field — it would measure
phrasing rather than extraction. `relative` values are now
`{tenor_years, anchor}`, which is machine-comparable and removes the
normalization guesswork entirely.

### `maturity_date` — the limb rule generalized

**Trigger:** document two, Plains GP Holdings.

The rule written after Paya covered "earliest of (i) a date (ii) termination
(iii) acceleration". Plains is "**later** of (a) five years (b) any extended
date under §2.14" — the mirror construction, with an extension option rather
than early termination, and not covered by the rule as written.

Generalized to: **record the limb that states a date or a period; limbs
referencing termination, acceleration, or an extension option are mechanics.**
This covers both constructions without either being a special case and does
not depend on limb order. An earlier draft said "the primary limb", which is
not mechanical enough for a second labeler to apply.

### `facility_name` — cut, not patched

**Trigger:** Kontoor Brands, `0001760965-21-000058`.

The field carried a standing instruction, written into schema.md after the
cover-page rule below: it had generated its own sub-rule on the second
document labeled, and **if it required a third rule it was to be cut rather
than patched**. Kontoor required a third rule. The field is gone.

Kontoor names the same tranche twice, in its own Article I defined terms, in
two incompatible styles. The definition of "Facility" gives `Revolving
Facility` and `Tranche A Term Facility`; §2.6(a) and §2.3 make `Revolving
Loans` and a `Tranche A Term Loan`. Both are the borrower's own label for the
tranche, which is all the rule ever said. Its list of places the name lives —
Article I, the commitment section, the cover page, the commitment schedule —
never ranked them, and its own examples pulled both ways, `"Revolving Credit
Facility"` alongside `"Term A Loans"`. With no ordering, the document supplies
two answers and the schema picks neither.

**The tempting escape was itself the third rule.** It is easy to argue that no
new rule is needed: the field is `facility_name`, Kontoor expressly names its
*facilities*, and "Revolving Loans" names loans rather than a facility. That
reading reaches the labeler's recorded values without adding a sentence to
schema.md. But it is a fresh interpretive step that the existing text does not
contain, and adopting it silently is how a field accumulates rules while
appearing not to. Recognizing that was the actual decision point.

**What the cut costs, honestly.** The case for keeping it was that a human
reviewer keys off the tranche name, and that a model which cannot name what it
just extracted is telling you something. But `facility_type` already carries
the semantic weight, and [record alignment](schema.md#record-alignment) keys
on `facility_type` and commitment, never on the name — so the diagnostic is
largely duplicated by a field that is actually well defined. Against that: three
documents, three rules, and a field where two careful readers disagree is
measuring phrasing rather than extraction. The same reasoning already produced
the structured `relative` maturity, which exists so that three correct
phrasings of one answer stop scoring as two misses.

The budget effect is small — one instance per facility, ~330 values instead of
~360 — because the field was cheap. Cheapness was never the argument for
keeping it.

**Why this is a result rather than an embarrassment.** The trigger was written
down before the document that fired it existed, which is what made it binding.
A rule invented at the moment it is needed can be argued away; one pre-
registered cannot, and the honest move is to honor it at the document that
fires it rather than grant an exception and write a fourth rule at document
seven. The three sub-rules the field generated are preserved below as the
evidence that produced the decision.

### `facility_name` — the cover-page rule

**Trigger:** document two, Plains GP Holdings.

Plains never names its tranche in the operative text. "Revolving Credit
Facility" appears **exactly once in 84,000 words**, as the tail of the
cover-page label "Senior Unsecured Revolving Credit Facility", sitting between
the arrangers and the table of contents. The body defines only "Commitment",
"Committed Loans" and "Aggregate Commitments".

Rule: for a single-facility agreement whose body uses only
"Commitment"/"Loans", take the cover-page label excluding ranking and security
descriptors, which describe capital-structure priority rather than the tranche.

Recorded with a maintenance warning in schema.md: this field has now generated
its own sub-rule on the second document, and it is already the weakest-signal
field, reported separately, first in the cut order. If it needs a third rule,
it gets cut instead. A field that keeps needing exceptions is not well defined.

> That warning came due at Kontoor Brands and the field was cut; the rule it
> guarded no longer exists in schema.md. This note is kept as written, because
> it is the record of the second of the three rules that produced the
> decision — see [`facility_name` — cut, not patched](#facility_name--cut-not-patched).

### `null_kind` — added to gold, deliberately excluded from the schema

**Trigger:** document two, Plains GP Holdings.

The label file needs to record whether a null is a deferral or an absence,
because that decides whether a citation is required. But `null_kind` is not an
extraction field and is not scored, for the same reason covenant direction was
excluded: it is fully determined by field identity. A null on
`applicable_margin_bps` is essentially always a deferral; one on
`springing_trigger` is essentially always an absence. A model producing it
would be right by construction, and scoring it would inflate the number with a
field that cannot be got wrong.

Kept as a gold annotation that configures the scorer. Machine-checkability
without the inflation.

### `maturity_date` — basis is decided by one definition, and the field is exempted from the cut test

**Trigger:** Extreme Networks, `0000950170-23-029645`.

Extreme's maturity definitions are anniversary formulations — "the date
occurring on the five-year anniversary of the Restatement Date" — but
`Restatement Date` is itself hard-coded in §1.1 as June 22, 2023, so the
maturity resolves inside the document to 2028-06-22. The rule said `stated`
applies "where the agreement gives a hard date" and gave the anniversary form
as its canonical `relative` example. It never said which one wins when the
anchor is a date and the maturity is a period.

**The gap was not confined to the document that flagged it.** Checking the
anchor definition across all five labeled filings: Plains, Advance Auto and
Kontoor define theirs by condition satisfaction and are unresolvable; Amentum
defines `Closing Date` as "September 27, 2024" and is resolvable, and was
already committed as `relative` with the resolved dates sitting in a note.
Only Extreme's labeler raised it. Two documents, one question, one of them
silent — the argument for checking a flag against the whole set rather than
the document that produced it, which is the same habit the reasoning error
above already argued for.

Rule: basis is decided by the Maturity Date definition alone.

**What settled it was a Saturday.** Amentum's term maturity resolves to
2031-09-27, and the definition carries a succeeding-Business-Day proviso that
the limb rule classifies as a mechanic to be disregarded. Resolving the date
forces a choice the schema explicitly declines to make — 2031-09-27 or
2031-09-29 — and the Amentum label had already computed both, which is the
two-defensible-answers condition demonstrated rather than hypothesized.
Secondary: resolving imports date arithmetic into an extraction score, and
nothing is lost by declining, since the structured value plus the anchor's own
definition resolves the date at scoring time.

**Re-application:** no label changed. All six facility records across five
documents are `relative`, including both resolvable ones.

#### The exemption, and the test that grants it

This was the fifth rule attached to `maturity_date`. `facility_name` was cut
at three. That asymmetry needed answering rather than assuming, and the answer
is a distinction rather than a count, now written into
[schema.md](schema.md#when-a-field-has-accumulated-too-many-rules): a rule that
**arbitrates between competing readings of the same construction** counts
against a field, because each one is evidence the field is underdetermined; a
rule that **extends coverage to a construction not previously seen** does not.
Second arbitrating rule earns a written warning naming the third as fatal.

`facility_name` took three arbitrating rules — which source ranks highest,
what to do when only the cover page names the tranche, how to choose when
Article I names it twice. `maturity_date`'s five each cover a different
construction and none overrules another on the same facts.

Applied retrospectively the test cuts `facility_name` at exactly the point it
was cut and leaves `maturity_date` alone, which is the only reason to trust it.
A test built after the fact that happened to spare the field in front of you
would be worth nothing. The `facility_name` cut has value precisely because
the trigger bound when it was unwelcome, and an exemption that read as carving
out the interesting field would spend that. So the reasoning is on the page
and a second reader can apply it to the same facts and disagree.

### `aggregate_commitment` — rolled-over loans are not commitments

**Trigger:** Amentum Holdings, `0000950157-24-001363`.

The existing rules covered later amendments and incremental capacity, both of
which are about debt that does not exist yet. Amentum is the mirror case: debt
that exists at closing but was committed somewhere else. `Initial Term Loans`
is defined as the loans made under §2.01(a) **plus** US$1,130,000,000 of
SpinCo Term Loans funded under a separate Term Credit Agreement of the same
date, rolled in at the Merger effective time. US$3,750,000,000 is outstanding
on day one against an `Initial Term Commitment` of US$2,620,000,000.

Rule: record the commitment made under this agreement; loans converted, rolled
or assumed from another instrument are noted in free text, not added.

**The citation requirement decided it, which is the point worth keeping.** Two
defensible readings existed — the commitment, or the economic tranche — and
the tie-break was not judgment. US$3,750,000,000 appears nowhere in the
document, so that answer cannot carry a verbatim quote. A rule that forces an
uncitable value is the wrong rule, and the citation guard turned a question of
taste into a mechanical test. That is the second time a rule written for
hallucination control has settled an unrelated classification question; the
first was the deferral null on Advance Auto, where "document **or** fact" held
for a case it was not written against.

Worth flagging for anyone reading the label: a reviewer keying off economic
tranche size will expect US$3.75B and should not conclude the label is wrong.
The note in the label file says so.

### `step_down_schedule` — `effective_from` gets the two-basis treatment

**Trigger:** Amentum Holdings, `0000950157-24-001363`.

`effective_from` was typed as an ISO-8601 date, and the field carried a rule
for fiscal-period drafting: record the date the agreement itself states, and
do not resolve a 52/53-week calendar. Both assumed the agreement names a date
somewhere. Amentum's §6.09 table names none. It is keyed purely to a formula —
5.25x for Test Periods through the fourth full Fiscal Quarter after the
Closing Date, 5.00x thereafter — and the Closing Date is itself defined by
condition satisfaction. The type had no legal value to hold, and the two rules
contradicted each other on this document.

`effective_from` now takes the same `{value, basis}` shape as `maturity_date`,
with `relative` carrying `{quarters_after, anchor}`.

**The rejected fix is the instructive part.** The obvious repair — record the
agreement's own formulation as a string — was proposed and declined, because
it rebuilds precisely the false-negative mechanism removed at Plains. "The
first Test Period ending after the last day of the fourth full Fiscal Quarter
ending after the Closing Date" and "after the fourth full fiscal quarter
following the Closing Date" are one answer and two strings. This field is
harsher than most: the whole array scores as a miss if any pair differs, so a
phrasing-sensitive key compounds rather than costing one instance. The second
time the same trap was walked into, which is an argument for stating the
principle rather than the instance — a value that a labeler could phrase two
ways is not a value.

**The off-by-one, and why the convention went the way it did.** Amentum's
second row reads "for any Test Period ending **thereafter**", and "thereafter"
points backwards at the fourth quarter. The recorded value is the fifth, the
first period actually tested at the new level. That matches what a `stated`
`effective_from` has always meant, so the two bases stay semantically
identical instead of becoming one field name with two meanings. The phrasing
is the trap and it is written into both the rule and the guide with this row
as the worked example.

**Re-application:** every committed label has `step_down_schedule: []` —
Plains, both Advance Auto covenants, both Kontoor covenants — so no committed
value changed. Amentum is the only document in the corpus so far with a step
at all, which is worth noticing on its own: the field the schema calls the
most expensive to label has fired exactly once in five documents.

### `springing_trigger` — a phase-in is not a springing trigger

**Trigger:** MP Materials, `0001193125-25-187776`.

MP Materials' covenant package switches phases. A minimum-liquidity covenant
applies from the Effective Date **until** the "Covenant Trigger Event"; a
leverage covenant and a coverage covenant do not apply until it and then apply
forever. The label arrived recording the two phase-in covenants as
`condition_type: other`, `threshold: 400000000`, `threshold_unit: currency`,
which is what the field's literal discriminator implies — they are not "tested
unconditionally every period".

Rule: `null`, `null_kind` `absence`, phase-in in free text.

**The decisive argument is that the recorded threshold would be false, not
merely incomplete.** The Covenant Trigger Event is the **earlier** of (a) a
certificate showing Consolidated EBITDA ≥ $400,000,000 and (b) delivery of the
financial statements for the quarter ending June 30, 2027. The limbs are not
commensurable, and limb (b) is a *certainty* — those statements will be
delivered, so the covenants turn on by mid-2027 whatever EBITDA does.
Recording `400000000` captures the limb that may never operate and drops the
one that must.

This is what separates it from the [greater-of
trigger](#springing_trigger--greater-of-triggers-record-the-currency-limb) at
G-III, where both limbs measure availability and picking one is a documented
convention with a stated cost. Here there is nothing to choose between: a
number and a date are not two readings of the same quantity.

**The second argument is what makes the rule principled rather than
convenient**, because the first one alone would invite a fix — add a second
threshold slot, or a date limb — rather than a rule. `springing_trigger` was
built for conditionality **re-evaluated at every test date**: a covenant that
bites this quarter because the revolver is drawn and not next quarter because
it was repaid. A one-time irreversible switch is a different phenomenon. After
it fires the covenant is tested unconditionally in every period, which is the
definition of `null`; before it fires the covenant does not exist to be
triggered. So the field is not being made to decline something it could hold —
it never held it.

**Precedent for the shape of the answer:** `maturity_date` excludes springing
maturity provisos and sends them to free text, because the field cannot hold
that construction faithfully either.

**The cost, stated rather than buried.** `condition_type: other` returns to
never having fired in this corpus. The phase-in structure — the first here,
and a real feature of how lenders underwrite a pre-revenue borrower — survives
only as a note, and the eval will not measure whether a system can find it. A
field that records a construction falsely is worse than one that declines to
record it, but the information is lost either way.

**Re-application:** no committed label changes. All five non-null triggers in
the corpus are per-period conditions — revolver utilization at Paya, Amentum
and Peloton, minimum availability at G-III — and none is a one-time switch.

### `has_margin_grid` — a calendar escalator is not a grid

**Trigger:** PureCycle Technologies, `0001830033-23-000021`.

PureCycle's `Applicable Margin` escalates 5.00% → 10.00% → 12.50% → 15.00% →
17.50% on fixed calendar dates. Neither existing branch fitted: the margin
plainly is not "flat for the life of the facility", and it plainly does not
"vary with a measured condition". The field had met flat pricing and grid
pricing and never met pricing that moves on a schedule.

Rule: `false`. The field distinguishes **performance-linked from
predetermined** pricing, not varying from unvarying.

**The argument that decides it is a consistency argument between two fields,
not an intuition about this one.** `applicable_margin_bps` is defined in terms
of a measured grid — "the rate in effect from the Closing Date until the first
compliance certificate is delivered", and "where the agreement is silent,
record the highest level in the grid". PureCycle **defines no Compliance
Certificate at all**; the phrase occurs five times and every one is a *U.S.
Tax* Compliance Certificate. Reading the escalator as a grid would leave
`has_margin_grid` asserting a grid exists while `applicable_margin_bps` had no
mechanism to locate an opening level within it. Two fields describing the same
definition have to agree about what that definition is.

**How the call was made is worth recording too.** The label arrived saying
`true` in its summary and `false` in the file, with the file carrying a note
that an audit had corrected it. The resolution was not to pick the more
plausible one: the document was re-read, `Applicable Margin` was confirmed to
occur exactly twice, and Pricing Level, Pricing Grid, Leverage Ratio and any
compliance-certificate reset were confirmed absent — zero occurrences each.
The artifact was right and the summary was stale.

That is the third time in this project a claim reported from memory has
diverged from the artifact it described; the other two are the `has_margin_grid`
degeneracy claim and a facility-record count, both recorded
[here](#the-same-shape-in-a-claim-about-the-corpus). All three were cheap
because something checkable existed. The [blind
relabel](schema.md#annotator-agreement) is where that stops being true —
reporting from memory is the exact failure it is designed to detect, and there
the artifact is deliberately not consulted.

### `springing_trigger` — greater-of triggers record the currency limb

**Trigger:** G-III Apparel, `0001558370-24-008935`.

G-III's fixed-charge covenant springs when Availability falls below "the
greater of 10% of the Maximum Borrowing Amount and $52,500,000" — a percentage
paired with a dollar floor, in a field that holds one `threshold` and one
`threshold_unit`. The rule records the currency limb.

**The labeler's first justification was wrong on the facts and is recorded
here because the correction is the useful part.** The note said the dollar
figure was "the only figure the document itself states". It is not: 10% is
stated too, and `threshold: 10, threshold_unit: percent` is expressible. Had
that reasoning gone into the schema unchecked, the rule would have rested on a
false premise and the next labeler would have had no way to see it.

The two reasons that survive: this field already pairs `minimum_availability`
with `currency`; and the dollar limb is a constant of the agreement, while the
percentage limb floats with a borrowing base redetermined monthly and absent
from the document, so only the currency limb has a level the document fixes.

**And the rule records the limb that usually does not bind.** At $700M of
commitments the 10% limb is $70M and governs whenever the borrowing base is
$525M or more; $52,500,000 is a floor that rarely operates. The rule prefers a
determinate value to an operative one. That is a real concession and it is
written into the rule rather than left to be worked out — the same handling as
the bullet-term-loan call, where the mechanical answer and the commercial one
diverge and the mechanical answer governs.

### `facility_type` — `delayed_draw_term_loan` requires the agreement to say so

**Trigger:** ANI Pharmaceuticals, `0000950103-24-012144`.

ANI's term tranche is, commercially, a delayed-draw term loan: committed on
the Closing Date, funded in a single draw at the Alimera acquisition close a
month later, with a ticking fee on the undrawn commitment and automatic
termination on an Acquisition Outside Date. **ANI's own 8-K and 10-Q call it
"a delayed-draw term loan facility (the Term Loan A)".** The agreement itself
never uses the phrase.

Rule: `delayed_draw_term_loan` applies where the agreement labels the tranche
delayed-draw or provides a multi-draw availability period. Both are findable
by searching the document. Otherwise classify by amortization — here
2.5%/5%/7.5%, so `term_loan_a`.

**This is the third field decided by the same principle, which is why the
principle is now stated once in [schema.md](schema.md#the-four-corners-rule)
instead of re-argued each time.** `applicable_margin_bps` goes `null` on a
deferred ratings grid rather than importing the borrower's actual credit
rating. `aggregate_commitment` records Amentum's US$2.62B commitment rather
than the US$3.75B tranche outstanding on day one. And now `facility_type`
reads amortization rather than the borrower's own press description.

Each time, the rejected answer was the one a credit analyst would give, and
each time the ground was the same: a gold value requiring knowledge from
outside the document is not extractable. Scoring against it would reward a
system for knowing things rather than for reading, which is a different
capability and not the one being measured. The citation requirement enforces
it mechanically — none of the three rejected answers can be quoted.

**The cost, stated:** `delayed_draw_term_loan` now needs a document that says
so itself, and may finish the corpus unfired. Accepted on the same basis as
`debt_service_coverage` — an unused enum value costs nothing, and admitting
external characterisation as evidence would cost the field its meaning.

### `step_down_schedule` — `effective_from` accepts a month, and finer is wrong

**Trigger:** Lamb Weston Holdings EX-10.1, `0001679273-24-000026`.

The second `effective_from` gap in two documents, and a different one. Amentum
keyed its table to a period measured from an anchor, which the `relative` basis
now handles. Lamb Weston §8.11(a) instead **names a fiscal period** — "the last
day of the Fiscal Quarter ending November 2027" — giving a month and no day.
`relative` cannot express that without counting quarters through a 52/53-week
calendar, which is the resolution the schema forbids. The agreement's only
calendar fact is that the Fiscal Year ends on the last Sunday in May.

Rule: `stated` accepts `YYYY-MM` as well as `YYYY-MM-DD`, and the labeler
records the precision the agreement gives, never more.

**The comparison rule is the part that needed writing down.** Gold `"2027-11"`
against a predicted `"2027-11-28"` is a **miss**, not a near-match and not a
rounding question, and the same in reverse. Left unstated, a scorer
implementation would have had to guess, and would have inherited whatever a
date library does with mixed precision — most likely parsing both to a
timestamp and calling them equal, which is the wrong answer.

It is the wrong answer for a reason this project already has a name for.
`"2027-11-28"` is a claim: it asserts the fiscal quarter ends on a specific
Sunday, which the document does not say. A system producing it has resolved a
calendar it was not given — the same act as inventing a margin where the
opening level was deferred. `applicable_margin_bps` refuses to reward that and
so does this field. Scoring the finer answer as correct would teach precisely
the behaviour the corpus exists to penalise.

The symmetry is deliberate rather than incidental: gold `"2027-11-28"` against
a predicted `"2027-11"` is also a miss, because the document stated a day and
the system dropped it. The target is fidelity to what the agreement says, in
both directions.

**Re-application:** one step-down exists in the corpus besides this one —
Amentum's, which is `relative` and unaffected. Every other covenant record is
`[]`.

### `covenant_type` — coverage covenants classified by denominator

**Trigger:** Advance Auto Parts, `0001158449-21-000208`.

Advance Auto carries two ratios that the enum did not cleanly decide, and both
are lease-adjusted. §6.09 tests a "Consolidated Coverage Ratio" — a neutral
label carrying no classification — defined as Consolidated EBITDAR over
Consolidated Interest Expense **plus Consolidated Rent Expense**. It is not
`interest_coverage`, because the denominator is not interest alone. Whether it
is `fixed_charge_coverage` depended on a term the schema never defined: what
counts as a fixed charge.

Rule: classify coverage covenants by the denominator. Interest alone is
`interest_coverage`; interest plus one or more recurring fixed obligations is
`fixed_charge_coverage`. The numerator does not decide it — EBITDA, EBITDAR
and Consolidated Net Income all appear over the same denominators — and the
lease-adjusted form is named explicitly, because EBITDAR over interest plus
rent is the standard shape in retail credits and should not be re-argued at
every document that carries it.

The narrower reading, requiring scheduled principal in the denominator, was
rejected on the grounds that decided `debt_service_coverage` and
`debt_to_capitalization`: fixed charge denominators vary widely, and demanding
a particular component would push a large share of genuine fixed charge
covenants into `other`. An enum whose catch-all absorbs a common construction
is not classifying anything.

The §6.08 leverage covenant in the same document needed no new rule. It is
also lease-adjusted — Consolidated Adjusted Funded Debt adds operating lease
liabilities, over EBITDAR — but the denominator-first rule added under Roper
already decides it: an earnings denominator and a 3.75 threshold make it a
leverage ratio, and Total Debt nets no cash, so `total_leverage_gross`. Both
hesitations the labeler recorded resolve to the values already chosen; no
label changed.

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

---

## A reasoning error worth recording

After labeling Advance Auto, one reader reported that `libor` and `null` were
becoming correlated across the corpus and that a model might therefore learn
"LIBOR-era document → decline" rather than reading.

**The premise was false.** Paya is LIBOR with `applicable_margin_bps` = 325 —
a flat sponsor-deal margin, no grid, nothing deferred, verified field by field
two documents earlier. Across the three LIBOR agreements labeled, the field is
an integer once and `null` twice. There is no correlation to worry about.

The error was generalizing from the two most recent documents — both
investment-grade revolvers with ratings grids — backward over a document
already checked. It is the same shape as an earlier mistake in this project,
where the document screen's pass rate looked reasonable while the filter was
wrong, because the passes were inspected and the rejects were not.

Recorded because the failure mode is cheap at document three and expensive at
document twelve, and because it argues for a specific habit: when reporting a
pattern across the corpus, check it against every labeled document rather than
the ones currently in mind. Two of the corrections in this file came from
re-reading the full set rather than from new evidence.

The concern did survive in a better form. A model cannot learn this corpus's
correlations — it is not trained on the set — unless few-shot examples are
drawn from the fifteen, which would be leakage. The genuine issue was
interpretive: `null` alone does not reveal whether a system read the deferral
clause or merely declined. That is now answered by requiring a citation on
deferral nulls, which uses machinery the harness already has.

---

## The syndication test is a proxy, and it fails at both tails

Two documents, found five days apart, break the frame's "Administrative Agent
and ≥3 lenders on the commitment schedule" test in opposite directions. Read
together they say more than either does alone.

**Lamb Weston EX-10.2 fails on form while being economically syndicated.**
Schedule 2.01 lists **one** Lender of record — AgWest Farm Credit, PCA —
holding 100% of every tranche. Roughly thirteen other Farm Credit institutions
sit behind it as Voting Participants under §11.06(e), with real economic
exposure and real votes. The document was excluded.

**PureCycle EX-10.2 passes on form while being economically one creditor.**
Three lenders sign: Sylebra Capital Partners Master Fund, Sylebra Capital Parc
Master Fund, Sylebra Capital Menlo Master Fund. Three vehicles, one manager,
one credit decision. The document is included, as a documented exception.

**What the test is actually for.** [schema.md](schema.md#sampling-frame) gives
the reason: "Bilateral agreements have no margin grid and often no agent, which
degenerates two fields." The lender count is a proxy for *is this a real
syndicated facility with the drafting conventions that come with one*. Counting
signature blocks approximates that well in the middle of the distribution and
badly at the edges — a participation structure hides lenders behind one name,
and a fund family multiplies one lender into several.

**Neither document was decided by the count.** Lamb Weston EX-10.2 went on
size as well as form; PureCycle is admitted on the strength of being the only
empty-covenant case available, with the count deviation written down rather
than argued away. In both, the count was evidence, and reading the document
was the decision.

**The general lesson is the one this project keeps relearning:** a mechanical
proxy is worth having because it is reproducible, and it is worth checking
because reproducible is not the same as correct. The screen's grid and
structure signals failed the same way — right often enough to be trusted,
wrong in a direction nobody was looking. The difference here is that the
failure is visible in both directions at once, which is what makes the pair
worth recording rather than the two incidents separately.

---

## `has_margin_grid`: the minority class, three documents and two constructions

Fourteen documents, twenty-three facility records, **nineteen `true` and four
`false`**, from three documents. The three are different kinds of credit and
the four values are two different kinds of `false`:

| Source | Credit | Construction |
|---|---|---|
| **Paya Holdings** — revolver and TLB | an ordinary sponsor LBO | flat 3.25% over LIBOR on both tranches, for life |
| **Peloton** — revolver only | a stressed refinancing | flat 5.00% revolver margin, beside a TLB that *is* gridded |
| **PureCycle** — revolver | a distressed bridge | escalates 5.00% → 17.50% on fixed calendar dates |

**Two constructions, not one.** Paya and Peloton's revolver are genuinely flat.
PureCycle is not flat at all — it is `false` because its escalation is
predetermined rather than performance-linked. A system that learned `false`
from flat pricing has learned part of what the label means.

**And not all from unusual documents.** Two of the three are stressed or
distressed credits, which invites the reading that `false` is a marker of
trouble. Paya is the counterexample: a healthy, ordinary sponsor deal, flat
because that is how its lenders chose to price it. The minority class spans a
healthy sponsor deal, a stressed refinancing and a distressed bridge.

**Every row selected to supply `false` supplied `true`.** Row 7 chose Lamb
Weston for "no grid" — both exhibits in that accession carry leverage grids.
Row 12 chose G-III for "no grid" — an availability grid. Row 15 chose Mattel for
"flat-margin revolver, no grid" — a five-level ratings grid. All three
rationales came from `pricing_grid_hint`, whose every measured error is a false
negative. None of the four `false` values came from a row selected for it.

**The corpus is not being adjusted, and it is reported instead.** Swapping a
row in to balance the column, having seen which documents produce which values,
would trade the thing that makes this set defensible for a column that looks
better. The field carries its instance count and one sentence more: the
minority class is 4 of 23 across three documents and two constructions, and **a
model that answered `true` unconditionally and read nothing would score 83%**.
That is the score to beat.

#### A wrong claim about this field reached the repo through an instruction

The line *"If Mattel also has a grid, Paya remains the sole source at 2 of 19
facility records"* was written into [corpus.md](corpus.md) when Boeing was
placed in row 14. **It was false when it was written.** PureCycle's `false`
had been committed five days earlier, and Peloton's revolver **ten minutes**
earlier, in the commit immediately preceding it. At that commit the label files
held 22 facility records and 4 `false` values from 3 documents — checked
against the tree as it stood then, not reconstructed.

It originated in an instruction given from memory in conversation, and it was
written into the file from that instruction without being recomputed. Neither
party checked it against the label files, both of which were sitting in the
repository and would have contradicted it in one command. It then propagated a
second time: the Mattel label arrived repeating "Paya is still the only
confirmed source".

This is the fifth instance in this project of a claim reported from memory
diverging from the artifact it describes, and the sharpest. The previous four
were caught before they were committed or were confined to one document. This
one **crossed from a conversation into the repo** — an error in a spoken
instruction became a sentence in a file that looks authoritative precisely
because it is committed. [results.md](results.md) had the figure right the
whole time; the files disagreed with each other, which is how it surfaced.

The lesson is narrower than "check your numbers". An instruction is not a
source. A claim that arrives as an instruction still has to be recomputed
against the artifact before it is written down, because being told a number by
the person who owns the project feels like verification and is not.

The underlying cause of the thin column is a measurement failure rather than a
selection accident, recorded at [Keyword heuristics
under-detect](#keyword-heuristics-under-detect-and-the-corpus-rationales-inherited-it):
the instrument used to pick documents for this field cannot see grids.

---

## `step_down_schedule`: one multi-step schedule, and it was not selected for

Fourteen documents labeled, twenty-three covenant records, **three non-empty
`step_down_schedule` arrays** — Amentum's single step (5.25x → 5.00x), Lamb
Weston EX-10.1's single step (5.00x → 4.75x), and **Mattel's two steps**
(4.50x → 4.25x at the quarter ending 2023-03-31 → 4.00x at 2023-09-30). Every
other covenant is flat. Multi-step arrays are **n = 1**.

That is still a thin field and it is still reported with its count. But it is
no longer the field this note used to describe.

#### What this note said before Mattel, kept because it was true then

Through thirteen documents the field held two one-element arrays and nothing
longer. The note said the ordering comparison "ships untested", because it
only compares when an array holds two or more elements, and that no document in
the corpus had forced it. Both documents selected as step-down candidates —
ANI, row 11, and Peloton, row 10 — had been read, and neither had a step-down.
The field was recorded as ending at n = 2.

#### What Mattel changed

**The ordering check has now executed against a real document.** Reversing
Mattel's two steps in a scratch copy makes the validator report
`step_downs_out_of_order`; in their true order they pass. That is the path this
note said had never run on real data, and it has now run.

A correction to the wording the note used, found while fixing it: it said
"the scorer's ordering comparison", but there is no scorer yet. What ran is the
**validator's** check. The accurate claim is narrower and better: when a scorer
is built, its sequence comparison will have one real multi-step gold array to
be tested against, where before it had none.

#### Why this is the best evidence in the corpus that selection preceded labeling

Mattel is row 15. It was drawn as "flat-margin revolver, **no grid**" — the
last unread candidate for `has_margin_grid: false`. It has a ratings grid, so
that rationale failed, the eleventh screen-derived rationale in eleven to do
so. And instead of the value it was selected for, it supplied the one value the
corpus had formally given up on, in the one field this note had declared
unmeasurable.

Nothing about that was arranged. The document was chosen before labeling, for
a different reason, from a signal already known to be unreliable; the rows
selected *as* step-down candidates produced none, and the row selected for
something else produced the only multi-step schedule. A corpus tuned to its
results would look the other way round. This is recorded as a finding in its
own right because it is the cleanest single demonstration that the thin columns
here are properties of the documents, not of the choices.

**It is not a reason to add more.** A second multi-step schedule would still be
worth having, but finding one by searching for it now would be the move the
frozen-corpus discipline prohibits. If one arrives, it arrives the way this one
did.

#### And the prediction about where step-downs live was wrong

This note used to say time-based step-down tables are "a sponsor-deal
convention, clustering in leverage-grid LBO credits", and
[corpus.md](corpus.md#two-drafting-traditions-and-what-that-predicts) predicts
that "leverage-based step-downs … are sponsor conventions that will not appear
in the IG deals." Mattel is neither a sponsor deal nor an LBO. It is a public
company's secured revolver on a ratings grid, with a schedule that tightens on
the way to investment grade — a crossover credit. The step-downs came from the
tradition predicted not to have them. One document does not overturn a
tendency, but it is enough to stop the prediction being stated as a rule.

---

## Flagged in advance for the blind relabel

The intra-annotator check in [schema.md](schema.md#annotator-agreement)
relabels five agreements blind two weeks on. One label is nominated now, with
its reasoning recorded, because a disagreement there would be worth more than
the agreement rate.

**Amentum `has_margin_grid` on the Initial Term Loans — labeled `true`.** The
margin is a flat 2.25% with no table. It carries one step-down: a one-time,
one-way 25bp reduction if Moody's, S&P and Fitch all reach Ba3/BB-/BB-. The
rule is explicit that *a single step-down on a one-time event is `true`* and
that the field draws fixed-versus-variable, not table-versus-no-table, so
`true` follows without judgment.

And nobody in the market would call this a grid. The labeler said so while
recording `true` anyway.

That is the interesting configuration: a rule fixed in advance that decides
the case cleanly, against a trained intuition that says otherwise. If the
blind pass returns `false`, the finding is not that the document was misread —
it is that the rule and the domain disagree, and the rule is what a model
would be scored against. That is a result about the schema, which is the kind
of thing an agreement rate is supposed to surface and usually does not.

**Lamb Weston `facility_type` on the European Term Loan — labeled
`term_loan_b`.** An unlettered euro tranche with no scheduled amortization: a
five-year bullet, held by three relationship banks, priced off the revolver's
own grid. The rule classifies unlettered term loans by amortization and a
bullet is 0%/yr, which satisfies ≤1%/yr, so `term_loan_b` follows without
judgment.

And every commercial instinct reads that as a pro rata bank tranche — a TLA.
The labeler recorded `term_loan_b` and said so.

The alternative was considered and rejected on a specific ground rather than a
preference: classifying by lender base or pricing cannot be written
mechanically. "Relationship banks" and "pro rata pricing" are judgments a
second labeler cannot replicate, and a rule requiring taste is not one this
schema can use. So the rule stands and the disagreement is recorded instead.

### These two are a category, not two flags

Both nominations have the same shape: **a rule fixed before labeling decides
the case cleanly, and trained intuition says the opposite.** Neither is a hard
reading or a close call. In both, the labeler knew what the rule returned,
recorded it, and wrote down that it felt wrong.

That makes them worth reporting as a group rather than as two incidents. If
the blind pass reverses one, it is a finding about that rule. If it reverses
both, the finding is about **how the rules were written** — that the schema
was made mechanical at the cost of tracking the domain, which is a defensible
trade and a very different claim from "the labeler was inconsistent." Either
way it is a result about the schema, not about a document, and
[schema.md](schema.md#one-category-of-disagreement-is-worth-more-than-the-rate)
now says to report it separately from the headline agreement rate.

The category also predicts where to look for more: any rule chosen for
mechanical applicability over domain fidelity is a candidate, and this project
has preferred mechanical rules deliberately and repeatedly — denominator-first
covenant classification, basis decided by one definition, the citation test
settling the Amentum rollover. Each of those bought reproducibility with a
concession, and the concessions are what a blind pass surfaces.

Recorded here so that a disagreement two weeks from now is a measurement
rather than a reconstruction. The point of writing it down in advance is that
it cannot be rationalized afterwards.

---

## The check that guaranteed the guarantee was missing

The `applicable_margin_bps` deferral null is the field class this project
argues hardest for. The case in [README.md](README.md) is that a `null` alone
cannot distinguish a system that read the deferral clause from one that
declined out of vagueness, and that requiring a citation resolves it "through
the citation check the harness already performs." [schema.md](schema.md#6-applicable_margin_bps)
says the same: the requirement makes `null` a falsifiable answer *using the
citation check that already exists*.

That check did not exist. The validator walked each field, and on seeing a
null value it confirmed `null_kind` and confirmed that a deferral carried
some citation — then returned, without ever testing the quote inside it
against the document. **A deferral null could have carried an entirely
invented quote and passed clean.** The guarantee the argument rests on was
the one place no quote was verified.

**How it surfaced.** Not by reading the code. The Advance Auto label declared
15 citations and the validator reported 14 checked. One field had a citation
nobody was looking at, and it was the deferral null.

Two things worth taking from this rather than one.

The first is about where to point a check. The rule was written, stated in
two documents, and satisfied in every label file — and the mechanism that was
supposed to enforce it silently skipped the case. A rule that is only enforced
where it is easy to enforce is not enforced. Nulls were the early-return case
in the walk precisely *because* they are the exceptional path, which is the
same reason they are the path that needed checking.

The second is that the discrepancy was found by a count, not by reading. The
validator reported a number, the label file asserted a different number, and
the gap was one line of arithmetic. That is worth generalizing: the cheapest
audits available here are the ones where two independent sources produce a
number that has to agree. This is the same shape as the Schedule 2.01
reconciliation on Plains — 20 lenders × $64M + 2 × $35M against a defined term
— and the same shape as the reasoning error above, which was caught by
checking a claim against every labeled document rather than the ones in mind.

Fixed in `2e03159`. Both label files now verify every citation they carry, and
a deferral null with a fabricated quote fails.

### It happened again, on the other exceptional branch

Amentum is the first document in the corpus with a **non-null**
`springing_trigger`, and the trigger carries a quote inside the value — the
sentence establishing the condition — separate from the field's own citation.
That quote was checked for presence and never against the document, exactly as
the deferral null had been. Fixed in `9b28290`.

Two gaps, found five weeks apart by two unrelated documents, and both sat on
the same kind of code path: the branch taken when a field is *not* an ordinary
value. The null branch, and the non-null object branch of a field that is
usually null. Routine values were verified from the first version.

**That convergence predicts where to look next.** Not "read the validator more
carefully" — the useful form is narrower: *any branch that fires rarely is
unverified until a document forces it*, and the corpus is what forces them. So
the remaining candidates are enumerable rather than vague. As of five
documents, `maturity_date` has never been `stated` in a label file; no covenant
has used `minimum_availability` or a `currency` threshold unit; no facility has
been `delayed_draw_term_loan`, `bridge` or `other`; no `step_down_schedule` has
carried more than one step, so the ordering check has never actually compared
two elements. Each is a path that will run for the first time on some document
between six and sixteen, and each should be assumed unverified until it does.

There is a second reason this matters beyond tooling hygiene. The rare branch
in the checker is the rare construction in the document — and a construction
the labeler meets once is the one where a sentence is most likely reconstructed
from memory rather than pasted. The place the check is weakest is the place the
label is weakest. They fail together, which is precisely when a guarantee is
worth least.

### The same shape, in a claim about the corpus

While reporting the screen-reliability finding above, a reader counted
`has_margin_grid` across the six label files then written — eleven facilities,
all `true` — and concluded the field was degenerate, i.e. that the corpus could
not score it at all. **The count was right and the conclusion was wrong.** Paya
Holdings is corpus row 1, was labeled, and carries two `false` values: a flat
3.25% margin on both the revolver and the TLB, no grid anywhere. The standing
count is 11 true / 2 false. The field is thin, not degenerate.

The error was computing over the *labeled subset* and reporting the result as a
property of the *corpus*. The disconfirming document was not hard to find — it
is the first row of the selection table and it had already been read.

This is the second time this exact substitution has produced a false claim in
this project; see [A reasoning error worth
recording](#a-reasoning-error-worth-recording), where a pattern was
generalized from the two most recent documents backward over one already
checked. And it is the same shape as the screen failures above: a conclusion
drawn confidently from the subset the tool happened to look at, with the
counterexample sitting outside the window.

That recurrence is the argument for making the habit mechanical rather than
intentional. *When reporting any claim about the corpus, enumerate the corpus,
not the artifacts currently in hand.* Fifteen rows are listed in
[corpus.md](corpus.md); a claim about the set is not ready until it has been
checked against all of them, including the ones not yet labeled — and where
they cannot be checked, the claim is about the labeled subset and must say so.

---

## Per-document observations

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
- **`$1,350,000,000` aggregate commitments**, confirmed two ways: the defined
  term, and Schedule 2.01 reconciling as 20 lenders × $64M + 2 × $35M.
- **The exclusion rules did substantial work here.** Three sublimits — L/C
  $400M, Swing Line $150M, Canadian Dollar $1B — are each "part of, and not in
  addition to, the Aggregate Commitments", and Canadian Bankers' Acceptances
  are a borrowing form under the same Commitment rather than a tranche. The
  §2.16 accordion permits increases to $2.1B. Booking any of them would have
  overstated the facility.
- **That $2.1B accordion is what the screen reported as the document's
  "largest dollar amount."** It is the exact noise the size-band signal was
  flagged as carrying — an option, not a commitment — and it confirms the
  decision to make that a signal rather than a filter.
- **`total_leverage_gross`, classified by definition rather than label.** The
  covenant is called "Consolidated Leverage Ratio", but `Consolidated Funded
  Indebtedness` contains no netting language at all — no "less", "minus", "net
  of", or cash-equivalents subtraction — so it is gross, not net. The facility
  is senior unsecured, so no lien-based variant applies.
- **Acquisition holiday handled correctly.** §7.08's table has two rows: 5.50x
  during an Acquisition Period, 5.00x otherwise. Recorded 5.00 per the
  non-holiday rule; the holiday level is a conditional override, not the
  covenant level.
- **`step_down_schedule` is `[]` and confirmed flat**, not merely absent. The
  table is keyed to Acquisition Period status, not to fiscal periods, so there
  is no time-based change to the 5.00x level for the life of the agreement.

### Advance Auto Parts, Inc. — 2021-11-09 — `0001158449-21-000208`

- **Benchmark is LIBOR.** `Eurodollar Rate` names it directly — "the London
  Interbank Offered Rate as administered by ICE Benchmark Administration ...
  ("LIBOR") as published on the applicable Bloomberg screen page ... 11:00
  a.m., London time". All 14 SOFR mentions are Benchmark Replacement
  machinery, including "if the then-current Benchmark is LIBOR, the Benchmark
  Replacement will replace such Benchmark."
- **`has_margin_grid` is true** — five Categories on S&P/Moody's Index Debt
  Ratings, 0.795% to 1.300% on Eurodollar loans, facility fee in the same
  table.
- **`applicable_margin_bps` is null, reached by a different limb than Plains.**
  Plains defers to a named closing certificate — a *document* outside the four
  corners. Advance Auto defers to nothing at all: the rate is "based upon the
  Ratings by S&P and Moody's ... applicable on such day", a *fact* outside the
  four corners, with no opening category stated anywhere. Searched
  specifically for an "Initially, the Applicable Rate shall be" clause; there
  is none.

  This is the first independent test of the deferral rule, and the rule held
  without amendment — the "document **or fact**" wording written for Plains
  turned out to be load-bearing for a case it was not written against.
