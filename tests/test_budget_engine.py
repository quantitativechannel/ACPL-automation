from io import BytesIO

import pandas as pd

from src.budget_engine import BudgetWorkbook, default_template, export_dashboard_workbook


def test_template_loads_and_builds_summaries() -> None:
    template_bytes = default_template()
    workbook = BudgetWorkbook.from_excel(BytesIO(template_bytes))

    company_summary = workbook.company_summary(["Base", "Conservative"])
    consolidated = workbook.consolidated_summary(["Base", "Conservative"])
    cash_flow = workbook.cash_flow(["Base", "Conservative"], opening_cash=1000)

    assert not company_summary.empty
    assert not consolidated.empty
    assert "closing_cash" in cash_flow.columns


def test_export_creates_expected_tabs() -> None:
    template_bytes = default_template()
    workbook = BudgetWorkbook.from_excel(BytesIO(template_bytes))

    output = BytesIO()
    export_dashboard_workbook(output, workbook.expenses, opening_cash=0.0, scenarios=["Base", "Conservative"])

    output.seek(0)
    sheets = pd.ExcelFile(output).sheet_names
    assert "Expenses" in sheets
    assert "Company Summary" in sheets
    assert "Consolidated" in sheets
    assert "Cash Flow" in sheets
