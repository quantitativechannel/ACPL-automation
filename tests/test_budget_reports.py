from __future__ import annotations

import pandas as pd

from src.reports.budget_reports import (
    build_entity_budget_report,
    build_group_budget_report,
    build_monthly_budget_matrix,
)


def _postings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"scenario_id": "BUD2026", "entity_id": "E1", "month": "2026-01", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 100.0},
            {"scenario_id": "BUD2026", "entity_id": "E1", "month": "2026-02", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 120.0},
            {"scenario_id": "BUD2026", "entity_id": "E1", "month": "2026-02", "account_code": "5001", "posting_type": "expense", "amount": 40.0},
            {"scenario_id": "BUD2026", "entity_id": "E2", "month": "2026-02", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 80.0},
            {"scenario_id": "BUD2026", "entity_id": "E2", "month": "2026-02", "account_code": "5001", "posting_type": "expense", "amount": 30.0},
        ]
    )


def _account_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"account_code": "4001", "report_line_name": "Revenue"},
            {"account_code": "5001", "report_line_name": "Operating Expense"},
        ]
    )


def _report_lines() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"line_code": "L2", "line_name": "Operating Expense", "section_name": "Expenses", "display_order": 2, "sign_convention": "reverse"},
            {"line_code": "L1", "line_name": "Revenue", "section_name": "Income", "display_order": 1, "sign_convention": "normal"},
            {"line_code": "L3", "line_name": "Other Income", "section_name": "Income", "display_order": 3, "sign_convention": "normal"},
        ]
    )


def test_entity_budget_report_aggregates_and_ytd_and_order_and_zero_rows() -> None:
    report = build_entity_budget_report(_postings(), _account_map(), _report_lines(), "BUD2026", "E1", "2026-02")

    assert list(report["line_name"]) == ["Revenue", "Operating Expense", "Other Income"]
    revenue = report.set_index("line_name").loc["Revenue"]
    expense = report.set_index("line_name").loc["Operating Expense"]
    other = report.set_index("line_name").loc["Other Income"]

    assert revenue["month_amount"] == 120.0
    assert revenue["ytd_amount"] == 220.0
    assert expense["month_amount"] == -40.0
    assert expense["ytd_amount"] == -40.0
    assert other["month_amount"] == 0.0
    assert other["ytd_amount"] == 0.0


def test_group_budget_report_aggregates_across_entities() -> None:
    report = build_group_budget_report(_postings(), _account_map(), _report_lines(), "BUD2026", "2026-02")
    revenue = report.set_index("line_name").loc["Revenue"]
    expense = report.set_index("line_name").loc["Operating Expense"]

    assert revenue["month_amount"] == 200.0
    assert revenue["ytd_amount"] == 300.0
    assert expense["month_amount"] == -70.0


def test_monthly_budget_matrix_shape() -> None:
    matrix = build_monthly_budget_matrix(
        _postings(), _account_map(), scenario_id="BUD2026", start_month="2026-01", end_month="2026-03", entity_id="E1"
    )
    assert list(matrix.columns) == ["report_line_name", "2026-01", "2026-02", "2026-03"]
    assert matrix.shape == (2, 4)
