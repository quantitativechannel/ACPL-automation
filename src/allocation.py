from __future__ import annotations

import pandas as pd

from .constants import ALLOCATION_METHODS, EXPENSE_UPLOAD_REQUIRED


def allocate_expenses_to_companies(assumptions_df: pd.DataFrame, companies: list[str]) -> pd.DataFrame:
    assumptions = assumptions_df.copy()
    assumptions.columns = [str(c).strip().lower() for c in assumptions.columns]
    missing = EXPENSE_UPLOAD_REQUIRED.difference(assumptions.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Expense upload is missing required columns: {missing_str}")

    assumptions["code"] = assumptions["code"].astype(str).str.strip()
    assumptions["expense_item"] = assumptions["expense_item"].astype(str).str.strip()
    assumptions["cashflow_item"] = assumptions["cashflow_item"].astype(str).str.strip()
    assumptions = assumptions[(assumptions["code"] != "") & (assumptions["expense_item"] != "")]
    if assumptions.empty:
        raise ValueError("Expense upload does not contain any valid rows.")

    if "scenario" not in assumptions.columns:
        assumptions["scenario"] = "Base"
    if "annual_cost" not in assumptions.columns:
        assumptions["annual_cost"] = 0.0
    if "allocation_method" not in assumptions.columns:
        assumptions["allocation_method"] = "monthly_average"
    if "year" not in assumptions.columns:
        assumptions["year"] = pd.Timestamp.today().year
    if "allocation_month" not in assumptions.columns:
        assumptions["allocation_month"] = 1

    expanded_rows: list[dict] = []
    for company in companies:
        company_rows = assumptions.copy()
        company_rows["company"] = company
        expanded_rows.extend(_expand_annual_rows(company_rows).to_dict("records"))

    from .normalization import _normalize_expenses

    return _normalize_expenses(pd.DataFrame(expanded_rows))


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
        alloc_month_val = pd.to_numeric(row.get("allocation_month", 1), errors="coerce")
        if pd.isna(alloc_month_val):
            alloc_month_val = 1
        alloc_month = int(alloc_month_val)
        alloc_month = min(max(1, alloc_month), 12)

        months = pd.date_range(f"{year}-01-01", periods=12, freq="MS")
        expense_by_month = {m: 0.0 for m in months}

        if method == "monthly_average":
            monthly_value = annual / 12.0
            for m in months:
                expense_by_month[m] = monthly_value
        elif method in {"quarterly", "quarterly_start"}:
            quarter_months = [1, 4, 7, 10]
            quarterly_value = annual / 4.0
            for m in months:
                if m.month in quarter_months:
                    expense_by_month[m] = quarterly_value
        elif method == "quarterly_end":
            quarter_months = [3, 6, 9, 12]
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
