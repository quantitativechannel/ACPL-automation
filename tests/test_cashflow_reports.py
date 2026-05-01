from __future__ import annotations

import pandas as pd

from src.reports.cashflow_reports import (
    build_cashflow_monthly_matrix,
    build_cashflow_report,
    build_group_cashflow_report,
)


def _sample_postings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"scenario_id": "S1", "entity_id": "E1", "month": "2026-01", "account_code": "1001", "posting_type": "cash_receipt", "source_module": "income", "amount": 100.0},
            {"scenario_id": "S1", "entity_id": "E1", "month": "2026-02", "account_code": "1001", "posting_type": "cash_receipt", "source_module": "income", "amount": 150.0},
            {"scenario_id": "S1", "entity_id": "E1", "month": "2026-02", "account_code": "2001", "posting_type": "cash_payment", "source_module": "expense", "amount": 80.0},
            {"scenario_id": "S1", "entity_id": "E1", "month": "2026-02", "account_code": "2002", "posting_type": "expense", "source_module": "expense", "amount": 70.0},
            {"scenario_id": "S1", "entity_id": "E2", "month": "2026-02", "account_code": "1001", "posting_type": "cash_receipt", "source_module": "income", "amount": 200.0},
            {"scenario_id": "S1", "entity_id": "E2", "month": "2026-02", "account_code": "2001", "posting_type": "cash_payment", "source_module": "expense", "amount": 50.0},
        ]
    )


def _account_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"account_code": "1001", "cashflow_line_name": "Operating Inflow", "report_line_name": "R1", "sort_order": 1},
            {"account_code": "2001", "cashflow_line_name": "Operating Outflow", "report_line_name": "R2", "sort_order": 2},
            {"account_code": "2002", "cashflow_line_name": pd.NA, "report_line_name": "R3", "sort_order": 3},
        ]
    )


def test_cash_receipt_maps_to_inflow() -> None:
    report = build_cashflow_report(_sample_postings(), _account_map(), "S1", "2026-02", entity_id="E1")
    inflow = report[report["cashflow_line_name"] == "Operating Inflow"].iloc[0]
    assert inflow["month_amount"] == 150.0


def test_cash_payment_maps_to_outflow() -> None:
    report = build_cashflow_report(_sample_postings(), _account_map(), "S1", "2026-02", entity_id="E1")
    outflow = report[report["cashflow_line_name"] == "Operating Outflow"].iloc[0]
    assert outflow["month_amount"] == 80.0


def test_expense_is_excluded_by_default() -> None:
    report = build_cashflow_report(_sample_postings(), _account_map(), "S1", "2026-02", entity_id="E1")
    assert "expense" not in set(report["cashflow_line_name"])


def test_expense_included_when_flag_enabled() -> None:
    report = build_cashflow_report(
        _sample_postings(), _account_map(), "S1", "2026-02", entity_id="E1", use_expense_as_cash_payment=True
    )
    fallback = report[report["cashflow_line_name"] == "cash_payment"]
    assert not fallback.empty
    assert fallback.iloc[0]["month_amount"] == 70.0


def test_ytd_calculation() -> None:
    report = build_cashflow_report(_sample_postings(), _account_map(), "S1", "2026-02", entity_id="E1")
    inflow = report[report["cashflow_line_name"] == "Operating Inflow"].iloc[0]
    assert inflow["ytd_amount"] == 250.0


def test_group_cashflow_aggregation() -> None:
    report = build_group_cashflow_report(_sample_postings(), _account_map(), "S1", "2026-02")
    inflow = report[report["cashflow_line_name"] == "Operating Inflow"].iloc[0]
    assert inflow["month_amount"] == 350.0


def test_monthly_matrix() -> None:
    matrix = build_cashflow_monthly_matrix(_sample_postings(), _account_map(), "S1", "2026-01", "2026-02", entity_id="E1")
    row = matrix.set_index("cashflow_line_name").loc["Operating Inflow"]
    assert row["2026-01"] == 100.0
    assert row["2026-02"] == 150.0


def test_fallback_line_when_cashflow_line_missing() -> None:
    report = build_cashflow_report(
        _sample_postings(), _account_map(), "S1", "2026-02", entity_id="E1", use_expense_as_cash_payment=True
    )
    assert "cash_payment" in set(report["cashflow_line_name"])
