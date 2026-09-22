"""What the corpus actually exercises, counted from the label files.

The reporting shape is fixed here, before any model output exists, for the
same reason the corpus was frozen before labeling: a table designed after
seeing the numbers is a table designed around them. Every field lists every
value its enum allows, including the ones nothing produced, so a reader sees
the whole value space rather than the part that happened to fire.

Two columns exist because a per-field accuracy number is unreadable without
them.

**n** is the instance count. A field scored over one or two instances is not
measured, and the count is what lets a reader see that instead of taking an F1
on trust.

**Naive** is the majority-class baseline: what a system scores by always
answering the most common value and reading nothing. On a skewed field that
number is high — always answering `true` on `has_margin_grid` beats four
fifths of the instances — and a result that does not clear it is not a result.
Publishing accuracy without it invites exactly the reading it cannot support.

The counts are generated rather than transcribed. Every hand-copied count in
this project's history has eventually been wrong.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .validate import SCHEMA_PATH, SchemaSets, load_schema_sets

# Values schema.md said, in advance, might never fire. An empty column for one
# of these is a documented outcome; an empty column for anything else is an
# unexercised case. Conflating them would let a gap hide behind a decision.
PRE_REGISTERED_EMPTY: dict[str, str] = {
    "debt_service_coverage": (
        "schema.md, covenant_type: \"will almost certainly never fire in this corpus … "
        "an empty column for it is the expected result, not a labeling gap\""
    ),
    "cdor": (
        "schema.md, interest_rate_benchmark: \"it may never fire; an unused enum value "
        "costs nothing\" — its one candidate, Lithia, was later excluded from the frame"
    ),
    "delayed_draw_term_loan": (
        "schema.md, facility_type: the ANI rule requires the agreement to say so, "
        "\"makes delayed_draw_term_loan harder to fire, and it may not fire at all. "
        "That is the accepted outcome\""
    ),
}


def _load(labels_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted(labels_dir.glob("*.json"))]


def tally(labels: list[dict[str, Any]], sets: SchemaSets) -> dict[str, Any]:
    """Count every scored value, by field, across the gold set."""
    facility: dict[str, Counter] = {f: Counter() for f in sets.facility_fields}
    covenant: dict[str, Counter] = {f: Counter() for f in sets.covenant_fields}
    derived: dict[str, Counter] = {
        "maturity_date.basis": Counter(),
        "aggregate_commitment.currency": Counter(),
        "springing_trigger.condition_type": Counter(),
        "springing_trigger.threshold_unit": Counter(),
        "step_down_schedule.length": Counter(),
    }
    empty_covenant_lists = 0

    for doc in labels:
        if doc.get("financial_covenants") == []:
            empty_covenant_lists += 1
        for fac in doc.get("facilities", []):
            for name in sets.facility_fields:
                entry = fac.get(name)
                if entry is None:
                    continue
                value = entry.get("value")
                if value is None:
                    facility[name]["(null)"] += 1
                elif name == "maturity_date":
                    facility[name]["(non-null)"] += 1
                    derived["maturity_date.basis"][value.get("basis")] += 1
                elif name == "aggregate_commitment":
                    facility[name]["(non-null)"] += 1
                    derived["aggregate_commitment.currency"][value.get("currency")] += 1
                elif isinstance(value, (str, bool)):
                    facility[name][str(value).lower() if isinstance(value, bool) else value] += 1
                else:
                    facility[name]["(non-null)"] += 1
        for cov in doc.get("financial_covenants", []):
            for name in sets.covenant_fields:
                entry = cov.get(name)
                if entry is None:
                    continue
                value = entry.get("value")
                if name == "springing_trigger":
                    if value is None:
                        covenant[name]["(null)"] += 1
                    else:
                        covenant[name]["(non-null)"] += 1
                        derived["springing_trigger.condition_type"][value.get("condition_type")] += 1
                        derived["springing_trigger.threshold_unit"][value.get("threshold_unit")] += 1
                elif name == "step_down_schedule":
                    covenant[name]["[]" if not value else "(non-empty)"] += 1
                    derived["step_down_schedule.length"][len(value)] += 1
                elif isinstance(value, str):
                    covenant[name][value] += 1
                elif value is None:
                    covenant[name]["(null)"] += 1
                else:
                    covenant[name]["(non-null)"] += 1

    return {
        "documents": len(labels),
        "facility_records": sum(len(d.get("facilities", [])) for d in labels),
        "covenant_records": sum(len(d.get("financial_covenants", [])) for d in labels),
        "empty_covenant_lists": empty_covenant_lists,
        "facility": facility,
        "covenant": covenant,
        "derived": derived,
    }


def naive_baseline(counts: Counter) -> tuple[str, int, float]:
    """The majority-class guess: value, its count, and the share it would score."""
    total = sum(counts.values())
    if not total:
        return ("—", 0, 0.0)
    value, hits = counts.most_common(1)[0]
    return (value, hits, hits / total)


def _rows(name: str, counts: Counter, allowed: list[str] | None) -> list[str]:
    total = sum(counts.values())
    value, hits, share = naive_baseline(counts)
    out = [f"\n### `{name}`  ·  n = {total}"]
    if total:
        out.append(f"*Naive baseline: always answer `{value}` → {hits}/{total} = {share:.0%}*\n")
    universe = list(allowed) if allowed else []
    for extra in counts:
        if extra not in universe:
            universe.append(extra)
    out.append("| Value | n | Status |")
    out.append("|---|---:|---|")
    for v in sorted(universe, key=lambda k: (-counts.get(k, 0), str(k))):
        n = counts.get(v, 0)
        if n:
            status = "—"
        elif v in PRE_REGISTERED_EMPTY:
            status = "**pre-registered as possibly never firing**"
        else:
            status = "**not exercised**"
        out.append(f"| `{v}` | {n} | {status} |")
    return out


def render(tallies: dict[str, Any], sets: SchemaSets) -> str:
    enum_for = {
        "facility_type": sorted(sets.enums["facility_type"]),
        "interest_rate_benchmark": sorted(sets.enums["interest_rate_benchmark"]),
        "covenant_type": sorted(sets.enums["covenant_type"]),
        "testing_frequency": sorted(sets.enums["testing_frequency"]),
        "maturity_date.basis": sorted(sets.maturity_basis),
        "springing_trigger.condition_type": sorted(sets.condition_type),
        "springing_trigger.threshold_unit": sorted(sets.threshold_unit),
    }
    lines = [
        f"**{tallies['documents']} documents · {tallies['facility_records']} facility records · "
        f"{tallies['covenant_records']} covenant records · "
        f"{tallies['empty_covenant_lists']} with an empty covenant list**",
        "",
        "## Facility fields",
    ]
    for name, counts in tallies["facility"].items():
        lines += _rows(name, counts, enum_for.get(name))
        if name == "maturity_date":
            lines += _rows("maturity_date.basis", tallies["derived"]["maturity_date.basis"],
                           enum_for["maturity_date.basis"])
        if name == "aggregate_commitment":
            lines += _rows("aggregate_commitment.currency",
                           tallies["derived"]["aggregate_commitment.currency"], None)
    lines.append("\n## Covenant fields")
    for name, counts in tallies["covenant"].items():
        lines += _rows(name, counts, enum_for.get(name))
        if name == "springing_trigger":
            for sub in ("condition_type", "threshold_unit"):
                key = f"springing_trigger.{sub}"
                lines += _rows(key, tallies["derived"][key], enum_for[key])
        if name == "step_down_schedule":
            lines += _rows("step_down_schedule.length (diagnostic)",
                           Counter({f"{k} step(s)": v for k, v in
                                    tallies["derived"]["step_down_schedule.length"].items()}), None)
    return "\n".join(lines) + "\n"


def run_coverage(labels_dir: Path, schema_path: Path = SCHEMA_PATH) -> str:
    sets = load_schema_sets(schema_path)
    return render(tally(_load(labels_dir), sets), sets)
