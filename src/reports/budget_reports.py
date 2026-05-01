from __future__ import annotations

import pandas as pd


def _ensure_month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y-%m", errors="coerce").dt.to_period("M")


def _normalize_postings(postings_df: pd.DataFrame) -> pd.DataFrame:
    if postings_df.empty:
        return pd.DataFrame(
            columns=[
                "scenario_id",
                "entity_id",
                "entity_code",
                "month",
                "account_code",
                "posting_type",
                "amount",
            ]
        )

    work = postings_df.copy()
    for col in ["scenario_id", "entity_id", "entity_code", "month", "account_code", "posting_type", "amount"]:
        if col not in work.columns:
            work[col] = pd.NA

    work["month"] = _ensure_month_period(work["month"])
    work = work[work["month"].notna()].copy()
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0)

    allowed_types = {"revenue_recognition", "expense"}
    work = work[work["posting_type"].isin(allowed_types)].copy()
    return work


def _normalize_report_lines(report_lines_df: pd.DataFrame) -> pd.DataFrame:
    cols = ["line_code", "line_name", "section_name", "display_order", "sign_convention"]
    lines = report_lines_df.copy()
    for col in cols:
        if col not in lines.columns:
            lines[col] = pd.NA
    lines["display_order"] = pd.to_numeric(lines["display_order"], errors="coerce")
    return lines[cols]


def _apply_sign(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    reverse = out["sign_convention"].fillna("normal").eq("reverse")
    out.loc[reverse, ["month_amount", "ytd_amount"]] = out.loc[reverse, ["month_amount", "ytd_amount"]] * -1
    return out


def _period_years(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype="int64", index=series.index)
    return pd.Series(pd.PeriodIndex(series, freq="M").year, index=series.index)


def _build_budget_report(postings_df: pd.DataFrame, account_map_df: pd.DataFrame, report_lines_df: pd.DataFrame, scenario_id: str, selected_month: str, entity_id: str | None = None) -> pd.DataFrame:
    selected_period = pd.Period(selected_month, freq="M")

    postings = _normalize_postings(postings_df)
    postings = postings[postings["scenario_id"] == scenario_id].copy()
    if entity_id is not None:
        key = "entity_id" if "entity_id" in postings.columns else "entity_code"
        postings = postings[postings[key] == entity_id].copy()

    mapped = postings.merge(account_map_df[["account_code", "report_line_name"]], on="account_code", how="left")
    mapped = mapped[mapped["report_line_name"].notna()].copy()

    in_month = mapped[mapped["month"] == selected_period].groupby("report_line_name", as_index=False)["amount"].sum().rename(columns={"amount": "month_amount"})
    ytd = mapped[(mapped["month"] <= selected_period) & (_period_years(mapped["month"]) == selected_period.year)].groupby("report_line_name", as_index=False)["amount"].sum().rename(columns={"amount": "ytd_amount"})

    lines = _normalize_report_lines(report_lines_df)
    merged = lines.merge(in_month, left_on="line_name", right_on="report_line_name", how="left")
    merged = merged.merge(ytd, left_on="line_name", right_on="report_line_name", how="left", suffixes=("", "_ytd"))
    merged["month_amount"] = pd.to_numeric(merged["month_amount"], errors="coerce").fillna(0.0)
    merged["ytd_amount"] = pd.to_numeric(merged["ytd_amount"], errors="coerce").fillna(0.0)

    merged = merged.sort_values(["display_order", "line_code"], na_position="last").reset_index(drop=True)
    merged = _apply_sign(merged)

    return merged[["line_code", "line_name", "section_name", "display_order", "sign_convention", "month_amount", "ytd_amount"]]


def build_entity_budget_report(postings_df: pd.DataFrame, account_map_df: pd.DataFrame, report_lines_df: pd.DataFrame, scenario_id: str, entity_id: str, selected_month: str) -> pd.DataFrame:
    return _build_budget_report(postings_df, account_map_df, report_lines_df, scenario_id, selected_month, entity_id=entity_id)


def build_group_budget_report(postings_df: pd.DataFrame, account_map_df: pd.DataFrame, report_lines_df: pd.DataFrame, scenario_id: str, selected_month: str) -> pd.DataFrame:
    return _build_budget_report(postings_df, account_map_df, report_lines_df, scenario_id, selected_month, entity_id=None)


def build_monthly_budget_matrix(postings_df: pd.DataFrame, account_map_df: pd.DataFrame, scenario_id: str, start_month: str, end_month: str, entity_id: str | None = None) -> pd.DataFrame:
    start_period = pd.Period(start_month, freq="M")
    end_period = pd.Period(end_month, freq="M")

    postings = _normalize_postings(postings_df)
    postings = postings[postings["scenario_id"] == scenario_id].copy()
    if entity_id is not None:
        key = "entity_id" if "entity_id" in postings.columns else "entity_code"
        postings = postings[postings[key] == entity_id].copy()

    postings = postings[(postings["month"] >= start_period) & (postings["month"] <= end_period)].copy()
    mapped = postings.merge(account_map_df[["account_code", "report_line_name"]], on="account_code", how="left")
    mapped = mapped[mapped["report_line_name"].notna()].copy()

    if mapped.empty:
        return pd.DataFrame(columns=["report_line_name"])

    matrix = (
        mapped.groupby(["report_line_name", "month"], as_index=False)["amount"]
        .sum()
        .pivot(index="report_line_name", columns="month", values="amount")
        .fillna(0.0)
    )

    month_range = pd.period_range(start=start_period, end=end_period, freq="M")
    matrix = matrix.reindex(columns=month_range, fill_value=0.0)
    matrix.columns = [str(col) for col in matrix.columns]
    return matrix.reset_index()
