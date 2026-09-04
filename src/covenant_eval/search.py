"""Stage 1: the corpus census.

Runs the frozen selection query from corpus.md across EDGAR full-text search,
then applies every filter that can be decided from search metadata alone —
which turns out to be most of them, because EDGAR returns SIC codes and 8-K
item numbers with each hit.

Every hit is written out with the reasons it was rejected, not just the
surviving candidates. When the final set skews in some way that wasn't
intended, the rejection log is the only thing that says which filter did it.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from .edgar import EdgarClient

# --- The frozen query (corpus.md). Changing any of this changes the corpus. ---

PHRASES = ["Applicable Margin", "Applicable Rate", "Applicable Percentage"]
FORMS = "8-K,10-Q,10-K"
START_DATE = date(2021, 6, 1)

PAGE_SIZE = 100
# EDGAR full-text search will not page beyond 10,000 results for one query.
# Month-chunking keeps every query far below this; the guard is for safety.
MAX_OFFSET = 9900

# --- Filters ---

EX10 = re.compile(r"^EX-10", re.IGNORECASE)

# An amendment that is not a restatement carries none of the schema's fields:
# it says "Section 6.12(a) is amended by replacing '4.50' with '4.25'".
# A&R agreements restate the whole package inline and are in scope.
AMENDMENT = re.compile(r"amendment|amend(ed)?\s+no|waiver|consent|joinder", re.I)
RESTATED = re.compile(r"amended\s+and\s+restated", re.I)

# Financials (6000-6499), blank check (6770) and REITs (6798) use a different
# covenant taxonomy — unencumbered asset tests, regulatory capital ratios —
# which at 15 documents would mean enum values appearing exactly once.
# This is a limitation, not a design win; see schema.md.
def _excluded_sic(sic: str) -> bool:
    if not sic or not sic.isdigit():
        return False
    code = int(sic)
    return 6000 <= code <= 6499 or code in (6770, 6798)


@dataclass
class Hit:
    """One indexed file from EDGAR full-text search."""

    hit_id: str
    accession: str
    filename: str
    cik: str
    company: str
    form: str
    file_type: str
    description: str
    filed: str
    sics: list[str]
    items: list[str]
    state: str
    phrases: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Hit:
        src = raw["_source"]
        hit_id = raw["_id"]
        accession, _, filename = hit_id.partition(":")
        names = src.get("display_names") or [""]
        return cls(
            hit_id=hit_id,
            accession=src.get("adsh") or accession,
            filename=filename,
            cik=(src.get("ciks") or [""])[0],
            company=names[0],
            form=src.get("form") or "",
            file_type=src.get("file_type") or "",
            description=src.get("file_description") or "",
            filed=src.get("file_date") or "",
            sics=src.get("sics") or [],
            items=src.get("items") or [],
            state=(src.get("biz_states") or [""])[0],
        )

    def screen(self) -> list[str]:
        """All failing filters, not just the first.

        Recording every reason rather than short-circuiting costs nothing and
        makes the overlap between filters visible — e.g. how much of what the
        sector filter removes the amendment filter would have caught anyway.
        """
        reasons: list[str] = []

        if not EX10.match(self.file_type):
            reasons.append("not_ex10")

        # Item 1.01 is "Entry into a Material Definitive Agreement". Only 8-Ks
        # carry item codes; periodic reports are not held to this.
        if self.form == "8-K" and "1.01" not in self.items:
            reasons.append("no_item_101")

        if any(_excluded_sic(s) for s in self.sics):
            reasons.append("excluded_sector")

        # Metadata-only amendment check. Weak on its own, because many exhibit
        # descriptions are just "EX-10.1"; the decisive amendment filter is the
        # document-text screen in stage 2.
        haystack = f"{self.description} {self.filename}"
        if AMENDMENT.search(haystack) and not RESTATED.search(haystack):
            reasons.append("amendment_title")

        return reasons

    def to_json(self) -> dict[str, Any]:
        return {
            "hit_id": self.hit_id,
            "accession": self.accession,
            "filename": self.filename,
            "cik": self.cik,
            "company": self.company,
            "form": self.form,
            "file_type": self.file_type,
            "description": self.description,
            "filed": self.filed,
            "sic": self.sics[0] if self.sics else "",
            "state": self.state,
            "phrases": sorted(self.phrases),
            "reasons": self.reasons,
            "kept": not self.reasons,
        }


def month_windows(start: date, end: date) -> Iterator[tuple[str, str]]:
    """Inclusive month boundaries.

    The census is chunked by month so no single query approaches EDGAR's
    10,000-result ceiling, which the unchunked query does exceed.
    """
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        first = date(y, m, 1)
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        last = min(date(ny, nm, 1).toordinal() - 1, end.toordinal())
        yield first.isoformat(), date.fromordinal(last).isoformat()
        y, m = ny, nm


def run_census(out_dir: Path, end: date | None = None) -> dict[str, Any]:
    end = end or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)

    hits: dict[str, Hit] = {}
    per_phrase_raw = Counter()
    windows = list(month_windows(START_DATE, end))

    with EdgarClient() as client:
        for i, (start_s, end_s) in enumerate(windows, 1):
            for phrase in PHRASES:
                offset = 0
                while True:
                    payload = client.search(phrase, FORMS, start_s, end_s, offset)
                    page = payload["hits"]["hits"]
                    total = payload["hits"]["total"]["value"]
                    for raw in page:
                        hit = hits.get(raw["_id"])
                        if hit is None:
                            hit = Hit.from_raw(raw)
                            hits[hit.hit_id] = hit
                        hit.phrases.add(phrase)
                        per_phrase_raw[phrase] += 1
                    offset += PAGE_SIZE
                    if offset >= min(total, MAX_OFFSET) or not page:
                        break
            print(
                f"  [{i:>2}/{len(windows)}] {start_s[:7]}  "
                f"unique={len(hits):>6}  requests={client.request_count}",
                flush=True,
            )
        requests_made = client.request_count

    for hit in hits.values():
        hit.reasons = hit.screen()

    hits_path = out_dir / "hits.jsonl"
    candidates_path = out_dir / "candidates.jsonl"
    kept = 0
    with hits_path.open("w") as fh, candidates_path.open("w") as cf:
        for hit in sorted(hits.values(), key=lambda h: (h.filed, h.hit_id)):
            record = hit.to_json()
            fh.write(json.dumps(record) + "\n")
            if record["kept"]:
                cf.write(json.dumps(record) + "\n")
                kept += 1

    reason_counts = Counter()
    for hit in hits.values():
        for reason in hit.reasons:
            reason_counts[reason] += 1

    # How much did each phrase actually contribute? "Applicable Percentage"
    # was added on the theory that older and middle-market agreements use it;
    # this is what says whether that was right.
    sole_source = Counter()
    for hit in hits.values():
        if len(hit.phrases) == 1:
            sole_source[next(iter(hit.phrases))] += 1

    funnel = {
        "query": {
            "phrases": PHRASES,
            "forms": FORMS,
            "startdt": START_DATE.isoformat(),
            "enddt": end.isoformat(),
        },
        "run_date": date.today().isoformat(),
        "requests_made": requests_made,
        "months_covered": len(windows),
        "raw_hits_including_duplicates": sum(per_phrase_raw.values()),
        "unique_files": len(hits),
        "hits_per_phrase": dict(per_phrase_raw),
        "unique_files_found_only_by_phrase": dict(sole_source),
        "rejected_by_reason": dict(reason_counts.most_common()),
        "candidates_after_metadata_filters": kept,
    }
    (out_dir / "funnel.json").write_text(json.dumps(funnel, indent=2) + "\n")
    return funnel
