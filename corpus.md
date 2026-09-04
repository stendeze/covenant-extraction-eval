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

## Selected agreements

| # | Borrower | Accession number | Filed | Exhibit | Structure | Benchmark | Aggregate commitments |
|---|----------|------------------|-------|---------|-----------|-----------|-----------------------|
| | | | | | | | |

*To be populated from the pull. One row per document; the accession number and
exhibit together identify the exact file, so a clean checkout can re-fetch the
corpus byte-for-byte.*

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
