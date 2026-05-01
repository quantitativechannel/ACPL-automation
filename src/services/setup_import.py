from __future__ import annotations

from io import BytesIO
import sqlite3

import pandas as pd


SETUP_IMPORT_TABLES = [
    "entities",
    "scenarios",
    "account_map",
    "report_lines",
    "income_revenue_policies",
    "revenue_allocation_rules",
    "cash_collection_rules",
    "capacity_assumptions",
    "maa_assumptions",
    "fund_assumptions",
    "prof_fee_assumptions",
    "other_exp_assumptions",
    "employees",
    "travel_policy",
    "travel_allocation",
    "manual_cashflow_items",
]


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]


def required_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    required: list[str] = []
    for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall():
        _, name, _, not_null, default_value, primary_key = row[:6]
        if primary_key:
            continue
        if not_null and default_value is None:
            required.append(name)
    return required


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.dropna(how="all").copy()
    out.columns = [str(col).strip() for col in out.columns]
    out = out.where(pd.notna(out), None)
    return out


def import_table_frame(conn: sqlite3.Connection, table: str, frame: pd.DataFrame) -> int:
    if table not in SETUP_IMPORT_TABLES:
        raise ValueError(f"Unsupported import table: {table}")

    data = _clean_frame(frame)
    if data.empty:
        return 0

    allowed = table_columns(conn, table)
    if not allowed:
        raise ValueError(f"Table does not exist: {table}")

    missing = sorted(set(required_columns(conn, table)) - set(data.columns))
    if missing:
        raise ValueError(f"{table} is missing required columns: {', '.join(missing)}")

    data = data[[col for col in data.columns if col in allowed]]
    if data.empty:
        raise ValueError(f"{table} has no columns that match the database table")

    placeholders = ", ".join(["?"] * len(data.columns))
    columns = ", ".join(data.columns)
    conn.executemany(
        f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
        [tuple(row) for row in data.itertuples(index=False, name=None)],
    )
    conn.commit()
    return len(data)


def import_setup_workbook(conn: sqlite3.Connection, payload: bytes) -> dict[str, int]:
    workbook = pd.read_excel(BytesIO(payload), sheet_name=None)
    imported: dict[str, int] = {}

    for table in SETUP_IMPORT_TABLES:
        if table in workbook:
            count = import_table_frame(conn, table, workbook[table])
            if count:
                imported[table] = count

    return imported


def build_template_workbook(conn: sqlite3.Connection) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for table in SETUP_IMPORT_TABLES:
            pd.DataFrame(columns=table_columns(conn, table)).to_excel(writer, index=False, sheet_name=table[:31])
    return buffer.getvalue()
