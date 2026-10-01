# Blind relabel

The intra-annotator check promised in [schema.md](schema.md#annotator-agreement):
five agreements relabeled blind, and the agreement between the two passes
reported per field. This file records how the five were chosen. **The method
below was committed before the draw was run**, so the selection cannot have been
shaped by what it produced.

## Method

**Eligible pool.** A document is eligible if its label file was first committed
to `data/labels/` at least 14 days before the draw date, 2026-09-30 — that is,
on or before 2026-09-16 — by committer date, from

```sh
git log --diff-filter=A --format=%cs -- data/labels/<file>
```

A recently labeled document cannot be relabeled blind: the labeler would be
reproducing a memory, not reading the agreement. Fourteen days is the protocol's
own interval ("two weeks after the initial pass").

Later commits do not reset eligibility unless they changed a scored value with
the labeler. None of the ten eligible files did after its first day: the only
later commits touching them are `0f4792c` (2026-09-10, a pointer in a Plains
note) and `4bc7610` (2026-09-27, the `document_file` key standardisation, which
changed no scored value).

The ten eligible documents, sorted by accession number, which is the order the
draw uses:

| Accession | Exhibit | File | Label first committed |
|---|---|---|---|
| `0000950103-24-012144` | EX-10.2 | `dp216536_ex1002.htm` | 2026-09-16 |
| `0000950157-24-001363` | EX-10.1 | `ex10-1.htm` | 2026-09-10 |
| `0000950170-23-029645` | EX-10.1 | `extr-ex10_1.htm` | 2026-09-10 |
| `0001104659-21-109833` | EX-10.1 | `tm2125730d3_ex10-1.htm` | 2026-09-07 |
| `0001158449-21-000208` | EX-10.1 | `aap_exhibit101x10092021.htm` | 2026-09-07 |
| `0001193125-22-199694` | EX-10.1 | `d291205dex101.htm` | 2026-09-16 |
| `0001213900-21-034493` | EX-10.1 | `ea143383ex10-1_payaholdings.htm` | 2026-09-11 |
| `0001558370-24-008935` | EX-10.1 | `giii-20240604xex10d1.htm` | 2026-09-16 |
| `0001679273-24-000026` | EX-10.1 | `ex10_1conformed-lwxbofax.htm` | 2026-09-11 |
| `0001760965-21-000058` | EX-10.1 | `exhibit101creditagreemen.htm` | 2026-09-10 |

Not eligible, too recent: PureCycle (2026-09-17), Boeing, Peloton and MP
Materials (2026-09-22), Mattel (2026-09-24), Hertz (2026-09-27).

**The draw.** A seeded random sample of five from that list, for the headline
agreement rate. Seed `20260930`, the draw date — the same convention as the
screen's seed `20260904`. Run with Python 3.13.5:

```python
import random

pool = [
    "0000950103-24-012144", "0000950157-24-001363", "0000950170-23-029645",
    "0001104659-21-109833", "0001158449-21-000208", "0001193125-22-199694",
    "0001213900-21-034493", "0001558370-24-008935", "0001679273-24-000026",
    "0001760965-21-000058",
]
draw = random.Random(20260930).sample(pool, 5)
```

**The two flagged items are reported separately, whatever the draw gives.**
[Amentum's `has_margin_grid`](labeling-notes.md#flagged-in-advance-for-the-blind-relabel)
and [Lamb Weston EX-10.1's European Term Loan
`facility_type`](labeling-notes.md#flagged-in-advance-for-the-blind-relabel)
were nominated in advance because a fixed rule and market intuition disagree on
them. Both were deliberated at length when labeled, so neither can be fully
blind: the labeler knows the question and remembers arguing it. They are
relabeled on their own, and their results never enter the headline rate, even
if their document is drawn. Their documents are in the pool on the same terms
as every other; only the two fields are set aside.

**Blindness.** The relabeler works from the agreement alone and does not open
the original label files — ideally does not look at `data/labels/` at all. The
selection below names documents, never values. Relabels are written to
`data/relabel/`, never to `data/labels/`; the gold set is not touched by this
step.

**Agreement** is measured per field, with each field's "Correct when" test in
[schema.md](schema.md) and the same [record
alignment](schema.md#record-alignment) rules a model would be scored by.
`facility_name` is not scored. A field the gold records as `unrepresentable` is
excluded, as it is from scoring.

**Resolution.** A disagreement is resolved the way the [annotator-agreement
protocol](schema.md#annotator-agreement) says — by tightening the rule and
re-applying it to the full set, every value change confirmed with the labeler —
and that is the only path by which a label changes before `label-freeze`. See
[After the freeze](schema.md#after-the-freeze-two-things-two-tags).

## Selection

Drawn 2026-09-30 by running the code above, unchanged, under Python 3.13.5,
after the method was committed in `090b7cc`. The draw, in the order the sample
returned it:

| Draw | Corpus row | Borrower | Accession | Exhibit | File |
|---|---|---|---|---|---|
| 1 | 12 | G-III Leather Fashions, Inc. | `0001558370-24-008935` | EX-10.1 | `giii-20240604xex10d1.htm` |
| 2 | 1 | Paya Holdings III | `0001213900-21-034493` | EX-10.1 | `ea143383ex10-1_payaholdings.htm` |
| 3 | 2 | Plains All American Pipeline, L.P. | `0001104659-21-109833` | EX-10.1 | `tm2125730d3_ex10-1.htm` |
| 4 | 13 | Roper Technologies | `0001193125-22-199694` | EX-10.1 | `d291205dex101.htm` |
| 5 | 6 | Extreme Networks | `0000950170-23-029645` | EX-10.1 | `extr-ex10_1.htm` |

These five give the headline agreement rate, every scored field relabeled.

Neither flagged document was drawn, so the two flagged items are relabeled on
their own and reported separately:

- Amentum Holdings, `0000950157-24-001363`, `ex10-1.htm` — `has_margin_grid`
  for each facility.
- Lamb Weston Holdings, `0001679273-24-000026`, `ex10_1conformed-lwxbofax.htm`
  — `facility_type` for the European Term Loan.

## Fields the repository already answers

Listed before the blind pass begins, as [schema.md](schema.md#how-agreement-is-computed)
requires. Several drawn documents were worked examples while the rules were
written, so for some fields the answer is printed in the rulebook the relabel
is done from, or elsewhere in this repository. Agreement on such a field
measures recall of the rulebook, not consistency. **The headline is agreement
without tier 1.** Beside it: agreement over every field, and without tiers 1
and 2. Each figure carries its count and the field's majority-class rate. The
relabel does not open the tier-2 files, or this file, until it is done.

A field is listed when a committed document states its value or a fact that
determines it — a sentence saying a tranche's margin is flat determines its
`has_margin_grid`. Some
passages quote a drawn agreement without naming it; those were found by
matching every quotation in schema.md and labeling-guide.md against the five
filings, and are marked. A passage that only discloses that a construction
exists, without determining the value, is listed separately and excluded from
nothing. No value is repeated here. Line numbers are as of `3733eb5`.

**Tier 1 — the rulebook** (schema.md, labeling-guide.md), which the relabel is
done from and cannot avoid:

| Document | Fields | Where |
|---|---|---|
| G-III | `aggregate_commitment`; `springing_trigger`; `testing_frequency` | schema.md:131, 144–146, 1239–1256; labeling-guide.md:477–489 |
| Paya | `applicable_margin_bps`, `has_margin_grid` and `interest_rate_benchmark` on both facilities; `facility_type` and `aggregate_commitment` of the term loan; `springing_trigger` | schema.md:165–169, 804–812; labeling-guide.md:76–78\*, 465–472\* |
| Plains | `applicable_margin_bps`; `maturity_date` | schema.md:686–690\*, 713\*, 602–605\*; labeling-guide.md:113\*, 174–176\* |
| Roper | `covenant_type`, `initial_threshold`, `testing_frequency`; `has_margin_grid` | schema.md:278, 740, 885–903, 963–965; labeling-guide.md:303, 351 |
| Extreme | `maturity_date` | schema.md:569–572; labeling-guide.md:121–123 |

\* Quoted without naming the document.

**Tier 2 — elsewhere in the repository** (README.md, results.md, corpus.md,
labeling-notes.md), which the relabel can avoid opening. Fields beyond tier 1:

| Document | Fields | Where |
|---|---|---|
| G-III | `facility_type`; `has_margin_grid`; `covenant_type`; record count | corpus.md:291, 351; labeling-notes.md:150, 667–671 |
| Paya | `facility_type` and `aggregate_commitment` of the revolver; `covenant_type`; `initial_threshold`; record count | labeling-notes.md:154, 1396–1425; corpus.md:340 |
| Plains | `facility_type`; `aggregate_commitment`; `interest_rate_benchmark`; `has_margin_grid`; `covenant_type`; `initial_threshold`; `step_down_schedule`; record count | labeling-notes.md:156, 259–263, 1325, 1426–1476; corpus.md:281, 341 |
| Roper | `facility_type`; `aggregate_commitment`; `applicable_margin_bps`; record count | corpus.md:293, 352, 753; README.md:21, 53; results.md:173–178; labeling-notes.md:158 |
| Extreme | `facility_type` on both facilities; `has_margin_grid` on at least one; record count | corpus.md:285, 345, 390; labeling-notes.md:149 |

Record count — how many facilities and covenants a document has — is not a
field; it bears on the record-level agreement line.

**Constructions disclosed, value not determined — excluded from nothing:**
Plains and Extreme carry a conditional override on `initial_threshold`
(schema.md:999); Roper's grid prints a level that is not its opening one
(schema.md:738–741).

**Not listed in either tier, and therefore the fields the "without tiers 1 and
2" figure rests on:** every field not named above. For Paya that leaves both
`maturity_date` values, `testing_frequency` and `step_down_schedule`; for
Plains, `testing_frequency` and `springing_trigger`. The figure will be thin,
and its count says so.
