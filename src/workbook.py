from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from .allocation import allocate_expenses_to_companies
from .consolidation import cash_flow, company_summary, consolidated_summary, scenario_reports
from .normalization import _normalize_expenses


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
        companies = sorted(self.expenses["company"].dropna().astype(str).str.strip().unique().tolist())
        if not companies:
            raise ValueError("No subsidiaries/companies found in current workbook.")

        uploaded = allocate_expenses_to_companies(assumptions_df=assumptions_df, companies=companies)
        self.expenses = pd.concat([self.expenses, uploaded], ignore_index=True).sort_values(
            ["company", "scenario", "month", "code", "expense_item"]
        )

    def company_summary(self, scenarios: list[str]) -> pd.DataFrame:
        return company_summary(self.expenses, scenarios)

    def consolidated_summary(self, scenarios: list[str]) -> pd.DataFrame:
        return consolidated_summary(self.expenses, scenarios)

    def cash_flow(self, scenarios: list[str], opening_cash: float = 0.0) -> pd.DataFrame:
        return cash_flow(self.expenses, scenarios, opening_cash)

    def scenario_reports(self, scenarios: list[str], opening_cash: float = 0.0) -> dict[str, pd.DataFrame]:
        return scenario_reports(self.expenses, scenarios, opening_cash)
