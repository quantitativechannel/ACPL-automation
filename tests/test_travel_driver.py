import pandas as pd
import pytest

from src.drivers.travel_driver import build_travel_postings


def test_even_monthly_spreading_without_weights() -> None:
    headcount = pd.DataFrame(
        [{"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10}]
    )
    policy = pd.DataFrame(
        [{"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200}]
    )
    allocation = pd.DataFrame([{"trip_category": "domestic", "account_code": "TRAVEL_DOM", "allocation_pct": 1.0}])

    out = build_travel_postings(headcount, policy, allocation)

    assert len(out) == 1
    assert out["amount"].iloc[0] == 10 * 6 * 1200 / 12


def test_weighted_monthly_spreading() -> None:
    headcount = pd.DataFrame(
        [
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10},
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-02", "role_type": "consultant", "active_headcount": 10},
        ]
    )
    policy = pd.DataFrame(
        [{"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200}]
    )
    allocation = pd.DataFrame([{"trip_category": "domestic", "account_code": "TRAVEL_DOM", "allocation_pct": 1.0}])
    weights = pd.DataFrame(
        [
            {"role_type": "consultant", "trip_category": "domestic", "month": "2026-01", "weight": 0.4},
            {"role_type": "consultant", "trip_category": "domestic", "month": "2026-02", "weight": 0.6},
        ]
    )

    out = build_travel_postings(headcount, policy, allocation, weights)
    jan = out.loc[out["month"] == "2026-01", "amount"].iloc[0]
    feb = out.loc[out["month"] == "2026-02", "amount"].iloc[0]

    annual_cost = 10 * 6 * 1200
    assert jan == annual_cost * 0.4
    assert feb == annual_cost * 0.6


def test_weights_must_sum_to_one() -> None:
    headcount = pd.DataFrame(
        [{"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10}]
    )
    policy = pd.DataFrame(
        [{"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200}]
    )
    allocation = pd.DataFrame([{"trip_category": "domestic", "account_code": "TRAVEL_DOM", "allocation_pct": 1.0}])
    bad_weights = pd.DataFrame(
        [
            {"role_type": "consultant", "trip_category": "domestic", "month": "2026-01", "weight": 0.7},
            {"role_type": "consultant", "trip_category": "domestic", "month": "2026-02", "weight": 0.7},
        ]
    )

    with pytest.raises(ValueError):
        build_travel_postings(headcount, policy, allocation, bad_weights)


def test_allocation_split_across_multiple_account_codes() -> None:
    headcount = pd.DataFrame(
        [{"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10}]
    )
    policy = pd.DataFrame(
        [{"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200}]
    )
    allocation = pd.DataFrame(
        [
            {"trip_category": "domestic", "account_code": "TRAVEL_A", "allocation_pct": 0.25},
            {"trip_category": "domestic", "account_code": "TRAVEL_B", "allocation_pct": 0.75},
        ]
    )

    out = build_travel_postings(headcount, policy, allocation)
    total = 10 * 6 * 1200 / 12
    assert len(out) == 2
    assert out.loc[out["account_code"] == "TRAVEL_A", "amount"].iloc[0] == total * 0.25
    assert out.loc[out["account_code"] == "TRAVEL_B", "amount"].iloc[0] == total * 0.75


def test_allocation_pct_supports_decimal_and_percent_formats() -> None:
    headcount = pd.DataFrame(
        [
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10},
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "manager", "active_headcount": 10},
        ]
    )
    policy = pd.DataFrame(
        [
            {"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200},
            {"role_type": "manager", "trip_category": "international", "est_trips": 6, "cost_per_trip": 1200},
        ]
    )
    allocation = pd.DataFrame(
        [
            {"trip_category": "domestic", "account_code": "TRAVEL_DEC", "allocation_pct": 0.5},
            {"trip_category": "international", "account_code": "TRAVEL_PCT", "allocation_pct": 50},
        ]
    )

    out = build_travel_postings(headcount, policy, allocation)
    dec = out.loc[out["account_code"] == "TRAVEL_DEC", "amount"].iloc[0]
    pct = out.loc[out["account_code"] == "TRAVEL_PCT", "amount"].iloc[0]
    expected = 10 * 6 * 1200 / 12 * 0.5
    assert dec == expected
    assert pct == expected


def test_multiple_role_types() -> None:
    headcount = pd.DataFrame(
        [
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10},
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "manager", "active_headcount": 5},
        ]
    )
    policy = pd.DataFrame(
        [
            {"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200},
            {"role_type": "manager", "trip_category": "domestic", "est_trips": 4, "cost_per_trip": 1500},
        ]
    )
    allocation = pd.DataFrame([{"trip_category": "domestic", "account_code": "TRAVEL_DOM", "allocation_pct": 1.0}])

    out = build_travel_postings(headcount, policy, allocation)

    assert sorted(out["role_type"].unique().tolist()) == ["consultant", "manager"]
    assert len(out) == 2


def test_multiple_entities() -> None:
    headcount = pd.DataFrame(
        [
            {"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "role_type": "consultant", "active_headcount": 10},
            {"scenario_id": 1, "entity_id": "E2", "month": "2026-01", "role_type": "consultant", "active_headcount": 10},
        ]
    )
    policy = pd.DataFrame(
        [{"role_type": "consultant", "trip_category": "domestic", "est_trips": 6, "cost_per_trip": 1200}]
    )
    allocation = pd.DataFrame([{"trip_category": "domestic", "account_code": "TRAVEL_DOM", "allocation_pct": 1.0}])

    out = build_travel_postings(headcount, policy, allocation)

    assert sorted(out["entity_id"].unique().tolist()) == ["E1", "E2"]
    assert len(out) == 2


def test_empty_input_returns_expected_columns() -> None:
    out = build_travel_postings(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
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
        "role_type",
        "trip_category",
    ]
    assert out.empty
