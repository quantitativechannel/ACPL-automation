import pandas as pd

from src.drivers.treasury_driver import (
    build_group_treasury_rollforward,
    build_treasury_rollforward,
)


def test_simple_opening_to_closing_rollforward() -> None:
    opening = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0}])
    operating = pd.DataFrame(
        [{"entity_id": "E1", "month": "2026-01", "operating_inflow": 50.0, "operating_outflow": 20.0}]
    )

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-01")

    assert out.iloc[0]["closing_cash"] == 130.0


def test_closing_cash_carries_to_next_month_opening() -> None:
    opening = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0}])
    operating = pd.DataFrame(
        [
            {"entity_id": "E1", "month": "2026-01", "operating_inflow": 50.0, "operating_outflow": 20.0},
            {"entity_id": "E1", "month": "2026-02", "operating_inflow": 10.0, "operating_outflow": 5.0},
        ]
    )

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-02")

    jan = out[out["month"] == "2026-01"].iloc[0]
    feb = out[out["month"] == "2026-02"].iloc[0]
    assert jan["closing_cash"] == 130.0
    assert feb["opening_cash"] == 130.0
    assert feb["closing_cash"] == 135.0


def test_manual_cashflow_included() -> None:
    opening = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0}])
    operating = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "operating_inflow": 0.0, "operating_outflow": 0.0}])
    manual = pd.DataFrame(
        [
            {"entity_id": "E1", "month": "2026-01", "cashflow_type": "misc", "amount": 25.0, "description": "cash in"},
            {"entity_id": "E1", "month": "2026-01", "cashflow_type": "misc", "amount": -5.0, "description": "cash out"},
        ]
    )

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-01", manual_cashflow_df=manual)

    assert out.iloc[0]["manual_net_cashflow"] == 20.0
    assert out.iloc[0]["closing_cash"] == 120.0


def test_injection_included() -> None:
    opening = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0}])
    operating = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "operating_inflow": 0.0, "operating_outflow": 0.0}])
    injections = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "amount": 40.0, "description": "capital"}])

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-01", injections_df=injections)

    assert out.iloc[0]["injections"] == 40.0
    assert out.iloc[0]["closing_cash"] == 140.0


def test_transfer_out_decreases_one_entity() -> None:
    opening = pd.DataFrame(
        [
            {"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0},
            {"entity_id": "E2", "month": "2026-01", "opening_cash": 50.0},
        ]
    )
    operating = pd.DataFrame(
        [
            {"entity_id": "E1", "month": "2026-01", "operating_inflow": 0.0, "operating_outflow": 0.0},
            {"entity_id": "E2", "month": "2026-01", "operating_inflow": 0.0, "operating_outflow": 0.0},
        ]
    )
    transfers = pd.DataFrame(
        [{"from_entity_id": "E1", "to_entity_id": "E2", "month": "2026-01", "amount": 30.0, "description": "xfer"}]
    )

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-01", transfers_df=transfers)

    e1 = out[out["entity_id"] == "E1"].iloc[0]
    assert e1["transfer_out"] == 30.0
    assert e1["closing_cash"] == 70.0


def test_transfer_in_increases_another_entity() -> None:
    opening = pd.DataFrame(
        [
            {"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0},
            {"entity_id": "E2", "month": "2026-01", "opening_cash": 50.0},
        ]
    )
    operating = pd.DataFrame(
        [
            {"entity_id": "E1", "month": "2026-01", "operating_inflow": 0.0, "operating_outflow": 0.0},
            {"entity_id": "E2", "month": "2026-01", "operating_inflow": 0.0, "operating_outflow": 0.0},
        ]
    )
    transfers = pd.DataFrame(
        [{"from_entity_id": "E1", "to_entity_id": "E2", "month": "2026-01", "amount": 30.0, "description": "xfer"}]
    )

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-01", transfers_df=transfers)

    e2 = out[out["entity_id"] == "E2"].iloc[0]
    assert e2["transfer_in"] == 30.0
    assert e2["closing_cash"] == 80.0


def test_group_rollforward_aggregates_correctly() -> None:
    rollforward = pd.DataFrame(
        [
            {
                "entity_id": "E1",
                "month": "2026-01",
                "opening_cash": 100.0,
                "operating_inflow": 20.0,
                "operating_outflow": 5.0,
                "manual_net_cashflow": 0.0,
                "injections": 0.0,
                "transfer_in": 0.0,
                "transfer_out": 10.0,
                "closing_cash": 105.0,
            },
            {
                "entity_id": "E2",
                "month": "2026-01",
                "opening_cash": 200.0,
                "operating_inflow": 30.0,
                "operating_outflow": 15.0,
                "manual_net_cashflow": 5.0,
                "injections": 10.0,
                "transfer_in": 10.0,
                "transfer_out": 0.0,
                "closing_cash": 240.0,
            },
        ]
    )

    grouped = build_group_treasury_rollforward(rollforward)
    row = grouped.iloc[0]

    assert row["opening_cash"] == 300.0
    assert row["operating_inflow"] == 50.0
    assert row["operating_outflow"] == 20.0
    assert row["manual_net_cashflow"] == 5.0
    assert row["injections"] == 10.0
    assert row["transfer_in"] == 10.0
    assert row["transfer_out"] == 10.0
    assert row["closing_cash"] == 345.0


def test_missing_months_filled_with_zeros_except_carried_opening_cash() -> None:
    opening = pd.DataFrame([{"entity_id": "E1", "month": "2026-01", "opening_cash": 100.0}])
    operating = pd.DataFrame([{"entity_id": "E1", "month": "2026-03", "operating_inflow": 30.0, "operating_outflow": 10.0}])

    out = build_treasury_rollforward(opening, operating, "2026-01", "2026-03")

    jan = out[out["month"] == "2026-01"].iloc[0]
    feb = out[out["month"] == "2026-02"].iloc[0]
    mar = out[out["month"] == "2026-03"].iloc[0]

    assert jan["closing_cash"] == 100.0
    assert feb["opening_cash"] == 100.0
    assert feb["operating_inflow"] == 0.0
    assert feb["operating_outflow"] == 0.0
    assert feb["closing_cash"] == 100.0
    assert mar["opening_cash"] == 100.0
    assert mar["closing_cash"] == 120.0
