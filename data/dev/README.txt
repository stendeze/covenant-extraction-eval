The development set. Three labeled credit agreements from outside the corpus,
used to check that the extraction pipeline and the scorer run, parse and score.

MECHANICS ONLY. Not for tuning: the prompt carries the adjudication rules from
schema.md and is frozen by commit before the first extraction run, so nothing
here is iterated against. Which is why three documents are enough.

None of these documents is in the corpus, and none may become a few-shot
example without being stated as such with the results.

0001679273-24-000026_EX10-2_labels.json
    Lamb Weston Holdings, EX-10.2, the AgWest Farm Credit facility. Out of
    frame: one Lender of record on Schedule 2.01. SAME ACCESSION, BORROWER AND
    DATE AS CORPUS ROW 7 (EX-10.1). Never use it for prompt iteration or
    few-shot examples: tuning against it is close to tuning against a corpus
    document.

0001418100-23-000041_EX10-7_labels.json
    Avaya Holdings, EX-10.7, a debtor-in-possession ABL. Out of frame:
    $128,125,000, below the $150M floor; DIP financing.

0001023128-22-000080_EX10-2_labels.json
    Lithia Motors, EX-10.2, a Canadian dealer floorplan package. Out of frame:
    Alberta borrower, Ontario law, CAD. Its section 4.3 margins are redacted,
    so the five applicable_margin_bps values carry
    excluded_from_scoring: "redacted". No null_kind fits a redaction, and a
    document outside the corpus does not get a new one. The marker leaves the
    labeled value in place, the scorer skips the field, and the validator
    rejects the marker anywhere under data/labels/.

    has_margin_grid is scored on all five facilities. The four non-revolver
    facilities are false on the Applicable Margins table's layout — one row
    each, no tier or ratio column — which the redaction does not hide.

Each label was brought current against schema.md as of 3733eb5 before moving
here from data/discarded/, where they had been kept since each document left
the corpus. Shape fixes and the exclusion marker only; no recorded value
changed. The re-application, rule by rule, is in the commit that added this
directory. Why each document left the corpus is in corpus.md.
