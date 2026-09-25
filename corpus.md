# Corpus

The held-out set: which documents are in it, and the query that produced them.

This file **freezes at the first extraction run**, before any model output is
looked at. A test set chosen after seeing which documents a system handles well
is not held out; a test set chosen for what its documents contain is stratified,
and every such choice is disclosed row by row below. The rule, and why the line
sits at model output rather than at the start of labeling, is in
[schema.md](schema.md#freezing); the inclusion rule and sampling frame are in
[schema.md](schema.md#corpus-selection).

**Status: sixteen of sixteen slots filled; fifteen labeled — row 8 (Hertz)
selected, label pending. Not yet frozen — no extraction has been run.**

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

Sixteen documents, selected three ways. **Three** were labeled or
benchmark-confirmed by hand during schema development (rows 1–3). **Twelve**
were selected from the qualified pool afterward by the stratification
described above (rows 4–15); two of those rows now hold documents from outside
the screened sample but inside the recorded query's candidate pool — row 7,
amended to the other exhibit in the accession first drawn, and row 8, whose
replacement had to come from the pool (see [Vacated
rows](#vacated-rows-8-and-14)). **One** — row 16, PureCycle — was added
purposively, after selection, to supply the empty-covenant case that nothing
else in the slate supplies. It is a documented exception to the frame rather
than a draw from it; see [Document 16](#document-16-purecycle-a-documented-exception).
The exception is to the frame's *criteria* — lender composition, commitment
schedule, size at the floor. Adding a document after labeling had begun, for
what it contains, was never an exception to anything; it is what the [freezing
rule](schema.md#freezing) permits until the first extraction run.

> ## ⚠ The "Selected for" column is unverified, and is wrong wherever it has been checked
>
> **Read this before using the table.** The rationales below — what each
> document is supposed to exercise — were generated from `screen.py`'s keyword
> and regex signals, not by reading the agreements. Those signals have a
> measured error rate. As each document is labeled, its rationale is checked
> against the document, and the result so far is this:
>
> | Row | Rationale said | Document says | |
> |---|---|---|---|
> | 1 Paya | flat margin, no grid, springing | as described | ✅ |
> | 2 Plains | revolver only; ratings grid; deferral null | as described | ✅ |
> | 3 Advance Auto | revolver only; ratings grid; deferral null | as described | ✅ |
> | 4 Kontoor | revolver + TLA + **TLB**; **3 covenants** | revolver + TLA; 2 covenants | ❌ |
> | 5 Amentum | revolver + **TLA** + TLB; **4 covenant types** | revolver + TLB; **1** covenant | ❌ |
> | 6 Extreme | revolver + TLA + **TLB**; **lettered tranches** | revolver + TLA; tranche is "Initial Term Loans" | ❌ |
> | 7 Lamb Weston | revolver + TLA; **no grid** | neither exhibit matches; both have grids | ❌ |
> | 8 Avaya | revolver + term; springing; **3 covenants** | no exhibit in the filing matches; DIP is revolver-only with 1 liquidity covenant | ❌ |
> | 9 MP Materials | **revolver + term**; **springing covenant** | revolver only — all term-loan language is incremental machinery; no utilization springing covenant | ❌ |
> | 10 Peloton | grid; **3 covenants**; **step-down candidate** | grid on the TLB only, revolver flat; 2 covenants; **no step-downs** | ❌ |
> | 11 ANI Pharma | grid; **3 covenants**; **step-down candidate** | grid holds; 2 covenants; **no step-downs** | ❌ |
> | 12 G-III Apparel | revolver + term; **3 covenants with no grid** | revolver-only ABL; 1 covenant; **has a grid** | ❌ |
> | 15 Mattel | revolver only; **flat margin, no grid** | revolver only holds; **five-level ratings grid** | ❌ |
> | 13 Roper | **covenant-free** | §7.1 Total Debt to Total Capital at 0.65:1.00 | ❌ |
>
> **Three hold, eleven fail — and the split is not random.** Rows 1–3 are
> precisely the three that the screen did not select; they were labeled or
> benchmark-confirmed by hand during schema development. **Every
> screen-derived rationale that has been checked has failed: eleven of eleven.**
>
> That count has gone five through eleven on consecutive documents. It is not
> drifting toward a rate — it has not yet produced a single success. The
> rationales are not partially reliable; they are unreliable, with a measured
> failure rate of 100% over eleven trials, and the only rationales that hold
> describe the three documents the instrument never touched.
>
> **The rows that got corrected are the rows that happened to be read, not the
> rows that happened to be wrong.** Nothing about labeling order was chosen to
> find errors, so the seven unread rows should be assumed to carry the same
> error rate as the five read ones, not a lower one. Corrections appear here
> as they are found, which makes the table look progressively more accurate
> while the unread remainder is exactly as unverified as it was on day one.
>
> **What this does and does not undermine.** The *inclusion* filters are a
> different question and mostly hold: these are real syndicated credit
> agreements in the size band, and where one was not — Lamb Weston EX-10.2,
> one lender of record — the criterion caught it on reading. What is
> unreliable is the *rationale*: why a document was chosen and what field
> values it is supposed to supply. Every claim in this file that depends on
> that column depends on an unverified instrument. That includes the
> stratification counts, the enrichment ratios quoted under [This is an
> enriched test set](#this-is-an-enriched-test-set-not-a-representative-sample),
> and any statement that a particular field is balanced across the corpus.
>
> The instrument's measured behaviour, and why this is also the baseline's
> failure mode, is in
> [labeling-notes.md](labeling-notes.md#keyword-heuristics-under-detect-and-the-corpus-rationales-inherited-it).
> This caveat stands until every row has been read, at which point it is
> replaced by the corrected table and a count of how many rows needed
> correcting.

| # | Borrower | Accession number | Filed | Structure | Selected for |
|---|---|---|---|---|---|
| 1 | Paya Holdings III | `0001213900-21-034493` | 2021-06-28 | revolver + term | LIBOR; flat margin (integer, no grid); springing covenant |
| 2 | Plains GP Holdings | `0001104659-21-109833` | 2021-08-26 | revolver only | LIBOR; ratings grid; deferral null (certificate) |
| 3 | Advance Auto Parts | `0001158449-21-000208` | 2021-11-15 | revolver only | LIBOR; ratings grid; deferral null (external fact) |
| 4 | Kontoor Brands | — | 2021-11-19 | revolver + TLA + TLB | Stated opening margin *then* a grid; CDOR/ESTR multicurrency; 3 covenants |
| 5 | Amentum Holdings | — | 2024-10-03 | revolver + TLA + TLB | 4 covenant types — richest record alignment case in the pool |
| 6 | Extreme Networks | — | 2023-06-23 | revolver + TLA + TLB | Lettered tranches; grid; 2 covenants |
| 7 | Lamb Weston Holdings | `0001679273-24-000026` **EX-10.1** | 2024-05-08 | 2 revolvers + EUR term | Non-USD commitment currency; EURIBOR — see [amendment](#row-7-amended-the-wrong-exhibit-and-a-false-rationale) |
| 8 | The Hertz Corporation | `0001104659-21-089858` **EX-10.3** | 2021-07-07 | revolver + term (named Term B, Term C) | Post-restructuring: Chapter 11 exit facility — **replacement, rationale verified by reading**; Avaya dropped, see [Vacated rows](#vacated-rows-8-and-14) |
| 9 | MP Materials | — | 2025-08-25 | revolver + term | Springing covenant |
| 10 | Peloton Interactive | — | 2024-05-30 | revolver + term | Grid; 3 covenants; step-down candidate |
| 11 | ANI Pharmaceuticals | — | 2024-08-13 | revolver + term | Grid; 3 covenants; step-down candidate |
| 12 | G-III Apparel | — | 2024-06-06 | revolver + term | 3 covenants with **no** grid — contrast against 10 and 11 |
| 13 | Roper Technologies | — | 2022-07-22 | revolver + term | **Covenant-free** — the empty-covenant-list case |
| 14 | The Boeing Company | `0000012927-24-000037` **EX-10.1** | 2024-05-17 | revolver only | Grid (ratings); debt-to-capitalization — **replacement, rationale verified by reading**; see [Vacated rows](#vacated-rows-8-and-14) |
| 15 | Mattel | `0001193125-22-246779` **EX-10.1** | 2022-09-19 | revolver only | ~~Flat-margin, no grid~~ — **read: ratings grid; two-step leverage schedule** |
| 16 | PureCycle Technologies | `0001830033-23-000021` **EX-10.2** | 2023-03-15 | revolver only | **Empty covenant list**; escalator, no grid — purposive addition, [documented exception](#document-16-purecycle-a-documented-exception) |

Accession numbers for 4–15 are to be filled from `data/screen/shortlist.jsonl`
when the set is frozen.

**The "Filed" column is the EDGAR filing date, not the agreement date.** The
two differ by days to weeks and the exhibit itself states only the agreement
date, so the filing date comes from the EDGAR index. Rows 1–3 originally
carried agreement dates here — 2021-06-25, 2021-08-20 and 2021-11-09 — and
were corrected against `data/search/candidates.jsonl`. Label files record both
dates separately.

**Resulting distribution:** 4 revolver-only, 7 revolver + unlettered term, 4
revolver + explicitly lettered tranches. Benchmark: 3 LIBOR, 12 SOFR-era.

The seven unlettered term loans are a feature rather than a shortfall. Each
one exercises the `facility_type` rule that classifies by amortization rather
than by name — a 1%/yr institutional tranche is a TLB whatever the agreement
calls it — which is among the more fragile adjudications in the schema and
would go untested by a corpus of neatly labeled Term A and Term B facilities.

### Vacated rows 8 and 14

Both documents were read before being removed, and both rows have since been
refilled by reading.

**Row 8 — Avaya Holdings, dropped.** The accession holds four credit
agreements and none qualifies. EX-10.4 and EX-10.7 are both $128,125,000,
below the floor; EX-10.7 is additionally a debtor-in-possession facility,
which is bankruptcy financing rather than syndicated corporate credit.
EX-10.5 is an $810,000,000 term-only exit loan whose lenders received their
positions as distributions under a plan of reorganization rather than through
syndication. EX-10.12 is an amendment. The label produced for EX-10.7 is
retained in `data/discarded/`.

**Row 8 — filled by The Hertz Corporation.** The replacement was chosen against
the original rationale, "revolver + term, post-restructuring credit", and
verified by reading before inclusion, on those two elements only. It is
Hertz's exit facility from Chapter 11 (D. Del., Case No. 20-11218; plan
confirmed June 10, 2021): the Credit Agreement dated June 30, 2021, filed as
EX-10.3 (`tm2121430d1_ex10-3.htm`) to Hertz Global Holdings' 8-K of 2021-07-07.
It is the accession's only credit agreement; the other nine EX-10 exhibits are
warrant and registration-rights agreements, vehicle-ABS documents and an
indemnification form.

- **Revolver + term:** a $1,255,000,000 revolver, $1,300,000,000 of Term B
  loans and $245,000,000 of Term C loans in one agreement, $2,800,000,000 in
  all.
- **Post-restructuring, and neither a DIP nor plan-allocated debt:** the
  lenders fund cash at closing — each "severally agrees to make, in Dollars,
  in a single draw on the Closing Date" (§2.1) — and the proceeds repay the DIP
  facility, among other debt, and fund the plan's distributions. The lenders
  funded it in cash; it was not distributed to them.
- **In frame:** Barclays Bank PLC as administrative agent; The Hertz
  Corporation, a Delaware corporation, as borrower, under New York law; a full
  agreement, not an amendment. Schedule A-3 is attached and lists 11 revolving
  lenders summing to $1,255,000,000, exactly the stated total.

**The term side at signing is one lender.** Schedules A-1 and A-2 put Barclays
at 100% of both term tranches: the arranger funding at signing and syndicating
afterward. The three-lender test passes on the revolver schedule, so this is a
clean draw, but the term-side composition at signing is recorded here: one
lender.

**The Term C construction is new to the corpus, and is left unresolved.** The
Term C is a funded term loan whose proceeds sit in cash collateral backing
letters of credit (§3.11). No labeled document has one. How it is labeled is
decided against the text when row 8 is labeled, not at selection.

**It comes from outside the screened sample.** The 400-document sample holds no
eligible post-restructuring agreement. Every document in it whose text refers
to a bankruptcy plan, an exit facility or a restructuring support agreement was
read, including the 288 the screen rejected. None qualified: the hits were
Avaya, DIP facilities, amendments, passing references (standard clauses on how
lenders vote in a bankruptcy, a counterparty's restructuring), and two
agreements made under transaction support agreements whose term loans were
exchanged or held by an affiliate — E.W. Scripps (2025) and New Fortress Energy
(2024). The search therefore went outside the sample: EDGAR full-text search
on 2026-09-25 for exit-facility language — `"Confirmation Order"`, `"Chapter 11
Plan"`, `"Chapter 11 Cases"`, `"Exit Facility"`, `"Plan Effective Date"`,
`"Reorganized Debtors"` and similar, crossed with margin and
revolving-commitment terms — over 8-K, 10-Q and 10-K filed from 2021-06-01,
with about 200 exhibits checked at the cover, and at the commitment section
wherever the cover left a document in contention. Hertz is in
`data/search/candidates.jsonl`, the recorded query's metadata-filtered pool:
the position Lamb Weston EX-10.1 already occupies at row 7.

**The rejected alternative: Talen Energy Supply.** Exactly two candidates
passed. The other was Talen's exit facility from Chapter 11 (S.D. Tex., Case
No. 22-90054): the Credit Agreement dated May 17, 2023, `exhibit101-sx1.htm` in
accession `0001628280-24-029107` — a $700,000,000 revolver, $580,000,000 of
Term B and $470,000,000 of Term C, Citibank, N.A. as agent, eight lenders on
the signature pages, a Delaware borrower under New York law. It passes the
frame. It was rejected on reproducibility: it was filed only as an exhibit to a
Form S-1, and the recorded query covers 8-K, 10-Q and 10-K, so it would have
been the first document in the corpus that rerunning the selection cannot
reach. Every earlier exception broke a frame criterion; this one would have
broken the census. Hertz sits in the query's pool, and its commitment schedule
reconciles exactly.

Everything else found failed the frame or one of the rationale's two
exclusions: term loans deemed made rather than funded (Cano Health and WW
International; Audacy in part) or exchanged for DIP loans (Diebold); revolver
and term in separate agreements (JOANN, The Container Store, QVC, XBP Global,
Mallinckrodt); exits that reached EDGAR within the date frame only as
amendments (Frontier, Endo); later refinancings rather than exits; and DIP
facilities, amendments and support agreements.

**Row 14 — filled by The Boeing Company.** Lithia was dropped (below); the
replacement was chosen against the original rationale, "revolver only | Grid;
leverage + fixed charge", and **verified by reading before inclusion rather
than after**. Revolver-only confirmed: §2.1(c) borrow/prepay/reborrow, no term
tranche, §2.6 and §2.7 reserved. Grid confirmed: a five-level ratings grid on
the margin itself, 120–165 bps. In frame on every mechanical test — $4B of
commitments, Citibank as agent, 26 lenders on an **attached** Schedule I that
sums to the stated total, US corporate under US law.

**The covenant type differs from the original rationale and that is recorded
rather than smoothed over.** The row was selected expecting leverage plus
fixed charge; Boeing carries a single debt-to-capitalization test at 60% of
Total Capital. The replacement discipline was to match the *stratification*
rationale — structure and grid — not to reproduce every clause of a
prediction that came from an instrument now 0 for 10.

**Row 14 — Lithia Motors, dropped.** Canadian borrower under Ontario law in
CAD, outside the frame as [clarified](schema.md#sampling-frame); a dealer
floorplan structure outside all three strata; and the entire §4.3 pricing grid
redacted, making `applicable_margin_bps` unlabelable across all five
facilities. Label retained in `data/discarded/`.

#### Mattel is the last unread candidate for `has_margin_grid: false`

Row 15 was selected as "Flat-margin revolver, no grid" and has not been read.
It is the **only** remaining row that could supply a second source of
`has_margin_grid: false`. The other candidate, row 12 G-III, was read and has
an availability grid; row 7 Lamb Weston was read and both its exhibits have
grids.

Boeing was placed in row 14 rather than row 15 for that reason — it has a
ratings grid, and putting it in Mattel's slot would have spent the last unread
chance at the minority class.

**Mattel has been read, and it has a grid** — a five-level ratings grid, so row
15's rationale failed like the other two rows selected for `has_margin_grid:
false`. The minority class ends at **4 of 23 facility records, from three
documents**: Paya (flat, an ordinary sponsor LBO), Peloton's revolver (flat, a
stressed refinancing) and PureCycle (a calendar escalator, a distressed
bridge). None came from a row selected for it. Reported with its count, per
[`has_margin_grid`](labeling-notes.md#has_margin_grid-the-minority-class-three-documents-and-two-constructions).

> **Correction.** This paragraph previously said *"If Mattel also has a grid,
> Paya remains the sole source at 2 of 19 facility records."* That was false
> when it was committed: PureCycle and Peloton had already supplied `false`
> values, the latter ten minutes before. It came from an instruction given from
> memory and was written down without being recomputed. The account of how it
> happened is in
> [labeling-notes.md](labeling-notes.md#a-wrong-claim-about-this-field-reached-the-repo-through-an-instruction).

**Mattel instead supplied the corpus's only multi-step `step_down_schedule`**
— the value the two rows selected *as* step-down candidates did not produce,
in the field that had been recorded as unmeasurable. That is the clearest
evidence here that the original draw was blind to document contents: the
document was drawn for a different reason, from a signal already known to be
unreliable, and supplied something nobody had selected for. Blindness to
contents is stricter than the [freezing rule](schema.md#freezing) requires — it
forbids only selection on model output — but it means the thin columns here are
properties of the documents rather than of curation. See
[labeling-notes.md](labeling-notes.md#step_down_schedule-one-multi-step-schedule-and-it-was-not-selected-for).

#### How the replacements will be chosen, and how they will not

**Against the original rationales.** Row 8 was selected as revolver + term,
post-restructuring credit; row 14 as revolver-only with a grid. Those
rationales predate any labeling, so replacing against them is frame
maintenance — restoring a slot to the specification it was drawn under.

**That is a choice, and a stricter one than the rule requires.** This section
originally said that choosing a document to supply a thin column was prohibited.
It is not: the prohibited move is selecting on model output, and until the first
extraction run, choosing documents for structural coverage is stratified
sampling — permitted, and disclosed per document with what it was selected to
exercise. PureCycle, row 16, is that move made openly, and it is what showed the
old line was drawn in the wrong place; see [Freezing](schema.md#freezing).
Rows 8 and 14 are nonetheless matched to their original rationales, as frame
maintenance. Where a column stays thin, it is reported with its instance count,
as recorded for
[`step_down_schedule`](labeling-notes.md#step_down_schedule-one-multi-step-schedule-and-it-was-not-selected-for)
and [`has_margin_grid`](labeling-notes.md#has_margin_grid-the-minority-class-three-documents-and-two-constructions).

**Rationale verified by reading, before inclusion rather than after — on the
stratum, not on the prediction.** Both original rationales came from the
screen, which is **0 for 11** on every rationale checked. A replacement
selected on an unread screen signal would carry the same defect into a slot
that exists because of it. So each replacement is confirmed against the
document first on its row's **stratification elements**, and the row records
what was read rather than what was predicted. For row 14 those elements were
structure and grid; for row 8 they are structure and category — revolver +
term, post-restructuring. The covenant count and springing covenant in the
original row 8 entry were the screen's predictions about Avaya, not the
stratum, and the screen is 0 for 11. This is the reasoning already applied at
row 14, where the discipline was to match structure and grid rather than
reproduce every clause of a failed prediction. What lies outside the stratum —
for row 8, covenants and pricing — is read during labeling, not selection.

This paragraph previously said that each replacement's "structure, covenant
count and pricing are confirmed against the document first". It was narrowed
at the row 8 replacement, whose stratum names neither covenants nor pricing.

### Document 16: PureCycle, a documented exception

The slate was extended from fifteen documents to sixteen after selection, for
one reason: **nothing in it supplies an empty covenant list.** Row 13, Roper,
was chosen for that case and turned out to carry a debt-to-capitalization
covenant in §7.1. No other row was ever selected for it, and no unread row is
a candidate.

That case is not optional. [schema.md](schema.md#covenant-fields) states that
an empty `financial_covenants` list is a real and correct answer and that a
model inventing a covenant there is penalised, and [README.md](README.md)
builds its central argument on the corpus measuring whether a system knows
when there is nothing to find. A corpus that never tests it leaves a hole in
exactly the claim the project makes loudest.

PureCycle Technologies, `0001830033-23-000021` EX-10.2, filed 2023-03-15, is
the only candidate. **Verified covenant-free by reading, not by regex:** zero
occurrences of `EBITDA` in 65,001 words; §7.11 and §7.12 both `[Reserved]`;
and all five occurrences of "Compliance Certificate" are *U.S. Tax Compliance
Certificate*, four in the withholding-tax provisions and one in the exhibit
index. There is no covenant compliance certificate in the document.

#### It deviates from the frame in three ways, all recorded

1. **The three lenders are affiliated funds of one manager.** Sylebra Capital
   Partners Master Fund, Sylebra Capital Parc Master Fund and Sylebra Capital
   Menlo Master Fund — three vehicles, one manager, Madison Pacific Trust
   Limited as Administrative Agent and Security Agent. The frame's "≥3
   lenders" test passes on form and arguably fails on substance.
2. **The commitment schedule is not attached.** `SCHEDULE 2.01` appears
   nowhere in the exhibit; "Commitments and Applicable Percentages" is listed
   in the schedule index only. The frame's test is ≥3 lenders *on the
   commitment schedule*, and that test cannot be run on this document at all —
   the count comes from signature pages.
3. **Aggregate commitments are $150,000,000 — the floor exactly.** *"The
   aggregate Commitment of all of the Lenders on the Closing Date shall be
   $150,000,000."* Inside the band as written, since the band is inclusive,
   but on the line rather than within it.

#### And it is not the kind of document the empty case was expected to come from

This file originally said the empty-covenant case would come from a
**cov-lite syndicated term loan B** — an institutional tranche whose lenders
accept no maintenance covenant because the revolver carries one. PureCycle is
not that. It is a **fifteen-month distressed bridge**: `Maturity Date` of June
30, 2024, and an `Applicable Margin` that escalates on a calendar schedule in
five steps — **5.00% → 10.00% → 12.50% → 15.00% → 17.50% thereafter** — with no
pricing grid and no pricing levels anywhere in the document. Rescue financing
from a single manager's funds, not a syndicated leveraged loan.

**State this wherever the empty-covenant result is reported.** A reader should
discount it appropriately rather than assume the corpus tested cov-lite
structures and found a model inventing covenants in one. What it tests is
whether a system invents covenants in a document that has none — which is the
hallucination mode that matters — on an atypical document, with n=1.

The pricing structure also raises a question the schema has not answered: a
margin that varies only with the passage of time is neither flat nor keyed to
a measured condition. That is left open deliberately until the document is
labeled, so the rule is written against what is in it.

### Row 7 amended: the wrong exhibit, and a false rationale

Row 7 originally read **"revolver + TLA | Lettered TLA with no grid"**. That
described neither document in the filing, and the accession alone did not
identify one: `0001679273-24-000026` contains **two** full credit agreements
filed the same day, both amended and restated, both dated 2024-05-03.

- **EX-10.2** (`ex10_2conformed-lwxagwes.htm`) — the AgWest Farm Credit
  facility. Term-loan-only: three tranches, Term A, Term A-3 and Term A-4, no
  revolver. **Three leverage grids.** Schedule 2.01 lists **one Lender of
  record**, AgWest Farm Credit PCA, holding 100% of every tranche; the ~13
  other Farm Credit institutions on the signature pages are Voting
  Participants under §11.06(e), not lenders on the commitment schedule.
- **EX-10.1** (`ex10_1conformed-lwxbofax.htm`) — the Bank of America facility.
  Revolving A-2 (~$1.44B, 13 lenders), Revolving B-2 ($60M, held entirely by
  AgWest), and a **€200,000,000 European Term Loan** to Lamb-Weston/Meijer
  v.o.f. across three lenders. Schedule 2.01 lists 14+ institutions with real
  commitments, Bank of America as Administrative Agent. **Also a leverage
  grid**, keyed to the Consolidated Net Leverage Ratio.

**EX-10.2 was labeled before this was noticed, then discarded.** It fails the
syndication criterion outright — the frame requires an Administrative Agent
and ≥3 lenders on the commitment schedule, and one lender of record is one,
whatever the economic reality of the participations. That disqualifies it
regardless of anything else, so the label was not committed. It is retained
outside `data/labels/` as evidence of the episode rather than deleted.

**The amended rationale** is EX-10.1, selected for two things the corpus has
never contained: a **non-USD commitment currency** (the term loan is
denominated in euro) and a **EURIBOR benchmark** (the Alternative Currency
Term Rate resolves to it). Both are enum values and code paths that have not
fired in any document read so far, so one document supplies two.

#### The "no grid" slot from this row was never real

The original rationale came from `pricing_grid_hint`, which the screen
computed as `false` — **on EX-10.2, and wrongly**. That document carries three
leverage grids. Its sibling EX-10.1 carries one too. So the signal was wrong
about the document it was computed on and also wrong about the agreement the
row was meant to describe.

The consequence matters more than the correction: **the "no grid" slot does
not transfer to the amended row, because it never existed.** No `false` value
for `has_margin_grid` was ever available from this filing. Paya Holdings
(row 1) supplies the only two `false` values in the corpus at present, and
row 12 — G-III Apparel, "3 covenants with **no** grid" — rests on the same
signal and has not been read. A manual audit of the Applicable Margin
definition across the unlabeled rows is underway; until it lands, the corpus
cannot claim `has_margin_grid` is balanced.

The general finding — that keyword heuristics under-detect, and that the
rationales in this file inherited the misses — is recorded in
[labeling-notes.md](labeling-notes.md#keyword-heuristics-under-detect-and-the-corpus-rationales-inherited-it)
and in [README.md](README.md), because it is also the baseline's failure mode.

**A note on the Structure column generally.** It was derived from the same
screen signal, which is correct 3 of 6 on the documents read so far. Row 7 is
corrected here because it was read; the other unread rows are not corrected,
because correcting them from the same signal would be no better than leaving
them. Treat the column as a selection artifact, not a finding, until each row
is labeled. The "Resulting distribution" line below inherits that caveat.

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
amended retroactively, because re-running the pull under a different filter
would change the candidate pool the recorded funnel describes, and the funnel's
value is that it can be reproduced exactly. The gap is recorded here instead,
and anyone rerunning the pull should widen the sector rule and treat a blank
SIC as requiring manual review.

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
