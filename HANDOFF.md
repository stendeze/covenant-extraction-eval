# Handoff

For a reader with no memory of how this repo got here. Everything below can be
checked against the files and `git log`; where this file and another disagree,
the other file governs and this one is stale. [schema.md](schema.md) governs
everything.

## Where things stand

The corpus is complete and the document set is frozen. Sixteen syndicated
credit agreements, sixteen gold label files in `data/labels/`, every row read,
labeled, and verified four ways: against the label, the recorded query's
output in `data/search/candidates.jsonl`, the live EDGAR filing index, and the
file on disk. The validator reports 0 errors on all sixteen.

**No extraction has been run.** No model has seen a corpus document. That is
the property the whole repo exists to protect, and it is what the tags below
make checkable.

The blind relabel set has been drawn and is waiting to be relabeled. Labels
are open to change only through that relabel's resolution, and close at a
second tag, `label-freeze`, which does not exist yet.

Fixed since, all before the relabel began:

| Commit | What |
|---|---|
| `3733eb5` | The comparison rules: record alignment by agreement on identifying fields, tenor in months, anchor normalization, the springing unit, the per-step diagnostic, and how the relabel's agreement is computed |
| `4f21be0` | The fields of the five drawn documents that the repository already answers, in relabel.md, so the headline agreement can exclude them |
| `afa93aa` | `data/dev/`, the development set, and the validator's `excluded_from_scoring` marker for it |
| `a1b6214` | The scorer core — per-field comparison, alignment, agreement — tested against `data/dev/` only |

## Tags and freeze points

| Tag | Commit | Meaning |
|---|---|---|
| `corpus-freeze` | `2e40560ed71f04920450ac189d0d26479f4cc643` | The document set is frozen. No document is added or removed. |
| `label-freeze` | *not yet created* | Labels are fixed. Made when the blind relabel is resolved. **The first extraction run comes after this tag.** |

Both are annotated tags. Check one with `git rev-parse corpus-freeze^{commit}`.

## The post-freeze procedure

Written in [schema.md](schema.md#after-the-freeze-two-things-two-tags), in
`251477b`. In short:

- **Document set:** frozen at `corpus-freeze`. No additions or removals.
- **Label values:** change only through the blind relabel's resolution — a
  disagreement between the blind pass and the original is resolved by
  tightening the rule in schema.md and re-applying it to the full set, with
  every value change confirmed with the labeler — and only before the first
  extraction run. Nothing else edits `data/labels/`.
- **`label-freeze`** marks the point after which labels are fixed.
- **After `label-freeze`, a label error is never silently corrected.** It is
  recorded as an erratum outside `data/labels/`, and both the score against
  the original gold and the score against the corrected value are reported,
  with how the error was found. This is what keeps model output from shaping
  the gold set.

## The next step

Two things can run in parallel; one must wait.

1. **The blind relabel** — by the labeler, Daniel, on his schedule; he is away
   on applications. Method and selection are in [relabel.md](relabel.md),
   committed method-first (`090b7cc`) and drawn after (`b82b499`). Five
   documents for the headline agreement rate — G-III, Paya, Plains, Roper,
   Extreme — plus two flagged items relabeled on their own and reported
   separately: Amentum's `has_margin_grid` and Lamb Weston EX-10.1's European
   Term Loan `facility_type`. Relabels go to `data/relabel/`, never
   `data/labels/`, in the label files' shape; `covenant-eval agree` pairs them
   with the originals by accession and `document_file`.
2. **Code that can be written now**, all developed against `data/dev/` and
   never run on a corpus document: the group B decisions below, then the
   model-facing schema and the prompt generated from schema.md, the
   extraction pipeline (Batch API), the regex baseline's spec and code, and
   the fetch script.
3. **Must wait:** running extraction on any corpus document. That is the
   first extraction run, and it comes after `label-freeze`.

The order of events is therefore: relabel → compute agreement → resolve
disagreements by rule → tag `label-freeze` → first extraction run.

**Decided, 2026-09-30:**

- **Model:** Claude Opus 5.5, run through the Batch API. It uses the tokenizer
  introduced with Opus 4.7. By local estimate every corpus document fits its
  1M window; the largest, Hertz, is 432k–618k tokens. Haiku 4.5 is out.
  Before `label-freeze`, token counts are local estimates only — never
  `count_tokens` on a corpus document.
- **The full-context arm stays.** Whether the truncation arm survives, and
  whether to add one Sonnet run on the best configuration as a cost
  comparison, are decided with group B.
- **The prompt carries the adjudication rules**, generated from schema.md and
  frozen by commit before the first run. The labeler worked from the
  rulebook, so the model gets the same rulebook.
- **The dev set is for mechanics only** — does the pipeline run, parse and
  score. Not tuning.
- **The errata format is deferred until the first erratum exists.** The
  post-freeze rule already guarantees that both scores are reported.

## Open decisions

- **Group B — scoring decisions schema.md has not made**, and the scorer core
  deliberately leaves out:
  - how per-field results become F1 — a wrong value on a paired record, and
    pooling over records or averaging per document;
  - how a correct decline is credited, since F1 cannot see one — the deferral
    nulls and the empty covenant list;
  - the conflict between README ("declining is only correct when the system
    can point at the sentence") and schema.md (citations scored separately);
  - whether a model's quote may differ in case or spacing;
  - putting the naive baselines on the F1 scale.
- **Not built:** the extraction pipeline, the regex baseline that
  [results.md](results.md) describes (its spec comes first, developed only on
  `data/dev/` and the candidate pool, with the screen's signals kept as they
  are where they cover a field), and the fetch script that
  [README.md](README.md) says will make the corpus reproducible from a clean
  checkout. Each label records accession and `document_file`, and the
  committed `data/search/candidates.jsonl` carries each filer's CIK, so the
  fetch script has everything it needs.
- **Waiting for Daniel** (raised 2026-09-30, while he was away):
  1. *The facility identifying fields were landed as measured, not as he
     approved them.* He chose the version where pairing on a value every
     record shares does not count. The list proposed with it named only
     `interest_rate_benchmark` and `has_margin_grid` as the shared facility
     fields. Counting the gold showed `applicable_margin_bps` (10 of 12
     within-document pairs) and `maturity_date` (8 of 12) are shared about as
     often, so `3733eb5` makes only `facility_type` and
     `aggregate_commitment` identifying. Reverting means one sentence in
     schema.md and `IDENTIFYING_FIELDS` in score.py.
  2. *Relabel.md's exposure list has to be transcribed to JSON* for
     `covenant-eval agree` to print the headline (without tier 1). Mapping
     "the term loan" to a record index means reading the original labels, so
     the default is to transcribe after the relabel is done, checked against
     relabel.md, committed with the agreement results.
  3. *The two flagged items need a file shape.* They are single fields, not
     whole records. Default: one `data/relabel/flagged.json` listing document,
     facility, field, value and citation, compared and reported on its own.
- **Watch one rule.** The seasonal-cycle rule for `initial_threshold`
  (most restrictive level) is recorded in schema.md as the closest of the
  Hertz rules to arbitration. If a second document ever splits on it, that is
  where to look.
- **Closed when the comparison rules were fixed:** the record-alignment
  tiebreak hole (two facilities with the same type, currency and amount).
  Records now align by agreement, with position as the last tie-break. See
  schema.md, Record alignment.

## Gotchas a fresh session will hit

**Superseded reasoning in old commits.**

- Commits before `9125e1f` argue from a superseded selection rule. They refuse
  additions "because the frozen-corpus discipline prohibits it", meaning the
  corpus froze at the start of labeling. That was wrong: the prohibited move
  is selecting on *model output*; selecting on document contents was permitted
  until the freeze. Do not re-derive the old rule from those messages. The
  refusals that still stand (no second multi-step schedule) stand for other
  stated reasons.
- Commits before `251477b` treat the freeze as one event. It is two: the
  document set at `corpus-freeze`, labels at `label-freeze`.
- [corpus.md](corpus.md) says of itself "This file froze at tag
  `corpus-freeze`". Treat it as a frozen record.

**Running a model.**

- Any model run over a corpus document is the first extraction run — including
  a "quick test" of the pipeline. Develop and test on documents outside the
  corpus. The candidate pool in `data/search/candidates.jsonl` has thousands.
- Few-shot examples come from outside the corpus too, and that is stated with
  the results.

**The relabel's blindness.**

- Never show the relabeler a value from `data/labels/` for the five drawn
  documents or the two flagged items, including in a summary or a progress
  note.
- Until his relabel is done, Daniel does not open relabel.md, README.md,
  results.md, corpus.md or labeling-notes.md. They state answers for several
  of the drawn documents. Do not quote from them to him either.

**Working rules the history depends on.**

- Commits are authored as `stendeze`, with **no co-author or
  "Generated with" trailers**, whatever a tool's default says. Push every
  commit.
- Never rebase, amend, squash or force-push. The commit dates are the evidence
  that rules were fixed before the documents and results they govern.
- A rule change is one commit naming the document that forced it, changing
  schema.md and [labeling-guide.md](labeling-guide.md) together, and
  reporting the re-application to every existing label — including when
  nothing changes. Any change to a recorded value is confirmed with the
  labeler first.
- Report and ask before any value-changing edit. Never auto-fix a label.

**Numbers.**

- Compute every figure from the files before writing it. Ten times a claim
  stated from memory, an instruction, a partial scan or a summary diverged
  from the artifact; the finding is that disagreement between two sources is
  the signal, whichever turns out right. See [labeling-notes.md](labeling-notes.md#the-finding-across-all-ten).
  The finding is made: when two sources disagree, recompute, and do not add
  an eleventh entry to that table.
- The results tables are generated, not typed:
  `uv run covenant-eval coverage --write results.md`. Hand-written counts in
  prose go stale when a label changes; grep for them.
- The screen's signals are unreliable and must not be treated as facts about a
  document: over seventeen documents read, structure was right 9 of 17, grid
  11 of 17, covenant counts 6 of 17.

**Documents and data.**

- An accession number does not identify a document. Three accessions this
  corpus drew on hold more than one credit agreement (Plains, Lamb Weston, the
  dropped Avaya). Always use `document_file`; the validator matches it exactly.
- `data/raw/` is gitignored. Raw filings live at
  `data/raw/{accession}_{file}`, and the validator needs them to check quotes.
- `data/dev/` is the development set: the three labels discarded from the
  corpus (Lamb Weston EX-10.2, Avaya EX-10.7, Lithia EX-10.2), brought
  current and committed. Mechanics only — never for tuning, and Lamb Weston
  EX-10.2 never for prompt iteration or few-shot examples (it shares corpus
  row 7's accession). See `data/dev/README.txt`. The gitignored
  `data/discarded/` where they used to live keeps only its README.
- EDGAR needs `SEC_USER_AGENT` set. It is in `~/.zshenv`, because
  non-interactive shells do not read `~/.zshrc`. EDGAR throttles with 503s:
  keep `EdgarClient(rate=...)` at 4 or below.
- Every label carries `facility_name`, which is no longer scored. The field
  was cut on a pre-registered trigger; the values were left in place.

**The validator and the schema.**

- The validator parses enum values from schema.md and asserts that the
  sentences defining its guarded sets are still present, word for word.
  Rewording one fails the run with exit code 2 by design: update the
  transcription in `validate.py` in the same commit.
- `null_kind` has three values — `deferral`, `absence`, `unrepresentable` —
  told apart by where the value is. `unrepresentable` is sanctioned only on
  `step_down_schedule` (seasonal cycles, Hertz), must cite the construction, is
  excluded from scoring, and the validator enforces both limits.

## Commands

```sh
uv run covenant-eval validate data/labels/*.json   # quotes, enums, shapes; 0 errors expected
uv run covenant-eval validate data/dev/*.json      # 0 errors, 5 info (Lithia's redacted margins)
uv run covenant-eval coverage --write results.md   # regenerate the generated tables
uv run pytest                                      # the scorer's tests, against data/dev/ only
uv run covenant-eval compare A.json B.json         # align two records of one agreement, field by field
uv run covenant-eval agree                         # relabel agreement: data/relabel/ against data/labels/
```

`compare` prints ok, MISS or excluded for each field and no values unless
asked with `--values`. Do not run it on a drawn document's original label in
front of the relabeler. `agree` prints rates and counts only.

`covenant-eval search` and `covenant-eval screen` reproduce the recorded census
and screen, and **by default they overwrite `data/search/` and `data/screen/`**
— committed files the corpus's provenance rests on. Do not run them casually;
if you need to, pass `--out` to a scratch directory.

## Where things are written down

| File | What it is |
|---|---|
| [schema.md](schema.md) | Governs. Fields, rules, freezing, alignment, annotator agreement. |
| [corpus.md](corpus.md) | The frozen record of the sixteen documents and how each was chosen. |
| [labeling-guide.md](labeling-guide.md) | What labeling is done from. Operational; schema.md wins. |
| [labeling-notes.md](labeling-notes.md) | Findings: baseline traps, rule changes under contact, the ten instances. |
| [results.md](results.md) | The reporting shape, fixed before any model run; generated tables. |
| [relabel.md](relabel.md) | The blind relabel's method and selection, and the fields the repository already answers. |
| `data/dev/README.txt` | The development set: what each document is, and what it may not be used for. |
| `src/covenant_eval/score.py` | The scorer core. schema.md's comparison rules, transcribed. |
| [README.md](README.md) | The project's argument, for an outside reader. |
