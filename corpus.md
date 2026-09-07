# Corpus

The held-out set: which documents are in it, and the query that produced them.

This file is **frozen before labeling begins and before any model output is
looked at**. A test set chosen after seeing which documents the system handles
well is not held out. The inclusion rule and sampling frame are in
[schema.md](schema.md#corpus-selection); this file is the record of what that
rule actually selected.

**Status: pull run 2026-09-04, corpus not yet frozen.** The census and the
document screen have been run and their funnels are recorded below. The final
fifteen have not been selected — that is a hand pick from the shortlist, and
the one open question is recorded under [Benchmark
balance](#benchmark-balance-finding).

Accession numbers are entered only from an actual EDGAR query — never
reconstructed from memory, because an accession number that looks plausible
and resolves to the wrong document, or to nothing, is worse than an empty
table.

---

## Selection query

**Source:** EDGAR full-text search, which covers every filing since 2001
including exhibits, at 10 requests/second with a declared User-Agent.

**Search terms:**

```
q:       "credit agreement" AND ("Applicable Margin" OR "Applicable Rate"
                                 OR "Applicable Percentage")
forms:   8-K, 10-Q, 10-K            (exhibits are attached to these)
startdt: 2021-06-01
enddt:   <date the pull is run — record it here>
```

`"Applicable Margin"` / `"Applicable Rate"` is in the query rather than the
post-filter because it is close to a perfect discriminator: it is a defined
term in essentially every syndicated credit agreement and appears in almost
nothing else filed as EX-10.

`"Applicable Percentage"` is included as a third alternate because EDGAR
full-text search is literal and older and middle-market agreements sometimes
use it in place of the other two. That drafting convention is more common
early in the date range — which is exactly where the LIBOR agreements are, and
therefore exactly where dropped hits would cost the most. It admits some extra
noise; the amendment filter absorbs it.

**Then filter the result set** by the rules in
[schema.md](schema.md#what-counts-as-a-credit-agreement):

1. Exhibit type is EX-10.
2. Title does not match `amendment|waiver|consent|joinder` unless it also
   matches `amended and restated`.
3. Document contains an Article I definitions section and a §2.01-equivalent
   commitment section. This is the mechanical amendment filter and it is the
   one that matters — amendments are the dominant contaminant.
4. Document is longer than ~30 pages.
5. Administrative Agent present and ≥3 lenders on the commitment schedule.
6. Aggregate commitments between $150M and $5B.
7. Borrower is a US corporate; not a bank, insurer, or REIT.

**Then stratify** to 15 documents across facility structure — target roughly
5 revolver-only, 5 revolver + TLA, 5 revolver + TLB — and within that, ensure
roughly 3 pre-2022 LIBOR agreements. Rationale for both in
[schema.md](schema.md#class-balance).

---

## Funnel, as run

**Endpoint:** `https://efts.sec.gov/LATEST/search-index`, one query per phrase
per calendar month. Month-chunking is required, not cosmetic: the unchunked
query for `"Applicable Rate"` returns `{"value": 10000, "relation": "gte"}`,
i.e. it hits EDGAR's paging ceiling and silently truncates. No monthly query
came close to it. Results are 100 per page, not the 10 the UI suggests.
EDGAR full-text search does **not** support `OR`, so the three alternates run
as three queries and are unioned.

**Run 2026-09-04**, covering 2021-06-01 to 2026-09-04 — 64 months, 752
requests.

| Stage | Count |
|---|---|
| Raw hits, including cross-phrase duplicates | 64,111 |
| Unique files | 51,607 |
| — rejected, not an EX-10 exhibit | 35,072 |
| — rejected, excluded sector by SIC | 9,528 |
| — rejected, 8-K without Item 1.01 | 3,967 |
| — rejected, amendment by title | 1,610 |
| **Candidates after metadata filters** | **12,144** |
| Screened (seeded sample, seed 20260904) | 400 |
| — rejected, fewer than 3 lender signatures | 170 |
| — rejected, not titled a credit/loan/facilities agreement | 135 |
| — rejected, amendment by title | 132 |
| — rejected, no definitions section | 127 |
| — rejected, too few commitment terms | 122 |
| — rejected, not agented | 95 |
| — rejected, under 15,000 words | 84 |
| **Passing the document screen** | **112** |
| Of those: in the $150M–$5B band | 100 |
| Of those: US syndicated style | 104 |
| Of those: at least one financial covenant detected | 91 |
| **Fully qualified (all three)** | **78** |

Rejection reasons are recorded per document, not just as counts, in
`data/search/hits.jsonl` and `data/screen/screened.jsonl`. Documents fail
multiple filters at once, so the rejection rows sum to more than the
difference between stages.

**What the noise actually is.** 68% of unique full-text hits are not EX-10
exhibits at all — they are the 8-K, 10-Q and 10-K bodies themselves, which the
search indexes as separate files and which discuss credit agreements without
being one. Of the documents that clear metadata filtering, only 28% survive
the document screen, and the largest single cause is amendments and
non-agreement exhibits rather than anything subtle.

**Contribution of each phrase alternate**, as unique files no other phrase
found:

| Phrase | Total hits | Unique to this phrase |
|---|---|---|
| `"Applicable Margin"` | 32,386 | 25,099 |
| `"Applicable Rate"` | 20,176 | 10,908 |
| `"Applicable Percentage"` | 11,549 | 4,964 |

`"Applicable Percentage"` was added on the theory that older and middle-market
agreements use it where others say "Margin". It contributed 4,964 files —
9.6% of the census — that neither other phrase returned. Carrying it was the
right call.

---

## Two drafting traditions, and what that predicts

The frame spans both sponsor-backed LBO credits and investment-grade corporate
revolvers, and these are different drafting traditions rather than variations
on one. The first two documents labeled sit on opposite sides of it: Paya
Holdings is a Credit Suisse-led sponsor deal with a flat margin, a
leverage-linked commitment fee grid and a springing covenant; Plains GP is an
investment-grade MLP revolver with a five-level grid keyed to S&P and Moody's
debt ratings and an opening level deferred to a closing certificate.

Ratings grids, deferred opening levels, and public-debt-rating mechanics are IG
conventions that will not appear in the sponsor deals at all. Leverage-based
step-downs, cov-lite structures and springing triggers are sponsor conventions
that will not appear in the IG deals.

**The consequence is that the schema should be expected to keep moving for
more documents than a homogeneous corpus would require** — each tradition
introduces constructions the other never uses, and the adjudication rules have
to cover both. Both of the first two documents forced a schema change.

This is a cost worth paying, because a corpus drawn from only one tradition
would produce a number that generalizes to only one tradition. But it needs
watching: **if the schema is still moving at document six, that is a signal,
not noise.** It would mean the rules are being written to fit documents rather
than to state a policy, and the intra-annotator agreement check becomes hard
to interpret — a labeler who relabels under a rule that has since changed is
not measuring their own consistency.

---

## Benchmark balance finding

The frame reaches back to 2021-06 specifically so that
`interest_rate_benchmark` is not a constant. That worked, but not in the way
the frame assumed, and it leaves one decision open.

Among the 78 fully-qualified candidates, **zero** mention LIBOR without also
mentioning SOFR. The split is 52 SOFR-only, 24 mentioning both, 2 neither.
Every 2021-filed agreement in the shortlist is in the "both" bucket.

That is the LIBOR transition showing up in the drafting: agreements signed
from mid-2021 onward almost universally carry SOFR fallback or replacement
language regardless of what they are actually priced off. A keyword screen
cannot separate "priced off LIBOR, with SOFR transition provisions" from
"priced off SOFR, with legacy LIBOR references" — and per
[schema.md](schema.md), the field records the benchmark *in effect*, not its
successor, so only reading the pricing section decides it.

Two options, and this is a judgment call to make before freezing:

1. **Source the LIBOR agreements from the "both" bucket by hand.** Candidates
   like the 2021-filed CDW, Advance Auto Parts, and Paya agreements are
   plausibly LIBOR-priced with transition language. Cost: a few minutes each
   to confirm from the pricing section.
2. **Extend the frame earlier than 2021-06** to reach unambiguously
   LIBOR-priced agreements. Cost: it changes the frozen frame, so it has to be
   recorded as a deliberate amendment to this file with the reason.

Option 1 preserves the frame and is the smaller change. Either way the
`interest_rate_benchmark` field stays non-degenerate, which is what the
stratification was for.

---

## This is an enriched test set, not a representative sample

State this plainly wherever results are reported, because the two framings
give different numbers and blurring them would be the most misleading thing in
the project.

The fifteen were selected to exercise each field's value space, not to mirror
the population of syndicated credit agreements. Springing covenants are 2 of
75 in the qualified pool and 3 of 15 here. Explicitly lettered tranches are 4
of 75 and 4 of 15. That is roughly 5x enrichment on both, and it is
deliberate: a representative sample of fifteen would contain zero or one
springing covenant, and `springing_trigger` would report an accuracy figure
computed over a single instance.

**The consequence for reporting.** Per-field F1 is the result. A single
headline accuracy number across all fields either should not be reported, or
must be explicitly caveated as computed over a set constructed to exercise
each field rather than to reflect how often each construction occurs in
practice. Weighting a mean by a distribution the corpus does not have would
produce a figure that describes nothing.

This is a stronger position than a representative sample would give, not a
weaker one — per-field measurement is what says whether the system can extract
step-down schedules, and a representative sample would not contain enough of
them to say anything. It just has to be stated rather than implied.

---

## How the selection signals were derived

Every signal used to select these documents — detected tranches, covenant
mentions, grid hints, springing hints, benchmark counts, dollar amounts — comes
from **keyword and regex counting** in `src/covenant_eval/screen.py`. No
language model read any document during screening or selection.

This matters for a reason that is easy to miss. Had the signals come from an
LLM pass, the corpus would be conditioned on model output about the exact
fields the eval is about to score — preferentially selecting documents the
model already reads well, and inflating the result by construction. Recording
the method is what lets a reader rule that out.

The regexes are lossy in the other direction, which is fine for selection and
is documented under [Covenant detection false
negatives](#covenant-detection-false-negatives) below. Final field values come
from reading the documents, never from these signals.

---

## Selected agreements

Fifteen documents. Three were labeled or benchmark-confirmed during schema
development; twelve were selected from the qualified pool afterward.

| # | Borrower | Accession number | Filed | Structure | Selected for |
|---|---|---|---|---|---|
| 1 | Paya Holdings III | `0001213900-21-034493` | 2021-06-25 | revolver + term | LIBOR; flat margin (integer, no grid); springing covenant |
| 2 | Plains GP Holdings | `0001104659-21-109833` | 2021-08-20 | revolver only | LIBOR; ratings grid; deferral null (certificate) |
| 3 | Advance Auto Parts | `0001158449-21-000208` | 2021-11-09 | revolver only | LIBOR; ratings grid; deferral null (external fact) |
| 4 | Kontoor Brands | — | 2021-11-19 | revolver + TLA + TLB | Stated opening margin *then* a grid; CDOR/ESTR multicurrency; 3 covenants |
| 5 | Amentum Holdings | — | 2024-10-03 | revolver + TLA + TLB | 4 covenant types — richest record alignment case in the pool |
| 6 | Extreme Networks | — | 2023-06-23 | revolver + TLA + TLB | Lettered tranches; grid; 2 covenants |
| 7 | Lamb Weston Holdings | — | 2024-05-08 | revolver + TLA | Lettered TLA with no grid |
| 8 | Avaya Holdings | — | 2023-09-08 | revolver + term | Springing covenant; 3 covenants; post-restructuring credit |
| 9 | MP Materials | — | 2025-08-25 | revolver + term | Springing covenant |
| 10 | Peloton Interactive | — | 2024-05-30 | revolver + term | Grid; 3 covenants; step-down candidate |
| 11 | ANI Pharmaceuticals | — | 2024-08-13 | revolver + term | Grid; 3 covenants; step-down candidate |
| 12 | G-III Apparel | — | 2024-06-06 | revolver + term | 3 covenants with **no** grid — contrast against 10 and 11 |
| 13 | Roper Technologies | — | 2022-07-22 | revolver + term | **Covenant-free** — the empty-covenant-list case |
| 14 | Lithia Motors | — | 2022-06-08 | revolver only | Grid; leverage + fixed charge |
| 15 | Mattel | — | 2022-09-19 | revolver only | Flat-margin revolver, no grid |

Accession numbers for 4–15 are to be filled from `data/screen/shortlist.jsonl`
when the set is frozen.

**Resulting distribution:** 4 revolver-only, 7 revolver + unlettered term, 4
revolver + explicitly lettered tranches. Benchmark: 3 LIBOR, 12 SOFR-era.

The seven unlettered term loans are a feature rather than a shortfall. Each
one exercises the `facility_type` rule that classifies by amortization rather
than by name — a 1%/yr institutional tranche is a TLB whatever the agreement
calls it — which is among the more fragile adjudications in the schema and
would go untested by a corpus of neatly labeled Term A and Term B facilities.

### Amendment to the stratification target

The frame called for roughly 5 revolver-only / 5 revolver+TLA / 5
revolver+TLB. **That is not reachable from this pool and the target is
amended.** Explicitly lettered tranches are 4 of 75 qualified candidates;
taking all four still gives 4, and manufacturing more would mean relabeling
unlettered tranches as lettered, which is the classification the schema
deliberately makes by amortization instead. Recorded rather than quietly
missed.

---

## The cov-lite gap, and how it was found

The first draft of this slate had **no covenant-free agreement in it**, which
would have made a schema rule unfireable: `financial_covenants` is explicitly
allowed to be an empty list, and a model inventing a covenant where none
exists is supposed to be penalized. With every document carrying at least one
covenant, that penalty never applies and the most important hallucination mode
in the covenant fields goes unmeasured.

**The cause was the qualification filter, not the corpus.** Selection ran over
78 candidates filtered on size band, US syndication style, **and covenant
presence**. Genuinely covenant-free agreements were excluded by construction
before selection began — 21 of the 112 documents that passed the document
screen have no covenant detected, and none of them were ever visible to the
selection step.

Reading those 21 produced a second finding, below. Two are genuinely
covenant-free: **Roper Technologies** (2022, revolver + term, $3.5B) and **PPG
Industries** (2023, term only, $1B) — in both, every "shall maintain" and
"shall not permit" in the document is administrative, about register-keeping
and notice addresses, not a financial maintenance test. Roper is selected,
because a revolver-plus-term structure exercises more facility fields than a
single term loan.

### Covenant detection false negatives

The covenant regexes match `Leverage Ratio`, `Interest Coverage Ratio`,
`Fixed Charge Coverage` and `First Lien Leverage`. Reading the 21
"covenant-free" documents shows they miss at least three constructions:

- **Debt-to-capitalization**, the standard investment-grade and utility
  covenant. Eversource Energy has one; it is not in the `covenant_type` enum
  at all.
- **Consolidated net worth**, which Phillips 66 appears to carry. Also not in
  the enum.
- **Interest coverage written as a ratio of components** — Analog Devices
  tests "Consolidated EBITDA to Consolidated Interest Expense Ratio", which is
  an interest coverage covenant that the `Interest Coverage Ratio` pattern
  never sees.

So some of the 21 are false empties, and the count of genuinely covenant-free
agreements in the pool is smaller than 21. This does not affect the selected
fifteen — Roper was verified by reading — but it does mean the funnel's
covenant-presence numbers understate covenant prevalence, and it flags two
enum values (`debt_to_capitalization`, `net_worth`) that would be needed if an
investment-grade document with those covenants ever enters the corpus.

---

## Sector filter gap

Four documents reached the qualified pool that the frame intends to exclude.
The sector rule excludes SIC 6798 (REITs) and 6000–6499 (financials), but:

- **Spirit Realty Capital** files as 6512, **Sunstone Hotel Investors** as
  7011, **Millrose Properties** as 6500 — all REITs, none caught.
- **PhenixFIN** is a BDC filing with a blank SIC, which no numeric rule
  catches.

All four were excluded by hand during selection. The filter itself is not
amended retroactively — that would change the frozen frame after seeing the
data — but the gap is recorded here, and anyone rerunning the pull should
widen the sector rule and treat a blank SIC as requiring manual review.

---

## Replacements

Any document swapped out after freezing is recorded here with its reason —
truncated exhibit, scanned image, or a wrong document type that survived the
filters. Replacements are drawn from the same stratum as the document they
replace.

| Removed | Reason | Replaced by |
|---------|--------|-------------|
| | | |

An empty table here is the expected outcome. A long one is a signal that the
filters need tightening, not that the corpus needs more churn.
