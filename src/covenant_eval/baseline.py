"""The regex baseline: the keyword extractor someone would build instead of a model.

Its specification is HANDOFF's R1, fixed before this code was written, and
this module follows it literally — including where literal is crude, because
a baseline tuned until it looks respectable is not the cheap method anymore.
Where R1 was silent, the gap and the choice are noted at the point they
arise, and listed in HANDOFF's questions.

screen.py's patterns are used unchanged wherever they cover a field: they
have already been measured against corpus documents (labeling-notes.md), and
editing them now would be tuning against known results. The rest is
developed on data/dev/ only, and like the extraction pipeline it refuses a
corpus document until label-freeze exists.

Every citation is the sentence around a match, taken from the document's own
text, so its quotes verify by construction. They are reported, and say
nothing.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .extract import RUNS_DIR, Document, guard, load_documents, sha256
from .screen import BENCHMARKS, COVENANTS, PRICING_GRID, SPRINGING, TRANCHES

WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}
MONTHS = "January February March April May June July August September October November December".split()

MONEY = re.compile(r"(US\$|C\$|Cdn\$|\$|€|£)\s?(\d[\d,]*(?:\.\d+)?)")
CURRENCY = {"US$": "USD", "$": "USD", "C$": "CAD", "Cdn$": "CAD", "€": "EUR", "£": "GBP"}
WRITTEN_DATE = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s+(\d{4})\b")
DEFINITION = r"[\"“]\s*{term}\s*[\"”]\s*(?:means|shall mean|:)"
MATURITY_DEF = re.compile(DEFINITION.format(term=r"[\w\- ]*Maturity Date"))
MARGIN_DEF = re.compile(DEFINITION.format(term=r"Applicable (?:Margin|Rate|Percentage)"))
YEARS_AFTER = re.compile(
    r"\b(\w+)(?:\s*\((\d+)\))?\s+years?\s+(?:after|from|following)\s+the\s+([A-Z][\w\- ]*?Date)\b")
ANNIVERSARY = re.compile(r"\b(\w+(?:st|nd|rd|th))\s+anniversary\s+of\s+the\s+([A-Z][\w\- ]*?Date)\b")
ORDINALS = {w: i for i, w in enumerate(
    "zeroth first second third fourth fifth sixth seventh eighth ninth tenth".split())}
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
RATIO = re.compile(r"(\d+\.\d{1,2})\s*(?:to|:)\s*1(?:\.0{1,2})?\b")
COVENANT_VERB = re.compile(r"shall\s+not\s+permit|shall\s+maintain", re.I)

# Ratio names per covenant record, for finding the covenant sentence.
RATIO_NAME = {
    "first_lien_net_leverage": re.compile(r"First\s+Lien\s+(?:Net\s+)?Leverage\s+Ratio", re.I),
    "total_net_leverage": re.compile(r"Leverage\s+Ratio", re.I),
    "total_leverage_gross": re.compile(r"Leverage\s+Ratio", re.I),
    "interest_coverage": re.compile(r"Interest\s+Coverage\s+Ratio", re.I),
    "fixed_charge_coverage": re.compile(r"Fixed\s+Charge\s+Coverage", re.I),
}


def _sentence(text: str, start: int, end: int, limit: int = 400) -> str:
    """The sentence around a match, cut at `limit` characters on each side."""
    left = max(text.rfind(". ", max(0, start - limit), start), text.rfind("\n", max(0, start - limit), start))
    left = left + 1 if left >= 0 else max(0, start - limit)
    right_candidates = [i for i in (text.find(". ", end, end + limit), text.find("\n", end, end + limit)) if i >= 0]
    right = min(right_candidates) + 1 if right_candidates else min(len(text), end + limit)
    return " ".join(text[left:right].split())


def _cite(section: str, text: str, m: re.Match) -> dict[str, str]:
    return {"section": section, "quote": _sentence(text, m.start(), m.end())}


def _number(s: str) -> float | int:
    v = float(s.replace(",", ""))
    return int(v) if v.is_integer() else v


# --- Facility fields ------------------------------------------------------------------


def _facility_types(text: str) -> list[tuple[str, re.Match]]:
    """R1: one record per tranche keyword screen.py's TRANCHES finds. An
    unlettered term loan is term_loan_b: a keyword tool cannot read
    amortization, and ≤1% is the schema's default."""
    found = []
    if m := TRANCHES["revolver"].search(text):
        found.append(("revolver", m))
    lettered = False
    for key, enum in (("term_loan_a", "term_loan_a"), ("term_loan_b", "term_loan_b")):
        if m := TRANCHES[key].search(text):
            found.append((enum, m))
            lettered = True
    if not lettered and (m := TRANCHES["term_loan"].search(text)):
        found.append(("term_loan_b", m))
    return found


COMMITMENT_PHRASE = {
    "revolver": re.compile(r"aggregate\s+(?:\w+\s+){0,4}?Revolving\s+(?:Credit\s+)?Commitments?", re.I),
    "term_loan_a": re.compile(r"aggregate\s+(?:\w+\s+){0,6}?Term\s+(?:A\s+)?(?:Loan\s+)?Commitments?", re.I),
    "term_loan_b": re.compile(r"aggregate\s+(?:\w+\s+){0,6}?Term\s+(?:B\s+)?(?:Loan\s+)?Commitments?", re.I),
}


def _commitment(text: str, facility_type: str) -> dict[str, Any]:
    """R1: the first dollar amount within 300 characters after an "aggregate …
    Commitments" phrase for that tranche."""
    for m in COMMITMENT_PHRASE[facility_type].finditer(text):
        money = MONEY.search(text, m.end(), m.end() + 300)
        if money:
            value = {"amount": int(_number(money.group(2))), "currency": CURRENCY.get(money.group(1), "USD")}
            return {"value": value, "citation": _cite("commitment", text, money)}
    return {"value": None, "citation": None}


def _maturity(text: str) -> dict[str, Any]:
    """R1: in the first "… Maturity Date" definition, a written calendar date
    is stated; "N years after / Nth anniversary of the X Date" is relative.
    R1 names "Maturity Date": a definition called something else — a
    "Termination Date" — is not looked for."""
    m = MATURITY_DEF.search(text)
    if not m:
        return {"value": None, "citation": None}
    window = text[m.end(): m.end() + 600]
    if d := WRITTEN_DATE.search(window):
        iso = f"{d.group(3)}-{MONTHS.index(d.group(1)) + 1:02d}-{int(d.group(2)):02d}"
        return {"value": {"value": iso, "basis": "stated"}, "citation": _cite("Maturity Date", text, m)}
    if y := YEARS_AFTER.search(window):
        years = int(y.group(2)) if y.group(2) else WORDS.get(y.group(1).lower())
        if years:
            return {"value": {"value": {"tenor_years": years, "anchor": y.group(3)}, "basis": "relative"},
                    "citation": _cite("Maturity Date", text, m)}
    if a := ANNIVERSARY.search(window):
        word = a.group(1).lower()
        years = ORDINALS.get(word) or (int(word[:-2]) if word[:-2].isdigit() else None)
        if years:
            return {"value": {"value": {"tenor_years": years, "anchor": a.group(2)}, "basis": "relative"},
                    "citation": _cite("Maturity Date", text, m)}
    return {"value": None, "citation": None}


def _benchmark(text: str) -> dict[str, Any]:
    """R1: the benchmark keyword with the most occurrences, from screen.py's
    BENCHMARKS. Where R1 was silent: its bare "SOFR" pattern also matches
    inside every "Term SOFR", so it counts only when no named benchmark is
    found; prime and base rate are the alternative, never counted; HIBOR is
    `other`. BENCHMARKS has no CDOR pattern, so the baseline cannot answer
    `cdor` — screen.py is used unchanged."""
    named = {"term_sofr": "term_sofr", "daily_simple_sofr": "daily_simple_sofr", "libor": "libor",
             "euribor": "euribor", "hibor": "other"}
    counts = {key: len(BENCHMARKS[key].findall(text)) for key in named}
    best = max(counts, key=lambda k: (counts[k], -list(named).index(k)))
    if counts[best]:
        m = BENCHMARKS[best].search(text)
        return {"value": named[best], "citation": _cite("benchmark", text, m)}
    if m := BENCHMARKS["sofr_other"].search(text):
        return {"value": "term_sofr", "citation": _cite("benchmark", text, m)}
    return {"value": None, "citation": None}


def _margin(text: str) -> dict[str, Any]:
    """R1: the first percentage in the Applicable Margin / Rate / Percentage
    definition, in basis points."""
    m = MARGIN_DEF.search(text)
    if m and (p := PERCENT.search(text, m.end(), m.end() + 1500)):
        return {"value": _number(f"{float(p.group(1)) * 100:.4f}"), "citation": _cite("Applicable Margin", text, p)}
    return {"value": None, "citation": None}


def _grid(text: str) -> dict[str, Any]:
    """R1: screen.py's PRICING_GRID hint, unchanged."""
    m = PRICING_GRID.search(text)
    if m:
        return {"value": True, "citation": _cite("pricing grid", text, m)}
    m = MARGIN_DEF.search(text)
    return {"value": False, "citation": _cite("Applicable Margin", text, m) if m else None}


# --- Covenant fields ------------------------------------------------------------------


def _covenant_types(text: str) -> list[str]:
    """R1: one record per type screen.py's COVENANTS finds."""
    types = []
    if COVENANTS["first_lien"].search(text):
        types.append("first_lien_net_leverage")
    if COVENANTS["leverage"].search(text):
        types.append("total_net_leverage" if re.search(r"Net\s+Leverage\s+Ratio", text, re.I) else "total_leverage_gross")
    if COVENANTS["interest_coverage"].search(text):
        types.append("interest_coverage")
    if COVENANTS["fixed_charge"].search(text):
        types.append("fixed_charge_coverage")
    return types


def _covenant(text: str, covenant_type: str, trigger: dict[str, Any]) -> dict[str, Any]:
    """R1: the threshold is the first "X.XX to 1.00" within 400 characters
    after the ratio's name, in a "shall not permit / shall maintain"
    sentence; the frequency is quarterly if that sentence says "fiscal
    quarter", else annual; the schedule is always []."""
    record: dict[str, Any] = {"covenant_type": {"value": covenant_type, "citation": None}}
    found = None
    for name in RATIO_NAME[covenant_type].finditer(text):
        sentence = _sentence(text, name.start(), name.end())
        if COVENANT_VERB.search(sentence) and (ratio := RATIO.search(text, name.end(), name.end() + 400)):
            found = (name, ratio, sentence)
            break
    first_name = RATIO_NAME[covenant_type].search(text)
    record["covenant_type"]["citation"] = _cite("covenant", text, first_name) if first_name else None
    if found:
        name, ratio, sentence = found
        record["initial_threshold"] = {"value": _number(ratio.group(1)), "citation": _cite("covenant", text, ratio)}
        quarterly = "fiscal quarter" in sentence.lower()
        record["testing_frequency"] = {"value": "quarterly" if quarterly else "annual",
                                       "citation": {"section": "covenant", "quote": sentence}}
        record["step_down_schedule"] = {"value": [], "citation": {"section": "covenant", "quote": sentence}}
    else:
        record["initial_threshold"] = {"value": None, "citation": None}
        record["testing_frequency"] = {"value": "annual", "citation": None}
        record["step_down_schedule"] = {"value": [], "citation": None}
    record["springing_trigger"] = trigger
    return record


def _trigger(text: str) -> dict[str, Any]:
    """R1: if screen.py's SPRINGING hint fires, the first "N%" near "Revolving"
    in that sentence, as revolver utilization in percent; otherwise null."""
    m = SPRINGING.search(text)
    if not m:
        return {"value": None, "citation": None}
    sentence = _sentence(text, m.start(), m.end())
    if "Revolving" in sentence and (p := PERCENT.search(sentence)):
        value = {"condition_type": "revolver_utilization", "threshold": _number(p.group(1)),
                 "threshold_unit": "percent", "quote": sentence}
        return {"value": value, "citation": {"section": "springing", "quote": sentence}}
    return {"value": None, "citation": None}


# --- The record -------------------------------------------------------------------------


def extract_record(text: str) -> dict[str, Any]:
    benchmark, margin, grid = _benchmark(text), _margin(text), _grid(text)
    facilities = []
    for facility_type, m in _facility_types(text):
        facilities.append({
            "facility_type": {"value": facility_type, "citation": _cite("facility", text, m)},
            "aggregate_commitment": _commitment(text, facility_type),
            "maturity_date": _maturity(text),
            "interest_rate_benchmark": benchmark,
            "applicable_margin_bps": margin,
            "has_margin_grid": grid,
        })
    trigger = _trigger(text)
    covenants = [_covenant(text, t, trigger) for t in _covenant_types(text)]
    return {"facilities": facilities, "financial_covenants": covenants, "notes": []}


def code_sha256() -> str:
    """The baseline is its code: the hash goes in every run's manifest."""
    here = Path(__file__)
    return hashlib.sha256((here.read_bytes() + (here.parent / "screen.py").read_bytes())).hexdigest()


def run_baseline(run_id: str, label_paths: list[Path], runs_dir: Path = RUNS_DIR,
                 raw_dir: Path | None = None) -> str:
    """Write a baseline run in the same shape as a model run, so score-run
    reads both. Refuses corpus documents before label-freeze, like the model."""
    from .extract import RAW_DIR, _git_commit

    docs: list[Document] = load_documents(label_paths, raw_dir or RAW_DIR)
    guard(docs)
    run_dir = runs_dir / run_id
    if run_dir.exists():
        raise FileExistsError(f"{run_dir} exists; a run is never overwritten")
    (run_dir / "predictions").mkdir(parents=True)
    commit, dirty = _git_commit()
    report = {}
    for doc in docs:
        record = extract_record(doc.text)
        prediction = {"source": {"accession_number": doc.accession, "document_file": doc.document_file},
                      **record, "run": run_id}
        (run_dir / "predictions" / f"{doc.custom_id}.json").write_text(json.dumps(prediction, indent=2) + "\n")
        report[doc.custom_id] = {"status": "ok"}
    manifest = {
        "run_id": run_id, "system": "regex baseline", "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": commit, "git_dirty": dirty, "baseline_sha256": code_sha256(),
        "documents": [{"accession": d.accession, "document_file": d.document_file, "custom_id": d.custom_id,
                       "text_sha256": sha256(d.text), "characters": len(d.text)} for d in docs],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (run_dir / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return f"wrote {len(docs)} baseline prediction(s) to {run_dir}"
