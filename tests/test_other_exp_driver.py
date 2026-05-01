import pandas as pd
import pytest

from src.drivers.other_exp_driver import build_other_exp_postings


def _base_row(**overrides: object) -> dict[str, object]:
    row = {
        "scenario_id": 1,
        "entity_id": "E1",
        "vendor": "Vendor A",
        "account_code": "6101",
        "expense_name": "Other Expense",
        "details": "Detail",
        "basis_type": "monthly",
        "currency": "RMB",
        "assumption_value": 120.0,
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
    }
    row.update(overrides)
    return row


def test_monthly_recurring_assumption() -> None:
    df = pd.DataFrame([_base_row()])
    out = build_other_exp_postings(df)
    assert out["month"].tolist() == ["2026-01", "2026-02", "2026-03"]
    assert out["amount"].tolist() == [120.0, 120.0, 120.0]


def test_lump_sum() -> None:
    df = pd.DataFrame([_base_row(basis_type="lump_sum", assumption_value=300.0)])
    out = build_other_exp_postings(df)
    assert len(out) == 1
    assert out.iloc[0]["month"] == "2026-01"
    assert out.iloc[0]["amount"] == 300.0


def test_annual_spread() -> None:
    df = pd.DataFrame([_base_row(basis_type="annual_spread", assumption_value=1200.0, end_date="2026-12-31")])
    out = build_other_exp_postings(df)
    assert len(out) == 12
    assert out["amount"].nunique() == 1
    assert out["amount"].iloc[0] == 100.0


def test_quarterly() -> None:
    df = pd.DataFrame([_base_row(basis_type="quarterly", assumption_value=1200.0, end_date="2026-12-31")])
    out = build_other_exp_postings(df)
    assert out["month"].tolist() == ["2026-03", "2026-06", "2026-09", "2026-12"]
    assert out["amount"].tolist() == [300.0, 300.0, 300.0, 300.0]


def test_quarterly_start() -> None:
    df = pd.DataFrame([_base_row(basis_type="quarterly_start", assumption_value=1200.0, end_date="2026-12-31")])
    out = build_other_exp_postings(df)
    assert out["month"].tolist() == ["2026-01", "2026-04", "2026-07", "2026-10"]
    assert out["amount"].tolist() == [300.0, 300.0, 300.0, 300.0]


def test_specific_month() -> None:
    df = pd.DataFrame([_base_row(basis_type="specific_month", assumption_value=500.0, end_date="2028-12-31")])
    out = build_other_exp_postings(df)
    assert out["month"].tolist() == ["2026-01", "2027-01", "2028-01"]
    assert out["amount"].tolist() == [500.0, 500.0, 500.0]


def test_custom_start_end_monthly() -> None:
    df = pd.DataFrame([_base_row(basis_type="custom_start_end_monthly", start_date="2026-02-01", end_date="2026-04-30")])
    out = build_other_exp_postings(df)
    assert out["month"].tolist() == ["2026-02", "2026-03", "2026-04"]


def test_fx_conversion() -> None:
    df = pd.DataFrame([_base_row(currency="USD", assumption_value=10.0)])
    fx = pd.DataFrame(
        [
            {"month": "2026-01", "currency": "USD", "rate_to_base": 7.0},
            {"month": "2026-02", "currency": "USD", "rate_to_base": 7.1},
            {"month": "2026-03", "currency": "USD", "rate_to_base": 7.2},
        ]
    )
    out = build_other_exp_postings(df, fx_df=fx, base_currency="RMB")
    assert out["amount"].round(2).tolist() == [70.0, 71.0, 72.0]


def test_missing_fx_rate_raises_error() -> None:
    df = pd.DataFrame([_base_row(currency="USD")])
    fx = pd.DataFrame([{"month": "2026-01", "currency": "USD", "rate_to_base": 7.0}])
    with pytest.raises(ValueError, match="Missing FX rate"):
        build_other_exp_postings(df, fx_df=fx)


def test_empty_input_returns_expected_columns() -> None:
    cols = [
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
    ]
    df = pd.DataFrame(columns=cols)
    out = build_other_exp_postings(df)
    assert out.empty
    assert out.columns.tolist() == [
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
