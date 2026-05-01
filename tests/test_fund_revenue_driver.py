import pandas as pd

from src.drivers.fund_revenue_driver import (
    build_fund_management_fee_postings,
    build_jv_fund_rollforward,
    build_xihe_fund_postings,
)


def _jv_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    capacity = pd.DataFrame(
        [
            {"scenario_id": 1, "month": "2026-04", "jv_equity_new_contribution": 1000.0},
            {"scenario_id": 1, "month": "2026-05", "jv_equity_new_contribution": 1000.0},
            {"scenario_id": 1, "month": "2026-06", "jv_equity_new_contribution": 0.0},
            {"scenario_id": 1, "month": "2027-01", "jv_equity_new_contribution": 0.0},
        ]
    )

    assumptions = pd.DataFrame(
        [
            {
                "scenario_id": 1,
                "month": "2026-04",
                "fund_equity_initial_cumulative": 100.0,
                "fund_expense_initial_cumulative": 50.0,
                "gp_initial_cumulative": 10.0,
                "lp_initial_cumulative": 20.0,
                "management_fee_rate": 0.01,
                "vat_rate": 0.06,
                "cit_rate": 0.25,
                "addition_timing_factor": 0.5,
                "incentive_flag": 0,
            },
            {
                "scenario_id": 1,
                "month": "2026-05",
                "management_fee_rate": 0.01,
                "vat_rate": 0.06,
                "cit_rate": 0.25,
                "addition_timing_factor": 0.5,
                "incentive_flag": 1,
            },
            {
                "scenario_id": 1,
                "month": "2026-06",
                "management_fee_rate": 0.01,
                "vat_rate": 0.06,
                "cit_rate": 0.25,
                "addition_timing_factor": 0.5,
                "incentive_flag": 0,
            },
            {
                "scenario_id": 1,
                "month": "2027-01",
                "management_fee_rate": 0.01,
                "vat_rate": 0.06,
                "cit_rate": 0.25,
                "addition_timing_factor": 0.5,
                "incentive_flag": 1,
            },
        ]
    )
    return capacity, assumptions


def test_fund_equity_contribution_is_75pct_of_jv_equity() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2026-05")

    assert roll.loc[roll["month"] == "2026-04", "fund_equity_new_contribution"].iloc[0] == 750.0


def test_fixed_fund_expense_contribution_timing() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2027-01")

    apr = roll.loc[roll["month"] == "2026-04", "fund_expense_new_contribution"].iloc[0]
    may = roll.loc[roll["month"] == "2026-05", "fund_expense_new_contribution"].iloc[0]
    jan_2027 = roll.loc[roll["month"] == "2027-01", "fund_expense_new_contribution"].iloc[0]
    assert apr == 500.0
    assert may == 0.0
    assert jan_2027 == 200.0


def test_gp_contribution_before_2026_05_uses_25pct() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2026-04")

    expected = (750.0 + 500.0) * 0.25
    assert round(roll["gp_new_contribution"].iloc[0], 6) == round(expected, 6)


def test_gp_contribution_from_2026_05_onward_uses_3_33pct() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-05", "2026-05")

    expected = 750.0 * 0.0333
    assert round(roll["gp_new_contribution"].iloc[0], 6) == round(expected, 6)


def test_lp_contribution_is_residual() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2026-04")

    row = roll.iloc[0]
    assert round(row["lp_new_contribution"], 6) == round(
        row["fund_equity_new_contribution"] + row["fund_expense_new_contribution"] - row["gp_new_contribution"], 6
    )


def test_cumulative_balances_roll_forward() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2026-05")

    apr = roll[roll["month"] == "2026-04"].iloc[0]
    may = roll[roll["month"] == "2026-05"].iloc[0]

    assert apr["fund_equity_cumulative_contribution"] == 850.0
    assert may["fund_equity_cumulative_contribution"] == 1600.0
    assert may["gp_cumulative_contribution"] > apr["gp_cumulative_contribution"]


def test_base_management_fee_calculation() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2026-04")

    row = roll.iloc[0]
    lp_new = row["lp_new_contribution"]
    lp_prior = 20.0
    base_pool = lp_prior / (1 - 0.01) * 0.01 / 365 * 30 + lp_new / 365 * 30 * 0.5
    expected = 0.70 * base_pool * (1 - 0.06) * (1 - 0.25)
    assert round(row["base_management_fee"], 6) == round(expected, 6)


def test_incentive_management_fee_only_when_flag_is_1() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2026-05")

    apr = roll[roll["month"] == "2026-04"]["incentive_management_fee"].iloc[0]
    may = roll[roll["month"] == "2026-05"]["incentive_management_fee"].iloc[0]

    assert apr == 0.0
    assert may > 0.0


def test_annual_prepaid_cash_receipt_in_january() -> None:
    capacity, assumptions = _jv_inputs()
    roll = build_jv_fund_rollforward(capacity, assumptions, "2026-04", "2027-01")

    allocations = pd.DataFrame(
        [
            {"revenue_type": "FUND_MGMT_BASE", "recipient_entity_code": "旭智咨询", "allocation_pct": 1.0, "haircut_pct": 0.0},
            {
                "revenue_type": "FUND_MGMT_INCENTIVE",
                "recipient_entity_code": "旭智咨询",
                "allocation_pct": 1.0,
                "haircut_pct": 0.0,
            },
        ]
    )
    cash_rules = pd.DataFrame(
        [
            {"revenue_type": "FUND_MGMT_BASE", "collection_method": "annual_prepaid", "collection_months": "1"},
            {"revenue_type": "FUND_MGMT_INCENTIVE", "collection_method": "annual_prepaid", "collection_months": "1"},
        ]
    )

    postings = build_fund_management_fee_postings(roll, allocations, cash_rules, "2026-04", "2027-01")

    jan_cash = postings[
        (postings["posting_type"] == "cash_receipt")
        & (postings["month"] == "2027-01")
        & (postings["revenue_type"] == "FUND_MGMT_BASE")
    ]
    assert not jan_cash.empty


def test_xihe_monthly_revenue_recognition() -> None:
    postings = build_xihe_fund_postings(scenario_id=2, start_month="2026-01", end_month="2026-03")

    monthly = postings[postings["posting_type"] == "revenue_recognition"]
    assert len(monthly) == 3
    assert monthly["amount"].nunique() == 1


def test_xihe_annual_prepaid_cash_receipt() -> None:
    postings = build_xihe_fund_postings(scenario_id=2, start_month="2026-01", end_month="2026-12")

    cash = postings[(postings["posting_type"] == "cash_receipt") & (postings["month"] == "2026-01")]
    rec = postings[postings["posting_type"] == "revenue_recognition"]

    assert len(cash) == 1
    assert round(cash["amount"].iloc[0], 6) == round(rec["amount"].sum(), 6)
