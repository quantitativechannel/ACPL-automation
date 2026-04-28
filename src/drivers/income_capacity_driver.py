import calendar
import math

import pandas as pd


DEFAULT_COLUMNS = [
    "scenario_id",
    "project_group",
    "month",
    "new_capacity_w",
    "addition_timing_factor",
    "avg_equity_price_per_w",
    "manual_project_count_override",
    "manual_region_count_override",
]


OUTPUT_COLUMNS = [
    "scenario_id",
    "project_group",
    "month",
    "calendar_days",
    "new_capacity_w",
    "addition_timing_factor",
    "month_end_capacity_w",
    "weighted_avg_capacity_w",
    "new_project_count",
    "month_end_project_count",
    "new_region_count",
    "month_end_region_count",
    "jv_equity_new_contribution",
    "jv_equity_cumulative_contribution",
]


def _to_month_period(month_value: object) -> pd.Period:
    return pd.Period(str(month_value), freq="M")


def _region_count_from_project_count(project_count: int) -> int:
    if project_count <= 0:
        return 0
    if project_count == 1:
        return 1
    if project_count == 2:
        return 2
    if project_count <= 6:
        return 3
    return 4


def build_capacity_rollforward(
    capacity_assumptions_df: pd.DataFrame,
    start_month: str,
    end_month: str,
    initial_capacity_w: float = 0,
    initial_project_count: int = 0,
    initial_region_count: int = 0,
    initial_jv_equity_contribution: float = 0,
) -> pd.DataFrame:
    assumptions = capacity_assumptions_df.copy()
    for col in DEFAULT_COLUMNS:
        if col not in assumptions.columns:
            assumptions[col] = pd.NA

    assumptions["month"] = assumptions["month"].map(_to_month_period)
    start_period = pd.Period(start_month, freq="M")
    end_period = pd.Period(end_month, freq="M")

    assumptions = assumptions[(assumptions["month"] >= start_period) & (assumptions["month"] <= end_period)]

    if assumptions.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    assumptions["new_capacity_w"] = pd.to_numeric(assumptions["new_capacity_w"], errors="coerce").fillna(0.0)
    assumptions["addition_timing_factor"] = pd.to_numeric(assumptions["addition_timing_factor"], errors="coerce").fillna(0.0)
    assumptions["avg_equity_price_per_w"] = pd.to_numeric(assumptions["avg_equity_price_per_w"], errors="coerce").fillna(0.0)

    aggregated = (
        assumptions.groupby(["scenario_id", "project_group", "month"], as_index=False)
        .agg(
            {
                "new_capacity_w": "sum",
                "addition_timing_factor": "first",
                "avg_equity_price_per_w": "first",
                "manual_project_count_override": "last",
                "manual_region_count_override": "last",
            }
        )
        .sort_values(["scenario_id", "project_group", "month"])
    )

    month_index = pd.period_range(start=start_period, end=end_period, freq="M")
    records: list[dict] = []

    for (scenario_id, project_group), group_df in aggregated.groupby(["scenario_id", "project_group"], dropna=False):
        group_df = group_df.set_index("month").reindex(month_index)
        group_df["scenario_id"] = scenario_id
        group_df["project_group"] = project_group
        group_df["new_capacity_w"] = group_df["new_capacity_w"].fillna(0.0)
        group_df["addition_timing_factor"] = group_df["addition_timing_factor"].fillna(0.0)
        group_df["avg_equity_price_per_w"] = group_df["avg_equity_price_per_w"].fillna(0.0)

        prior_capacity = float(initial_capacity_w)
        prior_project_count = int(initial_project_count)
        prior_region_count = int(initial_region_count)
        prior_jv_contribution = float(initial_jv_equity_contribution)

        for month, row in group_df.iterrows():
            new_capacity = float(row["new_capacity_w"])
            timing_factor = float(row["addition_timing_factor"])

            month_end_capacity = prior_capacity + new_capacity
            weighted_avg_capacity = prior_capacity + (new_capacity * timing_factor)

            new_project_count = 0 if new_capacity == 0 else int(math.ceil(new_capacity / 100.0))
            if pd.notna(row["manual_project_count_override"]):
                month_end_project_count = int(row["manual_project_count_override"])
            else:
                month_end_project_count = prior_project_count + new_project_count

            if pd.notna(row["manual_region_count_override"]):
                month_end_region_count = int(row["manual_region_count_override"])
            else:
                month_end_region_count = _region_count_from_project_count(month_end_project_count)

            new_region_count = month_end_region_count - prior_region_count

            jv_equity_new = new_capacity * float(row["avg_equity_price_per_w"])
            jv_equity_cumulative = prior_jv_contribution + jv_equity_new

            records.append(
                {
                    "scenario_id": scenario_id,
                    "project_group": project_group,
                    "month": month.strftime("%Y-%m"),
                    "calendar_days": calendar.monthrange(month.year, month.month)[1],
                    "new_capacity_w": new_capacity,
                    "addition_timing_factor": timing_factor,
                    "month_end_capacity_w": month_end_capacity,
                    "weighted_avg_capacity_w": weighted_avg_capacity,
                    "new_project_count": new_project_count,
                    "month_end_project_count": month_end_project_count,
                    "new_region_count": new_region_count,
                    "month_end_region_count": month_end_region_count,
                    "jv_equity_new_contribution": jv_equity_new,
                    "jv_equity_cumulative_contribution": jv_equity_cumulative,
                }
            )

            prior_capacity = month_end_capacity
            prior_project_count = month_end_project_count
            prior_region_count = month_end_region_count
            prior_jv_contribution = jv_equity_cumulative

    result = pd.DataFrame.from_records(records)
    return result[OUTPUT_COLUMNS].sort_values(["scenario_id", "project_group", "month"]).reset_index(drop=True)
