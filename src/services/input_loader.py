from __future__ import annotations

import sqlite3

import pandas as pd


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _read_table(
    conn: sqlite3.Connection,
    table: str,
    *,
    scenario_id: int | None = None,
    active_only: bool = False,
) -> pd.DataFrame:
    if not _table_exists(conn, table):
        return pd.DataFrame()

    columns = [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]
    where: list[str] = []
    params: list[object] = []

    if scenario_id is not None and "scenario_id" in columns:
        where.append("scenario_id = ?")
        params.append(scenario_id)
    if active_only and "active_flag" in columns:
        where.append("active_flag = 1")

    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return pd.read_sql_query(sql, conn, params=tuple(params))


def _drop_generated_columns(frame: pd.DataFrame) -> pd.DataFrame:
    generated = {"row_id", "policy_id", "rule_id"}
    return frame.drop(columns=[col for col in generated if col in frame.columns], errors="ignore")


def _has_columns(frame: pd.DataFrame, columns: set[str]) -> bool:
    return not frame.empty and columns.issubset(set(frame.columns))


def load_forecast_inputs_from_db(conn: sqlite3.Connection, scenario_id: int) -> dict[str, pd.DataFrame]:
    """Build the forecast orchestrator input dictionary from persisted tables."""

    inputs: dict[str, pd.DataFrame] = {}

    table_map = {
        "capacity_assumptions": ("capacity_assumptions", True),
        "maa_assumptions": ("maa_assumptions", True),
        "revenue_policies": ("income_revenue_policies", False),
        "revenue_allocation_rules": ("revenue_allocation_rules", False),
        "cash_collection_rules": ("cash_collection_rules", False),
        "fund_assumptions": ("fund_assumptions", True),
        "prof_fee_assumptions": ("prof_fee_assumptions", True),
        "other_exp_assumptions": ("other_exp_assumptions", True),
        "travel_policy": ("travel_policy", False),
        "travel_allocation": ("travel_allocation", False),
    }

    for input_name, (table_name, scenario_scoped) in table_map.items():
        frame = _read_table(
            conn,
            table_name,
            scenario_id=scenario_id if scenario_scoped else None,
            active_only=not scenario_scoped,
        )
        if not frame.empty:
            inputs[input_name] = _drop_generated_columns(frame)

    employees = _read_table(conn, "employees", active_only=True)
    if not employees.empty:
        employees = _drop_generated_columns(employees)
        if "scenario_id" not in employees.columns:
            employees["scenario_id"] = scenario_id
        inputs["employees"] = employees

    medical = _read_table(conn, "medical_assumptions", scenario_id=scenario_id)
    medical_required = {
        "scenario_id",
        "entity_id",
        "account_code",
        "benefit_type",
        "basis_type",
        "annual_cost",
        "monthly_cost",
        "headcount",
        "start_date",
        "end_date",
        "allocation_month",
    }
    if _has_columns(medical, medical_required):
        inputs["medical_benefit_assumptions"] = _drop_generated_columns(medical)

    return inputs
