from __future__ import annotations

import calendar

import pandas as pd


JV_FUND_NAME = "JV基金"
FUND_REVENUE_SOURCE = "fund_revenue"
BASE_REVENUE_TYPE = "FUND_MGMT_BASE"
INCENTIVE_REVENUE_TYPE = "FUND_MGMT_INCENTIVE"


def _to_month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y-%m").dt.to_period("M")


def _month_str(series: pd.Series) -> pd.Series:
    return series.astype(str)


def _month_days(period_value: pd.Period) -> int:
    return int(calendar.monthrange(period_value.year, period_value.month)[1])


def _ensure_assumption_columns(assumptions: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = assumptions.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = pd.NA
    return out


def _default_fund_expense(period_value: pd.Period) -> float:
    if period_value == pd.Period("2026-04", freq="M"):
        return 500.0
    if period_value.year in (2027, 2028, 2029, 2030) and period_value.month == 1:
        return 200.0
    return 0.0


def build_jv_fund_rollforward(
    capacity_rollforward_df: pd.DataFrame,
    fund_assumptions_df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")

    capacity = capacity_rollforward_df.copy()
    capacity["month"] = _to_month_period(capacity["month"])
    capacity = capacity[(capacity["month"] >= start) & (capacity["month"] <= end)].copy()

    if "jv_equity_new_contribution" not in capacity.columns:
        raise ValueError("capacity_rollforward_df must include jv_equity_new_contribution")

    assumptions = fund_assumptions_df.copy()
    if assumptions.empty:
        assumptions = pd.DataFrame(columns=["scenario_id", "month"])
    assumptions["month"] = _to_month_period(assumptions["month"])
    assumptions = _ensure_assumption_columns(
        assumptions,
        [
            "fund_name",
            "fund_equity_initial_cumulative",
            "fund_expense_initial_cumulative",
            "gp_initial_cumulative",
            "lp_initial_cumulative",
            "fund_expense_new_contribution",
            "gp_new_contribution",
            "management_fee_rate",
            "vat_rate",
            "cit_rate",
            "addition_timing_factor",
            "incentive_flag",
        ],
    )

    merged = capacity.merge(assumptions, on=["scenario_id", "month"], how="left")
    if "addition_timing_factor" not in merged.columns:
        if "addition_timing_factor_y" in merged.columns:
            merged["addition_timing_factor"] = merged["addition_timing_factor_y"]
        elif "addition_timing_factor_x" in merged.columns:
            merged["addition_timing_factor"] = merged["addition_timing_factor_x"]
    merged["fund_name"] = merged["fund_name"].fillna(JV_FUND_NAME)
    merged["jv_equity_new_contribution"] = merged["jv_equity_new_contribution"].fillna(0.0).astype(float)

    merged["fund_equity_new_contribution"] = merged["jv_equity_new_contribution"] * 0.75

    merged["fund_expense_new_contribution"] = merged.apply(
        lambda r: (
            float(r["fund_expense_new_contribution"])
            if pd.notna(r["fund_expense_new_contribution"])
            else _default_fund_expense(r["month"])
        ),
        axis=1,
    )

    merged["gp_new_contribution"] = merged.apply(
        lambda r: (
            float(r["gp_new_contribution"])
            if pd.notna(r["gp_new_contribution"])
            else (r["fund_equity_new_contribution"] + r["fund_expense_new_contribution"])
            * (0.25 if r["month"] < pd.Period("2026-05", freq="M") else 0.0333)
        ),
        axis=1,
    )

    merged["lp_new_contribution"] = (
        merged["fund_equity_new_contribution"] + merged["fund_expense_new_contribution"] - merged["gp_new_contribution"]
    )

    merged["management_fee_rate"] = merged["management_fee_rate"].fillna(0.0).astype(float)
    merged["vat_rate"] = merged["vat_rate"].fillna(0.0).astype(float)
    merged["cit_rate"] = merged["cit_rate"].fillna(0.0).astype(float)
    merged["addition_timing_factor"] = merged["addition_timing_factor"].fillna(1.0).astype(float)
    merged["incentive_flag"] = merged["incentive_flag"].fillna(0).astype(int)
    merged["calendar_days"] = merged["month"].apply(_month_days).astype(float)

    out_frames: list[pd.DataFrame] = []
    for scenario_id, grp in merged.groupby("scenario_id", sort=False):
        g = grp.sort_values("month").copy()

        equity_open = float(
            g.loc[g["month"] == pd.Period("2026-04", freq="M"), "fund_equity_initial_cumulative"].dropna().iloc[0]
        ) if not g.loc[g["month"] == pd.Period("2026-04", freq="M"), "fund_equity_initial_cumulative"].dropna().empty else 0.0
        expense_open = float(
            g.loc[g["month"] == pd.Period("2026-04", freq="M"), "fund_expense_initial_cumulative"].dropna().iloc[0]
        ) if not g.loc[g["month"] == pd.Period("2026-04", freq="M"), "fund_expense_initial_cumulative"].dropna().empty else 0.0
        gp_open = float(
            g.loc[g["month"] == pd.Period("2026-04", freq="M"), "gp_initial_cumulative"].dropna().iloc[0]
        ) if not g.loc[g["month"] == pd.Period("2026-04", freq="M"), "gp_initial_cumulative"].dropna().empty else 0.0
        lp_open = float(
            g.loc[g["month"] == pd.Period("2026-04", freq="M"), "lp_initial_cumulative"].dropna().iloc[0]
        ) if not g.loc[g["month"] == pd.Period("2026-04", freq="M"), "lp_initial_cumulative"].dropna().empty else 0.0

        g["fund_equity_cumulative_contribution"] = g["fund_equity_new_contribution"].cumsum() + equity_open
        g["fund_expense_cumulative_contribution"] = g["fund_expense_new_contribution"].cumsum() + expense_open
        g["gp_cumulative_contribution"] = g["gp_new_contribution"].cumsum() + gp_open
        g["lp_cumulative_contribution"] = g["lp_new_contribution"].cumsum() + lp_open

        g["lp_prior_cumulative_contribution"] = g["lp_cumulative_contribution"].shift(1).fillna(lp_open)

        g["management_fee_base_pool"] = (
            g["lp_prior_cumulative_contribution"]
            / (1.0 - g["management_fee_rate"]) * g["management_fee_rate"] / 365.0 * g["calendar_days"]
            + g["lp_new_contribution"] / 365.0 * g["calendar_days"] * g["addition_timing_factor"]
        )

        g["base_management_fee"] = (
            0.70 * g["management_fee_base_pool"] * (1.0 - g["vat_rate"]) * (1.0 - g["cit_rate"])
        )
        g["incentive_management_fee"] = (
            0.30
            * g["management_fee_base_pool"]
            * (1.0 - g["vat_rate"])
            * (1.0 - g["cit_rate"])
            * g["incentive_flag"]
        )
        out_frames.append(g)

    out = pd.concat(out_frames, ignore_index=True)
    out["month"] = _month_str(out["month"])

    return out[
        [
            "scenario_id",
            "fund_name",
            "month",
            "fund_equity_new_contribution",
            "fund_equity_cumulative_contribution",
            "fund_expense_new_contribution",
            "fund_expense_cumulative_contribution",
            "gp_new_contribution",
            "gp_cumulative_contribution",
            "lp_new_contribution",
            "lp_cumulative_contribution",
            "base_management_fee",
            "incentive_management_fee",
        ]
    ].sort_values(["scenario_id", "month"]).reset_index(drop=True)


def build_fund_management_fee_postings(
    fund_rollforward_df: pd.DataFrame,
    revenue_allocation_rules_df: pd.DataFrame,
    cash_collection_rules_df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")

    roll = fund_rollforward_df.copy()
    roll["month"] = _to_month_period(roll["month"])
    roll = roll[(roll["month"] >= start) & (roll["month"] <= end)].copy()

    fee_map = {
        BASE_REVENUE_TYPE: "base_management_fee",
        INCENTIVE_REVENUE_TYPE: "incentive_management_fee",
    }

    alloc = revenue_allocation_rules_df.copy()
    if alloc.empty:
        alloc = pd.DataFrame(
            [
                {"revenue_type": BASE_REVENUE_TYPE, "recipient_entity_code": "旭智咨询", "allocation_pct": 1.0, "haircut_pct": 0.0},
                {"revenue_type": INCENTIVE_REVENUE_TYPE, "recipient_entity_code": "旭智咨询", "allocation_pct": 1.0, "haircut_pct": 0.0},
            ]
        )
    alloc["allocation_pct"] = alloc["allocation_pct"].fillna(1.0).astype(float)
    alloc["haircut_pct"] = alloc["haircut_pct"].fillna(0.0).astype(float)

    rec_frames: list[pd.DataFrame] = []
    for revenue_type, fee_col in fee_map.items():
        src = roll[["scenario_id", "month", fee_col]].rename(columns={fee_col: "amount"}).copy()
        src = src[src["amount"] != 0].copy()
        if src.empty:
            continue

        rules = alloc[alloc["revenue_type"] == revenue_type].copy()
        if rules.empty:
            continue

        m = src.merge(rules, how="cross")
        m["amount"] = m["amount"] * m["allocation_pct"] * (1.0 - m["haircut_pct"])
        m["entity_code"] = m["recipient_entity_code"]
        m["account_code"] = "FUND_MANAGEMENT_FEE"
        m["posting_type"] = "revenue_recognition"
        m["revenue_type"] = revenue_type
        m["source_module"] = FUND_REVENUE_SOURCE
        m["reference_id"] = (
            m["revenue_type"]
            + "|"
            + m["scenario_id"].astype(str)
            + "|"
            + _month_str(m["month"])
            + "|"
            + m["entity_code"].astype(str)
        )
        m["description"] = "Fund management fee recognition"
        rec_frames.append(m)

    if not rec_frames:
        return pd.DataFrame(
            columns=[
                "scenario_id",
                "entity_code",
                "month",
                "account_code",
                "posting_type",
                "revenue_type",
                "source_module",
                "reference_id",
                "description",
                "amount",
            ]
        )

    recognition = pd.concat(rec_frames, ignore_index=True)

    cash_rules = cash_collection_rules_df.copy()
    if cash_rules.empty:
        cash_rules = pd.DataFrame(
            [
                {"revenue_type": BASE_REVENUE_TYPE, "collection_method": "annual_prepaid", "collection_months": "1"},
                {"revenue_type": INCENTIVE_REVENUE_TYPE, "collection_method": "annual_prepaid", "collection_months": "1"},
            ]
        )

    cash_frames: list[pd.DataFrame] = []
    for _, rule in cash_rules.iterrows():
        if str(rule.get("collection_method", "")).strip() != "annual_prepaid":
            continue
        revenue_type = rule.get("revenue_type")
        src = recognition[recognition["revenue_type"] == revenue_type].copy()
        if src.empty:
            continue

        src["year"] = src["month"].dt.year
        annual = src.groupby(["scenario_id", "entity_code", "revenue_type", "year"], as_index=False)["amount"].sum()
        annual["month"] = pd.PeriodIndex(annual["year"].astype(str) + "-01", freq="M")
        annual["account_code"] = "CASH_RECEIPT_SERVICES"
        annual["posting_type"] = "cash_receipt"
        annual["source_module"] = FUND_REVENUE_SOURCE
        annual["reference_id"] = (
            annual["revenue_type"].astype(str)
            + "|cash|"
            + annual["scenario_id"].astype(str)
            + "|"
            + _month_str(annual["month"])
            + "|"
            + annual["entity_code"].astype(str)
        )
        annual["description"] = "Fund management fee cash receipt"
        cash_frames.append(annual)

    postings = [recognition]
    if cash_frames:
        postings.append(pd.concat(cash_frames, ignore_index=True))

    out = pd.concat(postings, ignore_index=True)
    out = out[(out["month"] >= start) & (out["month"] <= end)].copy()
    out["month"] = _month_str(out["month"])

    return out[
        [
            "scenario_id",
            "entity_code",
            "month",
            "account_code",
            "posting_type",
            "revenue_type",
            "source_module",
            "reference_id",
            "description",
            "amount",
        ]
    ].sort_values(["scenario_id", "month", "posting_type", "revenue_type", "entity_code"]).reset_index(drop=True)


def build_xihe_fund_postings(
    scenario_id: int,
    start_month: str,
    end_month: str,
    fund_paid_in_capital: float = 2000,
    lp_pct: float = 0.96,
    management_fee_rate: float = 0.01,
    recipient_entity_code: str = "旭智私募",
) -> pd.DataFrame:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    months = pd.period_range(start, end, freq="M")

    lp_paid_in = float(fund_paid_in_capital) * float(lp_pct)
    monthly_revenue = lp_paid_in * float(management_fee_rate) / 12.0

    rec = pd.DataFrame({"month": months})
    rec["scenario_id"] = scenario_id
    rec["entity_code"] = recipient_entity_code
    rec["account_code"] = "FUND_MANAGEMENT_FEE"
    rec["posting_type"] = "revenue_recognition"
    rec["revenue_type"] = "XIHE_FUND_MANAGEMENT_FEE"
    rec["source_module"] = FUND_REVENUE_SOURCE
    rec["amount"] = monthly_revenue
    rec["reference_id"] = (
        rec["revenue_type"]
        + "|"
        + rec["scenario_id"].astype(str)
        + "|"
        + _month_str(rec["month"])
        + "|"
        + rec["entity_code"]
    )
    rec["description"] = "XiHe fund management fee recognition"

    cash = rec.copy()
    cash["year"] = cash["month"].dt.year
    cash = cash.groupby(["scenario_id", "entity_code", "revenue_type", "year"], as_index=False)["amount"].sum()
    cash["month"] = pd.PeriodIndex(cash["year"].astype(str) + "-01", freq="M")
    cash["account_code"] = "CASH_RECEIPT_SERVICES"
    cash["posting_type"] = "cash_receipt"
    cash["source_module"] = FUND_REVENUE_SOURCE
    cash["reference_id"] = (
        cash["revenue_type"].astype(str)
        + "|cash|"
        + cash["scenario_id"].astype(str)
        + "|"
        + _month_str(cash["month"])
        + "|"
        + cash["entity_code"].astype(str)
    )
    cash["description"] = "XiHe fund management fee cash receipt"

    out = pd.concat([rec, cash], ignore_index=True)
    out = out[(out["month"] >= start) & (out["month"] <= end)].copy()
    out["month"] = _month_str(out["month"])

    return out[
        [
            "scenario_id",
            "entity_code",
            "month",
            "account_code",
            "posting_type",
            "revenue_type",
            "source_module",
            "reference_id",
            "description",
            "amount",
        ]
    ].sort_values(["scenario_id", "month", "posting_type", "revenue_type", "entity_code"]).reset_index(drop=True)
