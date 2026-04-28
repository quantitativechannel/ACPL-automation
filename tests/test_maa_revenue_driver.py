import pandas as pd

from src.drivers.maa_revenue_driver import build_maa_postings


def _base_inputs():
    capacity = pd.DataFrame(
        [
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-01",
                "calendar_days": 31,
                "month_end_capacity_w": 1_000_000,
                "weighted_avg_capacity_w": 1_000_000,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-02",
                "calendar_days": 28,
                "month_end_capacity_w": 1_000_000,
                "weighted_avg_capacity_w": 1_000_000,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-03",
                "calendar_days": 31,
                "month_end_capacity_w": 1_000_000,
                "weighted_avg_capacity_w": 1_000_000,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-12",
                "calendar_days": 31,
                "month_end_capacity_w": 1_500_000,
                "weighted_avg_capacity_w": 1_500_000,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2030-12",
                "calendar_days": 31,
                "month_end_capacity_w": 2_000_000,
                "weighted_avg_capacity_w": 2_000_000,
            },
        ]
    )

    assumptions = pd.DataFrame(
        [
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-01",
                "incentive_1_flag": 1,
                "incentive_2_flag": 1,
                "reimbursed_cost_ex_vat": 0,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-02",
                "incentive_1_flag": 0,
                "incentive_2_flag": 1,
                "reimbursed_cost_ex_vat": 0,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-03",
                "incentive_1_flag": 0,
                "incentive_2_flag": 1,
                "reimbursed_cost_ex_vat": 0,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2026-12",
                "incentive_1_flag": 1,
                "incentive_2_flag": 1,
                "reimbursed_cost_ex_vat": 20,
            },
            {
                "scenario_id": "S1",
                "project_group": "PG1",
                "month": "2030-12",
                "incentive_1_flag": 1,
                "incentive_2_flag": 1,
                "reimbursed_cost_ex_vat": 0,
            },
        ]
    )

    policies = pd.DataFrame(
        [
            {"revenue_type": "MAA_BASE", "rate": 0.10, "vat_rate": 0.06, "cit_rate": 0.25},
            {"revenue_type": "MAA_INCENTIVE_1", "rate": 0.01, "vat_rate": 0.06, "cit_rate": 0.25},
            {"revenue_type": "MAA_INCENTIVE_2", "rate": 0.04, "vat_rate": 0.06, "cit_rate": 0.25},
        ]
    )

    allocations = pd.DataFrame(
        [
            {
                "revenue_type": "MAA_BASE",
                "recipient_entity_code": "ACPLSZ",
                "allocation_pct": 0.75,
                "haircut_pct": 0.0,
            },
            {
                "revenue_type": "MAA_BASE",
                "recipient_entity_code": "ACPLHK",
                "allocation_pct": 0.25,
                "haircut_pct": 0.05,
            },
            {
                "revenue_type": "MAA_INCENTIVE_1",
                "recipient_entity_code": "ACPLSZ",
                "allocation_pct": 0.75,
                "haircut_pct": 0.0,
            },
            {
                "revenue_type": "MAA_INCENTIVE_1",
                "recipient_entity_code": "ACPLHK",
                "allocation_pct": 0.25,
                "haircut_pct": 0.05,
            },
            {
                "revenue_type": "MAA_INCENTIVE_2",
                "recipient_entity_code": "ACPLSZ",
                "allocation_pct": 0.75,
                "haircut_pct": 0.0,
            },
            {
                "revenue_type": "MAA_INCENTIVE_2",
                "recipient_entity_code": "ACPLHK",
                "allocation_pct": 0.25,
                "haircut_pct": 0.05,
            },
        ]
    )

    cash_rules = pd.DataFrame(
        [
            {
                "revenue_type": "MAA_BASE",
                "collection_method": "quarterly_prepaid",
                "collection_months": "1,4,7,10",
                "settlement_month": None,
            },
            {
                "revenue_type": "MAA_INCENTIVE_1",
                "collection_method": "annual_settlement",
                "collection_months": None,
                "settlement_month": None,
            },
            {
                "revenue_type": "MAA_INCENTIVE_2",
                "collection_method": "full_cycle_settlement",
                "collection_months": None,
                "settlement_month": "2030-12",
            },
        ]
    )

    return capacity, assumptions, policies, allocations, cash_rules


def test_maa_base_monthly_revenue_recognition() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2026-03")

    jan_sz = result[
        (result["posting_type"] == "revenue_recognition")
        & (result["revenue_type"] == "MAA_BASE")
        & (result["entity_code"] == "ACPLSZ")
        & (result["month"] == "2026-01")
    ]["amount"].iloc[0]

    gross = 1_000_000 * 0.10 / 365 * 31 / 10000
    net_pool = gross * (1 - 0.06)
    assert round(jan_sz, 6) == round(net_pool * 0.75, 6)


def test_vat_and_reimbursed_cost_deduction() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-12", "2026-12")

    dec_sz = result[
        (result["posting_type"] == "revenue_recognition")
        & (result["revenue_type"] == "MAA_BASE")
        & (result["entity_code"] == "ACPLSZ")
        & (result["month"] == "2026-12")
    ]["amount"].iloc[0]

    gross = 1_500_000 * 0.10 / 365 * 31 / 10000
    net_pool = gross * (1 - 0.06) - 20
    assert round(dec_sz, 6) == round(net_pool * 0.75, 6)


def test_allocation_and_haircut_for_entities() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2026-01")

    jan_rows = result[
        (result["posting_type"] == "revenue_recognition")
        & (result["revenue_type"] == "MAA_BASE")
        & (result["month"] == "2026-01")
    ].set_index("entity_code")["amount"]

    gross = 1_000_000 * 0.10 / 365 * 31 / 10000
    net_pool = gross * (1 - 0.06)
    assert round(jan_rows["ACPLSZ"], 6) == round(net_pool * 0.75, 6)
    assert round(jan_rows["ACPLHK"], 6) == round(net_pool * 0.25 * (1 - 0.05), 6)


def test_quarterly_prepaid_cash_collection_timing() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2026-03")

    cash_rows = result[
        (result["posting_type"] == "cash_receipt")
        & (result["revenue_type"] == "MAA_BASE")
        & (result["month"] == "2026-01")
    ]
    assert not cash_rows.empty
    assert set(cash_rows["entity_code"].tolist()) == {"ACPLSZ", "ACPLHK"}


def test_incentive_1_only_when_flag_on() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    assumptions.loc[assumptions["month"].str.startswith("2026"), "incentive_1_flag"] = 0

    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2026-12")

    inc1 = result[(result["posting_type"] == "revenue_recognition") & (result["revenue_type"] == "MAA_INCENTIVE_1")]
    assert inc1.empty


def test_annual_settlement_cash_receipt_in_december() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2026-12")

    cash_inc1 = result[
        (result["posting_type"] == "cash_receipt")
        & (result["revenue_type"] == "MAA_INCENTIVE_1")
        & (result["month"] == "2026-12")
    ]
    assert not cash_inc1.empty


def test_incentive_2_full_cycle_settlement_in_2030_12() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2030-12")

    rec = result[
        (result["posting_type"] == "revenue_recognition")
        & (result["revenue_type"] == "MAA_INCENTIVE_2")
        & (result["month"] == "2030-12")
    ]
    cash = result[
        (result["posting_type"] == "cash_receipt")
        & (result["revenue_type"] == "MAA_INCENTIVE_2")
        & (result["month"] == "2030-12")
    ]
    assert not rec.empty
    assert not cash.empty


def test_output_contains_revenue_and_cash_postings() -> None:
    capacity, assumptions, policies, allocations, cash_rules = _base_inputs()
    result = build_maa_postings(capacity, assumptions, policies, allocations, cash_rules, "2026-01", "2026-12")

    assert {"revenue_recognition", "cash_receipt"}.issubset(set(result["posting_type"].unique().tolist()))
