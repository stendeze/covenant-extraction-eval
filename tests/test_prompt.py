"""The prompt generator's leak filter, on synthetic text.

The real check reads the corpus filings and gold labels, which a test suite
on a clean checkout does not have and should not read. So the filter is tested
here against invented documents: "Acme" stands for a corpus borrower, and its
filing, quotes and values are made up. The committed prompt is checked against
the real corpus by `covenant-eval prompt`.
"""

from __future__ import annotations

import re

import pytest

from covenant_eval import prompt as P
from covenant_eval.prompt import LeakSources, Report, build_output_schema, check_prompt, generate_rules, literals
from covenant_eval.validate import SchemaParseError

FILING = (
    "The Applicable Rate shall be determined by reference to the certificate delivered under "
    "Section 4.01(a)(ix) on the Closing Date."
)


@pytest.fixture
def sources():
    return LeakSources(
        names=re.compile(r"\b(?:Acme)\b"),
        accessions=frozenset({"0000000000-26-000001"}),
        filings=(FILING,),
        gold_quotes=("the Closing Date occurs within ninety days of the signing of this agreement by all parties",),
        gold_literals=frozenset({"750000000", "3.75", "2029-03"}),
    )


def schema_text(body: str) -> str:
    """A schema.md with every model-facing section present and the test body in one."""
    sections = [f"## {h}\n\nPlaceholder rule for {h}.\n" for h in P.MODEL_SECTIONS]
    sections[3] = "## Facility fields\n\n" + body
    return "\n".join(sections)


def rules(body, sources, report=None):
    return generate_rules(schema_text(body), sources, report or Report())


def test_a_bullet_keeps_its_rule_and_loses_its_example(sources):
    body = (
        "- **Record the commitment at closing.** Acme's commitment was set in its recitals. The figure was large.\n"
        "\n"
        "  The rest of this bullet continues Acme's example and states no name.\n"
        "- The next bullet is untouched.\n"
    )
    out = rules(body, sources)
    assert "**Record the commitment at closing.**" in out
    assert "The figure was large" not in out          # same paragraph, after the name
    assert "continues" not in out                      # continuation paragraph of the same bullet
    assert "The next bullet is untouched." in out


def test_a_heading_that_names_a_document_takes_its_subsection(sources):
    body = (
        "### 1. A field\n\nKept.\n\n"
        "#### Added under Acme\n\nAn orphan with no name.\n\n- Also gone.\n\n"
        "### 2. Another field\n\nKept too.\n"
    )
    out = rules(body, sources)
    assert "Kept." in out and "Kept too." in out
    assert "orphan" not in out and "Also gone" not in out and "Added under" not in out


def test_blockquotes_corpus_talk_and_accessions_are_dropped(sources):
    body = (
        "> An aside that names nothing.\n\n"
        "This rule stands. Six documents in this corpus do otherwise.\n\n"
        "The trigger was 0000000000-26-000001.\n\n"
        "A value that may never fire is still allowed.\n"
    )
    out = rules(body, sources)
    assert "aside" not in out
    assert "This rule stands." in out and "Six documents" not in out
    assert "0000000000" not in out
    assert "never fire" not in out


def test_a_long_quotation_from_a_filing_is_a_leak_and_a_short_one_is_a_term(sources):
    body = (
        'A grid that says "the Applicable Rate shall be determined by reference to the certificate delivered" defers.\n\n'
        'The definitions in Article I ("Closing Date") are where to look.\n'
    )
    out = rules(body, sources)
    assert "certificate delivered" not in out
    assert '("Closing Date")' in out


def test_a_gold_value_drops_its_sentence_but_not_the_rule_around_it(sources):
    body = (
        "- **A threshold below 1.00 is a capitalization test.** A covenant set at 3.75 is a leverage test. "
        "Apply this before netting.\n"
    )
    report = Report()
    out = rules(body, sources, report)
    assert "capitalization test" in out and "Apply this before netting." in out
    assert "3.75" not in out
    assert report.dropped["states a value the gold records"] == 1


def test_a_month_precision_gold_value_also_catches_its_resolved_day():
    assert {"2029-03-31", "2029-03"} <= literals("the quarter ending 2029-03-31")
    assert {"2029-03-31", "2029-03"} <= literals("on March 31, 2029")
    assert "350" in literals("3.50%") and "3.5" in literals("3.50%")
    assert "750000000" in literals("$750,000,000")
    assert "2.01" not in literals("Section 2.01 and §6.12")


def test_a_reviewed_illustration_is_kept_word_for_word_only(sources, monkeypatch):
    monkeypatch.setattr(P, "ALLOWED_ILLUSTRATIONS", {"$750,000,000 is `750000000`.": "format"})
    body = "Amounts are whole units. $750,000,000 is `750000000`. Or 3.75 for a ratio.\n"
    report = Report()
    out = rules(body, sources, report)
    assert "$750,000,000 is `750000000`." in out and "3.75" not in out
    assert report.allowed_illustrations == ["$750,000,000 is `750000000`."]


def test_the_final_guard_refuses_a_name_and_an_unused_illustration(sources, monkeypatch):
    with pytest.raises(SchemaParseError, match="names 'Acme'"):
        check_prompt("A rule that slipped through about Acme.", sources, Report())
    monkeypatch.setattr(P, "ALLOWED_ILLUSTRATIONS", {"A sentence schema.md no longer has.": "format"})
    with pytest.raises(SchemaParseError, match="no longer appear"):
        check_prompt("Clean text.", sources, Report())


def test_the_output_schema_is_closed_and_nullable_where_decided():
    schema = build_output_schema()

    def objects(o):
        if isinstance(o, dict):
            if o.get("type") == "object":
                yield o
            for v in o.values():
                yield from objects(v)
        elif isinstance(o, list):
            for v in o:
                yield from objects(v)

    for o in objects(schema):
        assert o["additionalProperties"] is False and sorted(o["required"]) == sorted(o["properties"])
    fields = {
        **schema["properties"]["facilities"]["items"]["properties"],
        **schema["properties"]["financial_covenants"]["items"]["properties"],
    }
    nullable = {name for name, f in fields.items() if {"type": "null"} in f["properties"]["value"].get("anyOf", [])}
    assert nullable == {"aggregate_commitment", "applicable_margin_bps", "step_down_schedule", "springing_trigger"}
    assert "null_kind" not in str(schema) and "facility_name" not in str(schema)
