from __future__ import annotations

import pandas as pd

from .allocation import _expand_annual_rows
from .constants import REQUIRED_COLUMNS


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
        df["allocation_method"] = "specific_month"
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
