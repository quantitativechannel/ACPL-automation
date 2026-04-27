from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd


def _coerce_frame(rows: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame(rows)


def _upsert_dataframe(
    conn: sqlite3.Connection,
    frame: pd.DataFrame,
    *,
    table: str,
    columns: list[str],
    conflict_cols: list[str],
    update_cols: list[str],
) -> None:
    if frame.empty:
        return

    payload = frame.reindex(columns=columns)
    placeholders = ", ".join(["?"] * len(columns))
    insert_cols = ", ".join(columns)
    conflict = ", ".join(conflict_cols)
    updates = ", ".join([f"{col} = excluded.{col}" for col in update_cols])

    conn.executemany(
        f"""
        INSERT INTO {table} ({insert_cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict}) DO UPDATE SET
            {updates}
        """,
        [tuple(row) for row in payload.itertuples(index=False, name=None)],
    )
    conn.commit()


def _insert_dataframe(
    conn: sqlite3.Connection,
    frame: pd.DataFrame,
    *,
    table: str,
    columns: list[str],
) -> None:
    if frame.empty:
        return

    payload = frame.reindex(columns=columns)
    placeholders = ", ".join(["?"] * len(columns))
    insert_cols = ", ".join(columns)

    conn.executemany(
        f"INSERT INTO {table} ({insert_cols}) VALUES ({placeholders})",
        [tuple(row) for row in payload.itertuples(index=False, name=None)],
    )
    conn.commit()


def _list_rows(
    conn: sqlite3.Connection,
    *,
    sql: str,
    params: tuple[Any, ...] = (),
) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def upsert_income_revenue_policies(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "policy_name",
        "revenue_type",
        "rate",
        "vat_rate",
        "cit_rate",
        "active_flag",
    ]
    _upsert_dataframe(
        conn,
        frame,
        table="income_revenue_policies",
        columns=columns,
        conflict_cols=["policy_name"],
        update_cols=[col for col in columns if col != "policy_name"],
    )


def list_income_revenue_policies(conn: sqlite3.Connection) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="SELECT * FROM income_revenue_policies ORDER BY policy_name, policy_id",
    )


def upsert_capacity_assumptions(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "scenario_id",
        "project_group",
        "month",
        "new_capacity_w",
        "addition_timing_factor",
        "avg_equity_price_per_w",
        "manual_project_count_override",
        "manual_region_count_override",
        "notes",
    ]
    _upsert_dataframe(
        conn,
        frame,
        table="capacity_assumptions",
        columns=columns,
        conflict_cols=["scenario_id", "project_group", "month"],
        update_cols=[
            "new_capacity_w",
            "addition_timing_factor",
            "avg_equity_price_per_w",
            "manual_project_count_override",
            "manual_region_count_override",
            "notes",
        ],
    )


def list_capacity_assumptions(conn: sqlite3.Connection, scenario_id: int) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="""
        SELECT *
        FROM capacity_assumptions
        WHERE scenario_id = ?
        ORDER BY month, project_group, row_id
        """,
        params=(scenario_id,),
    )


def upsert_maa_assumptions(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "scenario_id",
        "project_group",
        "month",
        "incentive_1_flag",
        "incentive_2_flag",
        "reimbursed_cost_ex_vat",
        "notes",
    ]
    _upsert_dataframe(
        conn,
        frame,
        table="maa_assumptions",
        columns=columns,
        conflict_cols=["scenario_id", "project_group", "month"],
        update_cols=[
            "incentive_1_flag",
            "incentive_2_flag",
            "reimbursed_cost_ex_vat",
            "notes",
        ],
    )


def list_maa_assumptions(conn: sqlite3.Connection, scenario_id: int) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="""
        SELECT *
        FROM maa_assumptions
        WHERE scenario_id = ?
        ORDER BY month, project_group, row_id
        """,
        params=(scenario_id,),
    )


def upsert_revenue_allocation_rules(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "revenue_type",
        "recipient_entity_code",
        "allocation_pct",
        "haircut_pct",
        "active_flag",
    ]
    _upsert_dataframe(
        conn,
        frame,
        table="revenue_allocation_rules",
        columns=columns,
        conflict_cols=["revenue_type", "recipient_entity_code"],
        update_cols=["allocation_pct", "haircut_pct", "active_flag"],
    )


def list_revenue_allocation_rules(conn: sqlite3.Connection) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="""
        SELECT *
        FROM revenue_allocation_rules
        ORDER BY revenue_type, recipient_entity_code, rule_id
        """,
    )


def upsert_cash_collection_rules(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "rule_id",
        "revenue_type",
        "collection_method",
        "collection_months",
        "settlement_month",
        "active_flag",
    ]
    _upsert_dataframe(
        conn,
        frame,
        table="cash_collection_rules",
        columns=columns,
        conflict_cols=["rule_id"],
        update_cols=[
            "revenue_type",
            "collection_method",
            "collection_months",
            "settlement_month",
            "active_flag",
        ],
    )


def list_cash_collection_rules(conn: sqlite3.Connection) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="SELECT * FROM cash_collection_rules ORDER BY rule_id",
    )


def upsert_fund_assumptions(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "scenario_id",
        "fund_name",
        "month",
        "initial_fund_equity_contribution",
        "fixed_expense_contribution",
        "gp_commitment_pct",
        "lp_commitment_pct",
        "management_fee_rate",
        "vat_rate",
        "cit_rate",
        "incentive_flag",
        "notes",
    ]
    _upsert_dataframe(
        conn,
        frame,
        table="fund_assumptions",
        columns=columns,
        conflict_cols=["scenario_id", "fund_name", "month"],
        update_cols=[
            "initial_fund_equity_contribution",
            "fixed_expense_contribution",
            "gp_commitment_pct",
            "lp_commitment_pct",
            "management_fee_rate",
            "vat_rate",
            "cit_rate",
            "incentive_flag",
            "notes",
        ],
    )


def list_fund_assumptions(conn: sqlite3.Connection, scenario_id: int) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="""
        SELECT *
        FROM fund_assumptions
        WHERE scenario_id = ?
        ORDER BY month, fund_name, row_id
        """,
        params=(scenario_id,),
    )


def insert_capacity_rollforward(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "scenario_id",
        "project_group",
        "month",
        "new_capacity_w",
        "month_end_capacity_w",
        "weighted_avg_capacity_w",
        "new_project_count",
        "month_end_project_count",
        "new_region_count",
        "month_end_region_count",
        "jv_equity_new_contribution",
        "jv_equity_cumulative_contribution",
    ]
    _insert_dataframe(conn, frame, table="capacity_rollforward", columns=columns)


def list_capacity_rollforward(conn: sqlite3.Connection, scenario_id: int) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="""
        SELECT *
        FROM capacity_rollforward
        WHERE scenario_id = ?
        ORDER BY month, project_group, row_id
        """,
        params=(scenario_id,),
    )


def insert_fund_rollforward(
    conn: sqlite3.Connection,
    rows: pd.DataFrame | list[dict[str, Any]],
) -> None:
    frame = _coerce_frame(rows)
    columns = [
        "scenario_id",
        "fund_name",
        "month",
        "fund_equity_new_contribution",
        "fund_equity_cumulative_contribution",
        "fund_expense_new_contribution",
        "fund_expense_cumulative_contribution",
        "gp_new_contribution",
        "gp_cumulative_contribution",
        "lp_new_contribution",
        "lp_cumulative_contribution",
        "base_management_fee",
        "incentive_management_fee",
    ]
    _insert_dataframe(conn, frame, table="fund_rollforward", columns=columns)


def list_fund_rollforward(conn: sqlite3.Connection, scenario_id: int) -> pd.DataFrame:
    return _list_rows(
        conn,
        sql="""
        SELECT *
        FROM fund_rollforward
        WHERE scenario_id = ?
        ORDER BY month, fund_name, row_id
        """,
        params=(scenario_id,),
    )
