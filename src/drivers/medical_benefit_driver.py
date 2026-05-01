from __future__ import annotations

import pandas as pd


POSTING_COLUMNS = [
    "scenario_id",
    "entity_id",
    "month",
    "account_code",
    "posting_type",
    "source_module",
    "reference_id",
    "description",
    "amount",
    "benefit_type",
]


SUPPORTED_BASIS_TYPES = {
    "monthly_fixed",
    "annual_spread",
    "annual_specific_month",
    "per_head_monthly",
    "custom_start_end_spread",
}


def _to_month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M")


def _month_range(start: pd.Period, end: pd.Period) -> pd.PeriodIndex:
    return pd.period_range(start=start, end=end, freq="M")


def build_medical_benefit_postings(
    assumptions_df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")

    if assumptions_df.empty:
        return pd.DataFrame(columns=POSTING_COLUMNS)

    assumptions = assumptions_df.copy()
    assumptions["start_period"] = _to_month_period(assumptions["start_date"])
    assumptions["end_period"] = _to_month_period(assumptions["end_date"])
    assumptions["allocation_period"] = pd.to_datetime(
        assumptions["allocation_month"].astype(str), format="%Y-%m", errors="coerce"
    ).dt.to_period("M")

    unsupported = sorted(set(assumptions["basis_type"].dropna()) - SUPPORTED_BASIS_TYPES)
    if unsupported:
        raise ValueError(f"Unsupported basis_type values: {unsupported}")

    assumptions["annual_cost"] = assumptions["annual_cost"].fillna(0.0).astype(float)
    assumptions["monthly_cost"] = assumptions["monthly_cost"].fillna(0.0).astype(float)
    assumptions["headcount"] = assumptions["headcount"].fillna(0.0).astype(float)

    postings: list[dict] = []

    for idx, row in assumptions.iterrows():
        row_start = row["start_period"] if pd.notna(row["start_period"]) else start
        row_end = row["end_period"] if pd.notna(row["end_period"]) else end

        active_start = max(start, row_start)
        active_end = min(end, row_end)

        if active_start > active_end:
            continue

        basis = row["basis_type"]
        description = row.get("description", "")

        if basis == "monthly_fixed":
            months = _month_range(active_start, active_end)
            amount_by_month = {m: row["monthly_cost"] for m in months}
        elif basis == "annual_spread":
            months = _month_range(active_start, active_end)
            amount_by_month = {m: row["annual_cost"] / 12.0 for m in months}
        elif basis == "annual_specific_month":
            alloc = row["allocation_period"]
            amount_by_month = {}
            if pd.notna(alloc) and active_start <= alloc <= active_end:
                amount_by_month[alloc] = row["annual_cost"]
        elif basis == "per_head_monthly":
            months = _month_range(active_start, active_end)
            amount_by_month = {m: row["monthly_cost"] * row["headcount"] for m in months}
        else:  # custom_start_end_spread
            months = _month_range(active_start, active_end)
            spread_amount = row["annual_cost"] / len(months)
            amount_by_month = {m: spread_amount for m in months}

        for month_period, amount in amount_by_month.items():
            if amount == 0:
                continue
            postings.append(
                {
                    "scenario_id": row["scenario_id"],
                    "entity_id": row["entity_id"],
                    "month": str(month_period),
                    "account_code": row["account_code"],
                    "posting_type": "expense",
                    "source_module": "medical_benefit",
                    "reference_id": f"medical_benefit:{idx}",
                    "description": description,
                    "amount": float(amount),
                    "benefit_type": row["benefit_type"],
                }
            )

    if not postings:
        return pd.DataFrame(columns=POSTING_COLUMNS)

    return pd.DataFrame(postings, columns=POSTING_COLUMNS).sort_values(
        ["scenario_id", "entity_id", "month", "account_code"]
    ).reset_index(drop=True)
