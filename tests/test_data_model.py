import sqlite3

import pytest

from src.data_model import (
    connect_db,
    create_schema,
    fetch_monthly_postings,
    get_entity_by_code,
    insert_account_map,
    insert_entity,
    insert_forecast_run,
    insert_monthly_posting,
    insert_scenario,
)


def test_create_schema_creates_all_expected_tables() -> None:
    conn = connect_db()
    create_schema(conn)

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row[0] for row in rows}

    expected = {
        "entities",
        "account_map",
        "report_lines",
        "scenarios",
        "employees",
        "travel_policy",
        "travel_allocation",
        "prof_fee_assumptions",
        "other_exp_assumptions",
        "medical_assumptions",
        "manual_cashflow_items",
        "monthly_postings",
        "forecast_runs",
    }
    assert expected.issubset(table_names)


def test_crud_helpers_insert_and_fetch_core_rows() -> None:
    conn = connect_db()
    create_schema(conn)

    entity_id = insert_entity(
        conn,
        {
            "entity_code": "ACPL",
            "entity_name": "ACPL China",
            "base_currency": "CNY",
            "country": "CN",
            "active_flag": 1,
        },
    )
    scenario_id = insert_scenario(
        conn,
        {
            "scenario_name": "Base",
            "description": "Baseline planning case",
            "active_flag": 1,
        },
    )
    insert_account_map(
        conn,
        {
            "account_code": "TRV-INT-AIR",
            "account_name": "International Airfare",
            "report_line_name": "Travel",
            "report_section": "OPEX",
            "cashflow_line_name": "Operating Cash Outflow",
            "expense_type": "Travel",
            "sort_order": 10,
            "active_flag": 1,
        },
    )

    posting_id = insert_monthly_posting(
        conn,
        {
            "scenario_id": scenario_id,
            "entity_id": entity_id,
            "month": "2026-01-01",
            "account_code": "TRV-INT-AIR",
            "source_module": "travel",
            "amount": 1234.56,
        },
    )

    saved_entity = get_entity_by_code(conn, "ACPL")
    assert saved_entity is not None
    assert saved_entity["entity_id"] == entity_id

    postings = fetch_monthly_postings(conn, scenario_id=scenario_id, entity_id=entity_id)
    assert len(postings) == 1
    assert postings[0]["posting_id"] == posting_id
    assert postings[0]["amount"] == 1234.56


def test_foreign_key_constraints_are_enforced() -> None:
    conn = connect_db()
    create_schema(conn)

    with pytest.raises(sqlite3.IntegrityError):
        insert_monthly_posting(
            conn,
            {
                "scenario_id": 999,
                "entity_id": 888,
                "month": "2026-01-01",
                "account_code": "UNKNOWN",
                "source_module": "manual",
                "amount": 10.0,
            },
        )


def test_insert_forecast_run_persists_timestamped_run() -> None:
    conn = connect_db()
    create_schema(conn)

    scenario_id = insert_scenario(
        conn,
        {
            "scenario_name": "Flash",
            "description": "Flash report scenario",
            "active_flag": 1,
        },
    )

    run_id = insert_forecast_run(
        conn,
        scenario_id=scenario_id,
        start_month="2026-01-01",
        end_month="2026-12-01",
        notes="Initial flash run",
    )

    row = conn.execute("SELECT * FROM forecast_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row is not None
    assert row["scenario_id"] == scenario_id
    assert row["start_month"] == "2026-01-01"
    assert row["end_month"] == "2026-12-01"
    assert row["notes"] == "Initial flash run"
    assert row["run_timestamp"]
