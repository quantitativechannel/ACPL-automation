import pandas as pd
import pytest

from src.drivers.medical_benefit_driver import POSTING_COLUMNS, build_medical_benefit_postings


def _base_row(**overrides):
    row = {
        "scenario_id": 1,
        "entity_id": "E1",
        "benefit_type": "medical",
        "account_code": "6100",
        "basis_type": "monthly_fixed",
        "annual_cost": 1200.0,
        "monthly_cost": 100.0,
        "headcount": 10,
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "allocation_month": "2026-02",
        "description": "medical benefit",
    }
    row.update(overrides)
    return row


def test_monthly_fixed() -> None:
    assumptions = pd.DataFrame([_base_row(basis_type="monthly_fixed", monthly_cost=150.0)])
    out = build_medical_benefit_postings(assumptions, "2026-01", "2026-03")

    assert len(out) == 3
    assert out["amount"].tolist() == [150.0, 150.0, 150.0]


def test_annual_spread() -> None:
    assumptions = pd.DataFrame([_base_row(basis_type="annual_spread", annual_cost=1200.0)])
    out = build_medical_benefit_postings(assumptions, "2026-01", "2026-03")

    assert len(out) == 3
    assert out["amount"].tolist() == [100.0, 100.0, 100.0]


def test_annual_specific_month() -> None:
    assumptions = pd.DataFrame([_base_row(basis_type="annual_specific_month", annual_cost=600.0, allocation_month="2026-02")])
    out = build_medical_benefit_postings(assumptions, "2026-01", "2026-03")

    assert len(out) == 1
    assert out.iloc[0]["month"] == "2026-02"
    assert out.iloc[0]["amount"] == 600.0


def test_per_head_monthly() -> None:
    assumptions = pd.DataFrame([_base_row(basis_type="per_head_monthly", monthly_cost=20.0, headcount=7)])
    out = build_medical_benefit_postings(assumptions, "2026-01", "2026-03")

    assert len(out) == 3
    assert out["amount"].tolist() == [140.0, 140.0, 140.0]


def test_custom_start_end_spread() -> None:
    assumptions = pd.DataFrame([
        _base_row(
            basis_type="custom_start_end_spread",
            annual_cost=900.0,
            start_date="2026-02-01",
            end_date="2026-04-30",
        )
    ])
    out = build_medical_benefit_postings(assumptions, "2026-01", "2026-12")

    assert out["month"].tolist() == ["2026-02", "2026-03", "2026-04"]
    assert out["amount"].tolist() == [300.0, 300.0, 300.0]


def test_start_end_date_boundaries() -> None:
    assumptions = pd.DataFrame([_base_row(basis_type="monthly_fixed", monthly_cost=100.0)])
    out = build_medical_benefit_postings(assumptions, "2026-02", "2026-02")

    assert len(out) == 1
    assert out.iloc[0]["month"] == "2026-02"


def test_empty_input_returns_expected_columns() -> None:
    assumptions = pd.DataFrame(columns=[
        "scenario_id",
        "entity_id",
        "benefit_type",
        "account_code",
        "basis_type",
        "annual_cost",
        "monthly_cost",
        "headcount",
        "start_date",
        "end_date",
        "allocation_month",
        "description",
    ])
    out = build_medical_benefit_postings(assumptions, "2026-01", "2026-12")

    assert out.empty
    assert out.columns.tolist() == POSTING_COLUMNS


def test_unsupported_basis_type_raises_error() -> None:
    assumptions = pd.DataFrame([_base_row(basis_type="not_supported")])

    with pytest.raises(ValueError, match="Unsupported basis_type"):
        build_medical_benefit_postings(assumptions, "2026-01", "2026-12")
