from __future__ import annotations

import pandas as pd


_BASE_POSTING_TYPES = {
    "cash_receipt",
    "cash_payment",
    "capital_contribution",
    "fund_contribution",
    "transfer",
}


def _ensure_month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y-%m", errors="coerce").dt.to_period("M")


def _resolve_entity_column(frame: pd.DataFrame) -> str:
    if "entity_id" in frame.columns:
        return "entity_id"
    if "entity_code" in frame.columns:
        return "entity_code"
    frame["entity_id"] = pd.NA
    return "entity_id"


def _prepare_postings(
    postings_df: pd.DataFrame,
    scenario_id: str,
    use_expense_as_cash_payment: bool,
) -> tuple[pd.DataFrame, str]:
    if postings_df.empty:
        return pd.DataFrame(columns=["scenario_id", "month", "account_code", "posting_type", "amount"]), "entity_id"

    work = postings_df.copy()
    entity_col = _resolve_entity_column(work)
    for col in ["scenario_id", "month", "account_code", "posting_type", "amount", entity_col]:
        if col not in work.columns:
            work[col] = pd.NA

    posting_types = set(_BASE_POSTING_TYPES)
    if use_expense_as_cash_payment:
        posting_types.add("expense")

    work = work[work["scenario_id"] == scenario_id].copy()
    work["month"] = _ensure_month_period(work["month"])
    work = work[work["month"].notna()].copy()
    work = work[work["posting_type"].isin(posting_types)].copy()
    if use_expense_as_cash_payment:
        work.loc[work["posting_type"] == "expense", "posting_type"] = "cash_payment"

    work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0)
    return work, entity_col


def _line_mapping(account_map_df: pd.DataFrame) -> pd.DataFrame:
    if account_map_df.empty:
        return pd.DataFrame(columns=["account_code", "cashflow_line_name", "sort_order"])

    cols = ["account_code", "cashflow_line_name", "sort_order"]
    mapping = account_map_df.copy()
    for col in cols:
        if col not in mapping.columns:
            mapping[col] = pd.NA

    mapping = mapping[cols].drop_duplicates(subset=["account_code"], keep="first")
    return mapping


def _period_years(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype="int64", index=series.index)
    return pd.Series(pd.PeriodIndex(series, freq="M").year, index=series.index)


def _enrich_lines(report: pd.DataFrame, cashflow_lines_df: pd.DataFrame | None) -> pd.DataFrame:
    if cashflow_lines_df is None or cashflow_lines_df.empty:
        return report

    line_cols = ["cashflow_line_name", "section_name", "display_order", "sign_convention"]
    lines = cashflow_lines_df.copy()
    for col in line_cols:
        if col not in lines.columns:
            lines[col] = pd.NA

    lines = lines[line_cols].drop_duplicates(subset=["cashflow_line_name"], keep="first")
    return report.merge(lines, on="cashflow_line_name", how="left")


def build_cashflow_report(
    postings_df: pd.DataFrame,
    account_map_df: pd.DataFrame,
    scenario_id: str,
    selected_month: str,
    entity_id: str | None = None,
    cashflow_lines_df: pd.DataFrame | None = None,
    use_expense_as_cash_payment: bool = False,
) -> pd.DataFrame:
    postings, entity_col = _prepare_postings(postings_df, scenario_id, use_expense_as_cash_payment)
    selected_period = pd.Period(selected_month, freq="M")

    if entity_id is not None:
        postings = postings[postings[entity_col] == entity_id].copy()

    if postings.empty:
        return pd.DataFrame(
            columns=[entity_col, "cashflow_line_name", "month", "month_amount", "ytd_amount", "sort_order"]
        )

    mapped = postings.merge(_line_mapping(account_map_df), on="account_code", how="left")
    mapped["cashflow_line_name"] = mapped["cashflow_line_name"].fillna(mapped["posting_type"])

    ytd_source = mapped[(mapped["month"] <= selected_period) & (_period_years(mapped["month"]) == selected_period.year)].copy()
    ytd = ytd_source.groupby([entity_col, "cashflow_line_name"], as_index=False)["amount"].sum().rename(
        columns={"amount": "ytd_amount"}
    )

    month_rows = mapped[mapped["month"] == selected_period].copy()
    month_rows = month_rows.groupby([entity_col, "cashflow_line_name", "sort_order"], as_index=False)["amount"].sum()
    month_rows = month_rows.rename(columns={"amount": "month_amount"})

    report = month_rows.merge(ytd, on=[entity_col, "cashflow_line_name"], how="left")
    report["ytd_amount"] = report["ytd_amount"].fillna(0.0)
    report["month"] = str(selected_period)
    report = _enrich_lines(report, cashflow_lines_df)
    return report.sort_values([entity_col, "sort_order", "cashflow_line_name"]).reset_index(drop=True)


def build_group_cashflow_report(
    postings_df: pd.DataFrame,
    account_map_df: pd.DataFrame,
    scenario_id: str,
    selected_month: str,
    cashflow_lines_df: pd.DataFrame | None = None,
    use_expense_as_cash_payment: bool = False,
) -> pd.DataFrame:
    base = build_cashflow_report(
        postings_df=postings_df,
        account_map_df=account_map_df,
        scenario_id=scenario_id,
        selected_month=selected_month,
        entity_id=None,
        cashflow_lines_df=cashflow_lines_df,
        use_expense_as_cash_payment=use_expense_as_cash_payment,
    )
    if base.empty:
        return pd.DataFrame(columns=["cashflow_line_name", "month", "month_amount", "ytd_amount", "sort_order"])

    group_cols = ["cashflow_line_name", "month", "sort_order"]
    if "section_name" in base.columns:
        group_cols.append("section_name")
    if "display_order" in base.columns:
        group_cols.append("display_order")
    if "sign_convention" in base.columns:
        group_cols.append("sign_convention")

    out = base.groupby(group_cols, as_index=False)[["month_amount", "ytd_amount"]].sum()
    return out.sort_values(["sort_order", "cashflow_line_name"]).reset_index(drop=True)


def build_cashflow_monthly_matrix(
    postings_df: pd.DataFrame,
    account_map_df: pd.DataFrame,
    scenario_id: str,
    start_month: str,
    end_month: str,
    entity_id: str | None = None,
    use_expense_as_cash_payment: bool = False,
) -> pd.DataFrame:
    postings, entity_col = _prepare_postings(postings_df, scenario_id, use_expense_as_cash_payment)
    start_period = pd.Period(start_month, freq="M")
    end_period = pd.Period(end_month, freq="M")

    if entity_id is not None:
        postings = postings[postings[entity_col] == entity_id].copy()

    postings = postings[(postings["month"] >= start_period) & (postings["month"] <= end_period)].copy()
    if postings.empty:
        return pd.DataFrame(columns=["cashflow_line_name"])

    mapped = postings.merge(_line_mapping(account_map_df), on="account_code", how="left")
    mapped["cashflow_line_name"] = mapped["cashflow_line_name"].fillna(mapped["posting_type"])
    mapped["month"] = mapped["month"].astype(str)

    grouped = mapped.groupby(["cashflow_line_name", "month"], as_index=False)["amount"].sum()
    matrix = grouped.pivot(index="cashflow_line_name", columns="month", values="amount").fillna(0.0).reset_index()
    return matrix
