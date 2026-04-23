from __future__ import annotations

import pandas as pd

from .allocation import _expand_annual_rows
from .constants import EXPENSE_UPLOAD_REQUIRED


def generate_forecast_table(
    assumptions_df: pd.DataFrame,
    company: str,
    end_year: int,
    annual_growth_pct: float,
    start_year: int | None = None,
) -> pd.DataFrame:
    start_year = start_year or pd.Timestamp.today().year
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    base = assumptions_df.copy()
    base.columns = [str(c).strip().lower() for c in base.columns]

    missing = EXPENSE_UPLOAD_REQUIRED.difference(base.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Forecast source is missing required columns: {missing_str}")

    if "annual_cost" not in base.columns:
        base["annual_cost"] = 0.0
    if "allocation_method" not in base.columns:
        base["allocation_method"] = "monthly_average"
    if "allocation_month" not in base.columns:
        base["allocation_month"] = 1

    base["annual_cost"] = pd.to_numeric(base["annual_cost"], errors="coerce").fillna(0.0)
    growth_factor = 1 + (annual_growth_pct / 100.0)

    long_rows: list[dict] = []
    for year in range(start_year, end_year + 1):
        year_multiplier = growth_factor ** (year - start_year)
        yearly = base.copy()
        yearly["company"] = company
        yearly["scenario"] = "Forecast"
        yearly["year"] = year
        yearly["annual_cost"] = yearly["annual_cost"] * year_multiplier
        allocated = _expand_annual_rows(yearly)
        long_rows.extend(allocated.to_dict("records"))

    long_df = pd.DataFrame(long_rows)
    if long_df.empty:
        return pd.DataFrame()

    long_df["month_label"] = pd.to_datetime(long_df["month"]).dt.strftime("%Y-%m")
    detail_cols = ["company", "code", "expense_item", "cashflow_item", "allocation_method", "allocation_month"]
    wide = (
        long_df.pivot_table(index=detail_cols, columns="month_label", values="expense", aggfunc="sum", fill_value=0.0)
        .reset_index()
        .sort_values(["code", "expense_item"])
    )
    annual_lookup = (
        base[["code", "expense_item", "annual_cost"]]
        .drop_duplicates(subset=["code", "expense_item"], keep="last")
        .rename(columns={"annual_cost": "annual_cost_assumption"})
    )
    wide = wide.merge(annual_lookup, on=["code", "expense_item"], how="left")
    ordered = [
        "company",
        "code",
        "expense_item",
        "cashflow_item",
        "annual_cost_assumption",
        "allocation_method",
        "allocation_month",
    ]
    month_cols = [c for c in wide.columns if c not in ordered]
    wide = wide[ordered + month_cols]
    wide.columns.name = None
    return wide
