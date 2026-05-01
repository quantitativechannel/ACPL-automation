import pandas as pd
import pytest

from src.drivers.manual_override_driver import build_manual_override_postings


def _base_row(**overrides: object) -> dict[str, object]:
    row = {
        "scenario_id": 1,
        "entity_id": "E1",
        "month": "2026-01-15",
        "account_code": "6101",
        "posting_type": "expense",
        "amount": 123.45,
        "description": "Manual adjustment",
        "source_module": "manual_input",
        "reference_id": "man-001",
    }
    row.update(overrides)
    return row


def test_valid_manual_expense_override() -> None:
    out = build_manual_override_postings(pd.DataFrame([_base_row(posting_type="expense")]))
    assert len(out) == 1
    assert out.iloc[0]["posting_type"] == "expense"


def test_valid_manual_revenue_override() -> None:
    out = build_manual_override_postings(pd.DataFrame([_base_row(posting_type="revenue_recognition", amount=500.0)]))
    assert len(out) == 1
    assert out.iloc[0]["posting_type"] == "revenue_recognition"
    assert out.iloc[0]["amount"] == 500.0


def test_negative_adjustment_allowed() -> None:
    out = build_manual_override_postings(pd.DataFrame([_base_row(posting_type="manual_adjustment", amount=-50.0)]))
    assert out.iloc[0]["amount"] == -50.0


def test_unsupported_posting_type_raises_error() -> None:
    with pytest.raises(ValueError, match="Unsupported posting_type"):
        build_manual_override_postings(pd.DataFrame([_base_row(posting_type="invalid_type")]))


def test_missing_required_columns_raises_error() -> None:
    df = pd.DataFrame([{"scenario_id": 1, "entity_id": "E1"}])
    with pytest.raises(ValueError, match="missing required columns"):
        build_manual_override_postings(df)


def test_month_normalization() -> None:
    out = build_manual_override_postings(pd.DataFrame([_base_row(month="2026/02/28")]))
    assert out.iloc[0]["month"] == "2026-02"


def test_blank_source_module_defaults_to_manual_override() -> None:
    out = build_manual_override_postings(pd.DataFrame([_base_row(source_module="   ")]))
    assert out.iloc[0]["source_module"] == "manual_override"


def test_empty_input_returns_expected_columns() -> None:
    df = pd.DataFrame(
        columns=[
            "scenario_id",
            "entity_id",
            "month",
            "account_code",
            "posting_type",
            "amount",
            "description",
            "source_module",
            "reference_id",
        ]
    )
    out = build_manual_override_postings(df)
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
        "revenue_type",
        "counterparty",
    ]
