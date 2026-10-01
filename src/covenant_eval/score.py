"""Compare two records of one agreement, field by field, as schema.md says.

Two consumers need the same comparison. A model's output is scored against
the gold, and the blind relabel's second pass is compared with the first. Both
ask, for every scored field on every record, whether two values are the same
answer — and before that, which record on one side is which record on the
other. If they asked it in different code, a model and a relabeler could be
held to different tests, and the agreement rate would not measure what the
model is scored against.

Everything this module decides is fixed in schema.md first: each field's
**Correct when** test, the normalization table, and record alignment. What
schema.md has not yet decided — how per-field results become F1, how a correct
decline is credited, how citations enter a score — is deliberately absent, so
that no accounting choice is made in code before it is made on the page.

The comparison takes a reference and a candidate. For a model, the gold is the
reference and only the gold can exclude a field from scoring: a prediction
that marks its own field as excluded is still scored. For the relabel the
comparison is symmetric, and either pass can.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from .validate import SCHEMA_PATH, SchemaParseError, SchemaSets, _normalize_prose, load_schema_sets

LEVELS = ("facilities", "financial_covenants")

# Record alignment pairs records only on agreement in an identifying field —
# one that rarely repeats across the records of one document. Transcribed from
# prose, so the defining sentence is asserted present, the same guard the
# validator puts on its structural sets: a reworded rule fails the run rather
# than leaving a stale copy here.
IDENTIFYING_FIELDS: dict[str, tuple[str, ...]] = {
    "facilities": ("facility_type", "aggregate_commitment"),
    "financial_covenants": ("covenant_type", "initial_threshold"),
}
IDENTIFYING_SENTENCE = (
    "For facilities the identifying fields are `facility_type` and `aggregate_commitment`; "
    "for covenants, `covenant_type` and `initial_threshold`."
)
TYPE_FIELD = {"facilities": "facility_type", "financial_covenants": "covenant_type"}

# A guard against a runaway prediction, not a rule. Alignment is exact over
# every candidate pairing; a gold document holds at most five records at one
# level, and a prediction with more than this many is reported, not aligned.
MAX_RECORDS = 16

WHITESPACE = re.compile(r"\s+")
QUOTE_MARKS = "\"'“”‘’"


# --- Values --------------------------------------------------------------------


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _num_eq(a: Any, b: Any) -> bool:
    """Exact numeric equality on the printed number: 4 and 4.00 are one value,
    112.5 is not 113, and nothing is rounded."""
    return _is_number(a) and _is_number(b) and Decimal(str(a)) == Decimal(str(b))


def _both_null(a: Any, b: Any) -> bool | None:
    """True if both null, False if exactly one is, None if neither."""
    if a is None or b is None:
        return a is None and b is None
    return None


def normalize_anchor(anchor: str) -> str:
    """schema.md, Normalization: casefold, strip one leading "the", surrounding
    quotation marks and trailing punctuation, collapse whitespace — nothing else.

    An anchor names a defined term, so it gets only what a defined term
    survives. "Closing Date" and "the Closing Date" match; "Restatement Date"
    does not, even where the agreement makes them the same day.
    """
    text = anchor.strip().strip(QUOTE_MARKS).rstrip(".,;:").strip().casefold()
    text = re.sub(r"^the\s+", "", text)
    return WHITESPACE.sub(" ", text).strip()


def _same_anchor(a: Any, b: Any) -> bool:
    return isinstance(a, str) and isinstance(b, str) and normalize_anchor(a) == normalize_anchor(b)


def _same_enum(a: Any, b: Any) -> bool:
    null = _both_null(a, b)
    if null is not None:
        return null
    return isinstance(a, str) and a == b


def _same_bool(a: Any, b: Any) -> bool:
    null = _both_null(a, b)
    if null is not None:
        return null
    return isinstance(a, bool) and isinstance(b, bool) and a is b


def _same_number(a: Any, b: Any) -> bool:
    null = _both_null(a, b)
    if null is not None:
        return null
    return _num_eq(a, b)


def _same_commitment(a: Any, b: Any) -> bool:
    null = _both_null(a, b)
    if null is not None:
        return null
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return False
    return _num_eq(a.get("amount"), b.get("amount")) and _same_enum(a.get("currency"), b.get("currency"))


def _tenor_months(value: Any) -> Decimal | None:
    """The maturity tenor in months. schema.md: `tenor_years: 5` and
    `tenor_months: 60` are one answer — both count calendar time from the same
    day. A value carrying both keys, or neither, is malformed and matches
    nothing."""
    if not isinstance(value, dict):
        return None
    years, months = value.get("tenor_years"), value.get("tenor_months")
    if (years is None) == (months is None):
        return None
    n = years * 12 if years is not None else months
    return Decimal(str(n)) if _is_number(n) else None


def _same_maturity(a: Any, b: Any) -> bool:
    null = _both_null(a, b)
    if null is not None:
        return null
    if not (isinstance(a, dict) and isinstance(b, dict)) or a.get("basis") != b.get("basis"):
        return False
    va, vb = a.get("value"), b.get("value")
    if a.get("basis") == "stated":
        return isinstance(va, str) and va == vb
    if a.get("basis") == "relative":
        ma, mb = _tenor_months(va), _tenor_months(vb)
        return (
            ma is not None and ma == mb
            and _same_anchor(va.get("anchor"), vb.get("anchor"))
        )
    return False


def _period_unit(value: dict[str, Any]) -> str | None:
    units = [k for k in ("quarters_after", "months_after") if k in value]
    return units[0] if len(units) == 1 else None


def _same_effective_from(a: Any, b: Any) -> bool:
    """Like a maturity, except that the unit is compared: counting fiscal
    quarters after an anchor is not calendar arithmetic, so `quarters_after`
    and `months_after` are never converted into each other. A stated value is
    compared as a string, so "2027-11" against "2027-11-28" is a miss in both
    directions (schema.md, Reduced precision)."""
    if not (isinstance(a, dict) and isinstance(b, dict)) or a.get("basis") != b.get("basis"):
        return False
    va, vb = a.get("value"), b.get("value")
    if a.get("basis") == "stated":
        return isinstance(va, str) and va == vb
    if a.get("basis") == "relative" and isinstance(va, dict) and isinstance(vb, dict):
        unit = _period_unit(va)
        return (
            unit is not None and unit == _period_unit(vb)
            and isinstance(va[unit], int) and not isinstance(va[unit], bool) and va[unit] == vb[unit]
            and _same_anchor(va.get("anchor"), vb.get("anchor"))
        )
    return False


def _same_step(a: Any, b: Any) -> bool:
    return (
        isinstance(a, dict) and isinstance(b, dict)
        and _same_effective_from(a.get("effective_from"), b.get("effective_from"))
        and _num_eq(a.get("threshold"), b.get("threshold"))
    )


def _same_schedule(a: Any, b: Any) -> bool:
    """Ordered sequences, same length, every step matching. A partial match is
    a miss; per-step credit is the separate diagnostic below."""
    null = _both_null(a, b)
    if null is not None:
        return null
    if not (isinstance(a, list) and isinstance(b, list)) or len(a) != len(b):
        return False
    return all(_same_step(x, y) for x, y in zip(a, b))


def _same_trigger(a: Any, b: Any) -> bool:
    """Null against non-null first; then condition, threshold and unit. The
    quote inside the value is a citation, not part of the answer."""
    null = _both_null(a, b)
    if null is not None:
        return null
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return False
    return (
        _same_enum(a.get("condition_type"), b.get("condition_type"))
        and _num_eq(a.get("threshold"), b.get("threshold"))
        and _same_enum(a.get("threshold_unit"), b.get("threshold_unit"))
    )


# Every field in schema.md's Field summary must have a test here. One that
# does not is an error at load time, not a field silently scored as a miss.
CORRECT_WHEN: dict[str, Callable[[Any, Any], bool]] = {
    "facility_type": _same_enum,
    "aggregate_commitment": _same_commitment,
    "maturity_date": _same_maturity,
    "interest_rate_benchmark": _same_enum,
    "applicable_margin_bps": _same_number,
    "has_margin_grid": _same_bool,
    "covenant_type": _same_enum,
    "initial_threshold": _same_number,
    "step_down_schedule": _same_schedule,
    "testing_frequency": _same_enum,
    "springing_trigger": _same_trigger,
}


def load_scoring_fields(schema_path: Path = SCHEMA_PATH) -> dict[str, tuple[str, ...]]:
    """The scored fields per level, from schema.md, checked against this module."""
    sets: SchemaSets = load_schema_sets(schema_path)
    if _normalize_prose(IDENTIFYING_SENTENCE) not in _normalize_prose(schema_path.read_text()):
        raise SchemaParseError(
            "schema.md: the sentence defining the identifying fields for record alignment is no "
            "longer present as transcribed in score.py; re-check IDENTIFYING_FIELDS by hand.\n"
            f"  expected: {IDENTIFYING_SENTENCE}"
        )
    fields = {"facilities": sets.facility_fields, "financial_covenants": sets.covenant_fields}
    for level, names in fields.items():
        missing = [n for n in names if n not in CORRECT_WHEN]
        if missing:
            raise SchemaParseError(f"schema.md scores {missing} at {level} level, and score.py has no test for it")
        for name in IDENTIFYING_FIELDS[level]:
            if name not in names:
                raise SchemaParseError(f"identifying field {name} is not a scored {level} field in schema.md")
    return fields


# --- Fields ----------------------------------------------------------------------


@dataclass(frozen=True)
class StepCredit:
    """schema.md's per-step diagnostic: never part of the field's score."""

    recovered: int  # reference steps the candidate also has, anywhere in its array
    reference_steps: int
    matched: int  # candidate steps the reference also has
    candidate_steps: int


@dataclass(frozen=True)
class FieldResult:
    field: str
    reference: Any
    candidate: Any
    correct: bool | None  # None: excluded from scoring
    excluded: str | None = None
    step_credit: StepCredit | None = None


def _entry_value(entry: Any) -> Any:
    return entry.get("value") if isinstance(entry, dict) else None


def _exclusion(entry: Any) -> str | None:
    """Why a field is not scored, if it is not. A gold null the field's type
    cannot hold is `unrepresentable`; a dev-set field can carry a marker."""
    if not isinstance(entry, dict):
        return None
    if entry.get("excluded_from_scoring"):
        return f"excluded_from_scoring: {entry['excluded_from_scoring']}"
    if entry.get("value") is None and entry.get("null_kind") == "unrepresentable":
        return "unrepresentable"
    return None


def step_credit(reference: list[Any], candidate: list[Any]) -> StepCredit:
    """A step counts once, wherever it sits; equality is an equivalence, so
    matching greedily is matching optimally."""
    remaining = list(candidate)
    recovered = 0
    for step in reference:
        hit = next((i for i, other in enumerate(remaining) if _same_step(step, other)), None)
        if hit is not None:
            recovered += 1
            remaining.pop(hit)
    return StepCredit(recovered, len(reference), recovered, len(candidate))


def compare_field(name: str, reference: Any, candidate: Any, *, symmetric: bool) -> FieldResult:
    """One field, two entries, each `{value, citation, ...}` or absent."""
    ref_value, cand_value = _entry_value(reference), _entry_value(candidate)
    excluded = _exclusion(reference) or (_exclusion(candidate) if symmetric else None)
    if excluded:
        return FieldResult(name, ref_value, cand_value, None, excluded)

    correct = CORRECT_WHEN[name](ref_value, cand_value)
    # schema.md, How agreement is computed: two nulls of different kinds
    # disagree, because the kind decides whether a citation is required and
    # whether the field is scored. A model is never asked for null_kind, so
    # this applies only to the symmetric comparison.
    if correct and symmetric and ref_value is None and cand_value is None:
        correct = reference.get("null_kind") == candidate.get("null_kind")

    credit = None
    if name == "step_down_schedule" and (ref_value or cand_value):
        credit = step_credit(ref_value if isinstance(ref_value, list) else [],
                             cand_value if isinstance(cand_value, list) else [])
    return FieldResult(name, ref_value, cand_value, correct, None, credit)


# --- Records ----------------------------------------------------------------------


@dataclass(frozen=True)
class PairResult:
    reference_index: int
    candidate_index: int
    fields: tuple[FieldResult, ...]

    @property
    def agreement(self) -> int:
        return sum(1 for f in self.fields if f.correct is True)

    def result(self, name: str) -> FieldResult:
        return next(f for f in self.fields if f.field == name)


@dataclass(frozen=True)
class LevelComparison:
    level: str
    pairs: tuple[PairResult, ...]
    unpaired_reference: tuple[int, ...]  # missed records, for a model
    unpaired_candidate: tuple[int, ...]  # spurious records, for a model


@dataclass(frozen=True)
class DocumentComparison:
    levels: dict[str, LevelComparison] = field(default_factory=dict)


def _currency(record: dict[str, Any]) -> Any:
    value = _entry_value(record.get("aggregate_commitment"))
    return value.get("currency") if isinstance(value, dict) else None


def _commitment_ranks(records: list[dict[str, Any]]) -> list[int]:
    """Each facility's rank by commitment amount, descending, nulls last,
    position breaking ties."""
    def key(i: int) -> tuple[bool, Decimal, int]:
        value = _entry_value(records[i].get("aggregate_commitment"))
        amount = value.get("amount") if isinstance(value, dict) else None
        if not _is_number(amount):
            return (True, Decimal(0), i)
        return (False, -Decimal(str(amount)), i)
    order = sorted(range(len(records)), key=key)
    ranks = [0] * len(records)
    for rank, i in enumerate(order):
        ranks[i] = rank
    return ranks


def align_level(
    level: str,
    reference: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    fields: tuple[str, ...],
    *,
    symmetric: bool,
) -> LevelComparison:
    """schema.md, Record alignment, step by step.

    1. Every candidate pair is scored by the fields on which it agrees.
    2. A pair must agree on an identifying field to be a candidate at all.
    3. The pairing with the most total agreement wins; then, in order, more
       pairs agreeing on type, on (type, currency) for facilities, and on
       commitment rank; then position, records pairing in the order they
       appear.

    Exact over every pairing. Position is compared as the tuple of candidate
    indices assigned to reference records in order, unpaired sorting last, so
    of two otherwise equal pairings the one that keeps both lists in order wins.
    """
    if len(candidate) > MAX_RECORDS or len(reference) > MAX_RECORDS:
        raise ValueError(f"{level}: more than {MAX_RECORDS} records on one side; not aligned")

    results: dict[tuple[int, int], tuple[FieldResult, ...]] = {}
    scores: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    ref_ranks, cand_ranks = _commitment_ranks(reference), _commitment_ranks(candidate)
    type_field = TYPE_FIELD[level]

    for i, ref in enumerate(reference):
        for j, cand in enumerate(candidate):
            row = tuple(compare_field(f, ref.get(f), cand.get(f), symmetric=symmetric) for f in fields)
            by_name = {r.field: r for r in row}
            if not any(by_name[f].correct is True for f in IDENTIFYING_FIELDS[level]):
                continue
            same_type = by_name[type_field].correct is True
            if level == "facilities":
                same_type_currency = same_type and _currency(ref) == _currency(cand)
                same_rank = ref_ranks[i] == cand_ranks[j]
            else:
                same_type_currency = same_rank = False
            results[(i, j)] = row
            scores[(i, j)] = (
                sum(1 for r in row if r.correct is True),
                int(same_type),
                int(same_type_currency),
                int(same_rank),
            )

    unpaired = len(candidate)  # sorts after every real candidate index

    @lru_cache(maxsize=None)
    def best(i: int, used: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
        if i == len(reference):
            return (0, 0, 0, 0), ()
        rest_score, rest = best(i + 1, used)
        options = [(rest_score, (unpaired,) + rest)]
        for j in range(len(candidate)):
            if used & (1 << j) or (i, j) not in scores:
                continue
            rest_score, rest = best(i + 1, used | (1 << j))
            options.append((tuple(a + b for a, b in zip(scores[(i, j)], rest_score)), (j,) + rest))
        return max(options, key=lambda o: (o[0], tuple(-k for k in o[1])))

    _, assignment = best(0, 0)
    pairs = tuple(
        PairResult(i, j, results[(i, j)]) for i, j in enumerate(assignment) if j != unpaired
    )
    paired_candidates = {p.candidate_index for p in pairs}
    return LevelComparison(
        level,
        pairs,
        tuple(i for i, j in enumerate(assignment) if j == unpaired),
        tuple(j for j in range(len(candidate)) if j not in paired_candidates),
    )


def compare_documents(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    fields: dict[str, tuple[str, ...]],
    *,
    symmetric: bool,
) -> DocumentComparison:
    """Both levels of one agreement. A missing or null record list is empty:
    a candidate that returns no covenants has returned an empty list."""
    return DocumentComparison({
        level: align_level(
            level, reference.get(level) or [], candidate.get(level) or [], fields[level], symmetric=symmetric
        )
        for level in LEVELS
    })


# --- The blind relabel's agreement ---------------------------------------------------


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


@dataclass
class FieldAgreement:
    field: str
    compared: int = 0
    agreed: int = 0
    values: Counter = field(default_factory=Counter)  # both passes pooled, canonical form
    excluded: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float | None:
        return self.agreed / self.compared if self.compared else None

    @property
    def majority_rate(self) -> float | None:
        """Share of the compared values, both passes pooled, taking the most
        common value — printed beside the agreement figure, because on a
        field that is mostly one value two passes agree mostly by both writing
        it, and five documents are too few for kappa to correct that."""
        total = sum(self.values.values())
        return max(self.values.values()) / total if total else None


@dataclass
class AgreementReport:
    fields: dict[str, FieldAgreement]
    paired: Counter  # by level
    only_original: Counter
    only_relabel: Counter


Include = Callable[[str, str, int, str], bool]


def agreement(
    comparisons: list[tuple[str, DocumentComparison]],
    fields: dict[str, tuple[str, ...]],
    include: Include = lambda doc, level, index, name: True,
) -> AgreementReport:
    """schema.md, How agreement is computed.

    `comparisons` are symmetric comparisons, original pass as reference.
    `include(document, level, original_index, field)` selects instances, which
    is how the views without the fields the repository already answers are
    computed. Records one pass has and the other does not are counted on their
    own and enter no field's rate.
    """
    per_field = {name: FieldAgreement(name) for level in LEVELS for name in fields[level]}
    paired, only_original, only_relabel = Counter(), Counter(), Counter()
    for doc, comparison in comparisons:
        for level, lc in comparison.levels.items():
            paired[level] += len(lc.pairs)
            only_original[level] += len(lc.unpaired_reference)
            only_relabel[level] += len(lc.unpaired_candidate)
            for pair in lc.pairs:
                for result in pair.fields:
                    if not include(doc, level, pair.reference_index, result.field):
                        continue
                    stats = per_field[result.field]
                    if result.correct is None:
                        stats.excluded.append(f"{doc} {level}[{pair.reference_index}].{result.field}: {result.excluded}")
                        continue
                    stats.compared += 1
                    stats.agreed += int(result.correct)
                    stats.values[_canonical(result.reference)] += 1
                    stats.values[_canonical(result.candidate)] += 1
    return AgreementReport(per_field, paired, only_original, only_relabel)


def render_agreement(report: AgreementReport, title: str) -> str:
    """Rates and counts only. No value is printed, so the table can be read
    before the disagreements are looked at one by one."""
    pct = lambda x: "—" if x is None else f"{x:.0%}"
    lines = [f"### {title}", "", "| Field | Agreement | n | Majority-class rate | Excluded |",
             "|---|---:|---:|---:|---:|"]
    for stats in report.fields.values():
        lines.append(
            f"| `{stats.field}` | {pct(stats.rate)} | {stats.agreed}/{stats.compared} | "
            f"{pct(stats.majority_rate)} | {len(stats.excluded)} |"
        )
    lines.append("")
    for level in LEVELS:
        lines.append(
            f"*{level}: {report.paired[level]} paired; {report.only_original[level]} only in the "
            f"original pass; {report.only_relabel[level]} only in the relabel.*"
        )
    excluded = [e for s in report.fields.values() for e in s.excluded]
    if excluded:
        lines += ["", "Excluded:"] + [f"- {e}" for e in excluded]
    return "\n".join(lines) + "\n"


# --- Files ------------------------------------------------------------------------


def document_key(label: dict[str, Any]) -> tuple[str, str]:
    """An accession does not identify a document; accession and file do."""
    source = label.get("source") or {}
    return source.get("accession_number", ""), source.get("document_file", "")


def load_labels(directory: Path) -> dict[tuple[str, str], dict[str, Any]]:
    labels = {}
    for path in sorted(directory.glob("*.json")):
        label = json.loads(path.read_text())
        key = document_key(label)
        if key in labels:
            raise ValueError(f"{path}: a second label for {key}")
        labels[key] = label
    return labels


def render_comparison(comparison: DocumentComparison, *, values: bool) -> str:
    mark = {True: "ok", False: "MISS", None: "excluded"}
    lines = []
    for level, lc in comparison.levels.items():
        lines.append(f"{level}: {len(lc.pairs)} paired, reference only {list(lc.unpaired_reference)}, "
                     f"candidate only {list(lc.unpaired_candidate)}")
        for pair in lc.pairs:
            lines.append(f"  reference[{pair.reference_index}] <-> candidate[{pair.candidate_index}]  "
                         f"agreement {pair.agreement}")
            for r in pair.fields:
                line = f"    {r.field:24} {mark[r.correct]}"
                if r.excluded:
                    line += f" ({r.excluded})"
                if r.step_credit:
                    c = r.step_credit
                    line += f"  steps: {c.recovered}/{c.reference_steps} recovered, {c.matched}/{c.candidate_steps} matched"
                if values:
                    line += f"\n      reference: {_canonical(r.reference)}\n      candidate: {_canonical(r.candidate)}"
                lines.append(line)
    return "\n".join(lines)


def run_compare(reference: Path, candidate: Path, schema_path: Path = SCHEMA_PATH, *,
                symmetric: bool, values: bool) -> str:
    fields = load_scoring_fields(schema_path)
    comparison = compare_documents(
        json.loads(reference.read_text()), json.loads(candidate.read_text()), fields, symmetric=symmetric
    )
    return render_comparison(comparison, values=values)


def load_exposure(path: Path) -> dict[tuple[str, str, int, str], int]:
    """The fields relabel.md lists, transcribed: (document_file, level, record
    index in the original label, field) -> tier."""
    rows = json.loads(path.read_text())
    return {(r["document_file"], r["level"], int(r["record"]), r["field"]): int(r["tier"]) for r in rows}


def run_agree(original_dir: Path, relabel_dir: Path, exposure_path: Path | None,
              schema_path: Path = SCHEMA_PATH) -> str:
    """The relabel's agreement, headline first.

    Only documents present in both directories are compared. Without an
    exposure file the headline view cannot be computed, and the output says so
    rather than presenting the every-field figure in its place.
    """
    fields = load_scoring_fields(schema_path)
    originals, relabels = load_labels(original_dir), load_labels(relabel_dir)
    common = sorted(set(originals) & set(relabels))
    if not common:
        return f"no document appears in both {original_dir} and {relabel_dir}"
    comparisons = [
        (key[1], compare_documents(originals[key], relabels[key], fields, symmetric=True)) for key in common
    ]
    out = [f"{len(common)} document(s) compared: {', '.join(k[1] for k in common)}", ""]
    every = render_agreement(agreement(comparisons, fields), "Every field")
    if exposure_path is None:
        out += ["*Headline (without tier 1) not computed: pass --exposure with relabel.md's list.*", "", every]
    else:
        tiers = load_exposure(exposure_path)
        not_tier1 = lambda doc, level, i, name: tiers.get((doc, level, i, name), 0) != 1
        neither = lambda doc, level, i, name: tiers.get((doc, level, i, name), 0) == 0
        out += [
            render_agreement(agreement(comparisons, fields, not_tier1), "Headline: without tier 1"),
            every,
            render_agreement(agreement(comparisons, fields, neither), "Without tiers 1 and 2"),
        ]
    return "\n".join(out)
