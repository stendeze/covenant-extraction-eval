"""The regex baseline does what R1 says, on synthetic text.

These test the spec, not the score. Where R1 is crude, the test pins the
crudeness, so that a later change which makes the baseline look better is
visible as a change to the spec rather than slipping in as a fix.
"""

from __future__ import annotations

from covenant_eval.baseline import extract_record

AGREEMENT = """
CREDIT AGREEMENT among Example Co., the Lenders and Big Bank, N.A., as Administrative Agent.
"Applicable Rate" means 1.75% per annum for Term SOFR Loans and 0.75% for Base Rate Loans.
"Maturity Date" means June 30, 2030.
"Revolving Credit Commitments" means commitments of the Lenders. The aggregate amount of the Revolving Credit Commitments on the Closing Date is $400,000,000.
Each Revolving Loan bears interest at Term SOFR plus the Applicable Rate. Term SOFR is published by CME. Term SOFR applies.
Section 7.11 Financial Covenants. The Borrower shall not permit the Consolidated Total Net Leverage Ratio as of the last day of any fiscal quarter to exceed 3.50 to 1.00.
The Borrower shall not permit the Interest Coverage Ratio as of the last day of any fiscal quarter to be less than 3.00 to 1.00.
"""


def test_a_plain_revolver_agreement():
    rec = extract_record(AGREEMENT)
    [fac] = rec["facilities"]
    assert fac["facility_type"]["value"] == "revolver"
    assert fac["aggregate_commitment"]["value"] == {"amount": 400_000_000, "currency": "USD"}
    assert fac["maturity_date"]["value"] == {"value": "2030-06-30", "basis": "stated"}
    assert fac["interest_rate_benchmark"]["value"] == "term_sofr"
    assert fac["applicable_margin_bps"]["value"] == 175
    assert fac["has_margin_grid"]["value"] is False
    types = [c["covenant_type"]["value"] for c in rec["financial_covenants"]]
    assert types == ["total_net_leverage", "interest_coverage"]
    lev, cov = rec["financial_covenants"]
    assert lev["initial_threshold"]["value"] == 3.5 and lev["testing_frequency"]["value"] == "quarterly"
    assert cov["initial_threshold"]["value"] == 3.0
    assert all(c["step_down_schedule"]["value"] == [] for c in rec["financial_covenants"])
    assert all(c["springing_trigger"]["value"] is None for c in rec["financial_covenants"])


def test_quotes_are_the_documents_own_text():
    rec = extract_record(AGREEMENT)
    normalized = " ".join(AGREEMENT.split())
    for level in ("facilities", "financial_covenants"):
        for record in rec[level]:
            for entry in record.values():
                quote = (entry.get("citation") or {}).get("quote")
                if quote:
                    assert quote in normalized


def test_an_unlettered_term_loan_is_term_loan_b_and_one_record_stands_for_all():
    text = AGREEMENT + "\nThe Term Loans shall be repaid in installments. Term Loans of each tranche.\n"
    types = [f["facility_type"]["value"] for f in extract_record(text)["facilities"]]
    assert types == ["revolver", "term_loan_b"]


def test_relative_maturity_and_a_termination_date_left_alone():
    rel = AGREEMENT.replace('"Maturity Date" means June 30, 2030.',
                            '"Maturity Date" means the date that is five (5) years after the Closing Date.')
    [fac] = extract_record(rel)["facilities"]
    assert fac["maturity_date"]["value"] == {"value": {"tenor_years": 5, "anchor": "Closing Date"}, "basis": "relative"}
    ann = AGREEMENT.replace('"Maturity Date" means June 30, 2030.',
                            '"Maturity Date" means the fifth anniversary of the Effective Date.')
    assert extract_record(ann)["facilities"][0]["maturity_date"]["value"]["value"] == {"tenor_years": 5, "anchor": "Effective Date"}
    term = AGREEMENT.replace('"Maturity Date" means', '"Termination Date" means')
    assert extract_record(term)["facilities"][0]["maturity_date"]["value"] is None  # R1 looks for "Maturity Date"


def test_the_benchmark_is_the_most_frequent_named_one_and_cdor_is_beyond_it():
    libor = AGREEMENT.replace("Term SOFR", "LIBOR") + "\nLIBOR LIBOR. Term SOFR is a successor rate.\n"
    assert extract_record(libor)["facilities"][0]["interest_rate_benchmark"]["value"] == "libor"
    cdor = AGREEMENT.replace("Term SOFR", "CDOR Rate")
    assert extract_record(cdor)["facilities"][0]["interest_rate_benchmark"]["value"] is None


def test_the_grid_is_screen_pys_hint_unchanged():
    grid = AGREEMENT + '\nPricing Grid: Level I 1.25%, Level II 1.50%.\n'
    assert extract_record(grid)["facilities"][0]["has_margin_grid"]["value"] is True


def test_a_springing_trigger_needs_the_hint_and_a_percentage_near_revolving():
    text = AGREEMENT + ("\nThe covenant applies only during a Testing Condition, which exists when Revolving "
                        "Loans outstanding exceed 35% of the Revolving Credit Commitments.\n")
    triggers = [c["springing_trigger"]["value"] for c in extract_record(text)["financial_covenants"]]
    assert all(t == {"condition_type": "revolver_utilization", "threshold": 35, "threshold_unit": "percent",
                     "quote": t["quote"]} for t in triggers)


def test_a_capitalization_covenant_is_invisible_to_it():
    text = AGREEMENT.split("Section 7.11")[0] + (
        "\nSection 7.1 Financial Condition Covenant. The Borrower shall not permit the ratio of Total Debt "
        "to Total Capital to exceed 0.65 to 1.00.\n")
    assert extract_record(text)["financial_covenants"] == []
