from __future__ import annotations

import pandas as pd

from .constants import TRIP_CATEGORIES


def sync_trip_type_config(people_df: pd.DataFrame, trip_config_df: pd.DataFrame | None = None) -> pd.DataFrame:
    people = people_df.copy()
    people.columns = [str(c).strip().lower() for c in people.columns]
    if "type" not in people.columns:
        return pd.DataFrame(columns=["type", "category", "est_trips", "cost_per_trip"])

    ordered_types: list[str] = []
    seen_types: set[str] = set()
    for raw_type in people["type"].fillna("").astype(str):
        type_value = raw_type.strip()
        if type_value and type_value not in seen_types:
            seen_types.add(type_value)
            ordered_types.append(type_value)

    if not ordered_types:
        return pd.DataFrame(columns=["type", "category", "est_trips", "cost_per_trip"])

    existing = trip_config_df.copy() if trip_config_df is not None else pd.DataFrame()
    existing.columns = [str(c).strip().lower() for c in existing.columns]
    for column in ["type", "category", "est_trips", "cost_per_trip"]:
        if column not in existing.columns:
            existing[column] = pd.Series(dtype="object" if column in {"type", "category"} else "float64")

    existing = existing[["type", "category", "est_trips", "cost_per_trip"]].copy()
    existing["type"] = existing["type"].fillna("").astype(str).str.strip()
    existing["category"] = existing["category"].fillna("").astype(str).str.strip()
    existing["est_trips"] = pd.to_numeric(existing["est_trips"], errors="coerce").fillna(0.0)
    existing["cost_per_trip"] = pd.to_numeric(existing["cost_per_trip"], errors="coerce").fillna(0.0)
    existing = existing[(existing["type"] != "") & (existing["category"] != "")]
    existing = existing.drop_duplicates(subset=["type", "category"], keep="first")

    template = pd.DataFrame(
        [{"type": type_value, "category": category} for type_value in ordered_types for category in TRIP_CATEGORIES]
    )
    synced = template.merge(existing, on=["type", "category"], how="left")
    synced["est_trips"] = synced["est_trips"].fillna(0.0)
    synced["cost_per_trip"] = synced["cost_per_trip"].fillna(0.0)
    return synced[["type", "category", "est_trips", "cost_per_trip"]]


def build_travel_assumptions_from_people(
    people_df: pd.DataFrame,
    trip_config_df: pd.DataFrame,
    allocation_df: pd.DataFrame,
    master_config_df: pd.DataFrame | None = None,
    scenario: str = "Base",
    year: int | None = None,
) -> pd.DataFrame:
    if year is None:
        year = pd.Timestamp.today().year

    people = people_df.copy()
    people.columns = [str(c).strip().lower() for c in people.columns]
    people = people.rename(columns={"person": "name"})
    required_people = {"name", "location", "company", "base_salary", "type"}
    missing_people = required_people.difference(people.columns)
    if missing_people:
        raise ValueError(f"People table missing required columns: {', '.join(sorted(missing_people))}")

    people["company"] = people["company"].astype(str).str.strip()
    people["type"] = people["type"].astype(str).str.strip()
    people = people[(people["company"] != "") & (people["type"] != "")]
    if people.empty:
        return pd.DataFrame()

    trip_cfg = trip_config_df.copy()
    trip_cfg.columns = [str(c).strip().lower() for c in trip_cfg.columns]
    required_trip = {"type", "category", "est_trips", "cost_per_trip"}
    missing_trip = required_trip.difference(trip_cfg.columns)
    if missing_trip:
        raise ValueError(f"Trip configuration missing columns: {', '.join(sorted(missing_trip))}")
    trip_cfg = trip_cfg[list(required_trip)].copy()
    trip_cfg["type"] = trip_cfg["type"].astype(str).str.strip()
    trip_cfg["category"] = trip_cfg["category"].astype(str).str.strip()
    trip_cfg["est_trips"] = pd.to_numeric(trip_cfg["est_trips"], errors="coerce").fillna(0.0)
    trip_cfg["cost_per_trip"] = pd.to_numeric(trip_cfg["cost_per_trip"], errors="coerce").fillna(0.0)
    trip_cfg = trip_cfg[(trip_cfg["type"] != "") & (trip_cfg["category"] != "")]

    alloc_cfg = allocation_df.copy()
    alloc_cfg.columns = [str(c).strip().lower() for c in alloc_cfg.columns]
    required_alloc = {"category", "expense_item", "allocation_pct"}
    missing_alloc = required_alloc.difference(alloc_cfg.columns)
    if missing_alloc:
        raise ValueError(f"Allocation configuration missing columns: {', '.join(sorted(missing_alloc))}")
    alloc_cfg = alloc_cfg[list(required_alloc)].copy()
    alloc_cfg["category"] = alloc_cfg["category"].astype(str).str.strip()
    alloc_cfg["expense_item"] = alloc_cfg["expense_item"].astype(str).str.strip()
    alloc_cfg["allocation_pct"] = pd.to_numeric(alloc_cfg["allocation_pct"], errors="coerce").fillna(0.0)
    alloc_cfg = alloc_cfg[(alloc_cfg["category"] != "") & (alloc_cfg["expense_item"] != "")]

    if trip_cfg.empty or alloc_cfg.empty:
        return pd.DataFrame()

    headcount = people.groupby(["company", "type"], as_index=False).agg(headcount=("name", "count"))
    cost_by_category = headcount.merge(trip_cfg, on="type", how="inner")
    if cost_by_category.empty:
        return pd.DataFrame()

    cost_by_category["annual_category_cost"] = (
        cost_by_category["headcount"] * cost_by_category["est_trips"] * cost_by_category["cost_per_trip"]
    )
    company_item_cost = cost_by_category.merge(alloc_cfg, on="category", how="inner")
    if company_item_cost.empty:
        return pd.DataFrame()

    company_item_cost["annual_cost"] = company_item_cost["annual_category_cost"] * (
        company_item_cost["allocation_pct"] / 100.0
    )
    annualized = (
        company_item_cost.groupby(["company", "expense_item"], as_index=False)
        .agg(annual_cost=("annual_cost", "sum"))
        .sort_values(["company", "expense_item"])
    )

    config_lookup = pd.DataFrame(columns=["expense_item", "code", "cashflow_item"])
    if master_config_df is not None and not master_config_df.empty:
        cfg = master_config_df.copy()
        cfg.columns = [str(c).strip().lower() for c in cfg.columns]
        cfg["expense_item"] = cfg["expense_item"].astype(str).str.strip()
        config_lookup = (
            cfg[["expense_item", "code", "cashflow_item"]].drop_duplicates(subset=["expense_item"], keep="first").copy()
        )

    annualized = annualized.merge(config_lookup, on="expense_item", how="left")
    generated_code = annualized["expense_item"].str.upper().str.replace(r"[^A-Z0-9]+", "_", regex=True).str.strip("_")
    annualized["code"] = annualized["code"].fillna("TRAVEL_" + generated_code)
    annualized["cashflow_item"] = annualized["cashflow_item"].fillna("Operating Expense")
    annualized["scenario"] = scenario
    annualized["year"] = int(year)
    annualized["allocation_method"] = "monthly_average"
    annualized["allocation_month"] = 1

    return annualized[
        [
            "company",
            "code",
            "expense_item",
            "cashflow_item",
            "scenario",
            "year",
            "annual_cost",
            "allocation_method",
            "allocation_month",
        ]
    ]
