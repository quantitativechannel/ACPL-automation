from __future__ import annotations

import pandas as pd

SUPPORTED_REVENUE_TYPES = ["MAA_BASE", "MAA_INCENTIVE_1", "MAA_INCENTIVE_2"]
DEFAULT_RATES = {
    "MAA_BASE": 0.10,
    "MAA_INCENTIVE_1": 0.01,
    "MAA_INCENTIVE_2": 0.04,
}


def _to_month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format="%Y-%m").dt.to_period("M")


def _month_str(series: pd.Series) -> pd.Series:
    return series.astype(str)


def _policy_lookup(revenue_policies_df: pd.DataFrame) -> pd.DataFrame:
    policies = revenue_policies_df.copy()
    if policies.empty:
        policies = pd.DataFrame(columns=["revenue_type", "rate", "vat_rate", "cit_rate"])
    policies = policies[policies["revenue_type"].isin(SUPPORTED_REVENUE_TYPES)].copy()
    for revenue_type, default_rate in DEFAULT_RATES.items():
        if revenue_type not in policies["revenue_type"].values:
            policies = pd.concat(
                [
                    policies,
                    pd.DataFrame(
                        [{"revenue_type": revenue_type, "rate": default_rate, "vat_rate": 0.0, "cit_rate": 0.0}]
                    ),
                ],
                ignore_index=True,
            )
    policies["rate"] = policies["rate"].fillna(policies["revenue_type"].map(DEFAULT_RATES)).astype(float)
    policies["vat_rate"] = policies["vat_rate"].fillna(0.0).astype(float)
    policies["cit_rate"] = policies["cit_rate"].fillna(0.0).astype(float)
    return policies.drop_duplicates(subset=["revenue_type"], keep="last").set_index("revenue_type")


def _build_base_gross(monthly_df: pd.DataFrame, rate: float) -> pd.DataFrame:
    gross = monthly_df[["scenario_id", "project_group", "month"]].copy()
    gross["gross_revenue"] = (
        monthly_df["weighted_avg_capacity_w"].astype(float)
        * float(rate)
        / 365.0
        * monthly_df["calendar_days"].astype(float)
        / 10000.0
    )
    gross["reimbursed_cost_ex_vat"] = monthly_df["reimbursed_cost_ex_vat"].astype(float)
    return gross


def _build_incentive_1_gross(monthly_df: pd.DataFrame, rate: float) -> pd.DataFrame:
    if monthly_df.empty:
        return pd.DataFrame(columns=["scenario_id", "project_group", "month", "gross_revenue", "reimbursed_cost_ex_vat"])

    work = monthly_df.copy()
    work["year"] = work["month"].dt.year

    annual = (
        work.groupby(["scenario_id", "project_group", "year"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "annual_weighted_avg_capacity_w": (
                        (g["weighted_avg_capacity_w"].astype(float) * g["calendar_days"].astype(float)).sum()
                        / g["calendar_days"].astype(float).sum()
                        if g["calendar_days"].astype(float).sum() > 0
                        else 0.0
                    ),
                    "flag_on": int((g["incentive_1_flag"].fillna(0).astype(int) == 1).any()),
                }
            )
        )
        .reset_index(drop=True)
    )

    annual["month"] = pd.PeriodIndex(annual["year"].astype(str) + "-12", freq="M")
    annual["gross_revenue"] = annual["annual_weighted_avg_capacity_w"] * float(rate)
    annual.loc[annual["flag_on"] != 1, "gross_revenue"] = 0.0

    reimb = work[work["month"].dt.month == 12][
        ["scenario_id", "project_group", "year", "reimbursed_cost_ex_vat"]
    ].copy()
    annual = annual.merge(reimb, on=["scenario_id", "project_group", "year"], how="left")
    annual["reimbursed_cost_ex_vat"] = annual["reimbursed_cost_ex_vat"].fillna(0.0).astype(float)
    annual.loc[annual["flag_on"] != 1, "reimbursed_cost_ex_vat"] = 0.0

    return annual[["scenario_id", "project_group", "month", "gross_revenue", "reimbursed_cost_ex_vat"]]


def _build_incentive_2_gross(monthly_df: pd.DataFrame, rate: float) -> pd.DataFrame:
    if monthly_df.empty:
        return pd.DataFrame(columns=["scenario_id", "project_group", "month", "gross_revenue", "reimbursed_cost_ex_vat"])

    settlement_month = pd.Period("2030-12", freq="M")

    full_cycle = (
        monthly_df.groupby(["scenario_id", "project_group"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "full_cycle_weighted_avg_capacity_w": (
                        (g["weighted_avg_capacity_w"].astype(float) * g["calendar_days"].astype(float)).sum()
                        / g["calendar_days"].astype(float).sum()
                        if g["calendar_days"].astype(float).sum() > 0
                        else 0.0
                    ),
                    "flag_on": int((g["incentive_2_flag"].fillna(0).astype(int) == 1).any()),
                }
            )
        )
        .reset_index(drop=True)
    )
    full_cycle["month"] = settlement_month
    full_cycle["gross_revenue"] = full_cycle["full_cycle_weighted_avg_capacity_w"] * float(rate)
    full_cycle.loc[full_cycle["flag_on"] != 1, "gross_revenue"] = 0.0

    reimb = monthly_df[monthly_df["month"] == settlement_month][
        ["scenario_id", "project_group", "reimbursed_cost_ex_vat"]
    ].copy()
    full_cycle = full_cycle.merge(reimb, on=["scenario_id", "project_group"], how="left")
    full_cycle["reimbursed_cost_ex_vat"] = full_cycle["reimbursed_cost_ex_vat"].fillna(0.0).astype(float)
    full_cycle.loc[full_cycle["flag_on"] != 1, "reimbursed_cost_ex_vat"] = 0.0

    return full_cycle[["scenario_id", "project_group", "month", "gross_revenue", "reimbursed_cost_ex_vat"]]


def _allocate_recognition(
    gross_df: pd.DataFrame,
    revenue_type: str,
    vat_rate: float,
    allocation_rules: pd.DataFrame,
) -> pd.DataFrame:
    rules = allocation_rules[allocation_rules["revenue_type"] == revenue_type].copy()
    if rules.empty or gross_df.empty:
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

    rules["allocation_pct"] = rules["allocation_pct"].astype(float)
    rules["haircut_pct"] = rules["haircut_pct"].fillna(0.0).astype(float)

    work = gross_df.copy()
    work["net_revenue_pool"] = work["gross_revenue"].astype(float) * (1.0 - float(vat_rate)) - work[
        "reimbursed_cost_ex_vat"
    ].astype(float)

    alloc = work.merge(rules, how="cross")
    alloc["amount"] = alloc["net_revenue_pool"] * alloc["allocation_pct"] * (1.0 - alloc["haircut_pct"])

    alloc["entity_code"] = alloc["recipient_entity_code"]
    alloc["account_code"] = "MAA_REVENUE"
    alloc["posting_type"] = "revenue_recognition"
    alloc["revenue_type"] = revenue_type
    alloc["source_module"] = "maa_revenue"
    alloc["reference_id"] = (
        revenue_type
        + "|"
        + alloc["scenario_id"].astype(str)
        + "|"
        + alloc["project_group"].astype(str)
        + "|"
        + _month_str(alloc["month"])
    )
    alloc["description"] = "MAA revenue recognition"

    return alloc[
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
    ]


def _build_cash_receipts(recognition_df: pd.DataFrame, cash_rules_df: pd.DataFrame) -> pd.DataFrame:
    if recognition_df.empty:
        return recognition_df.copy()

    out_frames: list[pd.DataFrame] = []
    cash_rules = cash_rules_df.copy()
    if cash_rules.empty:
        return pd.DataFrame(columns=recognition_df.columns)

    for _, rule in cash_rules.iterrows():
        revenue_type = rule["revenue_type"]
        method = str(rule.get("collection_method", "")).strip()
        settlement_month = rule.get("settlement_month")

        src = recognition_df[recognition_df["revenue_type"] == revenue_type].copy()
        if src.empty:
            continue

        if method == "quarterly_prepaid":
            src["quarter"] = src["month"].dt.to_timestamp().dt.to_period("Q")
            qsum = (
                src.groupby(["scenario_id", "entity_code", "revenue_type", "quarter"], as_index=False)["amount"].sum()
            )
            qsum["month"] = qsum["quarter"].dt.start_time.dt.to_period("M")
            receipts = qsum.drop(columns=["quarter"])

        elif method == "annual_settlement":
            src["year"] = src["month"].dt.year
            ysum = src.groupby(["scenario_id", "entity_code", "revenue_type", "year"], as_index=False)["amount"].sum()
            ysum["month"] = pd.PeriodIndex(ysum["year"].astype(str) + "-12", freq="M")
            receipts = ysum.drop(columns=["year"])

        elif method == "full_cycle_settlement":
            if pd.isna(settlement_month):
                continue
            setm = pd.Period(str(settlement_month), freq="M")
            fsum = src.groupby(["scenario_id", "entity_code", "revenue_type"], as_index=False)["amount"].sum()
            fsum["month"] = setm
            receipts = fsum
        else:
            continue

        receipts["account_code"] = "CASH_RECEIPT_SERVICES"
        receipts["posting_type"] = "cash_receipt"
        receipts["source_module"] = "maa_revenue"
        receipts["reference_id"] = (
            receipts["revenue_type"].astype(str)
            + "|cash|"
            + receipts["scenario_id"].astype(str)
            + "|"
            + _month_str(receipts["month"])
            + "|"
            + receipts["entity_code"].astype(str)
        )
        receipts["description"] = "MAA cash receipt"

        out_frames.append(
            receipts[
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
            ]
        )

    if not out_frames:
        return pd.DataFrame(columns=recognition_df.columns)

    return pd.concat(out_frames, ignore_index=True)


def build_maa_postings(
    capacity_rollforward_df: pd.DataFrame,
    maa_assumptions_df: pd.DataFrame,
    revenue_policies_df: pd.DataFrame,
    revenue_allocation_rules_df: pd.DataFrame,
    cash_collection_rules_df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")

    capacity = capacity_rollforward_df.copy()
    capacity["month"] = _to_month_period(capacity["month"])

    assumptions = maa_assumptions_df.copy()
    assumptions["month"] = _to_month_period(assumptions["month"])
    assumptions["incentive_1_flag"] = assumptions["incentive_1_flag"].fillna(0).astype(int)
    assumptions["incentive_2_flag"] = assumptions["incentive_2_flag"].fillna(0).astype(int)
    assumptions["reimbursed_cost_ex_vat"] = assumptions["reimbursed_cost_ex_vat"].fillna(0.0).astype(float)

    monthly = capacity.merge(assumptions, on=["scenario_id", "project_group", "month"], how="left")
    monthly["calendar_days"] = monthly["calendar_days"].fillna(0).astype(float)
    monthly["weighted_avg_capacity_w"] = monthly["weighted_avg_capacity_w"].fillna(0.0).astype(float)
    monthly["incentive_1_flag"] = monthly["incentive_1_flag"].fillna(0).astype(int)
    monthly["incentive_2_flag"] = monthly["incentive_2_flag"].fillna(0).astype(int)
    monthly["reimbursed_cost_ex_vat"] = monthly["reimbursed_cost_ex_vat"].fillna(0.0).astype(float)

    monthly = monthly[(monthly["month"] >= start) & (monthly["month"] <= end)].copy()

    policies = _policy_lookup(revenue_policies_df)

    recognition_frames: list[pd.DataFrame] = []

    base_gross = _build_base_gross(monthly, policies.loc["MAA_BASE", "rate"])
    recognition_frames.append(
        _allocate_recognition(
            base_gross,
            revenue_type="MAA_BASE",
            vat_rate=policies.loc["MAA_BASE", "vat_rate"],
            allocation_rules=revenue_allocation_rules_df,
        )
    )

    inc1_gross = _build_incentive_1_gross(monthly, policies.loc["MAA_INCENTIVE_1", "rate"])
    recognition_frames.append(
        _allocate_recognition(
            inc1_gross,
            revenue_type="MAA_INCENTIVE_1",
            vat_rate=policies.loc["MAA_INCENTIVE_1", "vat_rate"],
            allocation_rules=revenue_allocation_rules_df,
        )
    )

    inc2_gross = _build_incentive_2_gross(monthly, policies.loc["MAA_INCENTIVE_2", "rate"])
    recognition_frames.append(
        _allocate_recognition(
            inc2_gross,
            revenue_type="MAA_INCENTIVE_2",
            vat_rate=policies.loc["MAA_INCENTIVE_2", "vat_rate"],
            allocation_rules=revenue_allocation_rules_df,
        )
    )

    recognition = pd.concat(recognition_frames, ignore_index=True)
    recognition = recognition[recognition["amount"] != 0].copy()

    cash = _build_cash_receipts(recognition, cash_collection_rules_df)

    postings = pd.concat([recognition, cash], ignore_index=True)
    postings = postings[(postings["month"] >= start) & (postings["month"] <= end)].copy()
    postings["month"] = _month_str(postings["month"])
    postings["amount"] = postings["amount"].astype(float)

    return postings[
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
