"""Generate the extraction prompt and the output schema from schema.md.

The labeler worked from the rulebook, so the model gets the same rulebook —
with one difference, and it is the point of this module. schema.md's rules
are interleaved with worked examples drawn from the corpus: a commitment
amount, a covenant level, a trigger, named by borrower, and some quoted from
a filing without naming it. Reproduced in a prompt, they would hand the model
the gold value for any field an example covers, on any document it
recognizes, and the score would measure recognition.

So the prompt keeps the rules and loses the examples. From schema.md's
model-facing sections it drops every blockquote (narrative asides, not rules),
and every sentence that names a corpus or dev-set document, carries a corpus
accession number, speaks about the corpus itself, or quotes a passage found
verbatim in a corpus filing or a gold citation. Then it checks the result for
all of those again and refuses to write a prompt that fails. The asymmetry —
the labeler saw the examples, the model does not — is stated with the results.

The output schema is built from the same enum sets the validator reads, so a
value the prompt describes and a value the schema admits cannot drift apart.

Generation reads the corpus filings and gold labels to check for leaks. It
prints counts, never their text.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from .screen import to_text
from .validate import GUARDED_SETS, SCHEMA_PATH, SchemaParseError, load_schema_sets, normalize_for_quote_check

ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "prompts"
SYSTEM_PROMPT_PATH = PROMPT_DIR / "extraction_system.md"
OUTPUT_SCHEMA_PATH = PROMPT_DIR / "output_schema.json"

# The sections of schema.md a reader extracting one agreement needs. Corpus
# selection, record alignment, the labeling budget and annotator agreement
# are about building and scoring the set, not about reading a document.
MODEL_SECTIONS = (
    "The four corners rule",
    "Record shape",
    "Field summary",
    "Facility fields",
    "Covenant fields",
    "Citations",
    "Normalization applied before comparison",
    "Out of scope",
)
# "Worked example" is left out: its numbers coincide with gold values, so the
# leak check would drop its code and leave an empty heading, and the output
# schema the model is given already shows the record's shape.

# How each corpus and dev-set document is named in prose, by accession. Every
# corpus.md row must have an entry, which load_names() checks, so a document
# cannot be missed by being added without aliases.
CORPUS_ALIASES: dict[str, tuple[str, ...]] = {
    "0001213900-21-034493": ("Paya",),
    "0001104659-21-109833": ("Plains",),
    "0001158449-21-000208": ("Advance Auto",),
    "0001760965-21-000058": ("Kontoor",),
    "0000950157-24-001363": ("Amentum", "SpinCo"),
    "0000950170-23-029645": ("Extreme",),
    "0001679273-24-000026": ("Lamb Weston", "Lamb-Weston"),
    "0001104659-21-089858": ("Hertz",),
    "0001193125-25-187776": ("MP Materials",),
    "0001193125-24-150397": ("Peloton",),
    "0000950103-24-012144": ("ANI",),
    "0001558370-24-008935": ("G-III",),
    "0001193125-22-199694": ("Roper",),
    "0000012927-24-000037": ("Boeing",),
    "0001193125-22-246779": ("Mattel",),
    "0001830033-23-000021": ("PureCycle",),
}
DEV_ALIASES = ("Lithia", "Avaya", "AgWest")

# Sentences about the corpus rather than about reading a document: how often a
# value occurs, which values have fired. A prior about the test set is not a
# rule, and it is the one kind of leak a name check cannot see.
CORPUS_TALK = re.compile(r"\bcorpus\b|\bfir(?:e|es|ed|ing)\b", re.I)

# A quotation this long, found verbatim in a corpus filing or inside a gold
# citation, is that document's language, not an illustration. Shorter quoted
# strings are defined terms every agreement uses — "Revolving Credit
# Facility" — and dropping them would cut rules, not leaks.
MIN_LEAK_QUOTE = 40
QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
ACCESSION = re.compile(r"\b\d{10}-\d{2}-\d{6}\b")

# Abbreviations a sentence must not be split after.
# A bold lead — "**The rule.** Then its example." — ends a sentence too, so
# that a rule stated in bold survives when the example after it is dropped.
SENTENCE_END = re.compile(
    r"(?:(?<=[.!?])|(?<=[.!?]\*\*))(?<!e\.g\.)(?<!i\.e\.)(?<!\bNo\.)(?<!\bvs\.)(?<!U\.S\.)(?<!Inc\.)"
    r"\s+(?=[A-Z\"“*(`\[$\d])"
)

FRAME_BEFORE = """\
You are extracting structured terms from one credit agreement filed with the SEC.

The rules below are the adjudication rules a human labeler applied to build the reference answers \
for this task. They were written for the labeler: where they say "record", "label", "label file" or \
"labeler", read "your output" and "you". Worked examples drawn from particular agreements have been \
removed; the rules stand on their own.

Your output is one JSON object in the schema you are given. It has the record shape described below, \
with two differences from a label file: it has no `null_kind` — you are never asked to classify a \
null — and no `facility_name`. Where a rule sends a fact to free text, put it in `notes`.

Every non-null value carries a citation: the section it comes from, and a quote copied verbatim from \
the agreement — the exact characters of a sentence or clause that supports the value. A null that the \
agreement itself defers to a document or fact outside it carries a citation quoting the deferring \
language. A null meaning the thing does not exist carries no citation.

# The rules
"""

FRAME_AFTER = """\

# Your task

Read the whole agreement that follows. Return the one JSON object for it: every facility and every \
financial covenant the rules call for, each field decided by its rule, each value with its citation.
"""


@dataclass
class Report:
    sections: int = 0
    dropped_blockquotes: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    allowed_illustrations: list[str] = field(default_factory=list)

    def drop(self, reason: str) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + 1


# --- What counts as a leak ------------------------------------------------------------


@dataclass(frozen=True)
class LeakSources:
    names: re.Pattern[str]
    accessions: frozenset[str]
    filings: tuple[str, ...]  # normalized corpus filing text
    gold_quotes: tuple[str, ...]  # normalized gold citation quotes
    gold_literals: frozenset[str]  # every number and date the gold records, canonical


# A sentence carrying a number or date equal to some gold value is dropped
# unless it is reviewed here, word for word, as a format illustration or a
# rule constant — a number that belongs to the rule, not to any document.
# Keyed by the exact sentence, so allowing one sentence cannot let the same
# number through anywhere else, and a reworded sentence falls out and is
# dropped. Reviewed 2026-09-30. What was not allowed, and why, is in HANDOFF.
_RULE_CONSTANT = "a threshold that belongs to the rule itself, not a value of any document"
_FORMAT = "shows a normalization with a round number and names no document"
ALLOWED_ILLUSTRATIONS: dict[str, str] = {
    "**Where it lives:** the definitions in Article I (\"Revolving Credit Facility\", \"Term A Loans\", "
    "\"Initial Term Loans\"); the commitment section, usually §2.01; the cover page; the commitment schedule; "
    "and the amortization schedule (a 1%/yr amortizing institutional tranche is a TLB; a 5–10%/yr amortizing "
    "pro rata tranche is a TLA).": _RULE_CONSTANT,
    "Where it says only \"Term Loans\" with no letter, classify by amortization: ≤1%/yr → `term_loan_b`, more "
    "→ `term_loan_a`.": _RULE_CONSTANT,
    "**A bullet is 0%/yr, so an unlettered bullet term loan is `term_loan_b`.**": _RULE_CONSTANT,
    "A tranche repayable in full at maturity with no scheduled installments satisfies ≤1%/yr and needs no "
    "separate rule; this is stated only because the amortization test reads as though it assumes some "
    "amortization exists, and a labeler meeting a bullet should not have to re-derive it.": _RULE_CONSTANT,
    "$500,000,000 is `500000000`.": _FORMAT,
    "Where the agreement expresses the margin as a percentage (2.25%), convert to bps (225).": _FORMAT,
    "Ratios to two decimals (`4.00`); dollar thresholds as integers in whole currency units.": _FORMAT,
    "Where the agreement expresses the ratio as \"4.00:1.00\" or \"4.00 to 1.00\", normalize to `4.00`.": _FORMAT,
    "35 percent of commitments and $35 are different triggers, and the any-drawn rule below records `0` in "
    "`currency` precisely so that the unit carries meaning.": _FORMAT,
    "The typical trigger is revolver utilization above a threshold (commonly 35% or 40% of commitments) "
    "measured on the last day of a fiscal quarter.": "a market-standard range, named as typical, not as any document's",
    "Record the percentage as a number: 35% → `35`, unit `percent`.": _FORMAT,
}

MONTHS = ("January February March April May June July August September October November December").split()
MONEY = re.compile(r"(?:US\$|\$|€|£)\s?(\d[\d,]*(?:\.\d+)?)")
PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
DECIMAL = re.compile(r"(?<![\w.§])(?<!Section )(?<!§ )(\d+\.\d+)(?![\w.]|\(\w)")
BIG_INT = re.compile(r"(?<![\w.,$])(\d{5,})(?![\w.,])")
ISO_DATE = re.compile(r"(?<![\w-])(\d{4}-\d{2}(?:-\d{2})?)(?![\w-])")
WRITTEN_DATE = re.compile(r"\b(" + "|".join(MONTHS) + r") (\d{1,2}), (\d{4})\b")


def _canonical_number(x: Any) -> str:
    d = Decimal(str(x).replace(",", ""))
    return format(d.normalize(), "f") if d != 0 else "0"


def literals(text: str) -> set[str]:
    """Every dollar amount, percentage (and its basis points), decimal that is
    not a section number, long integer, and date in a piece of text."""
    found: set[str] = set()
    for m in MONEY.finditer(text):
        found.add(_canonical_number(m.group(1)))
    for m in PERCENT.finditer(text):
        found.add(_canonical_number(m.group(1)))
        found.add(_canonical_number(Decimal(m.group(1)) * 100))
    for m in DECIMAL.finditer(text):
        found.add(_canonical_number(m.group(1)))
    for m in BIG_INT.finditer(text):
        found.add(_canonical_number(m.group(1)))
    dates = [m.group(1) for m in ISO_DATE.finditer(text)]
    dates += [f"{m.group(3)}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}" for m in WRITTEN_DATE.finditer(text)]
    for date in dates:
        found.add(date)
        # A day inside a month the gold records at month precision is that
        # gold value resolved: it names the same period of the same document.
        found.add(date[:7])
    return found


def _gold_literals(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, bool) or value is None:
        return out
    if isinstance(value, (int, float)):
        out.add(_canonical_number(value))
    elif isinstance(value, str):
        if ISO_DATE.fullmatch(value):
            out.add(value)
    elif isinstance(value, dict):
        for v in value.values():
            out |= _gold_literals(v)
    elif isinstance(value, list):
        for v in value:
            out |= _gold_literals(v)
    return out


def load_names(corpus_md: Path = ROOT / "corpus.md") -> dict[str, str]:
    """Corpus accessions and borrowers, read from corpus.md's selection table,
    and checked against the alias table above."""
    rows = re.findall(r"^\| \d+ \| ([^|]+) \| `(\d{10}-\d{2}-\d{6})`", corpus_md.read_text(), re.M)
    if not rows:
        raise SchemaParseError("corpus.md: the selection table parsed to no rows")
    corpus = {acc: name.strip() for name, acc in rows}
    missing = sorted(set(corpus) - set(CORPUS_ALIASES))
    extra = sorted(set(CORPUS_ALIASES) - set(corpus))
    if missing or extra:
        raise SchemaParseError(f"prompt.py's alias table is out of step with corpus.md: missing {missing}, extra {extra}")
    for acc, aliases in CORPUS_ALIASES.items():
        if aliases[0].replace("-", " ").split()[0] not in corpus[acc].replace("-", " "):
            raise SchemaParseError(f"alias {aliases[0]!r} does not name {corpus[acc]!r}")
    return corpus


def load_leak_sources(root: Path = ROOT) -> LeakSources:
    load_names(root / "corpus.md")
    aliases = [a for names in CORPUS_ALIASES.values() for a in names] + list(DEV_ALIASES)
    names = re.compile(r"\b(?:" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r")\b")
    filings, quotes, numbers = [], [], set()
    for path in sorted((root / "data" / "labels").glob("*.json")):
        label = json.loads(path.read_text())
        source = label["source"]
        raw = root / "data" / "raw" / f"{source['accession_number']}_{source['document_file']}"
        if not raw.exists():
            raise FileNotFoundError(f"{raw}: the leak check needs every corpus filing on disk")
        filings.append(normalize_for_quote_check(to_text(raw.read_bytes())))
        for level in ("facilities", "financial_covenants"):
            for record in label.get(level) or []:
                for entry in record.values():
                    if not isinstance(entry, dict):
                        continue
                    numbers |= _gold_literals(entry.get("value"))
                    for q in (
                        (entry.get("citation") or {}).get("quote"),
                        (entry.get("value") or {}).get("quote") if isinstance(entry.get("value"), dict) else None,
                    ):
                        if isinstance(q, str) and q.strip():
                            quotes.append(normalize_for_quote_check(q))
    return LeakSources(names, frozenset(CORPUS_ALIASES), tuple(filings), tuple(quotes), frozenset(numbers))


def _leaked_quote(text: str, sources: LeakSources) -> bool:
    for m in QUOTED.finditer(text):
        # Case-folded on both sides: a quotation does not stop being the
        # document's language because its first letter changed case.
        q = normalize_for_quote_check((m.group(1) or m.group(2)).strip(" .,;:")).casefold()
        if len(q) < MIN_LEAK_QUOTE:
            continue
        if any(q in filing.casefold() for filing in sources.filings) or any(q in g.casefold() for g in sources.gold_quotes):
            return True
    return False


def taint(text: str, sources: LeakSources) -> str | None:
    """Why a piece of text opens or continues a corpus example. Text that
    taints takes the rest of its paragraph or bullet with it."""
    if sources.names.search(text):
        return "names a corpus or dev-set document"
    if any(acc in text for acc in sources.accessions):
        return "carries a corpus accession"
    if CORPUS_TALK.search(text):
        return "speaks about the corpus"
    if _leaked_quote(text, sources):
        return "quotes a corpus filing or gold citation"
    return None


def gold_value(text: str, sources: LeakSources) -> str | None:
    """A number or date equal to a gold value, in a sentence not reviewed as
    an illustration. Drops only the sentence: the rule around it is not an
    example."""
    if literals(text) & sources.gold_literals and text.strip() not in ALLOWED_ILLUSTRATIONS:
        return "states a value the gold records"
    return None


def offence(text: str, sources: LeakSources) -> str | None:
    return taint(text, sources) or gold_value(text, sources)


# --- Reading schema.md -------------------------------------------------------------------


def _model_sections(schema_text: str) -> list[str]:
    parts = re.split(r"(?m)^(?=## )", schema_text)
    by_heading = {p.splitlines()[0][3:].strip(): p for p in parts if p.startswith("## ")}
    missing = [h for h in MODEL_SECTIONS if h not in by_heading]
    if missing:
        raise SchemaParseError(f"schema.md: no '## ' section headed {missing}")
    return [by_heading[h].rstrip("\n").rstrip("-").rstrip() for h in MODEL_SECTIONS]


@dataclass
class Piece:
    """One paragraph, list item, heading, table row or code block of schema.md."""

    kind: str  # "prose", "bullet", "heading", "row", "code", "quote"
    indent: int
    marker: str  # the list marker for a bullet, "" otherwise
    text: str
    blank_before: bool


BULLET = re.compile(r"^(\s*)(- |\d+\. )")


def _pieces(section: str) -> list[Piece]:
    pieces: list[Piece] = []
    lines = section.splitlines()
    i, blank = 0, False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped:
            blank, i = True, i + 1
            continue
        if stripped.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            pieces.append(Piece("code", indent, "", "\n".join(lines[i:j + 1]), blank))
            i = j + 1
        elif stripped.startswith(">"):
            j = i
            while j < len(lines) and lines[j].strip().startswith(">"):
                j += 1
            pieces.append(Piece("quote", indent, "", "\n".join(lines[i:j]), blank))
            i = j
        elif stripped.startswith("#"):
            pieces.append(Piece("heading", indent, "", line, blank))
            i += 1
        elif stripped.startswith("|"):
            pieces.append(Piece("row", indent, "", line, blank))
            i += 1
        else:
            m = BULLET.match(line)
            kind, marker = ("bullet", m.group(2)) if m else ("prose", "")
            text = [line[m.end():].strip() if m else stripped]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip() or BULLET.match(nxt) or nxt.strip()[:1] in ("#", "|", ">") or nxt.strip().startswith("```"):
                    break
                text.append(nxt.strip())
                j += 1
            pieces.append(Piece(kind, indent, marker, " ".join(text), blank))
            i = j
        blank = False
    return pieces


def _units(pieces: list[Piece]) -> list[list[Piece]]:
    """A bullet and everything indented under it — its continuation paragraphs
    and nested bullets — is one unit. Every other piece is its own unit."""
    units: list[list[Piece]] = []
    for piece in pieces:
        if (units and units[-1][0].kind == "bullet" and piece.kind in ("prose", "bullet", "code")
                and piece.indent > units[-1][0].indent):
            units[-1].append(piece)
        else:
            units.append([piece])
    return units


def _heading_level(piece: Piece) -> int:
    return len(piece.text.lstrip()) - len(piece.text.lstrip().lstrip("#"))


def _render(piece: Piece, text: str) -> str:
    if piece.kind in ("bullet",):
        return " " * piece.indent + piece.marker + text
    if piece.kind == "prose":
        return " " * piece.indent + text
    return text


def generate_rules(schema_text: str, sources: LeakSources, report: Report) -> str:
    """Rules kept, examples dropped — by unit, not by sentence.

    A worked example runs for several sentences and names its document only
    in the first, so dropping just the naming sentence leaves the rest of the
    example, and its gold values, without a name. Once a sentence in a unit
    offends, the rest of that unit goes: the rest of a paragraph, or the rest
    of a bullet with everything indented under it. A heading that offends
    takes its whole subsection. The rule a bullet opens with, stated before
    its example, survives.
    """
    out: list[tuple[Piece, str]] = []
    for section in _model_sections(schema_text):
        report.sections += 1
        skip_below: int | None = None
        for unit in _units(_pieces(section)):
            head = unit[0]
            if head.kind == "heading":
                level = _heading_level(head)
                if skip_below is not None and level > skip_below:
                    report.drop("under a heading that names a document")
                    continue
                skip_below = None
                if offence(head.text, sources):
                    report.drop("heading names a document")
                    skip_below = level
                    continue
                out.append((head, head.text))
                continue
            if skip_below is not None:
                report.drop("under a heading that names a document")
                continue
            if head.kind == "quote":
                report.dropped_blockquotes += 1
                continue
            if head.kind in ("code", "row"):
                reason = offence(head.text, sources)
                if reason:
                    report.drop(f"{head.kind}: {reason}")
                else:
                    out.append((head, head.text))
                continue
            tainted = False
            for piece in unit:
                if tainted:
                    report.drop("rest of a unit after an offending sentence")
                    continue
                if piece.kind == "code":
                    if offence(piece.text, sources):
                        tainted = True
                        report.drop("code in a unit")
                    else:
                        out.append((piece, piece.text))
                    continue
                kept = []
                for sentence in SENTENCE_END.split(piece.text):
                    if reason := taint(sentence, sources):
                        report.drop(reason)
                        tainted = True
                        break
                    if reason := gold_value(sentence, sources):
                        report.drop(reason)
                        continue
                    if sentence.strip() in ALLOWED_ILLUSTRATIONS:
                        report.allowed_illustrations.append(sentence.strip())
                    kept.append(sentence)
                if kept:
                    out.append((piece, " ".join(kept)))
    # A lead-in left introducing a list that was dropped whole.
    lines: list[str] = []
    for i, (piece, text) in enumerate(out):
        nxt = out[i + 1][0] if i + 1 < len(out) else None
        if text.rstrip().endswith(":") and piece.kind == "prose" and (nxt is None or nxt.kind not in ("bullet", "code", "row")):
            report.drop("lead-in to a dropped list")
            continue
        if lines and (piece.blank_before or piece.kind in ("heading", "code")):
            lines.append("")
        lines.append(_render(piece, text))
    return "\n".join(lines) + "\n"


def check_prompt(text: str, sources: LeakSources, report: Report) -> None:
    """The final guard, over the finished prompt: no name, no accession, no
    leaked quote anywhere in it, and no sentence or line stating a gold value
    unless that exact sentence was reviewed. Re-splitting the finished text
    gives back the sentences the filter kept, so an allowed sentence is still
    recognized here."""
    problems = []
    if m := sources.names.search(text):
        problems.append(f"names {m.group(0)!r}")
    if any(acc in text for acc in sources.accessions):
        problems.append("carries a corpus accession")
    if _leaked_quote(text, sources):
        problems.append("quotes a corpus filing or gold citation")
    stated = 0
    for line in text.splitlines():
        body = BULLET.sub("", line).strip()
        parts = [body] if body.startswith("|") else SENTENCE_END.split(body)
        stated += sum(1 for s in parts if gold_value(s, sources))
    if stated:
        problems.append(f"{stated} sentence(s) state a value the gold records and are not reviewed illustrations")
    if problems:
        raise SchemaParseError("generated prompt fails the leak check: " + "; ".join(problems))
    unused = sorted(set(ALLOWED_ILLUSTRATIONS) - set(report.allowed_illustrations))
    if unused:
        raise SchemaParseError(
            f"{len(unused)} reviewed illustration(s) no longer appear in schema.md; remove them from "
            f"ALLOWED_ILLUSTRATIONS so the list says what the prompt contains:\n  " + "\n  ".join(unused)
        )


def generate_system_prompt(schema_path: Path = SCHEMA_PATH, root: Path = ROOT) -> tuple[str, Report]:
    sources = load_leak_sources(root)
    report = Report()
    text = FRAME_BEFORE + "\n" + generate_rules(schema_path.read_text(), sources, report) + FRAME_AFTER
    check_prompt(text, sources, report)
    return text, report


# --- The output schema --------------------------------------------------------------------


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    """Structured outputs require every object closed and every property listed."""
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


CITATION = _obj({"section": {"type": "string"}, "quote": {"type": "string"}})


def _field(value: dict[str, Any], *, nullable: bool) -> dict[str, Any]:
    if nullable:
        return _obj({"value": _nullable(value), "citation": _nullable(CITATION)})
    return _obj({"value": value, "citation": CITATION})


def _relative(period_keys: tuple[str, str]) -> dict[str, Any]:
    return {"anyOf": [_obj({k: {"type": "integer"}, "anchor": {"type": "string"}}) for k in period_keys]}


def build_output_schema(schema_path: Path = SCHEMA_PATH) -> dict[str, Any]:
    sets = load_schema_sets(schema_path)
    enum = lambda name: {"type": "string", "enum": sorted(sets.enums[name])}
    basis = sorted(GUARDED_SETS["maturity_basis"][0])
    if basis != ["relative", "stated"]:
        raise SchemaParseError(f"maturity basis set changed to {basis}; the output schema's branches need updating")

    maturity = {"anyOf": [
        _obj({"basis": {"type": "string", "const": "stated"}, "value": {"type": "string", "format": "date"}}),
        _obj({"basis": {"type": "string", "const": "relative"}, "value": _relative(("tenor_years", "tenor_months"))}),
    ]}
    effective_from = {"anyOf": [
        # YYYY-MM-DD or YYYY-MM; the API cannot enforce a pattern, so it is checked after the response.
        _obj({"basis": {"type": "string", "const": "stated"}, "value": {"type": "string"}}),
        _obj({"basis": {"type": "string", "const": "relative"}, "value": _relative(("quarters_after", "months_after"))}),
    ]}
    trigger = _obj({
        "condition_type": {"type": "string", "enum": sorted(sets.condition_type)},
        "threshold": {"type": "number"},
        "threshold_unit": {"type": "string", "enum": sorted(sets.threshold_unit)},
        "quote": {"type": "string"},
    })
    facility = _obj({
        "facility_type": _field(enum("facility_type"), nullable=False),
        "aggregate_commitment": _field(
            _obj({"amount": {"type": "integer"}, "currency": {"type": "string"}}), nullable=True),
        "maturity_date": _field(maturity, nullable=False),
        "interest_rate_benchmark": _field(enum("interest_rate_benchmark"), nullable=False),
        "applicable_margin_bps": _field({"type": "number"}, nullable=True),
        "has_margin_grid": _field({"type": "boolean"}, nullable=False),
    })
    covenant = _obj({
        "covenant_type": _field(enum("covenant_type"), nullable=False),
        "initial_threshold": _field({"type": "number"}, nullable=False),
        "step_down_schedule": _field(
            {"type": "array", "items": _obj({"effective_from": effective_from, "threshold": {"type": "number"}})},
            nullable=True),
        "testing_frequency": _field(enum("testing_frequency"), nullable=False),
        "springing_trigger": _field(trigger, nullable=True),
    })
    # The field lists must be schema.md's, in its order.
    for level, fields, obj in (("facility", sets.facility_fields, facility), ("covenant", sets.covenant_fields, covenant)):
        if tuple(obj["properties"]) != tuple(fields):
            raise SchemaParseError(f"output schema {level} fields {list(obj['properties'])} differ from schema.md's {list(fields)}")
    return _obj({
        "facilities": {"type": "array", "items": facility},
        "financial_covenants": {"type": "array", "items": covenant},
        "notes": {"type": "array", "items": {"type": "string"}},
    })


# --- Files ---------------------------------------------------------------------------------


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def render_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2) + "\n"


def run_prompt(write: bool, schema_path: Path = SCHEMA_PATH) -> str:
    """Generate both files. With write, replace the committed copies; without,
    report whether the committed copies are what schema.md generates now."""
    prompt, report = generate_system_prompt(schema_path)
    schema = render_schema(build_output_schema(schema_path))
    lines = [
        f"sections: {report.sections}; blockquotes dropped: {report.dropped_blockquotes}",
        "sentences and rows dropped: "
        + (", ".join(f"{n} {why}" for why, n in sorted(report.dropped.items())) or "none"),
        f"sentences stating a gold-equal number kept as reviewed illustrations: {len(report.allowed_illustrations)}",
        f"prompt {len(prompt):,} characters, sha256 {sha256(prompt)[:16]}; schema sha256 {sha256(schema)[:16]}",
    ]
    if write:
        PROMPT_DIR.mkdir(exist_ok=True)
        SYSTEM_PROMPT_PATH.write_text(prompt)
        OUTPUT_SCHEMA_PATH.write_text(schema)
        lines.append(f"wrote {SYSTEM_PROMPT_PATH.relative_to(ROOT)} and {OUTPUT_SCHEMA_PATH.relative_to(ROOT)}")
    else:
        same = (SYSTEM_PROMPT_PATH.exists() and SYSTEM_PROMPT_PATH.read_text() == prompt
                and OUTPUT_SCHEMA_PATH.exists() and OUTPUT_SCHEMA_PATH.read_text() == schema)
        lines.append("committed prompt and schema match schema.md" if same
                     else "committed prompt or schema DIFFERS from what schema.md generates")
    return "\n".join(lines)
