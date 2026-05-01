import pandas as pd
import pytest

from src.drivers.prof_fee_driver import build_prof_fee_postings


def _base_row() -> dict:
    return {
        "scenario_id": "Base",
        "entity_id": "E1",
        "vendor": "VendorA",
        "account_code": "PROF_FEE",
        "fee_name": "Legal",
        "details": "Contract",
        "basis_type": "monthly",
        "currency": "RMB",
        "assumption_value": 1200,
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
    }


def test_monthly_fee_over_date_range() -> None:
    df = pd.DataFrame([_base_row()])
    result = build_prof_fee_postings(df)
    assert result["month"].tolist() == ["2026-01", "2026-02", "2026-03"]
    assert result["amount"].tolist() == [1200.0, 1200.0, 1200.0]


def test_lump_sum() -> None:
    row = _base_row() | {"basis_type": "lump_sum", "assumption_value": 5000}
    result = build_prof_fee_postings(pd.DataFrame([row]))
    assert len(result) == 1
    assert result.iloc[0]["month"] == "2026-01"
    assert result.iloc[0]["amount"] == 5000.0


def test_annual_spread() -> None:
    row = _base_row() | {"basis_type": "annual_spread", "assumption_value": 12000}
    result = build_prof_fee_postings(pd.DataFrame([row]))
    assert len(result) == 12
    assert result["amount"].tolist() == [1000.0] * 12
    assert result.iloc[0]["month"] == "2026-01"
    assert result.iloc[-1]["month"] == "2026-12"


def test_quarterly() -> None:
    row = _base_row() | {"basis_type": "quarterly", "assumption_value": 4000}
    result = build_prof_fee_postings(pd.DataFrame([row]))
    assert result["month"].tolist() == ["2026-03", "2026-06", "2026-09", "2026-12"]
    assert result["amount"].tolist() == [1000.0, 1000.0, 1000.0, 1000.0]


def test_quarterly_start() -> None:
    row = _base_row() | {"basis_type": "quarterly_start", "assumption_value": 4000}
    result = build_prof_fee_postings(pd.DataFrame([row]))
    assert result["month"].tolist() == ["2026-01", "2026-04", "2026-07", "2026-10"]
    assert result["amount"].tolist() == [1000.0, 1000.0, 1000.0, 1000.0]


def test_specific_month() -> None:
    row = _base_row() | {"basis_type": "specific_month", "assumption_value": 700}
    result = build_prof_fee_postings(pd.DataFrame([row]))
    assert len(result) == 1
    assert result.iloc[0]["month"] == "2026-01"
    assert result.iloc[0]["amount"] == 700.0


def test_custom_start_end_monthly() -> None:
    row = _base_row() | {
        "basis_type": "custom_start_end_monthly",
        "assumption_value": 900,
        "start_date": "2026-02-01",
        "end_date": "2026-04-30",
    }
    result = build_prof_fee_postings(pd.DataFrame([row]))
    assert result["month"].tolist() == ["2026-02", "2026-03", "2026-04"]
    assert result["amount"].tolist() == [300.0, 300.0, 300.0]


def test_fx_conversion() -> None:
    row = _base_row() | {"currency": "USD", "assumption_value": 100}
    fx = pd.DataFrame(
        [
            {"month": "2026-01", "currency": "USD", "rate_to_base": 7.0},
            {"month": "2026-02", "currency": "USD", "rate_to_base": 7.1},
            {"month": "2026-03", "currency": "USD", "rate_to_base": 7.2},
        ]
    )
    result = build_prof_fee_postings(pd.DataFrame([row]), fx_df=fx, base_currency="RMB")
    assert result["amount"].tolist() == [700.0, 710.0, 720.0]


def test_missing_fx_rate_raises_error() -> None:
    row = _base_row() | {"currency": "USD"}
    fx = pd.DataFrame([{"month": "2026-01", "currency": "USD", "rate_to_base": 7.0}])
    with pytest.raises(ValueError, match="missing FX rate"):
        build_prof_fee_postings(pd.DataFrame([row]), fx_df=fx)


def test_unsupported_basis_type_raises_error() -> None:
    row = _base_row() | {"basis_type": "weekly"}
    with pytest.raises(ValueError, match="unsupported basis_type"):
        build_prof_fee_postings(pd.DataFrame([row]))


def test_empty_input_returns_empty_output_with_expected_columns() -> None:
    cols = [
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
    result = build_prof_fee_postings(pd.DataFrame(columns=cols))
    assert result.empty
    assert result.columns.tolist() == [
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
