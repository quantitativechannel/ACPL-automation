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
]

REQUIRED_COLUMNS = [
    "scenario_id",
    "entity_id",
    "vendor",
    "account_code",
    "fee_name",
    "details",
    "basis_type",
    "currency",
    "assumption_value",
    "start_date",
    "end_date",
]

SUPPORTED_BASIS_TYPES = {
    "monthly",
    "lump_sum",
    "annual_spread",
    "quarterly",
    "quarterly_start",
    "specific_month",
    "custom_start_end_monthly",
}


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _to_period(value: object, field_name: str) -> pd.Period:
    try:
        return pd.Period(pd.to_datetime(value), freq="M")
    except Exception as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _months_inclusive(start: pd.Period, end: pd.Period) -> list[pd.Period]:
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    return list(pd.period_range(start, end, freq="M"))


def _build_monthly_amounts(row: pd.Series, start: pd.Period, end: pd.Period) -> list[tuple[pd.Period, float]]:
    basis_type = str(row["basis_type"])
    value = float(row["assumption_value"])

    if basis_type == "monthly":
        return [(m, value) for m in _months_inclusive(start, end)]
    if basis_type == "lump_sum":
        return [(start, value)]
    if basis_type == "annual_spread":
        months = pd.period_range(pd.Period(f"{start.year}-01", freq="M"), pd.Period(f"{start.year}-12", freq="M"), freq="M")
        return [(m, value / 12.0) for m in months]
    if basis_type == "quarterly":
        q_months = [3, 6, 9, 12]
        return [(pd.Period(f"{start.year}-{month:02d}", freq="M"), value / 4.0) for month in q_months]
    if basis_type == "quarterly_start":
        q_months = [1, 4, 7, 10]
        return [(pd.Period(f"{start.year}-{month:02d}", freq="M"), value / 4.0) for month in q_months]
    if basis_type == "specific_month":
        return [(start, value)]
    if basis_type == "custom_start_end_monthly":
        months = _months_inclusive(start, end)
        monthly_value = value / len(months)
        return [(m, monthly_value) for m in months]

    raise ValueError(f"unsupported basis_type: {basis_type}")


def build_prof_fee_postings(
    assumptions_df: pd.DataFrame,
    fx_df: pd.DataFrame | None = None,
    base_currency: str = "RMB",
) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in assumptions_df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if assumptions_df.empty:
        return _empty_output()

    src = assumptions_df.copy()
    src["basis_type"] = src["basis_type"].astype(str)

    unsupported = sorted(set(src["basis_type"]) - SUPPORTED_BASIS_TYPES)
    if unsupported:
        raise ValueError(f"unsupported basis_type: {unsupported[0]}")

    fx_lookup: dict[tuple[str, str], float] = {}
    if fx_df is not None and not fx_df.empty:
        required_fx_cols = {"month", "currency", "rate_to_base"}
        if not required_fx_cols.issubset(fx_df.columns):
            missing_fx = sorted(required_fx_cols - set(fx_df.columns))
            raise ValueError(f"missing fx columns: {missing_fx}")
        fx_tmp = fx_df.copy()
        fx_tmp["month"] = pd.to_datetime(fx_tmp["month"].astype(str)).dt.to_period("M").astype(str)
        fx_lookup = {(r["month"], str(r["currency"])): float(r["rate_to_base"]) for _, r in fx_tmp.iterrows()}

    rows: list[dict[str, object]] = []
    for _, row in src.iterrows():
        start = _to_period(row["start_date"], "start_date")
        end_raw = row["end_date"]
        end = start if pd.isna(end_raw) else _to_period(end_raw, "end_date")

        month_amounts = _build_monthly_amounts(row, start, end)
        desc = " | ".join(str(row.get(c) or "") for c in ["vendor", "fee_name", "details"]).strip(" |")

        for month, amount in month_amounts:
            currency = str(row["currency"])
            if currency != base_currency:
                if fx_df is None or fx_df.empty:
                    raise ValueError("fx_df is required for non-base currency conversion")
                fx_key = (str(month), currency)
                if fx_key not in fx_lookup:
                    raise ValueError(f"missing FX rate for month={month} currency={currency}")
                amount = amount * fx_lookup[fx_key]

            rows.append(
                {
                    "scenario_id": row["scenario_id"],
                    "entity_id": row["entity_id"],
                    "month": str(month),
                    "account_code": row["account_code"],
                    "posting_type": "expense",
                    "source_module": "prof_fee",
                    "reference_id": None,
                    "description": desc,
                    "amount": float(amount),
                }
            )

    if not rows:
        return _empty_output()

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values(
        ["scenario_id", "entity_id", "month", "account_code"]
    ).reset_index(drop=True)
