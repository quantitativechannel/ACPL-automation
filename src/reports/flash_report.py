from __future__ import annotations

import pandas as pd

from src.reports.budget_reports import _build_budget_report


def build_flash_report(
    actual_postings_df: pd.DataFrame,
    budget_postings_df: pd.DataFrame,
    account_map_df: pd.DataFrame,
    report_lines_df: pd.DataFrame,
    selected_month: str,
    entity_id: str | None = None,
) -> pd.DataFrame:
    actual_scenario = actual_postings_df["scenario_id"].dropna().iloc[0] if (not actual_postings_df.empty and "scenario_id" in actual_postings_df.columns and actual_postings_df["scenario_id"].notna().any()) else "ACTUAL"
    budget_scenario = budget_postings_df["scenario_id"].dropna().iloc[0] if (not budget_postings_df.empty and "scenario_id" in budget_postings_df.columns and budget_postings_df["scenario_id"].notna().any()) else "BUDGET"

    actual = _build_budget_report(actual_postings_df, account_map_df, report_lines_df, actual_scenario, selected_month, entity_id=entity_id)
    budget = _build_budget_report(budget_postings_df, account_map_df, report_lines_df, budget_scenario, selected_month, entity_id=entity_id)

    out = actual[["line_code", "line_name", "section_name", "display_order", "sign_convention"]].copy()
    out = out.merge(
        budget[["line_code", "month_amount", "ytd_amount"]].rename(columns={"month_amount": "month_budget", "ytd_amount": "ytd_budget"}),
        on="line_code",
        how="left",
    )
    out = out.merge(
        actual[["line_code", "month_amount", "ytd_amount"]].rename(columns={"month_amount": "month_actual", "ytd_amount": "ytd_actual"}),
        on="line_code",
        how="left",
    )

    for col in ["month_budget", "month_actual", "ytd_budget", "ytd_actual"]:
        out[col] = out[col].fillna(0.0)

    out["month_variance"] = out["month_actual"] - out["month_budget"]
    out["ytd_variance"] = out["ytd_actual"] - out["ytd_budget"]

    return out[[
        "line_code",
        "line_name",
        "section_name",
        "display_order",
        "sign_convention",
        "month_budget",
        "month_actual",
        "month_variance",
        "ytd_budget",
        "ytd_actual",
        "ytd_variance",
    ]]
