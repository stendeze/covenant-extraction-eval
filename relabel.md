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
