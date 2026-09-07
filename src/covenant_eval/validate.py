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

The enum sets below are transcribed from schema.md, which remains the source of
truth. When a value set changes there, it changes here, and the mismatch this
file then reports across already-labeled documents is the re-application work
that the schema change implies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .screen import to_text

# schema.md "Field summary" — the scored fields, by level. A field absent from
# a label file is a hole in the gold record, not a null.
SCORED_FACILITY_FIELDS = (
    "facility_name",
    "facility_type",
    "aggregate_commitment",
    "maturity_date",
    "interest_rate_benchmark",
    "applicable_margin_bps",
    "has_margin_grid",
)
SCORED_COVENANT_FIELDS = (
    "covenant_type",
    "initial_threshold",
    "step_down_schedule",
    "testing_frequency",
    "springing_trigger",
)

# Enum value sets, transcribed from the field sections of schema.md.
ENUMS: dict[str, frozenset[str]] = {
    "facility_type": frozenset(
        {"revolver", "term_loan_a", "term_loan_b", "delayed_draw_term_loan", "bridge", "other"}
    ),
    "interest_rate_benchmark": frozenset(
        {"term_sofr", "daily_simple_sofr", "libor", "euribor", "cdor", "base_rate", "prime", "other"}
    ),
    "covenant_type": frozenset(
        {
            "total_net_leverage",
            "first_lien_net_leverage",
            "secured_net_leverage",
            "total_leverage_gross",
            "interest_coverage",
            "fixed_charge_coverage",
            "debt_service_coverage",
            "minimum_liquidity",
            "capex_limit",
            "other",
        }
    ),
    "testing_frequency": frozenset({"quarterly", "monthly", "semiannual", "annual", "event_driven"}),
}

MATURITY_BASIS = frozenset({"stated", "relative"})
CONDITION_TYPE = frozenset({"revolver_utilization", "minimum_availability", "other"})
THRESHOLD_UNIT = frozenset({"percent", "currency"})
NULL_KINDS = frozenset({"deferral", "absence"})

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


def _check_null_kind(report: Report, path: str, entry: dict[str, Any], value: Any) -> None:
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
        if null_kind not in NULL_KINDS:
            report.add(
                f"{path}.null_kind",
                "bad_null_kind",
                f"{null_kind!r} is not one of {sorted(NULL_KINDS)}",
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


def _check_maturity(report: Report, path: str, value: Any) -> None:
    if not isinstance(value, dict):
        report.add(path, "malformed_field", "expected {value, basis}")
        return
    basis = value.get("basis")
    inner = value.get("value")
    if basis not in MATURITY_BASIS:
        report.add(f"{path}.basis", "enum_not_in_schema", f"{basis!r} is not one of {sorted(MATURITY_BASIS)}")
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


def _check_springing(report: Report, path: str, value: Any) -> None:
    if not isinstance(value, dict):
        report.add(path, "malformed_field", "expected an object or null")
        return
    condition = value.get("condition_type")
    unit = value.get("threshold_unit")
    if condition not in CONDITION_TYPE:
        report.add(
            f"{path}.condition_type",
            "enum_not_in_schema",
            f"{condition!r} is not one of {sorted(CONDITION_TYPE)}",
        )
    if unit not in THRESHOLD_UNIT:
        report.add(
            f"{path}.threshold_unit",
            "enum_not_in_schema",
            f"{unit!r} is not one of {sorted(THRESHOLD_UNIT)}",
        )
    if not isinstance(value.get("threshold"), (int, float)) or isinstance(value.get("threshold"), bool):
        report.add(f"{path}.threshold", "malformed_field", f"expected a number, found {value.get('threshold')!r}")
    if not value.get("quote"):
        report.add(f"{path}.quote", "missing_citation_field", "springing_trigger carries its own quote")


def _check_step_downs(report: Report, path: str, value: Any) -> None:
    if not isinstance(value, list):
        report.add(path, "malformed_field", f"expected an array, found {type(value).__name__}")
        return
    dates: list[str] = []
    for i, step in enumerate(value):
        if not isinstance(step, dict):
            report.add(f"{path}[{i}]", "malformed_field", "expected {effective_from, threshold}")
            continue
        effective = step.get("effective_from")
        if not (isinstance(effective, str) and ISO_DATE.match(effective)):
            report.add(
                f"{path}[{i}].effective_from",
                "malformed_field",
                f"expected an ISO-8601 date, found {effective!r}",
            )
        else:
            dates.append(effective)
        if not isinstance(step.get("threshold"), (int, float)) or isinstance(step.get("threshold"), bool):
            report.add(f"{path}[{i}].threshold", "malformed_field", f"expected a number, found {step.get('threshold')!r}")
    if dates != sorted(dates):
        report.add(path, "step_downs_out_of_order", "schema.md orders the array by effective_from")


def _check_field(
    report: Report, path: str, name: str, entry: Any, document: str | None
) -> None:
    if not isinstance(entry, dict) or "value" not in entry:
        report.add(path, "malformed_field", "expected {value, citation}")
        return

    value = entry["value"]
    citation = entry.get("citation")
    _check_null_kind(report, path, entry, value)

    if value is None:
        return

    # schema.md: every scored field carries a citation. An empty step-down
    # array is the one place a labeler may reasonably have nothing to quote —
    # it records a confirmed absence of steps — so that is a warning.
    if not citation:
        severity = "warn" if (name == "step_down_schedule" and value == []) else "error"
        report.add(path, "missing_citation", "non-null value with no citation", severity=severity)
    else:
        _check_citation(report, f"{path}.citation", citation, document)

    if name in ENUMS:
        if value not in ENUMS[name]:
            report.add(path, "enum_not_in_schema", f"{value!r} is not in the {name} enum")
        elif name == "covenant_type" and value == "other":
            report.add(
                path,
                "covenant_type_other",
                "candidate for a named enum value; debt_to_capitalization is the known gap",
                severity="warn",
            )
    elif name == "maturity_date":
        _check_maturity(report, path, value)
    elif name == "aggregate_commitment":
        _check_commitment(report, path, value)
    elif name == "springing_trigger":
        _check_springing(report, path, value)
    elif name == "step_down_schedule":
        _check_step_downs(report, path, value)
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
    elif name == "facility_name" and not isinstance(value, str):
        report.add(path, "malformed_field", f"expected a string, found {value!r}")


def validate_label(label_path: Path, raw_dir: Path) -> Report:
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
        for name in SCORED_FACILITY_FIELDS:
            path = f"facilities[{i}].{name}"
            if name not in facility:
                report.add(path, "missing_field", "scored field absent from the record")
                continue
            _check_field(report, path, name, facility[name], document)

    # An empty covenant list is a real answer for a cov-lite agreement, so its
    # absence is a hole and its emptiness is not.
    covenants = label.get("financial_covenants")
    if covenants is None:
        report.add("financial_covenants", "missing_field", "expected an array, possibly empty")
        covenants = []
    for i, covenant in enumerate(covenants):
        for name in SCORED_COVENANT_FIELDS:
            path = f"financial_covenants[{i}].{name}"
            if name not in covenant:
                report.add(path, "missing_field", "scored field absent from the record")
                continue
            _check_field(report, path, name, covenant[name], document)

    return report


def run_validate(paths: list[Path], raw_dir: Path) -> dict[str, Any]:
    label_files: list[Path] = []
    for path in paths:
        if path.is_dir():
            label_files.extend(sorted(path.glob("*.json")))
        else:
            label_files.append(path)

    summary: dict[str, Any] = {"files": [], "clean": 0, "with_deviations": 0}
    for label_path in label_files:
        report = validate_label(label_path, raw_dir)
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
