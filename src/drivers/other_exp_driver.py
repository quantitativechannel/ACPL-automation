from __future__ import annotations

import hashlib

import pandas as pd

_REQUIRED_COLUMNS = {
    "scenario_id",
    "entity_id",
    "vendor",
    "account_code",
    "expense_name",
    "details",
    "basis_type",
    "currency",
    "assumption_value",
    "start_date",
    "end_date",
}

_OUTPUT_COLUMNS = [
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


def build_other_exp_postings(
    assumptions_df: pd.DataFrame,
    fx_df: pd.DataFrame | None = None,
    base_currency: str = "RMB",
) -> pd.DataFrame:
    assumptions = assumptions_df.copy()
    assumptions.columns = [str(c).strip().lower() for c in assumptions.columns]

    missing = _REQUIRED_COLUMNS.difference(assumptions.columns)
    if missing:
        raise ValueError(f"Other Exp assumptions missing required columns: {', '.join(sorted(missing))}")

    if assumptions.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    assumptions["start_date"] = pd.to_datetime(assumptions["start_date"], errors="coerce")
    assumptions["end_date"] = pd.to_datetime(assumptions["end_date"], errors="coerce")
    assumptions["assumption_value"] = pd.to_numeric(assumptions["assumption_value"], errors="coerce").fillna(0.0)
    assumptions["basis_type"] = assumptions["basis_type"].astype(str).str.strip().str.lower()
    assumptions["currency"] = assumptions["currency"].astype(str).str.strip()

    fx_lookup: dict[tuple[str, str], float] = {}
    if fx_df is not None and not fx_df.empty:
        fx = fx_df.copy()
        fx.columns = [str(c).strip().lower() for c in fx.columns]
        required_fx = {"month", "currency", "rate_to_base"}
        missing_fx = required_fx.difference(fx.columns)
        if missing_fx:
            raise ValueError(f"FX table missing required columns: {', '.join(sorted(missing_fx))}")
        fx["month"] = pd.to_datetime(fx["month"], errors="coerce").dt.to_period("M").astype(str)
        fx["currency"] = fx["currency"].astype(str).str.strip()
        fx["rate_to_base"] = pd.to_numeric(fx["rate_to_base"], errors="coerce")
        fx = fx.dropna(subset=["month", "currency", "rate_to_base"])
        fx_lookup = {(r.month, r.currency): float(r.rate_to_base) for r in fx.itertuples(index=False)}

    rows: list[dict] = []
    for rec in assumptions.itertuples(index=False):
        start = rec.start_date
        end = rec.end_date
        if pd.isna(start) or pd.isna(end) or end < start:
            continue

        months = pd.date_range(start.to_period("M").to_timestamp(), end.to_period("M").to_timestamp(), freq="MS")
        postings = _generate_basis_month_amounts(rec.basis_type, months, float(rec.assumption_value), start)

        desc = " | ".join([str(rec.vendor).strip(), str(rec.expense_name).strip(), str(rec.details).strip()]).strip()
        for month, amount in postings.items():
            converted = _convert_to_base(amount, rec.currency, base_currency, month, fx_lookup)
            ref = _build_reference_id(rec.scenario_id, rec.entity_id, rec.account_code, rec.vendor, month)
            rows.append(
                {
                    "scenario_id": rec.scenario_id,
                    "entity_id": rec.entity_id,
                    "month": month,
                    "account_code": rec.account_code,
                    "posting_type": "expense",
                    "source_module": "other_exp",
                    "reference_id": ref,
                    "description": desc,
                    "amount": converted,
                }
            )

    out = pd.DataFrame(rows, columns=_OUTPUT_COLUMNS)
    if out.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)
    return out.sort_values(["scenario_id", "entity_id", "month", "account_code"]).reset_index(drop=True)


def _generate_basis_month_amounts(basis_type: str, months: pd.DatetimeIndex, assumption_value: float, start: pd.Timestamp) -> dict[str, float]:
    result: dict[str, float] = {}
    if basis_type in {"monthly", "custom_start_end_monthly"}:
        for m in months:
            result[m.strftime("%Y-%m")] = assumption_value
    elif basis_type == "lump_sum":
        result[start.to_period("M").strftime("%Y-%m")] = assumption_value
    elif basis_type == "annual_spread":
        for m in months:
            result[m.strftime("%Y-%m")] = assumption_value / 12.0
    elif basis_type == "quarterly":
        for m in months:
            if m.month in {3, 6, 9, 12}:
                result[m.strftime("%Y-%m")] = assumption_value / 4.0
    elif basis_type == "quarterly_start":
        for m in months:
            if m.month in {1, 4, 7, 10}:
                result[m.strftime("%Y-%m")] = assumption_value / 4.0
    elif basis_type == "specific_month":
        specific = start.month
        for m in months:
            if m.month == specific:
                result[m.strftime("%Y-%m")] = assumption_value
    else:
        raise ValueError(f"Unsupported basis_type '{basis_type}'")

    return result


def _convert_to_base(amount: float, currency: str, base_currency: str, month: str, fx_lookup: dict[tuple[str, str], float]) -> float:
    if currency == base_currency:
        return amount
    key = (month, currency)
    if key not in fx_lookup:
        raise ValueError(f"Missing FX rate for currency={currency}, month={month}")
    return amount * fx_lookup[key]


def _build_reference_id(scenario_id: object, entity_id: object, account_code: object, vendor: object, month: str) -> str:
    raw = f"{scenario_id}|{entity_id}|{account_code}|{vendor}|{month}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"other_exp_{digest}"
