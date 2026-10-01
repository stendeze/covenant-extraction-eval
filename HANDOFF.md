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

1. **The blind relabel** — by the labeler, Daniel. Method and selection are in
   [relabel.md](relabel.md), committed method-first (`090b7cc`) and drawn after
   (`b82b499`). Five documents for the headline agreement rate — G-III, Paya,
   Plains, Roper, Extreme — plus two flagged items relabeled on their own and
   reported separately: Amentum's `has_margin_grid` and Lamb Weston EX-10.1's
   European Term Loan `facility_type`. Relabels go to `data/relabel/`, never
   `data/labels/`. Do not show the relabeler the original labels.
2. **Build the extraction pipeline and scorer.** Code can be written now.
3. **Must wait:** running extraction on any corpus document. That is the
   first extraction run, and it comes after `label-freeze`.

The order of events is therefore: relabel → compute agreement → resolve
disagreements by rule → tag `label-freeze` → first extraction run.

## Open decisions

- **The relabel's agreement computation is not built.** It needs the same
  per-field comparison the scorer needs — each field's "Correct when" test and
  the [record alignment](schema.md#record-alignment) rules — so building the
  scorer's comparison first serves both.
- **The validator still accepts legacy filename keys, and its comment is
  stale.** [validate.py:286](src/covenant_eval/validate.py#L286) says the
  filename key "was never fixed", but every label has used `document_file`
  only since `4bc7610`. Two options were put to Daniel and not yet answered:
  correct the comment, or tighten the validator to accept only
  `document_file`. Either is its own commit. A label edit is not involved.
- **The errata mechanism does not exist.** schema.md says post-`label-freeze`
  corrections are recorded outside `data/labels/` and reported with both
  scores; the format and location are undecided and should be fixed before
  the first extraction run, so nothing about them is designed after seeing
  results.
- **Not built:** the extraction pipeline, the scorer, the regex baseline that
  [results.md](results.md) describes, and the fetch script that
  [README.md](README.md) says will make the corpus reproducible from a clean
  checkout. Each label records accession and `document_file`, and the
  committed `data/search/candidates.jsonl` carries each filer's CIK, so the
  fetch script has everything it needs.
- **Watch one rule.** The seasonal-cycle rule for `initial_threshold`
  (most restrictive level) is recorded in schema.md as the closest of the
  Hertz rules to arbitration. If a second document ever splits on it, that is
  where to look.
- **Known and deliberately unpatched:** the record-alignment tiebreak hole
  (two facilities with the same type, currency and amount). See schema.md,
  Record alignment.

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

- Compute every figure from the files before writing it. Nine times a claim
  stated from memory, an instruction, a partial scan or a summary diverged
  from the artifact; the finding is that disagreement between two sources is
  the signal, whichever turns out right. See [labeling-notes.md](labeling-notes.md#the-finding-across-all-nine).
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
- `data/discarded/` is gitignored. It holds three discarded labels (Lamb
  Weston EX-10.2, Avaya EX-10.7, Lithia EX-10.2), which the final
  screen-signal measurement used.
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
uv run covenant-eval coverage --write results.md   # regenerate the generated tables
```

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
| [labeling-notes.md](labeling-notes.md) | Findings: baseline traps, rule changes under contact, the nine instances. |
| [results.md](results.md) | The reporting shape, fixed before any model run; generated tables. |
| [relabel.md](relabel.md) | The blind relabel's method and selection. |
| [README.md](README.md) | The project's argument, for an outside reader. |
