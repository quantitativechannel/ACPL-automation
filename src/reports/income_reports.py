from __future__ import annotations

import pandas as pd


CASHFLOW_LINE_SALES_SERVICE = "销售商品、提供劳务收到的现金"


def _ensure_month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y-%m", errors="coerce").dt.to_period("M")


def _prepare_income_postings(income_postings_df: pd.DataFrame) -> pd.DataFrame:
    if income_postings_df.empty:
        return pd.DataFrame(columns=["entity_code", "revenue_type", "month", "posting_type", "amount"])

    work = income_postings_df.copy()
    for col in ["entity_code", "revenue_type", "month", "posting_type", "amount"]:
        if col not in work.columns:
            work[col] = pd.NA

    work["month"] = _ensure_month_period(work["month"])
    work = work[work["month"].notna()].copy()
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0)

    return work


def _entity_filter(df: pd.DataFrame, entity_code: str | None) -> pd.DataFrame:
    if entity_code is None:
        return df
    return df[df["entity_code"] == entity_code].copy()


def _period_years(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype="int64", index=series.index)
    return pd.Series(pd.PeriodIndex(series, freq="M").year, index=series.index)


def _add_ytd(frame: pd.DataFrame, selected_period: pd.Period, amount_col: str) -> pd.DataFrame:
    if frame.empty:
        return frame

    ytd_source = frame[frame["month"] <= selected_period].copy()
    ytd_source = ytd_source[_period_years(ytd_source["month"]) == selected_period.year]
    ytd = (
        ytd_source.groupby(["entity_code", "revenue_type"], as_index=False)[amount_col]
        .sum()
        .rename(columns={amount_col: "ytd_amount"})
    )

    in_month = frame[frame["month"] == selected_period].copy()
    in_month = in_month.rename(columns={amount_col: "month_amount"})

    out = in_month.merge(ytd, on=["entity_code", "revenue_type"], how="left")
    out["ytd_amount"] = out["ytd_amount"].fillna(0.0)
    out["month"] = out["month"].astype(str)
    return out


def build_income_statement_revenue_report(
    income_postings_df: pd.DataFrame,
    selected_month: str,
    entity_code: str | None = None,
) -> pd.DataFrame:
    selected_period = pd.Period(selected_month, freq="M")
    postings = _prepare_income_postings(income_postings_df)
    postings = postings[postings["posting_type"] == "revenue_recognition"].copy()
    postings = _entity_filter(postings, entity_code)

    grouped = (
        postings.groupby(["entity_code", "revenue_type", "month"], as_index=False)["amount"]
        .sum()
        .sort_values(["entity_code", "revenue_type", "month"])
    )

    report = _add_ytd(grouped, selected_period, "amount")
    if report.empty:
        return pd.DataFrame(columns=["entity_code", "revenue_type", "month", "month_amount", "ytd_amount"])

    return report[["entity_code", "revenue_type", "month", "month_amount", "ytd_amount"]].reset_index(drop=True)


def build_cash_receipt_report(
    income_postings_df: pd.DataFrame,
    selected_month: str,
    entity_code: str | None = None,
) -> pd.DataFrame:
    selected_period = pd.Period(selected_month, freq="M")
    postings = _prepare_income_postings(income_postings_df)
    postings = postings[postings["posting_type"] == "cash_receipt"].copy()
    postings = _entity_filter(postings, entity_code)

    grouped = (
        postings.groupby(["entity_code", "revenue_type", "month"], as_index=False)["amount"]
        .sum()
        .sort_values(["entity_code", "revenue_type", "month"])
    )

    report = _add_ytd(grouped, selected_period, "amount")
    if report.empty:
        return pd.DataFrame(
            columns=[
                "entity_code",
                "revenue_type",
                "cashflow_line",
                "month",
                "month_amount",
                "ytd_amount",
            ]
        )

    report["cashflow_line"] = CASHFLOW_LINE_SALES_SERVICE
    return report[
        ["entity_code", "revenue_type", "cashflow_line", "month", "month_amount", "ytd_amount"]
    ].reset_index(drop=True)


def _revenue_bucket(revenue_type: object) -> str:
    text = str(revenue_type).upper()
    if "MAA" in text:
        return "MAA"
    if "XIHE" in text:
        return "XIHE_FUND"
    if "JV" in text:
        return "JV_FUND"
    return "OTHER"


def build_income_summary_by_entity(
    income_postings_df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    start_period = pd.Period(start_month, freq="M")
    end_period = pd.Period(end_month, freq="M")

    postings = _prepare_income_postings(income_postings_df)
    postings = postings[postings["posting_type"] == "revenue_recognition"].copy()
    postings = postings[(postings["month"] >= start_period) & (postings["month"] <= end_period)].copy()

    if postings.empty:
        return pd.DataFrame(columns=["summary_entity", "amount"])

    postings["bucket"] = postings["revenue_type"].map(_revenue_bucket)

    rows: list[dict[str, float | str]] = []

    acplsz_amount = postings[
        (postings["entity_code"] == "ACPLSZ") & (postings["bucket"].isin(["MAA", "JV_FUND"]))
    ]["amount"].sum()
    rows.append({"summary_entity": "旭智咨询", "amount": float(acplsz_amount)})

    acplhk_amount = postings[(postings["entity_code"] == "ACPLHK") & (postings["bucket"] == "MAA")]["amount"].sum()
    rows.append({"summary_entity": "ACPLHK", "amount": float(acplhk_amount)})

    xzsm_amount = postings[postings["bucket"] == "XIHE_FUND"]["amount"].sum()
    rows.append({"summary_entity": "旭智私募", "amount": float(xzsm_amount)})

    return pd.DataFrame(rows)
