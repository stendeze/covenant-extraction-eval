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
| `b200a0a` | Every decision before the first corpus run, with defaults (below) |
| `8ffd9ab` | The prompt generator and its output: `prompts/extraction_system.md`, `prompts/output_schema.json` (D1, D4) |
| `71811d0` | The extraction pipeline on the Batch API, with the corpus guard (D3, D5, D11, D12, B4, B7) |
| `fa7f69f` | The regex baseline, to R1 |

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
2. **Code**, all developed against `data/dev/` and never run on a corpus
   document, on the defaults in [Decisions before the first corpus
   run](#decisions-before-the-first-corpus-run) until Daniel reviews them.
   - *Built:* the prompt generator, the extraction pipeline and the regex
     baseline. The pipeline has not met the API — see Q4.
   - *Still to build:* the group B scoring on top of the scorer core —
     - F1 (B1);
     - null detection and the deferral-shape mapping (B2);
     - the deferral-citation span check (B3);
     - citation accuracy (B5);
     - the naive baseline through the scorer (B6).

     These wait for B1–B7 to be accepted. The fetch script also remains.
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
- **The full-context arm stays.** The truncation arm and a Sonnet cost
  comparison are proposed below, D8 and D9.
- **The prompt carries the adjudication rules**, generated from schema.md and
  frozen by commit before the first run. The labeler worked from the
  rulebook, so the model gets the same rulebook.
- **The dev set is for mechanics only** — does the pipeline run, parse and
  score. Not tuning.
- **The errata format is deferred until the first erratum exists.** The
  post-freeze rule already guarantees that both scores are reported.

## Decisions before the first corpus run

Every decision still open before the first extraction run, in one place, each
with a proposed default. Daniel reviews them in one sitting and accepts or
changes each. Until then the build proceeds on the defaults, against
`data/dev/` only, so a changed default changes code, not a result.

### The prompt and the model

**D1. The prompt must not carry corpus answers.** schema.md's rules are
interleaved with worked examples drawn from the corpus — Amentum's
commitment, Hertz's seasonal levels, Boeing's percentage covenant. Some
quote corpus filings without naming them (relabel.md, tier 1). A prompt that
reproduced schema.md would give the model the gold value for any field an
example covers, for any document it recognizes.
*Default:* the generator takes schema.md's model-facing sections — the four
corners rule, record shape, field summary, the eleven field sections,
citations, normalization, out of scope, the worked example — and drops:
- every blockquote — they are narrative asides, not rules;
- every sentence naming a corpus or dev-set document;
- every sentence carrying a corpus accession number;
- every sentence whose quotation occurs verbatim in a corpus filing or in a
  gold citation.

Generation fails if any of those survive. The cost: the labeler had the
examples, and the model gets the rules without them. That asymmetry is stated
with the results. The alternative, the rulebook verbatim, would be measuring
recognition.

**D2. No few-shot examples.** Zero-shot, rulebook only. A few-shot example
would have to come from outside the corpus. The only labeled documents
outside it are the dev set, which is mechanics-only.

**D3. Model settings.**
- `claude-opus-5-5`, through the Batch API.
- `effort: high`. Opus 5.5 defaults to `medium`, and the eval asks for the
  ceiling.
- Thinking left at its default: always on, adaptive, display omitted.
- `max_tokens: 64000`, no stop sequences.
- No fallback model. A refusal is a refusal: falling back would let a
  different model answer, and the Batch API rejects the parameter anyway.
- Sampling parameters are not accepted on this model, so runs are not
  repeatable. See D10.

**D4. The model-facing output schema** (generated, `prompts/output_schema.json`):
- The same record shape as a label file — `facilities[]` and
  `financial_covenants[]` — with every scored field as
  `{value, citation}`. A model output can then be compared, validated and
  quote-checked by the same code as a label.
- **No `null_kind` and no `facility_name`.**
- **Nullable:** `aggregate_commitment`, `applicable_margin_bps`,
  `springing_trigger` — the three schema.md makes nullable — and
  `step_down_schedule`. The last is because the rulebook tells a reader to
  record a seasonal cycle as null. A null there scores as a miss unless the
  gold is `unrepresentable`, so it is no escape hatch.
- **Citation:** `{section, quote}`, required on every non-null value. On a
  nullable field it may be null: the model, like the labeler, cites a
  deferral and does not cite an absence.
- **Alternative shapes** as `anyOf` branches with `const` discriminators:
  - maturity, `stated` with a `date`-format string, or `relative` with
    `{tenor_years, anchor}` or `{tenor_months, anchor}`;
  - `effective_from`, `stated` with a string, or `relative` with
    `{quarters_after, anchor}` or `{months_after, anchor}`;
  - springing trigger, null or the object.
- **Constraints the API does not support, checked after the response:**
  `YYYY-MM` precision on `effective_from` (no `pattern` support), integer
  ranges.
- Enums are taken from schema.md, as the validator does.
- One unscored `notes` array of strings, because the rulebook sends some
  facts "to free text".

**D5. The input is the whole filed exhibit, as `to_text` renders it** — the
same text quotes are verified against — in one user message, document first.
The system prompt carries the rulebook, cached across the batch.

### Scoring (group B)

**B1. F1 accounting, per field, pooled over every record in the corpus.**
- *Aligned pair, right value:* one true positive.
- *Aligned pair, wrong value:* a false positive and a false negative.
- *A null on either side:* gold null with a predicted value is a false
  positive; a predicted null against a gold value is a false negative; both
  null counts for nothing in F1 (see B2).
- *Spurious record:* each non-null field counts against precision.
- *Missed record:* each non-null gold field counts against recall.
- *Excluded fields* (`unrepresentable`, or the dev marker) count nowhere.

Per-document averages are reported as a secondary view only.

**B2. Correct declines get their own numbers, because F1 cannot see them.**
- *Null detection*, for the three nullable fields: the share of gold-null
  instances answered null, split by deferral shape (external fact,
  unattached exhibit); and beside it, the share of gold-non-null instances
  wrongly answered null.
- *The empty covenant list:* the count of covenants invented on the
  covenant-free document.

The deferral shape is read from a small committed mapping, since the labels
record it only in notes.

**B3. The README and schema.md conflict over deferral citations; schema.md
governs.** Field accuracy does not depend on the citation. README's sentence
("declining is only correct when the system can point at the sentence") gets
its own reported number. For gold deferral nulls answered null, it counts the
share whose citation is verbatim in the document and overlaps the gold
citation's span — the "derived programmatically from the quote by substring
search" offsets schema.md already defines. README is reworded to name that
number.

**B4. Model quotes are checked as labels are.** Typography and whitespace
are folded, and a whitespace-only difference passes, being an artifact of the
HTML-to-text step. A case difference fails, since the rule says verbatim.

**B5. Citation accuracy is reported separately:** the share of non-null
predicted citations whose quote verifies, per field and overall.

**B6. The naive baseline is put on the F1 scale by running it through the
scorer.** It emits one facility and one covenant per document, each field at
its corpus majority value from results.md's table. results.md's
per-instance table stays as it is. The naive predictor reads nothing, so it
cannot know how many records a document has. One of each is the reading-free
guess.

**B7. A failed document is scored as an empty prediction and listed.** That
covers a refusal, `max_tokens`, unparseable output or an expired request:
every gold record counts as missed, and the failure count is printed beside
every table. Errored and expired requests are retried once. Refusals and
`max_tokens` are not.

### Arms and runs

**D8. The truncation arm is dropped.** Every document fits Opus 5.5's window
with room to spare: the largest is 62% of it at the high estimate. Truncating
hard enough to lose the covenant section guarantees a large effect, which is
what schema.md asked the ablation to show, but only by measuring that a model
cannot extract what it is not shown. schema.md's ablation paragraph is
amended to say so.

**D9. One Sonnet 5.5 run on the final configuration, as a cost comparison.**
Same prompt and schema, `effort: high`. By local estimate it is about $4–8
cheaper per 16-document pass. It answers whether the ceiling model is needed,
and is reported beside the primary result, never instead of it.

**D10. The primary configuration runs three times.** Opus 5.5 takes no
sampling parameters, so one run is one draw. Three passes cost about
$23–49, from the per-pass estimate. Each field reports the mean, with the
min–max beside it.

**D11. Runs are committed.** `runs/<run-id>/` holds:
- the manifest — model, settings, prompt and schema hashes, git commit, batch
  id, document list, usage;
- the raw batch results;
- the parsed predictions.

Document text is not stored, only its hash.

**D12. The pipeline and the baseline refuse corpus documents until
`label-freeze` exists.** This is checked in code against `data/labels/`, by
accession and `document_file`. The dev set's Lamb Weston EX-10.2 shares an
accession with corpus row 7, and passes only because it is matched on its
file.

### The regex baseline

**R1. The spec, fixed before code.** A keyword extractor in the label
shape, the cheap tool someone would build instead of a model.
- Text from `to_text`.
- Every citation is the matched span, so its quotes verify by construction;
  it is reported, but its citation accuracy says nothing.
- **Facilities:** one record per tranche keyword that screen.py's existing
  `TRANCHES` patterns find. Revolver if `revolver` matches. A lettered Term A
  or Term B gives that type. An unlettered term loan gives `term_loan_b`: a
  keyword tool cannot read amortization, and ≤1% is the schema's default.
- **`aggregate_commitment`:** the first dollar amount within 300 characters
  after an "aggregate … Commitments" phrase for that tranche, USD unless a
  currency sign or code says otherwise; null if none.
- **`maturity_date`:** in the first "… Maturity Date" definition, a written
  calendar date gives `stated`. Failing that, "N years after / Nth
  anniversary of the X Date" gives `relative`. Otherwise null.
- **`interest_rate_benchmark`:** the benchmark keyword with the most
  occurrences, from screen.py's `BENCHMARKS`.
- **`applicable_margin_bps`:** the first percentage in the "Applicable
  Margin / Rate / Percentage" definition, converted to bps.
- **`has_margin_grid`:** screen.py's `PRICING_GRID` hint, unchanged.
- **Covenants:** one record per type that screen.py's `COVENANTS` patterns
  find.
  - `first_lien` gives `first_lien_net_leverage`.
  - `leverage` gives `total_net_leverage` if "Net Leverage Ratio" appears,
    otherwise `total_leverage_gross`.
  - Interest coverage and fixed charge map to themselves.
  - `initial_threshold`: the first "X.XX to 1.00" or "X.XX:1.00" within 400
    characters after the ratio's name in a "shall not permit / shall
    maintain" sentence.
  - `testing_frequency`: `quarterly` if "fiscal quarter" is in that
    sentence, else `annual`.
  - `step_down_schedule`: always `[]`. A keyword tool does not read tables,
    and saying so beats a schedule parser nobody would write.
  - `springing_trigger`: if screen.py's `SPRINGING` hint fires, the first
    "N%" near "Revolving" in that sentence, as `revolver_utilization` /
    `percent`; otherwise null.

**R2. How it is built.**
- Developed on `data/dev/` only, and committed before any corpus run.
- screen.py's patterns are reused unchanged where they cover a field. They
  have already been measured against 14 corpus documents (structure 9/17,
  grid 11/17, covenant counts 6/17 in labeling-notes.md). Changing them now
  would be tuning against known corpus results.
- The author knows the corpus traps labeling-notes.md documents. That is
  disclosed with the results, not designed around.

### Carried over

**C1. The facility identifying fields were landed as measured, not as
approved.** Daniel chose the version where pairing on a value every record
shares does not count. The list proposed with it named only
`interest_rate_benchmark` and `has_margin_grid` as the shared facility fields.
Counting the gold showed `applicable_margin_bps` (10 of 12 within-document
pairs) and `maturity_date` (8 of 12) are shared about as often, so `3733eb5`
makes only `facility_type` and `aggregate_commitment` identifying.
*Default:* keep. Reverting is one sentence in schema.md and
`IDENTIFYING_FIELDS` in score.py.

**C2. Relabel.md's exposure list must be transcribed to JSON** for
`covenant-eval agree` to print the headline. *Default:* after the relabel is
done, checked against relabel.md, committed with the agreement results.
Mapping "the term loan" to a record index means reading the original labels.

**C3. The two flagged items need a file shape.** *Default:* one
`data/relabel/flagged.json`, listing document, facility, field, value and
citation, compared and reported on its own.

### Questions from the build

Raised while building on the defaults. Each has a default; nothing waits on
an answer except Q4.

**Q1. Some rules lost a clause along with their example.** D1's filter drops a
sentence when its numbers or dates equal a gold value. Several rulebook
sentences state a rule and its example in one breath, so the rule went too:
- the calendar-date half of the maturity `basis` rule, the `stated` type
  description, and the "earliest of" example — their date equals a gold
  maturity;
- "a threshold below 1.00 cannot be an EBITDA multiple" — its example level
  equals a gold threshold;
- "record the precision the agreement states, which may be a month", and the
  exact-comparison examples — their month equals a gold step;
- the normalization row saying a percentage level is a ratio — its example is
  a corpus document's phrase.

Rules that existed only as examples are gone entirely: what `continuous` and
`weekly` mean, the "thereafter, add one" count, the explanations behind the
Term C, greater-of and any-drawn rules. Three harmless orphans remain
("Limbs (ii) and (iii) are mechanics.", "This is not hypothetical.", and a
bold lead about market usage).
*Default:* one schema.md commit restating each lost rule without a corpus
example, and swapping example values for ones no gold record holds. That
changes no rule and no label. Then regenerate the prompt, and correct
relabel.md's tier-1 line references, which would shift.

**Q2. The A8 list was matched on quotations, not values.** Building D1 showed
the rulebook also carries gold values with no quote around them — the
maturity example's date, for one. relabel.md's tier 1 may therefore miss
fields whose value, not wording, is printed in the rulebook.
*Default:* re-run the A8 check with value matching for the five drawn
documents, and update relabel.md before the relabel starts. Daniel need not
read it. If the relabel has already started, record the gap in its report
instead.

**Q3. The prompt keeps two generic priors:** "post-2022 agreements are almost
entirely Term SOFR", and triggers "commonly 35% or 40%". Both are market
facts, not corpus facts. *Default:* keep.

**Q4. The pipeline has not met the API.** This machine has no credentials:
no `ANTHROPIC_API_KEY`, no `ant` login. The first live call should be one dev
run — `covenant-eval extract data/dev/*_labels.json --run-id dev-1 --submit`
— which tests that the API accepts the output schema, that responses parse,
and that predictions score. At Batch prices, from the dev documents' sizes,
it costs $1.26–2.58.
*Default:* run it once a key is available, and commit the run (D11). Fix only
mechanical failures, never the prompt's wording: the dev set is not for
tuning.

**Q5. Two gaps in R1 were filled.**
- screen.py's `BENCHMARKS` has no CDOR pattern, so the baseline cannot answer
  `cdor`. Its bare "SOFR" also matches inside every "Term SOFR", so it counts
  only when no named benchmark is found.
- R1 reads only a definition named "… Maturity Date", so a "Termination
  Date" gives null.

*Default:* keep both as built. Both are the cheap tool's real limits.

**Q6. The prompt's frame is hand-written, not generated:** the opening that
maps "label" to "your output", the citation instruction, the closing task,
and the user-message template. It is in `prompt.py` and `extract.py`, hashed
into every run's manifest, and frozen with the rest at the first run.
*Default:* as written. Review it once.

**Q7. `max_tokens: 64000` at effort `high`** covers thinking and the JSON
together. Whether that is enough for the longest document is not knowable
before a live run. *Default:* keep. A `max_tokens` stop on the dev run (Q4)
is the signal to raise it, before any corpus run.

## Not built yet

The fetch script that [README.md](README.md) says will make the corpus
reproducible from a clean checkout. Each label records accession and
`document_file`, and the committed `data/search/candidates.jsonl` carries
each filer's CIK, so it has everything it needs.

## Watch

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
uv run covenant-eval prompt                        # check the committed prompt and schema still match schema.md
uv run covenant-eval prompt --write                # regenerate them (reads corpus filings for the leak check)
uv run covenant-eval extract data/dev/*_labels.json --run-id ID            # prepare a run; nothing sent
uv run covenant-eval extract data/dev/*_labels.json --run-id ID --submit   # send it to the Batch API (costs money)
uv run covenant-eval baseline data/dev/*_labels.json --run-id ID           # the regex baseline, as a run
uv run covenant-eval score-run ID --labels data/dev                         # predictions against labels, counts only
```

`extract` and `baseline` refuse any corpus document until the `label-freeze`
tag exists. That is the code half of the rule above; the rule itself does not
depend on the code.

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
