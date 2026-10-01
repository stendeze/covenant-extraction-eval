"""Run the extraction model over documents, through the Message Batches API.

One request per document: the generated rulebook as a cached system prompt,
the whole exhibit as `to_text` renders it — the same text every quote is
verified against — and the output schema as a structured-output format. The
settings are HANDOFF's D3: Claude Opus 5.5 at effort `high`, thinking left at
its default (always on), no fallback model, because a fallback would let a
different model answer.

**No corpus document leaves this machine before `label-freeze`.** Every run
checks each document against `data/labels/`, by accession and file, and
refuses a corpus document unless the `label-freeze` tag exists. Matching on
the file matters: the dev set's Lamb Weston EX-10.2 shares an accession with
corpus row 7 and is not a corpus document.

A run is prepared before it is sent, and nothing is sent without `--submit`.
Its directory, `runs/<run-id>/`, holds a manifest — model, settings, prompt
and schema hashes, git commit, each document's text hash — the raw batch
results, one parsed prediction per document, and a parse report. Document
text is not stored, only its hash.

A document that fails — refusal, `max_tokens`, unparseable output, an errored
or expired request after one retry — is written as an empty prediction with
its failure named, and is scored as one: every gold record missed (B7).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .prompt import OUTPUT_SCHEMA_PATH, ROOT, SYSTEM_PROMPT_PATH
from .score import document_key
from .screen import to_text
from .validate import ISO_DATE, ISO_MONTH, normalize_for_quote_check

MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 64_000
RUNS_DIR = ROOT / "runs"
LABELS_DIR = ROOT / "data" / "labels"
RAW_DIR = ROOT / "data" / "raw"

USER_TEMPLATE = (
    "<agreement>\n{document}\n</agreement>\n\n"
    "Extract the record for this agreement, following the rules."
)

RETRYABLE = ("errored", "expired")


def sha256(data: str | bytes) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


# --- Documents and the corpus guard -------------------------------------------------


@dataclass(frozen=True)
class Document:
    accession: str
    document_file: str
    text: str

    @property
    def key(self) -> tuple[str, str]:
        return self.accession, self.document_file

    @property
    def custom_id(self) -> str:
        """Batch custom ids allow letters, digits, _ and -, up to 64."""
        stem = Path(self.document_file).stem
        return re.sub(r"[^A-Za-z0-9_-]", "-", f"{self.accession}_{stem}")[:64]


class CorpusLocked(Exception):
    """A corpus document was about to be sent before `label-freeze`."""


def corpus_keys(labels_dir: Path = LABELS_DIR) -> set[tuple[str, str]]:
    return {document_key(json.loads(p.read_text())) for p in labels_dir.glob("*.json")}


def label_freeze_exists(repo: Path = ROOT) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/tags/label-freeze"],
        cwd=repo, capture_output=True, text=True,
    )
    return result.returncode == 0


def guard(documents: list[Document], labels_dir: Path = LABELS_DIR, repo: Path = ROOT) -> None:
    corpus = corpus_keys(labels_dir)
    blocked = [d for d in documents if d.key in corpus]
    if blocked and not label_freeze_exists(repo):
        raise CorpusLocked(
            f"{len(blocked)} of {len(documents)} document(s) are in the corpus, and the label-freeze tag "
            f"does not exist. No extraction, by the model or the baseline, runs on a corpus document "
            f"before label-freeze."
        )


def load_documents(label_paths: list[Path], raw_dir: Path = RAW_DIR) -> list[Document]:
    """Documents named by label-shaped files: each file's source block gives
    the accession and the exhibit file, and the text comes from data/raw."""
    docs = []
    for path in label_paths:
        accession, document_file = document_key(json.loads(path.read_text()))
        raw = raw_dir / f"{accession}_{document_file}"
        if not raw.exists():
            raise FileNotFoundError(f"{raw}: not on disk")
        docs.append(Document(accession, document_file, to_text(raw.read_bytes())))
    return docs


# --- Requests -------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    model: str = MODEL
    effort: str = EFFORT
    max_tokens: int = MAX_TOKENS


def build_request(doc: Document, system_prompt: str, output_schema: dict[str, Any], settings: Settings) -> dict:
    return {
        "custom_id": doc.custom_id,
        "params": {
            "model": settings.model,
            "max_tokens": settings.max_tokens,
            # One cached prefix for every request in the batch: the rulebook.
            "system": [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": USER_TEMPLATE.format(document=doc.text)}],
            "output_config": {
                "effort": settings.effort,
                "format": {"type": "json_schema", "schema": output_schema},
            },
        },
    }


# --- The run directory ------------------------------------------------------------------


def _git_commit(repo: Path = ROOT) -> tuple[str, bool]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip())
    return head, dirty


@dataclass
class Manifest:
    run_id: str
    created: str
    git_commit: str
    git_dirty: bool
    model: str
    effort: str
    max_tokens: int
    prompt_sha256: str
    schema_sha256: str
    user_template_sha256: str
    documents: list[dict[str, Any]]
    batches: list[dict[str, Any]] = field(default_factory=list)  # one per attempt
    status: str = "prepared"

    def write(self, run_dir: Path) -> None:
        (run_dir / "manifest.json").write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def read(cls, run_dir: Path) -> "Manifest":
        return cls(**json.loads((run_dir / "manifest.json").read_text()))


def prepare(run_id: str, docs: list[Document], settings: Settings, runs_dir: Path = RUNS_DIR) -> Path:
    """Write the manifest. Refuses an existing run id: a run is a record."""
    run_dir = runs_dir / run_id
    if run_dir.exists():
        raise FileExistsError(f"{run_dir} exists; a run is never overwritten")
    run_dir.mkdir(parents=True)
    commit, dirty = _git_commit()
    Manifest(
        run_id=run_id,
        created=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        git_commit=commit,
        git_dirty=dirty,
        model=settings.model,
        effort=settings.effort,
        max_tokens=settings.max_tokens,
        prompt_sha256=sha256(SYSTEM_PROMPT_PATH.read_text()),
        schema_sha256=sha256(OUTPUT_SCHEMA_PATH.read_text()),
        user_template_sha256=sha256(USER_TEMPLATE),
        documents=[
            {"accession": d.accession, "document_file": d.document_file, "custom_id": d.custom_id,
             "text_sha256": sha256(d.text), "characters": len(d.text)}
            for d in docs
        ],
    ).write(run_dir)
    return run_dir


# --- The batch client ------------------------------------------------------------------


class BatchClient(Protocol):
    """The slice of `anthropic.Anthropic().messages.batches` a run uses, so a
    fake can stand in for it in tests."""

    def create(self, *, requests: list[dict]) -> Any: ...
    def retrieve(self, batch_id: str) -> Any: ...
    def results(self, batch_id: str) -> Any: ...


def anthropic_batches() -> BatchClient:
    import anthropic  # imported here, so preparing a run needs no SDK credentials

    return anthropic.Anthropic().messages.batches


def as_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    for method in ("to_dict", "model_dump"):
        if hasattr(obj, method):
            return getattr(obj, method)()
    raise TypeError(f"cannot read {type(obj).__name__} as a dict")


def submit(client: BatchClient, run_dir: Path, docs: list[Document], system_prompt: str,
           output_schema: dict, settings: Settings) -> str:
    guard(docs)  # again, at the last moment before anything is sent
    manifest = Manifest.read(run_dir)
    batch = as_dict(client.create(requests=[build_request(d, system_prompt, output_schema, settings) for d in docs]))
    manifest.batches.append({"id": batch["id"], "custom_ids": [d.custom_id for d in docs],
                             "submitted": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    manifest.status = "submitted"
    manifest.write(run_dir)
    return batch["id"]


def wait(client: BatchClient, batch_id: str, poll_seconds: float = 60, timeout_seconds: float = 26 * 3600,
         sleep=time.sleep) -> dict:
    """Batches end within 24 hours; the timeout leaves margin."""
    waited = 0.0
    while True:
        batch = as_dict(client.retrieve(batch_id))
        if batch.get("processing_status") == "ended":
            return batch
        if waited >= timeout_seconds:
            raise TimeoutError(f"batch {batch_id} not ended after {waited:.0f}s")
        sleep(poll_seconds)
        waited += poll_seconds


# --- Results -----------------------------------------------------------------------------


@dataclass
class Outcome:
    custom_id: str
    status: str  # "ok", "refusal", "max_tokens", "unparseable", "errored", "expired", "canceled"
    prediction: dict[str, Any] | None = None
    problems: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


def parse_result(result: dict) -> Outcome:
    custom_id = result["custom_id"]
    body = result["result"]
    if body["type"] != "succeeded":
        return Outcome(custom_id, body["type"])
    message = body["message"]
    usage = message.get("usage") or {}
    stop = message.get("stop_reason")
    if stop in ("refusal", "max_tokens"):
        return Outcome(custom_id, stop, usage=usage)
    text = next((b.get("text", "") for b in message.get("content", []) if b.get("type") == "text"), "")
    try:
        prediction = json.loads(text)
    except json.JSONDecodeError:
        return Outcome(custom_id, "unparseable", usage=usage)
    return Outcome(custom_id, "ok", prediction, post_response_problems(prediction), usage)


def post_response_problems(prediction: dict) -> list[str]:
    """What the structured-output schema cannot enforce (D4): month or day
    precision on a stated effective_from, and positive period counts."""
    problems = []
    for i, cov in enumerate(prediction.get("financial_covenants") or []):
        steps = ((cov.get("step_down_schedule") or {}).get("value")) or []
        for j, step in enumerate(steps):
            ef = step.get("effective_from") or {}
            path = f"financial_covenants[{i}].step_down_schedule[{j}].effective_from"
            if ef.get("basis") == "stated" and not (ISO_DATE.match(str(ef.get("value"))) or ISO_MONTH.match(str(ef.get("value")))):
                problems.append(f"{path}: {ef.get('value')!r} is neither YYYY-MM-DD nor YYYY-MM")
            if ef.get("basis") == "relative":
                count = next((v for k, v in (ef.get("value") or {}).items() if k != "anchor"), None)
                if not isinstance(count, int) or count < 1:
                    problems.append(f"{path}: period count {count!r} is not a positive integer")
    for i, fac in enumerate(prediction.get("facilities") or []):
        value = (fac.get("maturity_date") or {}).get("value") or {}
        if value.get("basis") == "relative":
            tenor = next((v for k, v in (value.get("value") or {}).items() if k != "anchor"), None)
            if not isinstance(tenor, int) or tenor < 1:
                problems.append(f"facilities[{i}].maturity_date: tenor {tenor!r} is not a positive integer")
    return problems


def check_quotes(prediction: dict, document_text: str) -> list[tuple[str, str]]:
    """Every quote a prediction carries, and whether it is in the document (B4).

    Typography and whitespace are folded, as for labels. A difference only in
    spacing passes — an artifact of turning HTML into text. A difference in
    case fails: the rule says verbatim. Returns (path, verdict) pairs, verdict
    one of "verbatim", "spacing", "case", "absent"."""
    document = normalize_for_quote_check(document_text)
    squeezed = document.replace(" ", "")
    lowered = document.lower()
    out = []

    def verdict(quote: str) -> str:
        needle = normalize_for_quote_check(quote)
        if needle in document:
            return "verbatim"
        if needle.replace(" ", "") in squeezed:
            return "spacing"
        if needle.lower() in lowered:
            return "case"
        return "absent"

    for level in ("facilities", "financial_covenants"):
        for i, record in enumerate(prediction.get(level) or []):
            for name, entry in record.items():
                if not isinstance(entry, dict):
                    continue
                quote = (entry.get("citation") or {}).get("quote")
                if isinstance(quote, str) and quote.strip():
                    out.append((f"{level}[{i}].{name}.citation", verdict(quote)))
                value = entry.get("value")
                if isinstance(value, dict) and isinstance(value.get("quote"), str):
                    out.append((f"{level}[{i}].{name}.value.quote", verdict(value["quote"])))
    return out


def collect(client: BatchClient, run_dir: Path, docs: list[Document]) -> dict[str, Outcome]:
    """Read every attempt's results, keep the latest outcome per document,
    and write raw results, predictions and the parse report."""
    manifest = Manifest.read(run_dir)
    by_id = {d.custom_id: d for d in docs}
    outcomes: dict[str, Outcome] = {}
    raw_lines = []
    for attempt, batch in enumerate(manifest.batches):
        for result in client.results(batch["id"]):
            result = as_dict(result)
            raw_lines.append(json.dumps({"attempt": attempt, **result}))
            outcomes[result["custom_id"]] = parse_result(result)
    (run_dir / "results.jsonl").write_text("\n".join(raw_lines) + "\n")

    pred_dir = run_dir / "predictions"
    pred_dir.mkdir(exist_ok=True)
    report = {}
    for custom_id, doc in by_id.items():
        outcome = outcomes.get(custom_id, Outcome(custom_id, "missing"))
        source = {"accession_number": doc.accession, "document_file": doc.document_file}
        if outcome.status == "ok":
            prediction = {"source": source, **outcome.prediction}
            quotes = check_quotes(outcome.prediction, doc.text)
        else:
            # B7: a failed document is an empty prediction, named as failed.
            prediction = {"source": source, "facilities": [], "financial_covenants": [], "failure": outcome.status}
            quotes = []
        prediction["run"] = manifest.run_id
        (pred_dir / f"{custom_id}.json").write_text(json.dumps(prediction, indent=2) + "\n")
        report[custom_id] = {
            "status": outcome.status,
            "problems": outcome.problems,
            "quotes": {v: sum(1 for _, x in quotes if x == v) for v in ("verbatim", "spacing", "case", "absent")},
            "failed_quotes": [p for p, x in quotes if x in ("case", "absent")],
            "usage": outcome.usage,
        }
    (run_dir / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest.status = "collected"
    manifest.write(run_dir)
    return outcomes


def run(run_id: str, label_paths: list[Path], *, submit_batch: bool, settings: Settings = Settings(),
        client: BatchClient | None = None, poll_seconds: float = 60, sleep=time.sleep,
        runs_dir: Path = RUNS_DIR, raw_dir: Path = RAW_DIR) -> str:
    """Prepare, and with submit_batch send, wait, collect, and retry errored or
    expired requests once."""
    docs = load_documents(label_paths, raw_dir)
    guard(docs)
    system_prompt = SYSTEM_PROMPT_PATH.read_text()
    output_schema = json.loads(OUTPUT_SCHEMA_PATH.read_text())
    run_dir = prepare(run_id, docs, settings, runs_dir)
    chars = sum(len(d.text) for d in docs)
    lines = [f"prepared {run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}: "
             f"{len(docs)} document(s), {chars:,} characters, model {settings.model}, effort {settings.effort}"]
    if not submit_batch:
        lines.append("not sent: pass --submit to send the batch")
        return "\n".join(lines)

    client = client or anthropic_batches()
    batch_id = submit(client, run_dir, docs, system_prompt, output_schema, settings)
    wait(client, batch_id, poll_seconds, sleep=sleep)
    outcomes = collect(client, run_dir, docs)
    retry = [d for d in docs if outcomes.get(d.custom_id, Outcome(d.custom_id, "missing")).status in RETRYABLE]
    if retry:
        batch_id = submit(client, run_dir, retry, system_prompt, output_schema, settings)
        wait(client, batch_id, poll_seconds, sleep=sleep)
        outcomes = collect(client, run_dir, docs)
    counts: dict[str, int] = {}
    for o in outcomes.values():
        counts[o.status] = counts.get(o.status, 0) + 1
    lines.append(f"collected: {counts}" + (f"; {len(retry)} retried once" if retry else ""))
    return "\n".join(lines)


def score_run(run_dir: Path, labels_dir: Path) -> str:
    """Each prediction against its label, field by field — the scorer core in
    model mode: only the label can exclude a field. Counts only, no values.
    F1 is not computed here; its accounting is B1, still a proposal."""
    from .score import compare_documents, load_labels, load_scoring_fields

    fields = load_scoring_fields()
    labels = load_labels(labels_dir)
    report = json.loads((run_dir / "parse_report.json").read_text())
    lines = []
    for path in sorted((run_dir / "predictions").glob("*.json")):
        prediction = json.loads(path.read_text())
        key = document_key(prediction)
        status = report.get(path.stem, {}).get("status", "?")
        if key not in labels:
            lines.append(f"{path.stem}: {status}; no label in {labels_dir}")
            continue
        c = compare_documents(labels[key], prediction, fields, symmetric=False)
        parts = [f"{path.stem}: {status}"]
        for level, lc in c.levels.items():
            right = sum(1 for p in lc.pairs for r in p.fields if r.correct is True)
            wrong = sorted({r.field for p in lc.pairs for r in p.fields if r.correct is False})
            parts.append(
                f"  {level}: {len(lc.pairs)} paired, {len(lc.unpaired_reference)} missed, "
                f"{len(lc.unpaired_candidate)} spurious; {right} fields right; wrong: {', '.join(wrong) or 'none'}"
            )
        quotes = report.get(path.stem, {}).get("quotes", {})
        if quotes:
            parts.append(f"  quotes: {quotes}")
        lines += parts
    return "\n".join(lines)
