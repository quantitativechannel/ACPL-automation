from io import BytesIO

import pandas as pd

from src.budget_engine import (
    BudgetWorkbook,
    allocate_expenses_to_companies,
    default_template,
    export_dashboard_workbook,
    generate_annual_projection,
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

    # 12 months generated for each company in the workbook template (2 companies)
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


def test_generate_annual_projection_grows_only_year_over_year() -> None:
    base_inputs = pd.DataFrame(
        [
            {"item": "Rent", "monthly_budget": 1000, "monthly_expense": 900},
            {"item": "Utilities", "monthly_budget": 200, "monthly_expense": 150},
        ]
    )
    projection = generate_annual_projection(
        base_inputs=base_inputs,
        company="ACPL",
        base_year=2026,
        end_year=2027,
        growth_rate_pct=10.0,
        scenario="Budget",
    )

    assert len(projection) == 48

    rent_2026 = projection[(projection["item"] == "Rent") & (projection["month"].dt.year == 2026)]
    rent_2027 = projection[(projection["item"] == "Rent") & (projection["month"].dt.year == 2027)]
    assert rent_2026["budget"].nunique() == 1
    assert rent_2027["budget"].nunique() == 1
    assert rent_2026["budget"].iloc[0] == 1000
    assert rent_2027["budget"].iloc[0] == 1100
