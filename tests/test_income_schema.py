from __future__ import annotations

from pathlib import Path

from src.data_model import connect_db, create_schema


MIGRATION_004 = Path("db/migrations/004_income_schema.sql")


def _apply_income_migration(conn) -> None:
    script = MIGRATION_004.read_text(encoding="utf-8")
    conn.executescript(script)
    conn.commit()


def test_income_migration_applies_successfully() -> None:
    conn = connect_db()
    create_schema(conn)

    _apply_income_migration(conn)

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'income_revenue_policies'"
    ).fetchone()
    assert row is not None


def test_income_tables_exist_after_migration() -> None:
    conn = connect_db()
    create_schema(conn)
    _apply_income_migration(conn)

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
    _apply_income_migration(conn)

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info('monthly_postings')").fetchall()
    }

    assert {"posting_type", "revenue_type", "counterparty"}.issubset(columns)
