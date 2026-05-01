from __future__ import annotations

from src.data_model import connect_db, create_schema


def test_create_schema_applies_income_schema_successfully() -> None:
    conn = connect_db()
    create_schema(conn)

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'income_revenue_policies'"
    ).fetchone()
    assert row is not None


def test_income_tables_exist_after_migration() -> None:
    conn = connect_db()
    create_schema(conn)

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row[0] for row in rows}

    assert {
        "income_revenue_policies",
        "capacity_assumptions",
        "capacity_rollforward",
        "maa_assumptions",
        "revenue_allocation_rules",
        "cash_collection_rules",
        "fund_assumptions",
        "fund_rollforward",
    }.issubset(table_names)


def test_monthly_postings_contains_income_extension_columns() -> None:
    conn = connect_db()
    create_schema(conn)

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info('monthly_postings')").fetchall()
    }

    assert {"posting_type", "revenue_type", "counterparty"}.issubset(columns)
