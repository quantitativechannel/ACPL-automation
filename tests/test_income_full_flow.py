import pandas as pd

from examples.demo_income_flow import (
    _build_demo_inputs,
    _build_fund_postings,
    _build_income_statement_report,
)
from src.drivers.income_capacity_driver import build_capacity_rollforward
from src.drivers.maa_revenue_driver import build_maa_postings


def test_income_full_flow() -> None:
    capacity_assumptions, maa_assumptions, revenue_policies, allocation_rules, cash_collection_rules, fund_assumptions = _build_demo_inputs()

    capacity_rollforward = build_capacity_rollforward(capacity_assumptions, "2026-01", "2026-12")
    maa_postings = build_maa_postings(
        capacity_rollforward,
        maa_assumptions,
        revenue_policies,
        allocation_rules,
        cash_collection_rules,
        "2026-01",
        "2026-12",
    )
    all_postings = pd.concat([maa_postings, _build_fund_postings("DEMO", fund_assumptions)], ignore_index=True)

    assert not all_postings[all_postings["posting_type"] == "revenue_recognition"].empty
    assert not all_postings[all_postings["posting_type"] == "cash_receipt"].empty

    maa_entities = set(all_postings[all_postings["revenue_type"] == "MAA_BASE"]["entity_code"].unique())
    assert {"ACPLSZ", "ACPLHK"}.issubset(maa_entities)

    assert not all_postings[(all_postings["entity_code"] == "旭智咨询") & (all_postings["revenue_type"] == "JV_FUND")].empty
    assert not all_postings[(all_postings["entity_code"] == "旭智私募") & (all_postings["revenue_type"] == "XIHE_FUND")].empty

    q_cash_months = sorted(
        all_postings[
            (all_postings["posting_type"] == "cash_receipt")
            & (all_postings["revenue_type"] == "MAA_BASE")
        ]["month"].unique().tolist()
    )
    assert q_cash_months == ["2026-01", "2026-04", "2026-07", "2026-10"]

    annual_prepaid_months = sorted(
        all_postings[
            (all_postings["posting_type"] == "cash_receipt")
            & (all_postings["revenue_type"] == "ANNUAL_PREPAID")
        ]["month"].unique().tolist()
    )
    assert annual_prepaid_months == ["2026-01"]

    income_report = _build_income_statement_report(all_postings)
    acplsz = income_report[income_report["entity_code"] == "ACPLSZ"].copy()
    assert round(acplsz["ytd_revenue"].iloc[-1], 6) == round(acplsz["amount"].sum(), 6)
