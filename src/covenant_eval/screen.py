"""Stage 2: the document screen.

Stage 1 filters on search metadata. The filters that actually decide whether a
document is a credit agreement need the text: an amendment and a full
agreement are indistinguishable from their EDGAR metadata, and the decisive
test is structural — a real agreement has an Article I definitions section and
a Section 2.01 commitment section, and an amendment has neither.

This stage downloads candidates, applies those tests, and extracts cheap
signals (detected tranches, benchmark, covenant mentions, commitment amounts)
used to stratify the final selection. It does not pick the corpus. It produces
a ranked shortlist; the final 15 are chosen by hand and recorded in corpus.md,
because stratification requires judgment the regexes do not have.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
from typing import Any

from .edgar import EdgarClient

# A credit agreement in this size band runs 150-300 pages. 15,000 words is
# roughly 30 pages and sits well below any real agreement, so it excludes
# term sheets, notes, and amendment stubs without excluding short agreements.
MIN_WORDS = 15_000

# Structural tests are done by counting, not by matching section headings.
# Agreements number themselves inconsistently — some use "ARTICLE I
# DEFINITIONS", some use a bare "SECTION 1.", and tables of contents are full
# of entity noise — so heading regexes produce false negatives on documents
# that are plainly credit agreements. Counts of the vocabulary a credit
# agreement cannot avoid using are stable across all of those layouts.
MIN_DEFINITIONS = 100  # definitional density, either drafting style
MIN_COMMITMENT = 20
MIN_AGENT = 25

DEFINITIONS_HEADING = re.compile(r"DEFINITIONS|DEFINED\s+TERMS", re.I)

# Agreements define terms in one of two styles and both are common:
#   "Applicable Margin" means the rate per annum ...
#   "Applicable Margin": the rate per annum ...
# Counting only the first silently rejects every agreement drafted in the
# second, which is what happened to a $1.365B Bunge revolver.
MEANS = re.compile(r"\bmeans\b|\bshall\s+mean\b", re.I)
COLON_DEFINITION = re.compile(r"[\"“]\s*[A-Z][^\"”\n]{1,60}\s*[\"”]\s*:")

COMMITMENT_WORD = re.compile(r"\bCommitments?\b", re.I)

# "Administrative Agent" is the US syndicated convention, but ABL facilities
# often define a bare "Agent", and LMA-style deals use "Facility Agent". The
# test is whether the deal is agented at all — that is what separates a
# syndicated facility from a bilateral loan — so count the general term and
# keep the specific ones as signals.
ADMIN_AGENT = re.compile(r"Administrative\s+Agent", re.I)
ANY_AGENT = re.compile(r"\bAgent\b")

# The document must say it is a credit facility. Without this, anything long
# and heavily defined passes — a servicing agreement for a credit fund cleared
# every other test.
AGREEMENT_TITLE = re.compile(
    r"\b(?:CREDIT|LOAN|FACILIT(?:Y|IES)|FINANCING)\s+AGREEMENT\b", re.I
)

ORDINALS = (
    r"FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH"
)
# An amendment names itself in its title. Note this deliberately does NOT
# exempt "amended and restated": "Amendment No. 1 to Fifth Amended and
# Restated Loan Agreement" is an amendment, and the earlier version of this
# check let it through because the A&R exemption fired first.
AMENDMENT_TITLE = re.compile(
    rf"\bAMENDMENT\s+(?:NO\.?|NUMBER|\d)|\b(?:{ORDINALS})\s+AMENDMENT\b|"
    rf"\bAMENDMENT\s+(?:AND\s+\w+\s+)?TO\b|\bWAIVER\s+(?:AND|TO)\b",
    re.I,
)

# Distinct lender signatures. Syndicated deals sign "as a Lender"; a bilateral
# facility will not clear three.
LENDER_SIGNATURE = re.compile(r"\bas\s+a\s+Lender\b", re.I)

BENCHMARKS = {
    "term_sofr": re.compile(r"Term\s+SOFR", re.I),
    "daily_simple_sofr": re.compile(r"Daily\s+Simple\s+SOFR", re.I),
    # Catches agreements that reference SOFR only through a defined
    # "Adjusted SOFR" or "Benchmark" and never say "Term SOFR" — without it a
    # 2023 agreement can come back with no benchmark at all.
    "sofr_other": re.compile(r"\bSOFR\b", re.I),
    "libor": re.compile(r"\bLIBOR\b|London\s+Interbank", re.I),
    "euribor": re.compile(r"\bEURIBOR\b", re.I),
    "hibor": re.compile(r"\bHIBOR\b", re.I),
    "prime_or_base": re.compile(r"\bPrime\s+Rate\b|\bBase\s+Rate\b", re.I),
}

TRANCHES = {
    "revolver": re.compile(r"Revolving\s+(?:Credit\s+)?(?:Facilit|Commitment|Loan)", re.I),
    "term_loan": re.compile(r"\bTerm\s+Loans?\b", re.I),
    # Only an explicit letter is evidence of the tranche letter. "Initial Term
    # Loans" appears in both pro rata and institutional deals, so it is not
    # treated as a TLB tell — schema.md classifies by amortization, which is
    # a labeling decision, not a screening one.
    "term_loan_a": re.compile(r"Term\s+A\s+Loan|Term\s+Loan\s+A\b|Tranche\s+A\s+Term", re.I),
    "term_loan_b": re.compile(r"Term\s+B\s+Loan|Term\s+Loan\s+B\b|Tranche\s+B\s+Term", re.I),
    "delayed_draw": re.compile(r"Delayed\s+Draw", re.I),
}

COVENANTS = {
    "leverage": re.compile(r"Leverage\s+Ratio", re.I),
    "interest_coverage": re.compile(r"Interest\s+Coverage\s+Ratio", re.I),
    "fixed_charge": re.compile(r"Fixed\s+Charge\s+Coverage", re.I),
    "first_lien": re.compile(r"First\s+Lien\s+(?:Net\s+)?Leverage", re.I),
}

PRICING_GRID = re.compile(r"Pricing\s+Grid|Applicable\s+Margin[\s\S]{0,600}?Level\s+I", re.I)
SPRINGING = re.compile(
    r"Covenant\s+Trigger|Financial\s+Covenant\s+Test(?:ing)?\s+Period|"
    r"Testing\s+Condition",
    re.I,
)

# Dollar amounts of $100M or more, which is the band the frame cares about.
BIG_DOLLARS = re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3}){2,})(?:\.\d+)?")

TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"[ \t\xa0]+")


def to_text(raw: bytes) -> str:
    """EDGAR exhibits are .htm or .txt. Strip markup crudely but predictably.

    Table structure is lost, which is fine here — the screen asks whether
    certain language is present, not what the numbers in a pricing grid are.
    """
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style)[\s\S]*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|td|th)>", "\n", text)
    text = TAG.sub(" ", text)
    # Decode every entity, not a hand-listed few. Tables of contents are dense
    # with &#160;, and leaving those in place breaks any pattern that spans a
    # heading and its page number.
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = WHITESPACE.sub(" ", text)
    return re.sub(r"\n{3,}", "\n\n", text)


@dataclass
class Screened:
    hit_id: str
    accession: str
    filename: str
    cik: str
    company: str
    filed: str
    form: str
    words: int = 0
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    @property
    def kept(self) -> bool:
        return not self.reasons


def screen_text(text: str) -> tuple[list[str], dict[str, Any]]:
    """Structural tests, then signal extraction. Returns (reasons, signals)."""
    reasons: list[str] = []
    words = len(text.split())

    if words < MIN_WORDS:
        reasons.append("too_short")

    # A credit agreement defines its terms exhaustively; an amendment borrows
    # them from the agreement it amends. Definitional density separates the
    # two regardless of how either is laid out.
    means_count = len(MEANS.findall(text))
    colon_count = len(COLON_DEFINITION.findall(text))
    definition_count = means_count + colon_count
    if definition_count < MIN_DEFINITIONS or not DEFINITIONS_HEADING.search(text):
        reasons.append("no_definitions_section")

    commitment_count = len(COMMITMENT_WORD.findall(text))
    if commitment_count < MIN_COMMITMENT:
        reasons.append("no_commitment_terms")

    # Title-region test only. The body of a genuine agreement discusses
    # amendment constantly — amendment mechanics, the amended definition of
    # EBITDA — so scanning the body is what produced false negatives on real
    # agreements whose table of contents happened to fall inside the window.
    title = text[:2500]
    if AMENDMENT_TITLE.search(title):
        reasons.append("amendment_title")

    if not AGREEMENT_TITLE.search(title):
        reasons.append("not_a_credit_agreement")

    admin_agent_count = len(ADMIN_AGENT.findall(text))
    agent_count = len(ANY_AGENT.findall(text))
    if agent_count < MIN_AGENT:
        reasons.append("not_agented")

    lender_signatures = len(LENDER_SIGNATURE.findall(text))
    if lender_signatures < 3:
        reasons.append("too_few_lender_signatures")

    amounts = sorted(
        {int(m.group(1).replace(",", "")) for m in BIG_DOLLARS.finditer(text)},
        reverse=True,
    )
    largest = amounts[0] if amounts else 0
    # Band from the frame. Applied as a signal, not a hard reject: the largest
    # dollar figure in the document is often a basket or a definition, not the
    # aggregate commitment, so this is too noisy to filter on.
    in_size_band = 150_000_000 <= largest <= 5_000_000_000

    signals = {
        "words": words,
        "definition_count": definition_count,
        "commitment_count": commitment_count,
        "admin_agent_count": admin_agent_count,
        "agent_count": agent_count,
        # US syndicated agreements say "Administrative Agent"; an LMA-style
        # facilities agreement (typically a non-US borrower, outside the
        # frame) says "Facility Agent" or just "Agent". Flagged rather than
        # filtered, because the metadata gives the filer's state, not the
        # borrower's — a Nevada parent can file a Macau facility.
        "us_syndicated_style": admin_agent_count >= 10,
        "lender_signatures": lender_signatures,
        "largest_dollar_amount": largest,
        "in_size_band": in_size_band,
        "benchmarks": [k for k, r in BENCHMARKS.items() if r.search(text)],
        "tranches": [k for k, r in TRANCHES.items() if r.search(text)],
        "covenants": [k for k, r in COVENANTS.items() if r.search(text)],
        "pricing_grid_hint": bool(PRICING_GRID.search(text)),
        "springing_hint": bool(SPRINGING.search(text)),
    }
    return reasons, signals


SOFR_KEYS = {"term_sofr", "daily_simple_sofr", "sofr_other"}


def _benchmark_bucket(benchmarks: list[str]) -> str:
    has_sofr = bool(SOFR_KEYS.intersection(benchmarks))
    has_libor = "libor" in benchmarks
    if has_sofr and has_libor:
        return "both"
    if has_sofr:
        return "sofr"
    if has_libor:
        return "libor"
    return "neither"


def structure_of(signals: dict[str, Any]) -> str:
    """Stratification bucket, from detected tranches.

    Deliberately conservative: where a term loan is present but carries no
    explicit letter, the bucket says so rather than guessing. Guessing here
    would quietly bias the stratification the corpus depends on.
    """
    tranches = set(signals.get("tranches", []))
    revolver = "revolver" in tranches
    term = "term_loan" in tranches

    if term and "term_loan_b" in tranches:
        return "revolver_plus_tlb" if revolver else "tlb_only"
    if term and "term_loan_a" in tranches:
        return "revolver_plus_tla" if revolver else "tla_only"
    if term:
        return "revolver_plus_term_unlettered" if revolver else "term_only"
    if revolver:
        return "revolver_only"
    return "unclassified"


def run_screen(
    candidates_path: Path,
    out_dir: Path,
    limit: int = 400,
    seed: int = 20260904,
    raw_dir: Path | None = None,
) -> dict[str, Any]:
    """Screen a deterministic sample of candidates.

    The sample is shuffled with a fixed seed rather than taken in date order,
    so the shortlist is not front-loaded with one period, and is reproducible
    from a clean checkout.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in candidates_path.read_text().splitlines() if line]
    random.Random(seed).shuffle(rows)
    rows = rows[:limit]

    results: list[Screened] = []
    with EdgarClient() as client:
        for i, row in enumerate(rows, 1):
            item = Screened(
                hit_id=row["hit_id"], accession=row["accession"],
                filename=row["filename"], cik=row["cik"], company=row["company"],
                filed=row["filed"], form=row["form"],
            )
            try:
                raw = client.document(row["cik"], row["accession"], row["filename"])
            except Exception as exc:  # noqa: BLE001 - record and move on
                item.reasons = [f"fetch_failed:{type(exc).__name__}"]
                results.append(item)
                continue

            text = to_text(raw)
            item.reasons, item.signals = screen_text(text)
            item.words = item.signals["words"]
            item.signals["structure"] = structure_of(item.signals)
            results.append(item)

            if item.kept and raw_dir is not None:
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / f"{item.accession}_{item.filename}").write_bytes(raw)

            if i % 25 == 0:
                kept = sum(r.kept for r in results)
                print(f"  screened {i}/{len(rows)}  passing={kept}", flush=True)

    screened_path = out_dir / "screened.jsonl"
    shortlist_path = out_dir / "shortlist.jsonl"
    with screened_path.open("w") as fh, shortlist_path.open("w") as sf:
        for item in results:
            record = asdict(item) | {"kept": item.kept}
            fh.write(json.dumps(record) + "\n")
            if item.kept:
                sf.write(json.dumps(record) + "\n")

    from collections import Counter

    reason_counts: Counter[str] = Counter()
    for item in results:
        for reason in item.reasons:
            reason_counts[reason] += 1

    passing = [r for r in results if r.kept]
    summary = {
        "candidates_available": len(candidates_path.read_text().splitlines()),
        "screened": len(results),
        "sample_seed": seed,
        "passing": len(passing),
        "rejected_by_reason": dict(reason_counts.most_common()),
        "structure_mix": dict(
            Counter(r.signals.get("structure", "unclassified") for r in passing)
        ),
        # Reported as four buckets rather than a winner, because "both" is a
        # real and common state: a 2021-22 agreement carries LIBOR pricing
        # plus SOFR transition language. Which one is the answer for
        # `interest_rate_benchmark` is a labeling decision (schema.md says the
        # benchmark in effect, not its successor), not one to guess here.
        "benchmark_mix": dict(
            Counter(_benchmark_bucket(r.signals.get("benchmarks", [])) for r in passing)
        ),
        "in_size_band": sum(1 for r in passing if r.signals.get("in_size_band")),
        "pricing_grid_hint": sum(1 for r in passing if r.signals.get("pricing_grid_hint")),
        "springing_hint": sum(1 for r in passing if r.signals.get("springing_hint")),
    }
    (out_dir / "screen_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
