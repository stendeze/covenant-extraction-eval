# Results — reporting shape

**Status: no results. No model has been run.** This file fixes *how* results
will be reported, and it is committed before any output exists to be tempted
by.

That is the same move as freezing the corpus before labeling, for the same
reason. A table designed after seeing the numbers is a table designed around
them — fields quietly dropped because they came out badly, baselines omitted
because the headline looks better without them, enum values shown only where
something fired. None of those requires bad faith; each is what a person does
when presenting work they care about. Deciding the shape first removes the
opportunity.

---

## Four rules, fixed in advance

**1. Every per-field number carries its instance count.** A field scored over
one or two instances is not measured. `n` is what lets a reader see that
rather than take an F1 on trust, and it is printed beside the number, not in a
footnote.

**2. Every skewed field carries *two* baselines, and they test different
things.**

- **Naive (majority class)** — always answer the most common value, read
  nothing. This asks *does reading the document help at all?* It needs no
  implementation; it is a property of the gold set, computable today, and it
  is printed in the coverage table below.
- **Regex (keyword extraction)** — the cheap method someone would actually
  build instead of an LLM. This asks *does the expensive method beat the
  obvious one?* It has to be run, and it is the headline comparison this
  project was designed around.

**A system can clear one and fail the other, and neither substitutes for the
other.** Beating the majority class on `has_margin_grid` proves only that the
system is reading something; beating a keyword extractor proves the reading is
worth paying for. Failing the naive baseline while beating regex would mean
both methods are worse than a constant.

The regex baseline is the more interesting of the two here because of what is
already known about it. The same class of tool was used to help select this
corpus, and **ten of ten of its selection rationales failed when checked
against their documents**. Its failure modes are documented from real
agreements in
[labeling-notes.md](labeling-notes.md#baseline-false-positive-mechanisms) — in
both directions, since existence questions under-report and counting questions
over-report — which is what makes the comparison fair rather than a strawman.
Report both baselines in the same table as the system score, on every field.

The naive figures, from the gold set as it stands:

| Field | Naive strategy | Scores |
|---|---|---|
| `has_margin_grid` | always `true` | **82%** |
| `testing_frequency` | always `quarterly` | **86%** |
| `springing_trigger` | always `null` | **76%** |
| `step_down_schedule` | always `[]` | **90%** |
| `aggregate_commitment` | always non-null | **95%** |
| `interest_rate_benchmark` | always `term_sofr` | **68%** |
| `facility_type` | always `revolver` | **68%** |

A system reporting 84% on `has_margin_grid` has beaten reading-nothing by two
points. The reader should see all three numbers side by side — system, naive,
regex — without doing arithmetic, and on every skewed field rather than only
the worst one.

**3. Every enum value appears, including the ones nothing produced.** A field's
table lists its whole value space with `n = 0` where nothing fired. Showing
only the values that occurred makes a corpus look more complete than it is.

**4. Values that were pre-registered as possibly never firing are marked as
such, and not pooled with the rest.** Pre-registered-and-empty is a decision
whose reasoning is on the record; unexpectedly-empty is a gap. Three values are
in the first category:

| Value | Where it was pre-registered |
|---|---|
| `debt_service_coverage` | [schema.md](schema.md#7-covenant_type) — "will almost certainly never fire in this corpus … an empty column for it is the expected result, not a labeling gap" |
| `cdor` | [schema.md](schema.md#4-interest_rate_benchmark) — "it may never fire; an unused enum value costs nothing". Its one candidate, Lithia Motors, was later excluded from the frame |
| `delayed_draw_term_loan` | [schema.md](schema.md#1-facility_type) — the rule added under ANI requires the agreement to say so, and "it may not fire at all. That is the accepted outcome" |

Everything else that comes out empty is an unexercised case and says so.

---

## Lead with `covenant_type`

**A reader skimming should land on `covenant_type` first**, and the table
should be ordered so they do.

It is the one field where a number means something without a caveat attached.
Eight of eleven enum values have fired, no value dominates, and the naive
baseline is **24%** — so a system scoring 70% there has demonstrated something,
and the figure can be read at face value.

Compare the fields where that is not true. On `has_margin_grid` the floor is
82%, on `testing_frequency` 86%, on `step_down_schedule` 90%. A high number on
those is mostly the skew, and every one of them needs its baseline printed
beside it to be read correctly at all.

This is also the field the project is actually about. `covenant_type` is what
[README.md](README.md) means by "there is no public benchmark for the financial
terms of credit agreements" — CUAD and ContractEval classify legal clause
types, and none of their categories is a leverage ratio. It is the hardest
field to label, it is where the adjudication rules did the most work, and it is
the only one whose distribution can carry a result on its own.

Leading with it is not cherry-picking, because the weak fields are in the same
table with their baselines and their instance counts. It is putting the
interpretable number where a reader will see it instead of burying it under
four fields whose floors are above 80%.

---

## Findings that are already fixed, before any model runs

These are properties of the corpus, not of a system, and they do not change
when results arrive.

**`step_down_schedule` is not measurable at this corpus size.** Two non-empty
arrays across 21 covenant records, neither with more than one element. Both
documents selected as step-down candidates were read and neither had one.
**The scorer's ordering comparison has therefore never executed against real
data** — it only compares when an array holds two or more elements. A passing
test suite does not imply otherwise; it exercises that path with constructed
fixtures.

**`has_margin_grid`'s minority class comes from three documents and two
different constructions.** Paya is genuinely flat pricing; PureCycle is a
predetermined calendar escalator; Peloton's revolver is flat while its term
loan is gridded. A system that learned `false` from flat pricing has learned
part of what the label means.

**`testing_frequency` is 18 of 21 quarterly**, with `continuous`, `monthly` and
`weekly` at one instance each.

**The empty covenant list is n = 1**, and that document — PureCycle — is a
fifteen-month distressed bridge admitted as a
[documented exception](corpus.md#document-16-purecycle-a-documented-exception)
rather than a draw from the frame. The case [README.md](README.md) builds its
central argument on is tested once, on an atypical document.

---

## Also reported, separately from field accuracy

**Citation accuracy**, scored on whether each quote appears verbatim in the
source. Already mechanically checkable and already run over the gold set —
every committed label verifies.

**The two deferral shapes, not pooled.** Deferral to an external *fact* (Plains,
Advance Auto, Roper — a rating that exists in the world and not in the
document) and deferral to an *unattached exhibit* (Peloton — a schedule the
filer did not attach) are different capabilities. Reported apart.

**The blind-relabel category**, per
[schema.md](schema.md#one-category-of-disagreement-is-worth-more-than-the-rate):
labels where a pre-registered rule decides cleanly against trained market
intuition. Two are nominated in advance. A reversal there is a finding about
the schema, not about a document, and is reported separately from the headline
agreement rate.

**The selection-rationale failure rate.** Ten of ten screen-derived rationales
checked against their documents have failed. That is a measured property of the
instrument this project used to help choose its own test set, and it belongs
with the results rather than buried in
[corpus.md](corpus.md#-the-selected-for-column-is-unverified-and-is-wrong-wherever-it-has-been-checked).

---

## The table itself

Generated from the label files, never transcribed:

```
uv run covenant-eval coverage
```

Every hand-copied count in this project's history has eventually been wrong —
four times in one working session. The command reads `data/labels/` and the
current enum sets out of [schema.md](schema.md), so the table cannot drift from
the data or from the schema. Paste its output into the results write-up rather
than retyping it.

A snapshot as of the current gold set is below. It is **not** a result; it is
the shape a result will be reported in, filled with instance counts.

<!-- BEGIN COVERAGE SNAPSHOT -->
**14 documents · 22 facility records · 21 covenant records · 1 with an empty covenant list**

## Facility fields

### `facility_type`  ·  n = 22
*Naive baseline: always answer `revolver` → 15/22 = 68%*

| Value | n | Status |
|---|---:|---|
| `revolver` | 15 | — |
| `term_loan_b` | 4 | — |
| `term_loan_a` | 3 | — |
| `bridge` | 0 | **not exercised** |
| `delayed_draw_term_loan` | 0 | **pre-registered as possibly never firing** |
| `other` | 0 | **not exercised** |

### `aggregate_commitment`  ·  n = 22
*Naive baseline: always answer `(non-null)` → 21/22 = 95%*

| Value | n | Status |
|---|---:|---|
| `(non-null)` | 21 | — |
| `(null)` | 1 | — |

### `aggregate_commitment.currency`  ·  n = 21
*Naive baseline: always answer `USD` → 20/21 = 95%*

| Value | n | Status |
|---|---:|---|
| `USD` | 20 | — |
| `EUR` | 1 | — |

### `maturity_date`  ·  n = 22
*Naive baseline: always answer `(non-null)` → 22/22 = 100%*

| Value | n | Status |
|---|---:|---|
| `(non-null)` | 22 | — |

### `maturity_date.basis`  ·  n = 22
*Naive baseline: always answer `relative` → 12/22 = 55%*

| Value | n | Status |
|---|---:|---|
| `relative` | 12 | — |
| `stated` | 10 | — |

### `interest_rate_benchmark`  ·  n = 22
*Naive baseline: always answer `term_sofr` → 15/22 = 68%*

| Value | n | Status |
|---|---:|---|
| `term_sofr` | 15 | — |
| `libor` | 6 | — |
| `euribor` | 1 | — |
| `base_rate` | 0 | **not exercised** |
| `cdor` | 0 | **pre-registered as possibly never firing** |
| `daily_simple_sofr` | 0 | **not exercised** |
| `other` | 0 | **not exercised** |
| `prime` | 0 | **not exercised** |

### `applicable_margin_bps`  ·  n = 22
*Naive baseline: always answer `(non-null)` → 18/22 = 82%*

| Value | n | Status |
|---|---:|---|
| `(non-null)` | 18 | — |
| `(null)` | 4 | — |

### `has_margin_grid`  ·  n = 22
*Naive baseline: always answer `true` → 18/22 = 82%*

| Value | n | Status |
|---|---:|---|
| `true` | 18 | — |
| `false` | 4 | — |

## Covenant fields

### `covenant_type`  ·  n = 21
*Naive baseline: always answer `interest_coverage` → 5/21 = 24%*

| Value | n | Status |
|---|---:|---|
| `interest_coverage` | 5 | — |
| `total_net_leverage` | 4 | — |
| `first_lien_net_leverage` | 3 | — |
| `debt_to_capitalization` | 2 | — |
| `fixed_charge_coverage` | 2 | — |
| `minimum_liquidity` | 2 | — |
| `total_leverage_gross` | 2 | — |
| `other` | 1 | — |
| `capex_limit` | 0 | **not exercised** |
| `debt_service_coverage` | 0 | **pre-registered as possibly never firing** |
| `secured_net_leverage` | 0 | **not exercised** |

### `initial_threshold`  ·  n = 21
*Naive baseline: always answer `(non-null)` → 21/21 = 100%*

| Value | n | Status |
|---|---:|---|
| `(non-null)` | 21 | — |

### `step_down_schedule`  ·  n = 21
*Naive baseline: always answer `[]` → 19/21 = 90%*

| Value | n | Status |
|---|---:|---|
| `[]` | 19 | — |
| `(non-empty)` | 2 | — |

### `step_down_schedule.length (diagnostic)`  ·  n = 21
*Naive baseline: always answer `0 step(s)` → 19/21 = 90%*

| Value | n | Status |
|---|---:|---|
| `0 step(s)` | 19 | — |
| `1 step(s)` | 2 | — |

### `testing_frequency`  ·  n = 21
*Naive baseline: always answer `quarterly` → 18/21 = 86%*

| Value | n | Status |
|---|---:|---|
| `quarterly` | 18 | — |
| `continuous` | 1 | — |
| `monthly` | 1 | — |
| `weekly` | 1 | — |
| `annual` | 0 | **not exercised** |
| `event_driven` | 0 | **not exercised** |
| `semiannual` | 0 | **not exercised** |

### `springing_trigger`  ·  n = 21
*Naive baseline: always answer `(null)` → 16/21 = 76%*

| Value | n | Status |
|---|---:|---|
| `(null)` | 16 | — |
| `(non-null)` | 5 | — |

### `springing_trigger.condition_type`  ·  n = 5
*Naive baseline: always answer `revolver_utilization` → 4/5 = 80%*

| Value | n | Status |
|---|---:|---|
| `revolver_utilization` | 4 | — |
| `minimum_availability` | 1 | — |
| `other` | 0 | **not exercised** |

### `springing_trigger.threshold_unit`  ·  n = 5
*Naive baseline: always answer `currency` → 3/5 = 60%*

| Value | n | Status |
|---|---:|---|
| `currency` | 3 | — |
| `percent` | 2 | — |
<!-- END COVERAGE SNAPSHOT -->
