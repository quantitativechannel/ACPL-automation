from io import BytesIO

import pandas as pd

from src.budget_engine import (
    BudgetWorkbook,
    allocate_expenses_to_companies,
    default_template,
    export_dashboard_workbook,
    generate_forecast_table,
)


def test_template_loads_and_builds_summaries() -> None:
    template_bytes = default_template()
    workbook = BudgetWorkbook.from_excel(BytesIO(template_bytes))

    company_summary = workbook.company_summary(["Base", "Conservative"])
    consolidated = workbook.consolidated_summary(["Base", "Conservative"])
    cash_flow = workbook.cash_flow(["Base", "Conservative"], opening_cash=1000)

    assert not company_summary.empty
    assert not consolidated.empty
    assert "closing_cash" in cash_flow.columns
    assert "expense" in consolidated.columns
    assert "budget" not in consolidated.columns


def test_expense_upload_auto_populates_subsidiaries() -> None:
    template_bytes = default_template()
    workbook = BudgetWorkbook.from_excel(BytesIO(template_bytes))

    assumptions = pd.DataFrame(
        [
            {
                "code": "FIN-901",
                "expense_item": "Audit",
                "cashflow_item": "Operating Expense",
                "scenario": "Base",
                "annual_cost": 12000,
                "allocation_method": "monthly_average",
                "year": 2026,
                "allocation_month": 1,
            }
        ]
    )

    existing_count = len(workbook.expenses)
    workbook.upload_expense_assumptions(assumptions)

    assert len(workbook.expenses) == existing_count + 24


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


def test_allocate_expenses_to_companies_defaults_and_spread() -> None:
    assumptions = pd.DataFrame(
        [
            {
                "code": "IT-001",
                "expense_item": "Software License",
                "cashflow_item": "Operating Expense",
                "annual_cost": 1200,
            }
        ]
    )
    result = allocate_expenses_to_companies(assumptions_df=assumptions, companies=["ACPL", "ACPLHK"])

    assert sorted(result["company"].unique().tolist()) == ["ACPL", "ACPLHK"]
    assert len(result) == 24
    assert result["scenario"].nunique() == 1
    assert result["scenario"].iloc[0] == "Base"
    assert result.groupby("company")["expense"].sum().round(2).tolist() == [1200.0, 1200.0]


def test_allocate_supports_quarterly_end_and_specific_month() -> None:
    assumptions = pd.DataFrame(
        [
            {
                "code": "OPS-100",
                "expense_item": "Compliance",
                "cashflow_item": "Operating Expense",
                "annual_cost": 1200,
                "allocation_method": "quarterly_end",
                "year": 2026,
            },
            {
                "code": "OPS-200",
                "expense_item": "Insurance",
                "cashflow_item": "Operating Expense",
                "annual_cost": 600,
                "allocation_method": "specific_month",
                "allocation_month": 5,
                "year": 2026,
            },
        ]
    )
    result = allocate_expenses_to_companies(assumptions_df=assumptions, companies=["ACPL"])

    q_end = result[result["code"] == "OPS-100"].set_index(result[result["code"] == "OPS-100"]["month"].dt.month)["expense"]
    assert q_end.loc[3] == 300
    assert q_end.loc[6] == 300
    assert q_end.loc[9] == 300
    assert q_end.loc[12] == 300

    specific = result[result["code"] == "OPS-200"].set_index(result[result["code"] == "OPS-200"]["month"].dt.month)["expense"]
    assert specific.loc[5] == 600
    assert specific.sum() == 600


def test_generate_forecast_table_creates_month_columns() -> None:
    assumptions = pd.DataFrame(
        [
            {
                "code": "OPS-RENT",
                "expense_item": "Rent",
                "cashflow_item": "Operating Expense",
                "annual_cost": 12000,
                "allocation_method": "monthly_average",
                "allocation_month": 1,
            }
        ]
    )
    forecast = generate_forecast_table(
        assumptions_df=assumptions,
        company="ACPL",
        end_year=2027,
        annual_growth_pct=10.0,
        start_year=2026,
    )

    assert "2026-01" in forecast.columns
    assert "2027-12" in forecast.columns
    row = forecast.iloc[0]
    assert row["2026-01"] == 1000
    assert round(row["2027-01"], 2) == 1100
