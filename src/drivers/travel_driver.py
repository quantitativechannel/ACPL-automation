from __future__ import annotations

import pandas as pd


OUTPUT_COLUMNS = [
    "scenario_id",
    "entity_id",
    "month",
    "account_code",
    "posting_type",
    "source_module",
    "reference_id",
    "description",
    "amount",
    "role_type",
    "trip_category",
]


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _to_month_str(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y-%m").dt.strftime("%Y-%m")


def _normalize_allocation_pct(series: pd.Series) -> pd.Series:
    pct = series.astype(float)
    return pct.where(pct <= 1.0, pct / 100.0)


def _validate_weights_sum_to_one(weights_df: pd.DataFrame) -> None:
    if weights_df.empty:
        return

    sums = weights_df.groupby(["role_type", "trip_category", "year"], as_index=False)["weight"].sum()
    invalid = sums[~sums["weight"].round(10).eq(1.0)]
    if not invalid.empty:
        raise ValueError("month_weights_df weights must sum to 1 for each role_type/trip_category/year")


def build_travel_postings(
    headcount_df: pd.DataFrame,
    travel_policy_df: pd.DataFrame,
    travel_allocation_df: pd.DataFrame,
    month_weights_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if headcount_df.empty or travel_policy_df.empty or travel_allocation_df.empty:
        return _empty_output()

    headcount = headcount_df.copy()
    headcount["month"] = _to_month_str(headcount["month"])

    policy = travel_policy_df.copy()
    policy["est_trips"] = policy["est_trips"].astype(float)
    policy["cost_per_trip"] = policy["cost_per_trip"].astype(float)

    annual = headcount.merge(policy, on="role_type", how="inner")
    if annual.empty:
        return _empty_output()

    annual["annual_category_cost"] = (
        annual["active_headcount"].astype(float) * annual["est_trips"] * annual["cost_per_trip"]
    )

    if month_weights_df is None:
        annual["monthly_category_cost"] = annual["annual_category_cost"] / 12.0
    else:
        weights = month_weights_df.copy()
        weights["month"] = _to_month_str(weights["month"])
        weights["weight"] = weights["weight"].astype(float)
        weights["year"] = pd.to_datetime(weights["month"], format="%Y-%m").dt.year
        _validate_weights_sum_to_one(weights)

        annual["year"] = pd.to_datetime(annual["month"], format="%Y-%m").dt.year
        annual = annual.merge(weights, on=["role_type", "trip_category", "month", "year"], how="left")
        annual["weight"] = annual["weight"].fillna(0.0)
        annual["monthly_category_cost"] = annual["annual_category_cost"] * annual["weight"]

    allocations = travel_allocation_df.copy()
    allocations["allocation_pct"] = _normalize_allocation_pct(allocations["allocation_pct"])

    postings = annual.merge(allocations, on="trip_category", how="inner")
    if postings.empty:
        return _empty_output()

    postings["amount"] = postings["monthly_category_cost"] * postings["allocation_pct"]
    postings["posting_type"] = "expense"
    postings["source_module"] = "travel"
    postings["reference_id"] = (
        "travel|"
        + postings["scenario_id"].astype(str)
        + "|"
        + postings["entity_id"].astype(str)
        + "|"
        + postings["role_type"].astype(str)
        + "|"
        + postings["trip_category"].astype(str)
        + "|"
        + postings["month"].astype(str)
        + "|"
        + postings["account_code"].astype(str)
    )
    postings["description"] = "Travel expense posting"

    out = postings[OUTPUT_COLUMNS].copy()
    out["amount"] = out["amount"].astype(float)
    out["month"] = _to_month_str(out["month"])
    return out
