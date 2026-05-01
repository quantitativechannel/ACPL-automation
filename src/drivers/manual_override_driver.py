from __future__ import annotations

import pandas as pd

_REQUIRED_COLUMNS = {
    "scenario_id",
    "entity_id",
    "month",
    "account_code",
    "posting_type",
    "amount",
    "description",
    "source_module",
    "reference_id",
}

_ALLOWED_POSTING_TYPES = {
    "revenue_recognition",
    "cash_receipt",
    "expense",
    "cash_payment",
    "capital_contribution",
    "fund_contribution",
    "transfer",
    "manual_adjustment",
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
    "revenue_type",
    "counterparty",
]



def build_manual_override_postings(overrides_df: pd.DataFrame) -> pd.DataFrame:
    overrides = overrides_df.copy()
    overrides.columns = [str(c).strip().lower() for c in overrides.columns]

    missing = _REQUIRED_COLUMNS.difference(overrides.columns)
    if missing:
        raise ValueError(f"Manual override input missing required columns: {', '.join(sorted(missing))}")

    if overrides.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    for optional_col in ["revenue_type", "counterparty"]:
        if optional_col not in overrides.columns:
            overrides[optional_col] = ""

    overrides["month"] = pd.to_datetime(overrides["month"], errors="coerce").dt.to_period("M").astype(str)
    if (overrides["month"] == "NaT").any():
        raise ValueError("Manual override input contains invalid month values")

    overrides["posting_type"] = overrides["posting_type"].astype(str).str.strip().str.lower()
    unsupported = set(overrides["posting_type"].dropna().unique()) - _ALLOWED_POSTING_TYPES
    if unsupported:
        raise ValueError(f"Unsupported posting_type values: {', '.join(sorted(unsupported))}")

    source_module = overrides["source_module"].fillna("").astype(str).str.strip()
    overrides["source_module"] = source_module.mask(source_module == "", "manual_override")

    overrides["amount"] = pd.to_numeric(overrides["amount"], errors="coerce")
    if overrides["amount"].isna().any():
        raise ValueError("Manual override input contains invalid amount values")

    out = overrides[_OUTPUT_COLUMNS].copy()
    return out.reset_index(drop=True)
