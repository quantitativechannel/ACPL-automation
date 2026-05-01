from __future__ import annotations

import sqlite3

import pandas as pd

OUTPUT_TABLES = {
    "monthly_postings",
    "capacity_rollforward",
    "fund_rollforward",
    "forecast_runs",
    "forecast_results",
}

BASE_ASSUMPTION_TABLES = {
    "capacity_assumptions",
    "maa_assumptions",
    "fund_assumptions",
    "prof_fee_assumptions",
    "other_exp_assumptions",
    "medical_assumptions",
    "manual_cashflow_items",
}


def create_scenario(
    conn: sqlite3.Connection,
    scenario_name: str,
    description: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO scenarios (scenario_name, description, active_flag)
        VALUES (?, ?, 1)
        """,
        (scenario_name, description),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_active_scenarios(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT scenario_id, scenario_name, description, active_flag
        FROM scenarios
        WHERE active_flag = 1
        ORDER BY scenario_id
        """,
        conn,
    )


def deactivate_scenario(conn: sqlite3.Connection, scenario_id: int) -> None:
    conn.execute(
        "UPDATE scenarios SET active_flag = 0 WHERE scenario_id = ?",
        (scenario_id,),
    )
    conn.commit()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _columns_for_table(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return [str(row[1]) for row in rows]


def _discover_clone_tables(conn: sqlite3.Connection) -> list[str]:
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }

    clone_tables = set()
    for table in tables:
        if table in OUTPUT_TABLES:
            continue
        cols = _columns_for_table(conn, table)
        if "scenario_id" not in cols:
            continue
        if table == "scenarios":
            continue
        if table in BASE_ASSUMPTION_TABLES or "manual_override" in table:
            clone_tables.add(table)

    return sorted(clone_tables)


def clone_scenario(
    conn: sqlite3.Connection,
    source_scenario_id: int,
    new_scenario_name: str,
    description: str | None = None,
) -> int:
    source_row = conn.execute(
        "SELECT scenario_id FROM scenarios WHERE scenario_id = ?",
        (source_scenario_id,),
    ).fetchone()
    if source_row is None:
        raise ValueError(f"Source scenario_id {source_scenario_id} does not exist")

    new_scenario_id = create_scenario(conn, new_scenario_name, description)

    for table in _discover_clone_tables(conn):
        if not _table_exists(conn, table):
            continue
        columns = _columns_for_table(conn, table)
        insert_cols = [c for c in columns if c != "row_id"]
        if "scenario_id" not in insert_cols:
            continue

        select_expr = ["? AS scenario_id" if c == "scenario_id" else c for c in insert_cols]

        conn.execute(
            f"""
            INSERT INTO {table} ({', '.join(insert_cols)})
            SELECT {', '.join(select_expr)}
            FROM {table}
            WHERE scenario_id = ?
            """,
            (new_scenario_id, source_scenario_id),
        )

    conn.commit()
    return new_scenario_id
