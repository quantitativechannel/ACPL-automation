from __future__ import annotations

import pandas as pd

from src.reports.flash_report import build_flash_report


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
            {"line_code": "L1", "line_name": "Revenue", "section_name": "Income", "display_order": 1, "sign_convention": "normal"},
            {"line_code": "L2", "line_name": "Operating Expense", "section_name": "Expenses", "display_order": 2, "sign_convention": "reverse"},
        ]
    )


def test_flash_report_variance_and_reverse_sign() -> None:
    budget = pd.DataFrame(
        [
            {"scenario_id": "BUD", "entity_id": "E1", "month": "2026-01", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 100.0},
            {"scenario_id": "BUD", "entity_id": "E1", "month": "2026-02", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 100.0},
            {"scenario_id": "BUD", "entity_id": "E1", "month": "2026-02", "account_code": "5001", "posting_type": "expense", "amount": 50.0},
        ]
    )
    actual = pd.DataFrame(
        [
            {"scenario_id": "ACT", "entity_id": "E1", "month": "2026-01", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 90.0},
            {"scenario_id": "ACT", "entity_id": "E1", "month": "2026-02", "account_code": "4001", "posting_type": "revenue_recognition", "amount": 130.0},
            {"scenario_id": "ACT", "entity_id": "E1", "month": "2026-02", "account_code": "5001", "posting_type": "expense", "amount": 40.0},
        ]
    )

    report = build_flash_report(actual, budget, _account_map(), _report_lines(), "2026-02", entity_id="E1")
    rev = report.set_index("line_name").loc["Revenue"]
    exp = report.set_index("line_name").loc["Operating Expense"]

    assert rev["month_budget"] == 100.0
    assert rev["month_actual"] == 130.0
    assert rev["month_variance"] == 30.0
    assert rev["ytd_budget"] == 200.0
    assert rev["ytd_actual"] == 220.0
    assert rev["ytd_variance"] == 20.0

    assert exp["month_budget"] == -50.0
    assert exp["month_actual"] == -40.0
    assert exp["month_variance"] == 10.0
