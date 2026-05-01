from __future__ import annotations

import pandas as pd

from src.drivers.fund_revenue_driver import build_fund_management_fee_postings, build_jv_fund_rollforward, build_xihe_fund_postings
from src.drivers.income_capacity_driver import build_capacity_rollforward
from src.drivers.maa_revenue_driver import build_maa_postings
from src.drivers.medical_benefit_driver import build_medical_benefit_postings
from src.drivers.other_exp_driver import build_other_exp_postings
from src.drivers.personnel_driver import build_monthly_headcount, build_personnel_postings
from src.drivers.prof_fee_driver import build_prof_fee_postings
from src.drivers.travel_driver import build_travel_postings

STANDARD_COLUMNS = ["scenario_id", "entity_id", "entity_code", "month", "account_code", "posting_type", "source_module", "reference_id", "description", "amount", "revenue_type", "counterparty"]


def _valid_month(m: str) -> bool:
    try:
        pd.Period(m, freq="M")
        return True
    except Exception:
        return False


def _normalize(df: pd.DataFrame, scenario_id: int) -> pd.DataFrame:
    out = df.copy()
    for col in STANDARD_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out["scenario_id"] = out["scenario_id"].fillna(scenario_id)
    out["month"] = out["month"].astype(str)
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce")
    return out[STANDARD_COLUMNS]


def run_forecast_orchestration(scenario_id: int, start_month: str, end_month: str, inputs: dict) -> dict:
    warnings: list[str] = []
    frames: list[pd.DataFrame] = []

    if not _valid_month(start_month) or not _valid_month(end_month) or pd.Period(start_month, freq="M") > pd.Period(end_month, freq="M"):
        warnings.append(f"Unsupported date range: start_month={start_month}, end_month={end_month}")
        empty = pd.DataFrame(columns=STANDARD_COLUMNS)
        return {"postings": empty, "validation_warnings": warnings, "driver_summaries": pd.DataFrame(columns=["source_module", "posting_type", "row_count", "total_amount"]) }

    capacity = pd.DataFrame()
    if "capacity_assumptions" in inputs and not inputs["capacity_assumptions"].empty:
        try:
            capacity = build_capacity_rollforward(inputs["capacity_assumptions"], start_month, end_month)
        except ValueError as exc:
            warnings.append(f"capacity roll-forward failed validation: {exc}")
    else:
        warnings.append("Skipped capacity roll-forward: missing capacity_assumptions")

    if not capacity.empty and all(k in inputs for k in ["maa_assumptions", "revenue_policies", "revenue_allocation_rules", "cash_collection_rules"]):
        try:
            frames.append(build_maa_postings(capacity, inputs["maa_assumptions"], inputs["revenue_policies"], inputs["revenue_allocation_rules"], inputs["cash_collection_rules"], start_month, end_month))
        except ValueError as exc:
            warnings.append(f"MAA postings failed validation: {exc}")
    else:
        warnings.append("Skipped MAA postings: missing required inputs")

    if not capacity.empty and "fund_assumptions" in inputs:
        try:
            rf = build_jv_fund_rollforward(capacity, inputs["fund_assumptions"], start_month, end_month)
            frames.append(build_fund_management_fee_postings(rf, inputs.get("revenue_allocation_rules", pd.DataFrame()), inputs.get("cash_collection_rules", pd.DataFrame()), start_month, end_month))
        except ValueError as exc:
            warnings.append(f"JV fund drivers failed validation: {exc}")
    else:
        warnings.append("Skipped JV fund drivers: missing required inputs")

    if "xihe_fund_assumptions" in inputs:
        frames.append(build_xihe_fund_postings(scenario_id, start_month, end_month))

    for key, fn, label in [
        ("prof_fee_assumptions", lambda: build_prof_fee_postings(inputs["prof_fee_assumptions"], inputs.get("fx_rates")), "professional fee"),
        ("other_exp_assumptions", lambda: build_other_exp_postings(inputs["other_exp_assumptions"], inputs.get("fx_rates")), "other expense"),
    ]:
        if key in inputs:
            try:
                frames.append(fn())
            except ValueError as exc:
                warnings.append(f"{label} postings failed validation: {exc}")
        else:
            warnings.append(f"Skipped {label} postings: missing {key}")

    if "employees" in inputs and "burden_rules" in inputs:
        try:
            frames.append(build_personnel_postings(inputs["employees"], inputs["burden_rules"], start_month, end_month, inputs.get("bonus_rules"), inputs.get("medical_rules")))
        except ValueError as exc:
            warnings.append(f"Personnel postings failed validation: {exc}")
    else:
        warnings.append("Skipped personnel postings: missing employees or burden_rules")

    if "medical_benefit_assumptions" in inputs:
        try:
            frames.append(build_medical_benefit_postings(inputs["medical_benefit_assumptions"], start_month, end_month))
        except ValueError as exc:
            warnings.append(f"Medical benefit postings failed validation: {exc}")

    if "travel_policy" in inputs and "travel_allocation" in inputs:
        headcount = build_monthly_headcount(inputs.get("employees", pd.DataFrame()), start_month, end_month) if "employees" in inputs else pd.DataFrame()
        if "employees" not in inputs:
            warnings.append("Travel driver has no employees input; using empty headcount")
        try:
            frames.append(build_travel_postings(headcount, inputs["travel_policy"], inputs["travel_allocation"], inputs.get("travel_month_weights")))
        except ValueError as exc:
            warnings.append(f"Travel postings failed validation: {exc}")
    else:
        warnings.append("Skipped travel postings: missing travel_policy or travel_allocation")

    if "manual_overrides" in inputs:
        manual = inputs["manual_overrides"].copy()
        manual["source_module"] = manual.get("source_module", "manual_override")
        manual["posting_type"] = manual.get("posting_type", "manual_override")
        frames.append(manual)

    postings = pd.concat([_normalize(f, scenario_id) for f in frames], ignore_index=True) if frames else pd.DataFrame(columns=STANDARD_COLUMNS)

    if postings["account_code"].isna().any():
        warnings.append("Some postings have missing account_code")
    if postings["amount"].isna().any() or (postings["amount"] == 0).any():
        warnings.append("Some postings have zero or null amount")
    dup_keys = ["scenario_id", "entity_id", "entity_code", "month", "account_code", "source_module", "reference_id"]
    if not postings.empty and postings.duplicated(subset=dup_keys).any():
        warnings.append("Duplicate postings detected by scenario/entity/month/account/source/reference")

    summaries = postings.groupby(["source_module", "posting_type"], dropna=False, as_index=False).agg(row_count=("amount", "size"), total_amount=("amount", "sum"))
    return {"postings": postings, "validation_warnings": warnings, "driver_summaries": summaries}
