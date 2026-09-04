# Corpus

The held-out set: which documents are in it, and the query that produced them.

This file is **frozen before labeling begins and before any model output is
looked at**. A test set chosen after seeing which documents the system handles
well is not held out. The inclusion rule and sampling frame are in
[schema.md](schema.md#corpus-selection); this file is the record of what that
rule actually selected.

**Status: not yet populated.** The selection query below is recorded; the pull
has not been run. Accession numbers are entered only from an actual EDGAR
query — never reconstructed from memory, because an accession number that
looks plausible and resolves to the wrong document, or to nothing, is worse
than an empty table.

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

Record here, when the pull is run: the exact endpoint and parameters, the date
run, the total hit count, and the count surviving each filter step. The funnel
numbers are worth keeping — "1,400 hits, 310 after the amendment filter, 96
after size and syndication, 15 sampled" is itself a finding about how much of
EX-10 is noise.

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
