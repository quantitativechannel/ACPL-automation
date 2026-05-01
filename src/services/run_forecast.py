from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from src.data_model import insert_forecast_run
from src.services.forecast_orchestrator import run_forecast_orchestration


_POSTING_COLUMNS = [
    "scenario_id",
    "entity_id",
    "month",
    "account_code",
    "source_module",
    "amount",
    "entity_code",
    "posting_type",
    "reference_id",
    "description",
    "revenue_type",
    "counterparty",
]


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return any(row[1] == column for row in rows)


def _ensure_persistence_schema(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "monthly_postings", "run_id"):
        conn.execute("ALTER TABLE monthly_postings ADD COLUMN run_id INTEGER")

    for ddl in [
        """
        CREATE TABLE IF NOT EXISTS forecast_warnings (
            warning_id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            warning_type TEXT NOT NULL,
            warning_message TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS forecast_driver_summaries (
            row_id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            source_module TEXT,
            posting_type TEXT,
            row_count INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
        )
        """,
    ]:
        conn.execute(ddl)
    conn.commit()


def _insert_postings(conn: sqlite3.Connection, run_id: int, postings: pd.DataFrame) -> None:
    if postings.empty:
        return

    existing_cols = [row[1] for row in conn.execute("PRAGMA table_info('monthly_postings')").fetchall()]
    payload = postings.copy()
    for col in _POSTING_COLUMNS:
        if col not in payload.columns:
            payload[col] = pd.NA
    payload["run_id"] = run_id

    insert_cols = [col for col in (_POSTING_COLUMNS + ["run_id"]) if col in existing_cols]
    placeholders = ", ".join(["?"] * len(insert_cols))
    conn.executemany(
        f"INSERT INTO monthly_postings ({', '.join(insert_cols)}) VALUES ({placeholders})",
        [tuple(row) for row in payload[insert_cols].itertuples(index=False, name=None)],
    )


def run_forecast_and_persist(
    conn: sqlite3.Connection,
    scenario_id: int,
    start_month: str,
    end_month: str,
    inputs: dict,
    notes: str | None = None,
) -> dict[str, Any]:
    """Run forecast orchestration and persist an append-only audit trail.

    Append-only strategy:
    - Every execution creates a new row in forecast_runs and therefore a new run_id.
    - New postings are inserted and never overwrite prior postings.
    - Downstream reports should filter monthly_postings by run_id to select a specific run.
    """

    _ensure_persistence_schema(conn)
    run_id = insert_forecast_run(conn, scenario_id=scenario_id, start_month=start_month, end_month=end_month, notes=notes)

    output = run_forecast_orchestration(scenario_id, start_month, end_month, inputs)
    postings: pd.DataFrame = output["postings"]
    warnings: list[str] = output["validation_warnings"]
    summaries: pd.DataFrame = output["driver_summaries"]

    _insert_postings(conn, run_id, postings)

    if warnings:
        conn.executemany(
            "INSERT INTO forecast_warnings (run_id, warning_type, warning_message) VALUES (?, ?, ?)",
            [(run_id, "validation", msg) for msg in warnings],
        )

    if not summaries.empty:
        rows = summaries.copy()
        rows["run_id"] = run_id
        for col in ["source_module", "posting_type", "row_count", "total_amount"]:
            if col not in rows.columns:
                rows[col] = pd.NA
        conn.executemany(
            """
            INSERT INTO forecast_driver_summaries
            (run_id, source_module, posting_type, row_count, total_amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            [tuple(row) for row in rows[["run_id", "source_module", "posting_type", "row_count", "total_amount"]].itertuples(index=False, name=None)],
        )

    conn.commit()
    return {
        "run_id": run_id,
        "postings": postings,
        "validation_warnings": warnings,
        "driver_summaries": summaries,
    }
