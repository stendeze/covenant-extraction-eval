"""The scorer core, tested against the development set only.

Every fixture is a label from data/dev/ or a deliberate perturbation of one.
No corpus label is read here: the corpus is held out from model runs until
label-freeze, and the scorer is built the same way — against documents
outside it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from covenant_eval.score import (
    LEVELS,
    agreement,
    compare_documents,
    compare_field,
    load_scoring_fields,
    normalize_anchor,
    step_credit,
)

DEV = Path(__file__).resolve().parents[1] / "data" / "dev"
LITHIA = "0001023128-22-000080_EX10-2_labels.json"   # 5 facilities, 2 covenants, 5 excluded margins
AVAYA = "0001418100-23-000041_EX10-7_labels.json"    # 1 facility, 1 covenant
LAMB = "0001679273-24-000026_EX10-2_labels.json"     # 3 term loans, 2 covenants, one month-precision step


@pytest.fixture(scope="module")
def fields():
    return load_scoring_fields()


def dev(name: str) -> dict:
    return json.loads((DEV / name).read_text())


def compare(reference, candidate, fields, symmetric=False):
    return compare_documents(reference, candidate, fields, symmetric=symmetric)


def pairs(comparison, level):
    return [(p.reference_index, p.candidate_index) for p in comparison.levels[level].pairs]


def misses(comparison, level):
    return sorted(
        (p.reference_index, r.field)
        for p in comparison.levels[level].pairs for r in p.fields if r.correct is False
    )


# --- Identity and order -------------------------------------------------------------


@pytest.mark.parametrize("name", [LITHIA, AVAYA, LAMB])
def test_a_label_matches_itself_on_the_diagonal(name, fields):
    label = dev(name)
    c = compare(label, label, fields)
    for level in LEVELS:
        n = len(label[level])
        assert pairs(c, level) == [(i, i) for i in range(n)]
        assert misses(c, level) == []
        assert c.levels[level].unpaired_reference == c.levels[level].unpaired_candidate == ()


def test_order_of_the_candidate_list_does_not_change_the_pairing(fields):
    gold = dev(LAMB)
    pred = copy.deepcopy(gold)
    pred["facilities"].reverse()
    pred["financial_covenants"].reverse()
    c = compare(gold, pred, fields)
    assert pairs(c, "facilities") == [(0, 2), (1, 1), (2, 0)]
    assert pairs(c, "financial_covenants") == [(0, 1), (1, 0)]
    assert misses(c, "facilities") == misses(c, "financial_covenants") == []


def test_excluded_fields_are_neither_hit_nor_miss(fields):
    gold = dev(LITHIA)
    pred = copy.deepcopy(gold)
    for f in pred["facilities"]:
        f["applicable_margin_bps"]["value"] = 999
    c = compare(gold, pred, fields)
    margins = [p.result("applicable_margin_bps") for p in c.levels["facilities"].pairs]
    assert all(r.correct is None and r.excluded == "excluded_from_scoring: redacted" for r in margins)
    assert misses(c, "facilities") == []


def test_a_prediction_cannot_exclude_its_own_field(fields):
    gold = dev(AVAYA)
    pred = copy.deepcopy(gold)
    pred["facilities"][0]["has_margin_grid"] = {"value": True, "excluded_from_scoring": "redacted"}
    assert misses(compare(gold, pred, fields), "facilities") == [(0, "has_margin_grid")]
    # The relabel's comparison is symmetric: either pass can exclude.
    r = compare(gold, pred, fields, symmetric=True).levels["facilities"].pairs[0].result("has_margin_grid")
    assert r.correct is None


def test_an_unrepresentable_gold_null_is_excluded(fields):
    gold = dev(AVAYA)
    gold["financial_covenants"][0]["step_down_schedule"] = {
        "value": None, "null_kind": "unrepresentable", "citation": {"section": "x", "quote": "y"},
    }
    pred = dev(AVAYA)  # predicts []
    r = compare(gold, pred, fields).levels["financial_covenants"].pairs[0].result("step_down_schedule")
    assert r.correct is None and r.excluded == "unrepresentable"


# --- Alignment: a type is a field, not the key -------------------------------------


def test_a_wrong_covenant_type_costs_the_type_field_only(fields):
    gold = dev(LAMB)
    pred = copy.deepcopy(gold)
    pred["financial_covenants"][0]["covenant_type"]["value"] = "first_lien_net_leverage"
    c = compare(gold, pred, fields)
    assert pairs(c, "financial_covenants") == [(0, 0), (1, 1)]
    assert misses(c, "financial_covenants") == [(0, "covenant_type")]


def test_a_wrong_facility_type_with_the_right_commitment_still_pairs(fields):
    gold = dev(LAMB)
    pred = copy.deepcopy(gold)
    pred["facilities"][1]["facility_type"]["value"] = "term_loan_b"
    c = compare(gold, pred, fields)
    assert pairs(c, "facilities") == [(0, 0), (1, 1), (2, 2)]
    assert misses(c, "facilities") == [(1, "facility_type")]


def test_a_record_wrong_on_every_identifying_field_is_not_the_same_record(fields):
    gold = dev(AVAYA)
    pred = copy.deepcopy(gold)
    cov = pred["financial_covenants"][0]
    cov["covenant_type"]["value"] = "interest_coverage"
    cov["initial_threshold"]["value"] = 3.0
    c = compare(gold, pred, fields)
    lc = c.levels["financial_covenants"]
    assert lc.pairs == () and lc.unpaired_reference == (0,) and lc.unpaired_candidate == (0,)


def test_agreeing_only_on_shared_defaults_does_not_make_a_pair(fields):
    """A hallucinated covenant beside a missed one: same frequency, same flat
    schedule, same null trigger — and nothing that identifies it."""
    gold = dev(LAMB)
    pred = copy.deepcopy(gold)
    junk = copy.deepcopy(gold["financial_covenants"][1])
    junk["covenant_type"]["value"] = "fixed_charge_coverage"
    junk["initial_threshold"]["value"] = 1.25
    pred["financial_covenants"] = [gold["financial_covenants"][0], junk]
    lc = compare(gold, pred, fields).levels["financial_covenants"]
    assert [(p.reference_index, p.candidate_index) for p in lc.pairs] == [(0, 0)]
    assert lc.unpaired_reference == (1,) and lc.unpaired_candidate == (1,)


def test_a_missing_and_a_spurious_record_are_reported_as_such(fields):
    gold = dev(LAMB)
    pred = copy.deepcopy(gold)
    del pred["facilities"][2]
    extra = copy.deepcopy(gold["facilities"][0])
    extra["facility_type"]["value"] = "revolver"
    extra["aggregate_commitment"]["value"] = {"amount": 1_000_000_000, "currency": "USD"}
    pred["facilities"].append(extra)
    lc = compare(gold, pred, fields).levels["facilities"]
    assert [(p.reference_index, p.candidate_index) for p in lc.pairs] == [(0, 0), (1, 1)]
    assert lc.unpaired_reference == (2,) and lc.unpaired_candidate == (2,)


def test_commitment_rank_breaks_a_tie_before_position(fields):
    """Two term loans, both amounts wrong, listed in reverse order: rank pairs
    the larger with the larger, though position alone would not."""
    gold = dev(LAMB)
    gold["facilities"] = gold["facilities"][:2]  # Term A $300M, Term A-3 $450M
    for f in gold["facilities"]:
        f["maturity_date"]["value"] = {"value": "2030-01-31", "basis": "stated"}
        f["applicable_margin_bps"]["value"] = 200
    pred = copy.deepcopy(gold)
    pred["facilities"].reverse()  # now $450M first
    pred["facilities"][0]["aggregate_commitment"]["value"]["amount"] = 460_000_000
    pred["facilities"][1]["aggregate_commitment"]["value"]["amount"] = 310_000_000
    c = compare(gold, pred, fields)
    assert pairs(c, "facilities") == [(0, 1), (1, 0)]


def test_position_is_the_last_tie_break_for_mirrored_records(fields):
    """Lithia's mirror: two facilities identical on every field. Content
    cannot tell them apart; the lists' order does, deterministically."""
    gold = dev(LITHIA)
    twin = copy.deepcopy(gold["facilities"][0])
    gold["facilities"] = [twin, copy.deepcopy(twin)]
    pred = copy.deepcopy(gold)
    c = compare(gold, pred, fields)
    assert pairs(c, "facilities") == [(0, 0), (1, 1)]
    assert pairs(compare(gold, pred, fields), "facilities") == pairs(c, "facilities")


def test_an_empty_or_missing_covenant_list_is_empty(fields):
    gold = dev(AVAYA)
    gold["financial_covenants"] = []
    pred = dev(AVAYA)
    pred.pop("financial_covenants")
    lc = compare(gold, pred, fields).levels["financial_covenants"]
    assert lc.pairs == () and lc.unpaired_reference == () and lc.unpaired_candidate == ()
    lc = compare(gold, dev(AVAYA), fields).levels["financial_covenants"]
    assert lc.unpaired_candidate == (0,)  # a covenant invented on a covenant-free document


# --- Correct when, field by field ------------------------------------------------------


def entry(value, **extra):
    return {"value": value, **extra}


def correct(name, a, b, symmetric=False):
    return compare_field(name, entry(a), entry(b), symmetric=symmetric).correct


def test_tenor_is_compared_in_months():
    rel = lambda **k: {"value": {"anchor": "Closing Date", **k}, "basis": "relative"}
    assert correct("maturity_date", rel(tenor_years=3), rel(tenor_months=36))
    assert not correct("maturity_date", rel(tenor_years=3), rel(tenor_months=37))
    assert not correct("maturity_date", rel(tenor_years=3), {"value": "2025-06-03", "basis": "stated"})


def test_anchor_normalization_is_narrow():
    assert normalize_anchor("the Closing Date.") == normalize_anchor("“Closing Date”") == "closing date"
    rel = lambda a: {"value": {"tenor_years": 5, "anchor": a}, "basis": "relative"}
    assert correct("maturity_date", rel("Closing Date"), rel("the closing  date"))
    assert not correct("maturity_date", rel("Closing Date"), rel("Restatement Date"))
    assert not correct("maturity_date", rel("Closing Date"), rel("Closing Dates"))


def test_quarters_and_months_are_never_converted():
    step = lambda **k: [{"effective_from": {"value": {"anchor": "Closing Date", **k}, "basis": "relative"},
                         "threshold": 5.0}]
    assert correct("step_down_schedule", step(quarters_after=5), step(quarters_after=5))
    assert not correct("step_down_schedule", step(quarters_after=5), step(months_after=15))


def test_month_precision_is_exact_in_both_directions():
    gold = dev(LAMB)["financial_covenants"][0]["step_down_schedule"]
    finer = copy.deepcopy(gold)
    finer["value"][0]["effective_from"]["value"] = "2027-11-28"
    assert compare_field("step_down_schedule", gold, finer, symmetric=False).correct is False
    assert compare_field("step_down_schedule", finer, gold, symmetric=False).correct is False


def test_a_schedule_is_an_ordered_sequence_and_partial_credit_is_a_diagnostic():
    s = lambda d, t: {"effective_from": {"value": d, "basis": "stated"}, "threshold": t}
    gold = [s("2026-06-30", 4.25), s("2027-06-30", 4.0)]
    assert not correct("step_down_schedule", gold, list(reversed(gold)))
    r = compare_field("step_down_schedule", entry(gold), entry([gold[1]]), symmetric=False)
    assert r.correct is False
    assert (r.step_credit.recovered, r.step_credit.reference_steps) == (1, 2)
    assert (r.step_credit.matched, r.step_credit.candidate_steps) == (1, 1)
    assert step_credit(gold, gold + gold).matched == 2


def test_the_springing_unit_is_part_of_the_answer():
    t = lambda unit: {"condition_type": "revolver_utilization", "threshold": 35, "threshold_unit": unit,
                      "quote": "anything"}
    assert correct("springing_trigger", t("percent"), dict(t("percent"), quote="something else"))
    assert not correct("springing_trigger", t("percent"), t("currency"))
    assert not correct("springing_trigger", None, t("percent"))
    assert correct("springing_trigger", None, None)


def test_numbers_are_exact_and_not_rounded():
    assert correct("applicable_margin_bps", 112.5, 112.5)
    assert not correct("applicable_margin_bps", 112.5, 113)
    assert correct("initial_threshold", 4, 4.00)
    assert not correct("initial_threshold", 0.60, 60)
    assert not correct("has_margin_grid", True, 1)


def test_null_kinds_are_compared_only_in_the_symmetric_comparison():
    a = {"value": None, "null_kind": "deferral", "citation": {"section": "x", "quote": "y"}}
    b = {"value": None, "null_kind": "absence"}
    assert compare_field("applicable_margin_bps", a, b, symmetric=False).correct is True
    assert compare_field("applicable_margin_bps", a, b, symmetric=True).correct is False


# --- Agreement -------------------------------------------------------------------------


def test_agreement_counts_rates_and_majority_class(fields):
    original = dev(LAMB)
    relabel = copy.deepcopy(original)
    relabel["facilities"][2]["applicable_margin_bps"]["value"] = 200
    comparisons = [("lamb", compare(original, relabel, fields, symmetric=True))]
    report = agreement(comparisons, fields)
    margin = report.fields["applicable_margin_bps"]
    assert (margin.agreed, margin.compared) == (2, 3)
    # Pooled: 185, 200, 185 and 185, 200, 200 — three of each.
    assert margin.majority_rate == pytest.approx(3 / 6)
    freq = report.fields["testing_frequency"]
    assert (freq.agreed, freq.compared, freq.majority_rate) == (2, 2, 1.0)
    assert report.paired["facilities"] == 3 and report.only_original["facilities"] == 0


def test_agreement_views_select_instances(fields):
    original = dev(AVAYA)
    relabel = copy.deepcopy(original)
    relabel["financial_covenants"][0]["testing_frequency"]["value"] = "quarterly"
    comparisons = [("avaya", compare(original, relabel, fields, symmetric=True))]
    every = agreement(comparisons, fields).fields["testing_frequency"]
    assert (every.agreed, every.compared) == (0, 1)
    without = agreement(comparisons, fields, lambda doc, level, i, name: name != "testing_frequency")
    assert without.fields["testing_frequency"].compared == 0


def test_records_one_pass_lacks_enter_no_field_rate(fields):
    original = dev(LAMB)
    relabel = copy.deepcopy(original)
    del relabel["financial_covenants"][1]
    report = agreement([("lamb", compare(original, relabel, fields, symmetric=True))], fields)
    assert report.only_original["financial_covenants"] == 1
    assert report.fields["covenant_type"].compared == 1
