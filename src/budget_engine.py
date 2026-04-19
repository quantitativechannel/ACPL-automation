from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd

REQUIRED_COLUMNS = {
    "company",
    "code",
    "expense_item",
    "cashflow_item",
    "scenario",
    "month",
    "annual_cost",
    "allocation_method",
    "allocation_month",
    "expense",
}

ALLOCATION_METHODS = {"monthly_average", "quarterly", "particular_month"}


@dataclass
class BudgetWorkbook:
    expenses: pd.DataFrame

    @classmethod
    def from_excel(cls, file: BinaryIO | BytesIO) -> "BudgetWorkbook":
        raw = pd.read_excel(file, sheet_name="Expenses")
        normalized = _normalize_expenses(raw)
        return cls(expenses=normalized)

    def apply_company_updates(self, company: str, edited_company_df: pd.DataFrame) -> None:
        remainder = self.expenses[self.expenses["company"] != company].copy()
        updated_company = _normalize_expenses(edited_company_df)
        self.expenses = pd.concat([remainder, updated_company], ignore_index=True)

    def upload_expense_assumptions(self, assumptions_df: pd.DataFrame) -> None:
        required = {"code", "expense_item", "cashflow_item", "scenario", "annual_cost", "allocation_method"}
        assumptions = assumptions_df.copy()
        assumptions.columns = [str(c).strip().lower() for c in assumptions.columns]
        missing = required.difference(assumptions.columns)
        if missing:
            missing_str = ", ".join(sorted(missing))
            raise ValueError(f"Expense upload is missing required columns: {missing_str}")

        if "year" not in assumptions.columns:
            assumptions["year"] = pd.Timestamp.today().year
        if "allocation_month" not in assumptions.columns:
            assumptions["allocation_month"] = 1

        scenarios = assumptions["scenario"].astype(str).str.strip().unique().tolist()
        if not scenarios:
            raise ValueError("Expense upload must contain at least one scenario.")

        companies = sorted(self.expenses["company"].dropna().astype(str).str.strip().unique().tolist())
        if not companies:
            raise ValueError("No subsidiaries/companies found in current workbook.")

        expanded_rows: list[dict] = []
        for company in companies:
            company_rows = assumptions.copy()
            company_rows["company"] = company
            expanded_rows.extend(_expand_annual_rows(company_rows).to_dict("records"))

        uploaded = _normalize_expenses(pd.DataFrame(expanded_rows))
        self.expenses = pd.concat([self.expenses, uploaded], ignore_index=True).sort_values(
            ["company", "scenario", "month", "code", "expense_item"]
        )

    def company_summary(self, scenarios: list[str]) -> pd.DataFrame:
        scoped = self.expenses[self.expenses["scenario"].isin(scenarios)].copy()
        grouped = (
            scoped.groupby(["company", "scenario", "month"], as_index=False)
            .agg(expense=("expense", "sum"))
            .sort_values(["company", "scenario", "month"])
        )
        return grouped

    def consolidated_summary(self, scenarios: list[str]) -> pd.DataFrame:
        scoped = self.expenses[self.expenses["scenario"].isin(scenarios)].copy()
        grouped = (
            scoped.groupby(["scenario", "month"], as_index=False)
            .agg(expense=("expense", "sum"))
            .sort_values(["scenario", "month"])
        )
        grouped["net_flow"] = -grouped["expense"]
        return grouped

    def cash_flow(self, scenarios: list[str], opening_cash: float = 0.0) -> pd.DataFrame:
        consolidated = self.consolidated_summary(scenarios)

        def add_running_balance(frame: pd.DataFrame) -> pd.DataFrame:
            frame = frame.sort_values("month").copy()
            frame["closing_cash"] = opening_cash + frame["net_flow"].cumsum()
            return frame

        return consolidated.groupby("scenario", group_keys=False).apply(add_running_balance).reset_index(drop=True)

    def scenario_reports(self, scenarios: list[str], opening_cash: float = 0.0) -> dict[str, pd.DataFrame]:
        cash = self.cash_flow(scenarios, opening_cash)
        reports: dict[str, pd.DataFrame] = {}
        for scenario in scenarios:
            scenario_cash = cash[cash["scenario"] == scenario]
            reports[scenario] = scenario_cash[["month", "expense", "net_flow", "closing_cash"]].copy()
        return reports


def _normalize_expenses(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    if "item" in df.columns and "expense_item" not in df.columns:
        df["expense_item"] = df["item"]
    if "person" in df.columns and "code" not in df.columns:
        df["code"] = df["person"]
    if "cashflow_item" not in df.columns:
        df["cashflow_item"] = "Operating Expense"
    if "annual_cost" not in df.columns and "expense" in df.columns:
        df["annual_cost"] = pd.to_numeric(df["expense"], errors="coerce").fillna(0.0)
    if "allocation_method" not in df.columns:
        df["allocation_method"] = "particular_month"
    if "allocation_month" not in df.columns:
        month_source = pd.to_datetime(df.get("month"), errors="coerce")
        df["allocation_month"] = month_source.dt.month.fillna(1).astype(int)

    if "year" not in df.columns:
        month_source = pd.to_datetime(df.get("month"), errors="coerce")
        df["year"] = month_source.dt.year.fillna(pd.Timestamp.today().year).astype(int)

    if "expense" not in df.columns:
        expanded = _expand_annual_rows(df)
    else:
        expanded = df.copy()

    missing = REQUIRED_COLUMNS.difference(expanded.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Expenses sheet is missing required columns: {missing_str}")

    expanded = expanded[list(REQUIRED_COLUMNS)].copy()
    expanded["month"] = pd.to_datetime(expanded["month"]).dt.to_period("M").dt.to_timestamp()
    expanded["annual_cost"] = pd.to_numeric(expanded["annual_cost"], errors="coerce").fillna(0.0)
    expanded["allocation_month"] = pd.to_numeric(expanded["allocation_month"], errors="coerce").fillna(1).astype(int)
    expanded["expense"] = pd.to_numeric(expanded["expense"], errors="coerce").fillna(0.0)

    for text_col in ["company", "code", "expense_item", "cashflow_item", "scenario", "allocation_method"]:
        expanded[text_col] = expanded[text_col].astype(str).str.strip()

    return expanded.sort_values(["company", "scenario", "month", "code", "expense_item"]).reset_index(drop=True)


def _expand_annual_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in df.iterrows():
        method = str(row["allocation_method"]).strip().lower()
        if method not in ALLOCATION_METHODS:
            raise ValueError(
                f"Unsupported allocation_method '{method}'. Use one of: {', '.join(sorted(ALLOCATION_METHODS))}."
            )

        annual = float(pd.to_numeric(row["annual_cost"], errors="coerce") or 0.0)
        year = int(pd.to_numeric(row.get("year", pd.Timestamp.today().year), errors="coerce") or pd.Timestamp.today().year)
        alloc_month = int(pd.to_numeric(row.get("allocation_month", 1), errors="coerce") or 1)

        months = pd.date_range(f"{year}-01-01", periods=12, freq="MS")
        expense_by_month = {m: 0.0 for m in months}

        if method == "monthly_average":
            monthly_value = annual / 12.0
            for m in months:
                expense_by_month[m] = monthly_value
        elif method == "quarterly":
            quarter_months = [1, 4, 7, 10]
            quarterly_value = annual / 4.0
            for m in months:
                if m.month in quarter_months:
                    expense_by_month[m] = quarterly_value
        else:
            for m in months:
                if m.month == alloc_month:
                    expense_by_month[m] = annual

        for m in months:
            rows.append(
                {
                    "company": row["company"],
                    "code": row["code"],
                    "expense_item": row["expense_item"],
                    "cashflow_item": row["cashflow_item"],
                    "scenario": row["scenario"],
                    "month": m,
                    "annual_cost": annual,
                    "allocation_method": method,
                    "allocation_month": alloc_month,
                    "expense": expense_by_month[m],
                }
            )

    return pd.DataFrame(rows)


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
                "allocation_method": "quarterly",
                "allocation_month": 1,
            },
        ]
    )
    normalized = _normalize_expenses(template)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        normalized.to_excel(writer, sheet_name="Expenses", index=False)
    return output.getvalue()


def generate_annual_projection(
    base_inputs: pd.DataFrame,
    company: str,
    base_year: int,
    end_year: int,
    growth_rate_pct: float,
    scenario: str = "Base",
) -> pd.DataFrame:
    required_columns = {"item", "monthly_budget", "monthly_expense"}
    missing = required_columns.difference(base_inputs.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Projection input is missing required columns: {missing_str}")

    if end_year < base_year:
        raise ValueError("Projection end year must be greater than or equal to base year.")

    normalized = base_inputs.copy()
    normalized["item"] = normalized["item"].astype(str).str.strip()
    normalized["monthly_budget"] = pd.to_numeric(normalized["monthly_budget"], errors="coerce").fillna(0.0)
    normalized["monthly_expense"] = pd.to_numeric(normalized["monthly_expense"], errors="coerce").fillna(0.0)
    normalized = normalized[normalized["item"] != ""].drop_duplicates(subset=["item"]).reset_index(drop=True)

    growth_multiplier = 1 + (growth_rate_pct / 100.0)
    records: list[dict[str, object]] = []

    for _, row in normalized.iterrows():
        for year in range(base_year, end_year + 1):
            years_from_base = year - base_year
            multiplier = growth_multiplier**years_from_base
            budget_for_year = float(row["monthly_budget"]) * multiplier
            expense_for_year = float(row["monthly_expense"]) * multiplier

            for month in range(1, 13):
                records.append(
                    {
                        "company": company,
                        "person": "N/A",
                        "item": row["item"],
                        "scenario": scenario,
                        "month": pd.Timestamp(year=year, month=month, day=1),
                        "budget": round(budget_for_year, 2),
                        "expense": round(expense_for_year, 2),
                    }
                )

    projected = pd.DataFrame.from_records(records)
    return _normalize_expenses(projected)
