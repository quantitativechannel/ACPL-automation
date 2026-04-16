from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd

REQUIRED_COLUMNS = {
    "company",
    "person",
    "item",
    "scenario",
    "month",
    "budget",
    "expense",
}


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

    def company_summary(self, scenarios: list[str]) -> pd.DataFrame:
        scoped = self.expenses[self.expenses["scenario"].isin(scenarios)].copy()
        grouped = (
            scoped.groupby(["company", "scenario", "month"], as_index=False)
            .agg(budget=("budget", "sum"), expense=("expense", "sum"))
            .sort_values(["company", "scenario", "month"])
        )
        grouped["variance"] = grouped["budget"] - grouped["expense"]
        return grouped

    def consolidated_summary(self, scenarios: list[str]) -> pd.DataFrame:
        scoped = self.expenses[self.expenses["scenario"].isin(scenarios)].copy()
        grouped = (
            scoped.groupby(["scenario", "month"], as_index=False)
            .agg(budget=("budget", "sum"), expense=("expense", "sum"))
            .sort_values(["scenario", "month"])
        )
        grouped["net_flow"] = grouped["budget"] - grouped["expense"]
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
            reports[scenario] = scenario_cash[["month", "budget", "expense", "net_flow", "closing_cash"]].copy()
        return reports


def _normalize_expenses(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Expenses sheet is missing required columns: {missing_str}")

    df = df[list(REQUIRED_COLUMNS)].copy()
    df["month"] = pd.to_datetime(df["month"]).dt.to_period("M").dt.to_timestamp()
    df["budget"] = pd.to_numeric(df["budget"], errors="coerce").fillna(0.0)
    df["expense"] = pd.to_numeric(df["expense"], errors="coerce").fillna(0.0)

    for text_col in ["company", "person", "item", "scenario"]:
        df[text_col] = df[text_col].astype(str).str.strip()

    return df.sort_values(["company", "scenario", "month", "item", "person"]).reset_index(drop=True)


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
                "person": "Jane Doe",
                "item": "Marketing",
                "scenario": "Base",
                "month": "2026-01-01",
                "budget": 20000,
                "expense": 18000,
            },
            {
                "company": "Company A",
                "person": "Jane Doe",
                "item": "Marketing",
                "scenario": "Conservative",
                "month": "2026-01-01",
                "budget": 18000,
                "expense": 17000,
            },
        ]
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        template.to_excel(writer, sheet_name="Expenses", index=False)
    return output.getvalue()
