from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

import pandas as pd

from .normalization import _normalize_expenses
from .workbook import BudgetWorkbook


def export_dashboard_workbook(
    file_obj: BinaryIO | BytesIO,
    expenses_df: pd.DataFrame,
    opening_cash: float,
    scenarios: list[str],
) -> None:
    workbook = BudgetWorkbook(expenses=expenses_df)
    company_summary = workbook.company_summary(scenarios)
    consolidated = workbook.consolidated_summary(scenarios)
    cash_flow = workbook.cash_flow(scenarios, opening_cash)
    reports = workbook.scenario_reports(scenarios, opening_cash)

    with pd.ExcelWriter(file_obj, engine="xlsxwriter") as writer:
        workbook.expenses.to_excel(writer, sheet_name="Expenses", index=False)
        company_summary.to_excel(writer, sheet_name="Company Summary", index=False)
        consolidated.to_excel(writer, sheet_name="Consolidated", index=False)
        cash_flow.to_excel(writer, sheet_name="Cash Flow", index=False)

        for scenario, frame in reports.items():
            safe_name = str(scenario)[:27]
            frame.to_excel(writer, sheet_name=f"Report {safe_name}", index=False)


def default_template() -> bytes:
    template = pd.DataFrame(
        [
            {
                "company": "Company A",
                "code": "MKT-001",
                "expense_item": "Marketing",
                "cashflow_item": "Operating Expense",
                "scenario": "Base",
                "year": 2026,
                "annual_cost": 24000,
                "allocation_method": "monthly_average",
                "allocation_month": 1,
            },
            {
                "company": "Company B",
                "code": "OPS-100",
                "expense_item": "Compliance Filing",
                "cashflow_item": "Operating Expense",
                "scenario": "Conservative",
                "year": 2026,
                "annual_cost": 12000,
                "allocation_method": "quarterly_end",
                "allocation_month": 1,
            },
        ]
    )
    normalized = _normalize_expenses(template)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        normalized.to_excel(writer, sheet_name="Expenses", index=False)

    buffer.seek(0)
    return buffer.getvalue()
