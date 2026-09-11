"""Check a label file against the current schema without changing it.

The labels in this corpus are hand-made over weeks, and schema.md moves while
they are being made — four rules changed under the first two documents alone.
A label produced against last week's snapshot is not wrong in any way a reader
notices: it is well-formed JSON with plausible values, and the deviation is
visible only if you happen to remember which rule changed when. The first such
case here was a `relative` maturity recorded as a verbatim string, in the label
for the very document whose reading replaced that form.

So this module reports deviations and stops. It does not repair them, because
the two causes look identical from the outside and only the labeler can tell
them apart: staleness, where the rule moved after the label was written, and a
deliberate call, where the labeler read the document and disagrees. Auto-fixing
would silently convert the second into the first, and a label file edited to
satisfy a checker is no longer evidence of what a human found in the document.

What the schema says is read out of schema.md at runtime rather than
transcribed here, so the two cannot drift. The list of scored fields comes from
the Field summary table — it changed once already, when facility_name was cut,
and a transcribed copy would have had to be edited in the same breath. Four
value sets — the scored enums — are written in a uniform shape and are parsed
too. The remaining four are structural sets defined
inside prose sentences, in three different shapes; parsing English would break
on rewording that changes nothing, so those stay transcribed and are guarded by
asserting their defining sentence still appears verbatim in schema.md. Either
way, nothing is silently assumed: a schema.md this module cannot read raises
rather than falling back to a stale copy, because a parser that quietly returns
a short enum turns every unrecognized value into a false labeling error across
every file in the corpus.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .screen import to_text

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.md"

# The scored fields are parsed from the "Field summary" table in schema.md, for
# the same reason the enum values are: a transcribed copy is a second source of
# truth for something that changes. It changed at Kontoor, where facility_name
# was cut, and the cut had to be made in two places at once. A field absent
# from a label file is a hole in the gold record, not a null; a field a label
# file carries but the schema no longer scores — facility_name, in files
# written before the cut — is ignored rather than flagged.
FIELD_SUMMARY_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([a-z_0-9]+)`\s*\|\s*(\w+)\s*\|", re.M)
FIELD_LEVELS = ("facility", "covenant")

# The scored enums, parsed from schema.md. Each is written as a "### N.
# `field_name`" heading followed by a "**Type:** enum — " line whose backticked
# values wrap across up to four lines and close with a period.
PARSED_ENUMS = ("facility_type", "interest_rate_benchmark", "covenant_type", "testing_frequency")

# The structural sets, defined inside prose rather than in the uniform enum
# shape. These are transcribed, and each is paired with the sentence in
# schema.md that defines it. The sentence is asserted to still be present, so a
# reword or a changed value fails the run and forces a human to re-check the
# set rather than trusting the copy below. They are closed sets describing
# record structure — unlike covenant_type, they do not grow when a new document
# turns up a construction nobody had seen.
GUARDED_SETS: dict[str, tuple[frozenset[str], str]] = {
    "maturity_basis": (
        frozenset({"stated", "relative"}),
        "**Type:** object — `{value, basis}` where `basis` is `stated` or `relative`.",
    ),
    "condition_type": (
        frozenset({"revolver_utilization", "minimum_availability", "other"}),
        "**Type:** object or `null`. When non-null: `{condition_type: enum, threshold: number, "
        "threshold_unit: enum, quote: string}` where `condition_type` is `revolver_utilization`, "
        "`minimum_availability`, or `other`, and `threshold_unit` is `percent` or `currency`.",
    ),
    "threshold_unit": (
        frozenset({"percent", "currency"}),
        "where `condition_type` is `revolver_utilization`, `minimum_availability`, or `other`, "
        "and `threshold_unit` is `percent` or `currency`.",
    ),
    "null_kind": (
        frozenset({"deferral", "absence"}),
        "Label files carry `null_kind` alongside any null value, taking `\"deferral\"` or "
        "`\"absence\"`.",
    ),
}

ENUM_TYPE_LINE = re.compile(r"\*\*Type:\*\*\s+enum\s+—\s+(.+?)\.\s*\n", re.S)
BACKTICKED = re.compile(r"`([a-z_0-9]+)`")
SECTION_BREAK = re.compile(r"\n### |\n---")


class SchemaParseError(Exception):
    """schema.md could not be read in the shape this module expects.

    Raised rather than falling back, because a partial value set is
    indistinguishable in the output from a corpus full of bad enum values.
    """


@dataclass(frozen=True)
class SchemaSets:
    enums: dict[str, frozenset[str]]
    facility_fields: tuple[str, ...]
    covenant_fields: tuple[str, ...]
    maturity_basis: frozenset[str]
    condition_type: frozenset[str]
    threshold_unit: frozenset[str]
    null_kinds: frozenset[str]


def _normalize_prose(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def parse_enum(schema_text: str, field: str) -> frozenset[str]:
    """Read one `**Type:** enum — ...` value set out of its field section."""
    heading = re.search(rf"^### \d+\. `{re.escape(field)}`$", schema_text, re.M)
    if heading is None:
        raise SchemaParseError(
            f"schema.md: no '### N. `{field}`' heading found; the field section may have been "
            f"renamed or removed"
        )
    body_start = heading.end()
    break_match = SECTION_BREAK.search(schema_text, body_start)
    body = schema_text[body_start : break_match.start() if break_match else len(schema_text)]

    type_line = ENUM_TYPE_LINE.search(body)
    if type_line is None:
        raise SchemaParseError(
            f"schema.md: the `{field}` section has no '**Type:** enum — ...' line ending in a "
            f"period; the enum may have been reformatted"
        )
    values = frozenset(BACKTICKED.findall(type_line.group(1)))
    if not values:
        raise SchemaParseError(
            f"schema.md: the `{field}` enum line parsed to an empty value set: "
            f"{_normalize_prose(type_line.group(1))!r}"
        )
    return values


def parse_scored_fields(schema_text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Read the scored fields and their levels out of the Field summary table."""
    heading = re.search(r"^## Field summary$", schema_text, re.M)
    if heading is None:
        raise SchemaParseError("schema.md: no '## Field summary' heading found")
    break_match = re.search(r"\n---", schema_text[heading.end() :])
    body = schema_text[heading.end() :][: break_match.start() if break_match else None]

    rows = FIELD_SUMMARY_ROW.findall(body)
    if not rows:
        raise SchemaParseError(
            "schema.md: the Field summary table parsed to no rows; expected lines shaped "
            "'| N | `field_name` | facility|covenant | type |'"
        )

    by_level: dict[str, list[str]] = {level: [] for level in FIELD_LEVELS}
    for _, field, level in rows:
        if level not in by_level:
            raise SchemaParseError(
                f"schema.md: field `{field}` has level {level!r}, expected one of {list(FIELD_LEVELS)}"
            )
        by_level[level].append(field)

    # The numbering is the cheapest check that a row was not dropped or
    # duplicated by an edit — exactly the kind of slip cutting a field invites.
    numbers = [int(n) for n, _, _ in rows]
    if numbers != list(range(1, len(numbers) + 1)):
        raise SchemaParseError(
            f"schema.md: Field summary rows are numbered {numbers}, expected 1..{len(numbers)}; "
            f"a row was probably added or removed without renumbering"
        )
    for level, fields in by_level.items():
        if not fields:
            raise SchemaParseError(f"schema.md: the Field summary table has no {level}-level fields")

    return tuple(by_level["facility"]), tuple(by_level["covenant"])


def load_schema_sets(schema_path: Path = SCHEMA_PATH) -> SchemaSets:
    """Parse the scored enums; assert the guarded sets are still defined as transcribed."""
    try:
        schema_text = schema_path.read_text()
    except OSError as exc:
        raise SchemaParseError(f"cannot read {schema_path}: {exc}") from exc

    enums = {field: parse_enum(schema_text, field) for field in PARSED_ENUMS}
    facility_fields, covenant_fields = parse_scored_fields(schema_text)

    flat = _normalize_prose(schema_text)
    for name, (_, sentence) in GUARDED_SETS.items():
        if _normalize_prose(sentence) not in flat:
            raise SchemaParseError(
                f"schema.md: the sentence defining `{name}` is no longer present as transcribed. "
                f"This module keeps that set as a copy because it is defined in prose, so the "
                f"copy must be re-checked by hand against schema.md and updated here.\n"
                f"  expected: {_normalize_prose(sentence)}"
            )

    return SchemaSets(
        enums=enums,
        facility_fields=facility_fields,
        covenant_fields=covenant_fields,
        maturity_basis=GUARDED_SETS["maturity_basis"][0],
        condition_type=GUARDED_SETS["condition_type"][0],
        threshold_unit=GUARDED_SETS["threshold_unit"][0],
        null_kinds=GUARDED_SETS["null_kind"][0],
    )

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

# Typographic variants that survive HTML-to-text and would fail an exact
# substring test for reasons that have nothing to do with whether the labeler
# read the sentence. Curly quotes and dashes are the whole list: the point of
# the verbatim rule is that the language exists in the document, and a label
# that types an apostrophe where the filing renders a right single quote has
# not invented anything.
TYPOGRAPHY = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"',
        "–": "-", "—": "-", "‑": "-", "−": "-",
        " ": " ",
    }
)
WHITESPACE = re.compile(r"\s+")


def normalize_for_quote_check(text: str) -> str:
    """Fold typography and whitespace, and nothing else.

    Case is preserved: schema.md calls the quote verbatim, and a case
    difference is reported separately rather than forgiven, because it is the
    kind of thing that distinguishes a transcribed sentence from a remembered
    one.
    """
    return WHITESPACE.sub(" ", text.translate(TYPOGRAPHY)).strip()


@dataclass
class Deviation:
    path: str
    code: str
    detail: str
    severity: str = "error"

    def line(self) -> str:
        return f"  [{self.severity}] {self.path}\n      {self.code}: {self.detail}"


class Report:
    def __init__(self, label_path: Path) -> None:
        self.label_path = label_path
        self.deviations: list[Deviation] = []
        self.quotes_checked = 0
        self.raw_path: Path | None = None

    def add(self, path: str, code: str, detail: str, severity: str = "error") -> None:
        self.deviations.append(Deviation(path, code, detail, severity))

    @property
    def errors(self) -> int:
        return sum(1 for d in self.deviations if d.severity == "error")


def find_raw(accession: str, raw_dir: Path) -> Path | None:
    """Raw filings are stored as {accession}_{original filename}."""
    matches = sorted(raw_dir.glob(f"{accession}_*"))
    return matches[0] if matches else None


def _check_citation(
    report: Report, path: str, citation: Any, document: str | None
) -> None:
    if not isinstance(citation, dict):
        report.add(path, "malformed_citation", f"expected an object, found {type(citation).__name__}")
        return
    for key in ("section", "quote"):
        if not citation.get(key):
            report.add(f"{path}.{key}", "missing_citation_field", f"citation has no {key}")
    quote = citation.get("quote")
    if not isinstance(quote, str) or not quote.strip():
        return
    if document is None:
        return

    report.quotes_checked += 1
    needle = normalize_for_quote_check(quote)
    if needle in document:
        return
    # Ordered from most to least forgiving explanation, so the report names the
    # actual difference rather than just saying the quote is absent.
    if needle.lower() in document.lower():
        report.add(
            f"{path}.quote",
            "quote_case_mismatch",
            f"present but cased differently: {quote[:90]!r}",
            severity="warn",
        )
        return
    if needle.replace(" ", "") in document.replace(" ", ""):
        report.add(
            f"{path}.quote",
            "quote_spans_table_cells",
            f"present only with spacing removed, likely a table split: {quote[:90]!r}",
            severity="warn",
        )
        return
    report.add(f"{path}.quote", "quote_not_verbatim", f"not found in the source document: {quote[:90]!r}")


def _check_null_kind(
    report: Report, path: str, entry: dict[str, Any], value: Any, sets: SchemaSets
) -> None:
    """schema.md, `null_kind` — a gold annotation, not a schema field.

    It decides whether a citation is demanded, so a null without it leaves the
    scorer unable to tell a deferral from an absence.
    """
    null_kind = entry.get("null_kind")
    citation = entry.get("citation")

    if value is None:
        if null_kind is None:
            report.add(path, "null_missing_null_kind", "null value carries no null_kind")
            return
        if null_kind not in sets.null_kinds:
            report.add(
                f"{path}.null_kind",
                "bad_null_kind",
                f"{null_kind!r} is not one of {sorted(sets.null_kinds)}",
            )
            return
        if null_kind == "deferral" and not citation:
            report.add(
                path,
                "deferral_null_without_citation",
                "a deferral null must quote the language that defers",
            )
        if null_kind == "absence" and citation:
            report.add(
                path,
                "absence_null_with_citation",
                "an absence null has nothing to quote; citation should be null",
                severity="warn",
            )
    elif null_kind is not None:
        report.add(path, "null_kind_on_non_null", f"value is not null but null_kind is {null_kind!r}")


def _check_maturity(report: Report, path: str, value: Any, sets: SchemaSets) -> None:
    if not isinstance(value, dict):
        report.add(path, "malformed_field", "expected {value, basis}")
        return
    basis = value.get("basis")
    inner = value.get("value")
    if basis not in sets.maturity_basis:
        report.add(f"{path}.basis", "enum_not_in_schema", f"{basis!r} is not one of {sorted(sets.maturity_basis)}")
        return

    if basis == "stated":
        if not (isinstance(inner, str) and ISO_DATE.match(inner)):
            report.add(f"{path}.value", "malformed_field", f"stated basis wants an ISO-8601 date, found {inner!r}")
        return

    # The check this module was written for.
    if isinstance(inner, str):
        report.add(
            f"{path}.value",
            "relative_maturity_not_structured",
            f"relative basis wants {{tenor_years|tenor_months, anchor}}, found the string {inner!r}",
        )
        return
    if not isinstance(inner, dict):
        report.add(f"{path}.value", "malformed_field", f"relative basis wants an object, found {type(inner).__name__}")
        return
    if "tenor_years" not in inner and "tenor_months" not in inner:
        report.add(f"{path}.value", "malformed_field", "relative value has neither tenor_years nor tenor_months")
    if not inner.get("anchor"):
        report.add(f"{path}.value", "malformed_field", "relative value has no anchor")


def _check_commitment(report: Report, path: str, value: Any) -> None:
    if not isinstance(value, dict):
        report.add(path, "malformed_field", "expected {amount, currency}")
        return
    amount = value.get("amount")
    currency = value.get("currency")
    if not isinstance(amount, int) or isinstance(amount, bool):
        report.add(
            f"{path}.amount",
            "malformed_field",
            f"expected whole currency units as an integer, found {amount!r}",
        )
    if not (isinstance(currency, str) and CURRENCY_CODE.match(currency)):
        report.add(f"{path}.currency", "malformed_field", f"expected an ISO 4217 code, found {currency!r}")


def _check_springing(
    report: Report, path: str, value: Any, sets: SchemaSets, document: str | None
) -> None:
    if not isinstance(value, dict):
        report.add(path, "malformed_field", "expected an object or null")
        return
    condition = value.get("condition_type")
    unit = value.get("threshold_unit")
    if condition not in sets.condition_type:
        report.add(
            f"{path}.condition_type",
            "enum_not_in_schema",
            f"{condition!r} is not one of {sorted(sets.condition_type)}",
        )
    if unit not in sets.threshold_unit:
        report.add(
            f"{path}.threshold_unit",
            "enum_not_in_schema",
            f"{unit!r} is not one of {sorted(sets.threshold_unit)}",
        )
    if not isinstance(value.get("threshold"), (int, float)) or isinstance(value.get("threshold"), bool):
        report.add(f"{path}.threshold", "malformed_field", f"expected a number, found {value.get('threshold')!r}")
    # springing_trigger carries a quote inside the value, in addition to the
    # field's citation. It is the sentence that establishes the trigger, so it
    # gets the same verbatim check as any other quote — the deferral-null gap
    # fixed in 2e03159 was this same shape, a quote the walk never reached.
    quote = value.get("quote")
    if not quote:
        report.add(f"{path}.quote", "missing_citation_field", "springing_trigger carries its own quote")
    elif isinstance(quote, str) and document is not None:
        _check_citation(report, path, {"section": "n/a", "quote": quote}, document)


def _check_effective_from(report: Report, path: str, value: Any, sets: SchemaSets) -> Any:
    """`effective_from` mirrors `maturity_date`: {value, basis}, both bases.

    Returns a sort key where the step is comparable to its neighbours, else
    None. The two bases share the value set defined in the maturity_date
    section of schema.md, which is what `sets.maturity_basis` holds.
    """
    if isinstance(value, str):
        report.add(
            path,
            "effective_from_not_structured",
            f"expected {{value, basis}} as in maturity_date, found the bare value {value!r}",
        )
        return None
    if not isinstance(value, dict) or "basis" not in value:
        report.add(path, "malformed_field", "expected {value, basis}")
        return None

    basis, inner = value.get("basis"), value.get("value")
    if basis not in sets.maturity_basis:
        report.add(
            f"{path}.basis", "enum_not_in_schema", f"{basis!r} is not one of {sorted(sets.maturity_basis)}"
        )
        return None

    if basis == "stated":
        if not (isinstance(inner, str) and ISO_DATE.match(inner)):
            report.add(
                f"{path}.value", "malformed_field", f"stated basis wants an ISO-8601 date, found {inner!r}"
            )
            return None
        return ("stated", inner)

    if not isinstance(inner, dict):
        report.add(
            f"{path}.value",
            "malformed_field",
            f"relative basis wants {{quarters_after|months_after, anchor}}, found {inner!r}",
        )
        return None
    periods = inner.get("quarters_after", inner.get("months_after"))
    if not isinstance(periods, int) or isinstance(periods, bool):
        report.add(
            f"{path}.value",
            "malformed_field",
            "relative value needs an integer quarters_after or months_after",
        )
        return None
    if not inner.get("anchor"):
        report.add(f"{path}.value", "malformed_field", "relative value has no anchor")
        return None
    unit = "quarters_after" if "quarters_after" in inner else "months_after"
    return ("relative", inner["anchor"], unit, periods)


def _check_step_downs(report: Report, path: str, value: Any, sets: SchemaSets) -> None:
    if not isinstance(value, list):
        report.add(path, "malformed_field", f"expected an array, found {type(value).__name__}")
        return
    keys: list[Any] = []
    for i, step in enumerate(value):
        if not isinstance(step, dict):
            report.add(f"{path}[{i}]", "malformed_field", "expected {effective_from, threshold}")
            continue
        keys.append(_check_effective_from(report, f"{path}[{i}].effective_from", step.get("effective_from"), sets))
        if not isinstance(step.get("threshold"), (int, float)) or isinstance(step.get("threshold"), bool):
            report.add(f"{path}[{i}].threshold", "malformed_field", f"expected a number, found {step.get('threshold')!r}")

    # Ordering is only meaningful between steps expressed the same way. Mixed
    # bases, or relative steps off different anchors, are not comparable — and
    # a corpus that produces one is telling you something the schema should
    # answer before a checker pretends to.
    comparable = [k for k in keys if k is not None]
    if len(comparable) == len(keys) and len(comparable) > 1:
        kinds = {k[:2] if k[0] == "relative" else k[:1] for k in comparable}
        if len(kinds) == 1 and comparable != sorted(comparable):
            report.add(path, "step_downs_out_of_order", "schema.md orders the array by effective_from")


def _check_field(
    report: Report, path: str, name: str, entry: Any, document: str | None, sets: SchemaSets
) -> None:
    if not isinstance(entry, dict) or "value" not in entry:
        report.add(path, "malformed_field", "expected {value, citation}")
        return

    value = entry["value"]
    citation = entry.get("citation")
    _check_null_kind(report, path, entry, value, sets)

    if value is None:
        # A deferral null's citation is the whole reason the null is
        # falsifiable — schema.md requires it to quote the deferring sentence
        # precisely so the existing citation check can tell a system that read
        # the clause from one that declined out of vagueness. Checking only
        # that the citation exists would leave the project's most important
        # field class as the one place a quote is never verified.
        if citation:
            _check_citation(report, f"{path}.citation", citation, document)
        return

    # schema.md: every scored field carries a citation. An empty step-down
    # array is the one place a labeler may reasonably have nothing to quote —
    # it records a confirmed absence of steps — so that is a warning.
    if not citation:
        severity = "warn" if (name == "step_down_schedule" and value == []) else "error"
        report.add(path, "missing_citation", "non-null value with no citation", severity=severity)
    else:
        _check_citation(report, f"{path}.citation", citation, document)

    if name in sets.enums:
        if value not in sets.enums[name]:
            report.add(path, "enum_not_in_schema", f"{value!r} is not in the {name} enum")
        elif name == "covenant_type" and value == "other":
            report.add(
                path,
                "covenant_type_other",
                "candidate for a named enum value; debt_to_capitalization is the known gap",
                severity="warn",
            )
    elif name == "maturity_date":
        _check_maturity(report, path, value, sets)
    elif name == "aggregate_commitment":
        _check_commitment(report, path, value)
    elif name == "springing_trigger":
        _check_springing(report, path, value, sets, document)
    elif name == "step_down_schedule":
        _check_step_downs(report, path, value, sets)
    elif name == "has_margin_grid" and not isinstance(value, bool):
        report.add(path, "malformed_field", f"expected a boolean, found {value!r}")
    elif name in ("initial_threshold",) and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        report.add(path, "malformed_field", f"expected a number, found {value!r}")
    elif name == "applicable_margin_bps" and (
        not isinstance(value, int) or isinstance(value, bool)
    ):
        report.add(path, "malformed_field", f"expected an integer in basis points, found {value!r}")


def validate_label(label_path: Path, raw_dir: Path, sets: SchemaSets) -> Report:
    report = Report(label_path)
    try:
        label = json.loads(label_path.read_text())
    except json.JSONDecodeError as exc:
        report.add(label_path.name, "invalid_json", str(exc))
        return report

    source = label.get("source") or {}
    accession = source.get("accession_number")
    document: str | None = None
    if not accession:
        report.add("source.accession_number", "missing_field", "no accession number; quotes cannot be checked")
    else:
        raw = find_raw(accession, raw_dir)
        if raw is None:
            report.add(
                "source",
                "raw_document_unavailable",
                f"no file matching {accession}_* in {raw_dir}; quotes not checked",
                severity="info",
            )
        else:
            report.raw_path = raw
            document = normalize_for_quote_check(to_text(raw.read_bytes()))

    facilities = label.get("facilities")
    if not isinstance(facilities, list) or not facilities:
        report.add("facilities", "missing_field", "expected a non-empty array of facilities")
        facilities = []
    for i, facility in enumerate(facilities):
        for name in sets.facility_fields:
            path = f"facilities[{i}].{name}"
            if name not in facility:
                report.add(path, "missing_field", "scored field absent from the record")
                continue
            _check_field(report, path, name, facility[name], document, sets)

    # An empty covenant list is a real answer for a cov-lite agreement, so its
    # absence is a hole and its emptiness is not.
    covenants = label.get("financial_covenants")
    if covenants is None:
        report.add("financial_covenants", "missing_field", "expected an array, possibly empty")
        covenants = []
    for i, covenant in enumerate(covenants):
        for name in sets.covenant_fields:
            path = f"financial_covenants[{i}].{name}"
            if name not in covenant:
                report.add(path, "missing_field", "scored field absent from the record")
                continue
            _check_field(report, path, name, covenant[name], document, sets)

    return report


def run_validate(paths: list[Path], raw_dir: Path, schema_path: Path = SCHEMA_PATH) -> dict[str, Any]:
    sets = load_schema_sets(schema_path)

    label_files: list[Path] = []
    for path in paths:
        if path.is_dir():
            label_files.extend(sorted(path.glob("*.json")))
        else:
            label_files.append(path)

    summary: dict[str, Any] = {"files": [], "clean": 0, "with_deviations": 0}
    for label_path in label_files:
        report = validate_label(label_path, raw_dir, sets)
        if report.deviations:
            summary["with_deviations"] += 1
        else:
            summary["clean"] += 1

        print(f"\n{label_path}")
        print(
            f"  quotes checked: {report.quotes_checked}"
            + (f"  against {report.raw_path.name}" if report.raw_path else "  (no raw document)")
        )
        if not report.deviations:
            print("  no deviations")
        for deviation in report.deviations:
            print(deviation.line())

        summary["files"].append(
            {
                "path": str(label_path),
                "quotes_checked": report.quotes_checked,
                "errors": report.errors,
                "deviations": [
                    {"path": d.path, "code": d.code, "detail": d.detail, "severity": d.severity}
                    for d in report.deviations
                ],
            }
        )

    summary["total_deviations"] = sum(len(f["deviations"]) for f in summary["files"])
    summary["total_errors"] = sum(f["errors"] for f in summary["files"])
    return summary
