"""The extraction pipeline, against a fake batch client.

No request leaves the machine. The documents are the dev set's, named by its
labels, with stand-in raw text in a temporary directory, so the suite runs on
a clean checkout and never touches a corpus filing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from covenant_eval import extract as X
from covenant_eval.extract import (
    CorpusLocked,
    Document,
    Manifest,
    Settings,
    build_request,
    check_quotes,
    guard,
    parse_result,
    post_response_problems,
)
from covenant_eval.score import compare_documents, load_scoring_fields

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"
DEV_LABELS = sorted(DEV.glob("*_labels.json"))


def as_model_output(label: dict) -> dict:
    """What a perfect model would return for a label: scored fields only, as
    {value, citation}, no null_kind, no facility_name, plus notes."""
    fields = load_scoring_fields()
    out = {"notes": []}
    for level in ("facilities", "financial_covenants"):
        out[level] = [
            {name: {"value": rec[name]["value"], "citation": rec[name].get("citation")} for name in fields[level]}
            for rec in label[level]
        ]
    return out


def succeeded(custom_id: str, payload: dict, stop: str = "end_turn") -> dict:
    return {"custom_id": custom_id, "result": {"type": "succeeded", "message": {
        "stop_reason": stop,
        "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": json.dumps(payload)}],
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }}}


class FakeBatches:
    """Answers each batch from a script: custom_id -> list of results, one per attempt."""

    def __init__(self, script: dict[str, list[dict]]):
        self.script = script
        self.created: list[list[dict]] = []

    def create(self, *, requests):
        self.created.append(requests)
        return {"id": f"batch-{len(self.created)}", "processing_status": "in_progress"}

    def retrieve(self, batch_id):
        return {"id": batch_id, "processing_status": "ended"}

    def results(self, batch_id):
        attempt = int(batch_id.split("-")[1]) - 1
        ids = [r["custom_id"] for r in self.created[attempt]]
        return [self.script[i][min(attempt, len(self.script[i]) - 1)] for i in ids]


@pytest.fixture
def raw_dir(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for path in DEV_LABELS:
        source = json.loads(path.read_text())["source"]
        (raw / f"{source['accession_number']}_{source['document_file']}").write_text(
            "<html><p>Stand-in text for a dev document.</p></html>")
    return raw


# --- The guard --------------------------------------------------------------------------


def test_a_corpus_document_is_refused_before_label_freeze():
    corpus = json.loads(next((ROOT / "data" / "labels").glob("*.json")).read_text())["source"]
    with pytest.raises(CorpusLocked):
        guard([Document(corpus["accession_number"], corpus["document_file"], "")])


def test_a_dev_document_sharing_a_corpus_accession_is_not_refused():
    """Lamb Weston EX-10.2 shares its accession with corpus row 7; the file
    tells them apart."""
    lamb = json.loads((DEV / "0001679273-24-000026_EX10-2_labels.json").read_text())["source"]
    labels_accessions = {json.loads(p.read_text())["source"]["accession_number"]
                         for p in (ROOT / "data" / "labels").glob("*.json")}
    assert lamb["accession_number"] in labels_accessions
    guard([Document(lamb["accession_number"], lamb["document_file"], "")])


# --- Requests ---------------------------------------------------------------------------


def test_a_request_carries_the_rulebook_the_document_and_the_schema():
    doc = Document("0000000000-26-000001", "ex10-1.htm", "AGREEMENT TEXT")
    req = build_request(doc, "RULES", {"type": "object"}, Settings())
    params = req["params"]
    assert req["custom_id"] == "0000000000-26-000001_ex10-1"
    assert params["model"] == "claude-opus-5-5" and params["output_config"]["effort"] == "high"
    assert params["system"][0]["text"] == "RULES" and params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert params["messages"][0]["content"].startswith("<agreement>\nAGREEMENT TEXT\n</agreement>")
    assert params["output_config"]["format"] == {"type": "json_schema", "schema": {"type": "object"}}
    assert "thinking" not in params and "fallbacks" not in params and "temperature" not in params


def test_custom_ids_are_legal():
    doc = Document("0001023128-22-000080", "executed-bns_lithiaxsynd.htm", "")
    assert len(doc.custom_id) <= 64 and all(c.isalnum() or c in "_-" for c in doc.custom_id)


# --- A whole run, against the fake ---------------------------------------------------------


def test_a_run_prepares_sends_retries_once_and_writes_empty_predictions_for_failures(tmp_path, raw_dir):
    labels = {p: json.loads(p.read_text()) for p in DEV_LABELS}
    docs = X.load_documents(DEV_LABELS, raw_dir)
    lithia, avaya, lamb = (next(d for d in docs if d.accession.startswith(a)) for a in ("0001023128", "0001418100", "0001679273"))
    lamb_label = labels[DEV / "0001679273-24-000026_EX10-2_labels.json"]
    script = {
        lamb.custom_id: [succeeded(lamb.custom_id, as_model_output(lamb_label))],
        avaya.custom_id: [succeeded(avaya.custom_id, {}, stop="refusal")],
        lithia.custom_id: [
            {"custom_id": lithia.custom_id, "result": {"type": "errored", "error": {"type": "api_error"}}},
            {"custom_id": lithia.custom_id, "result": {"type": "expired"}},
        ],
    }
    fake = FakeBatches(script)
    summary = X.run("test-run", DEV_LABELS, submit_batch=True, client=fake, sleep=lambda s: None,
                    runs_dir=tmp_path / "runs", raw_dir=raw_dir)
    run_dir = tmp_path / "runs" / "test-run"

    assert len(fake.created) == 2 and [r["custom_id"] for r in fake.created[1]] == [lithia.custom_id]
    assert "retried once" in summary
    manifest = Manifest.read(run_dir)
    assert manifest.status == "collected" and len(manifest.batches) == 2
    assert all("text_sha256" in d and "text" not in d for d in manifest.documents)

    report = json.loads((run_dir / "parse_report.json").read_text())
    assert report[lamb.custom_id]["status"] == "ok"
    assert report[avaya.custom_id]["status"] == "refusal"
    assert report[lithia.custom_id]["status"] == "expired"  # errored, retried once, then expired: no third try

    for doc in (avaya, lithia):
        pred = json.loads((run_dir / "predictions" / f"{doc.custom_id}.json").read_text())
        assert pred["facilities"] == [] and pred["financial_covenants"] == [] and pred["failure"]

    # A perfect answer parses and scores perfect against its label.
    pred = json.loads((run_dir / "predictions" / f"{lamb.custom_id}.json").read_text())
    c = compare_documents(lamb_label, pred, load_scoring_fields(), symmetric=False)
    assert all(r.correct for lc in c.levels.values() for p in lc.pairs for r in p.fields)
    assert not any(lc.unpaired_reference or lc.unpaired_candidate for lc in c.levels.values())


def test_a_run_is_never_overwritten(tmp_path, raw_dir):
    X.run("once", DEV_LABELS, submit_batch=False, runs_dir=tmp_path / "runs", raw_dir=raw_dir)
    with pytest.raises(FileExistsError):
        X.run("once", DEV_LABELS, submit_batch=False, runs_dir=tmp_path / "runs", raw_dir=raw_dir)


def test_preparing_without_submit_sends_nothing(tmp_path, raw_dir):
    summary = X.run("dry", DEV_LABELS, submit_batch=False, runs_dir=tmp_path / "runs", raw_dir=raw_dir)
    assert "not sent" in summary
    assert Manifest.read(tmp_path / "runs" / "dry").batches == []


# --- Parsing and checking --------------------------------------------------------------------


def test_max_tokens_and_unparseable_output_are_failures():
    assert parse_result(succeeded("a", {}, stop="max_tokens")).status == "max_tokens"
    broken = succeeded("b", {})
    broken["result"]["message"]["content"][1]["text"] = "{not json"
    assert parse_result(broken).status == "unparseable"


def test_what_the_schema_cannot_enforce_is_checked_after_the_response():
    label = json.loads((DEV / "0001679273-24-000026_EX10-2_labels.json").read_text())
    output = as_model_output(label)
    assert post_response_problems(output) == []
    bad = copy.deepcopy(output)
    bad["financial_covenants"][0]["step_down_schedule"]["value"][0]["effective_from"]["value"] = "Nov 2027"
    bad["facilities"][0]["maturity_date"]["value"] = {"basis": "relative", "value": {"tenor_years": 0, "anchor": "Closing Date"}}
    problems = post_response_problems(bad)
    assert len(problems) == 2


def test_quotes_are_checked_as_labels_are():
    text = "The Borrower shall not permit the  Consolidated\nLeverage Ratio to exceed 4.00 to 1.00."
    prediction = {"facilities": [], "financial_covenants": [{
        "covenant_type": {"value": "x", "citation": {"section": "7", "quote": "Consolidated Leverage Ratio"}},
        "initial_threshold": {"value": 4.0, "citation": {"section": "7", "quote": "exceed 4.00to 1.00"}},
        "testing_frequency": {"value": "x", "citation": {"section": "7", "quote": "the borrower shall not permit"}},
        "step_down_schedule": {"value": [], "citation": {"section": "7", "quote": "a sentence that is not there"}},
        "springing_trigger": {"value": None, "citation": None},
    }]}
    verdicts = dict(check_quotes(prediction, text))
    assert verdicts["financial_covenants[0].covenant_type.citation"] == "verbatim"
    assert verdicts["financial_covenants[0].initial_threshold.citation"] == "spacing"
    assert verdicts["financial_covenants[0].testing_frequency.citation"] == "case"
    assert verdicts["financial_covenants[0].step_down_schedule.citation"] == "absent"
