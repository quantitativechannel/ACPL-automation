from __future__ import annotations

import sqlite3
from datetime import datetime

from src.db.connection import create_connection
from typing import Any


def connect_db(db_path: str = ":memory:") -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    return create_connection(db_path)


def create_schema(conn: sqlite3.Connection) -> None:
    """Create ACPL forecasting schema tables if they do not exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS entities (
            entity_id INTEGER PRIMARY KEY,
            entity_code TEXT NOT NULL UNIQUE,
            entity_name TEXT NOT NULL,
            base_currency TEXT NOT NULL,
            country TEXT,
            active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS account_map (
            account_code TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            report_line_name TEXT,
            report_section TEXT,
            cashflow_line_name TEXT,
            expense_type TEXT,
            sort_order INTEGER,
            active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS report_lines (
            report_line_id INTEGER PRIMARY KEY,
            report_name TEXT NOT NULL,
            line_code TEXT NOT NULL,
            line_name TEXT NOT NULL,
            parent_line_code TEXT,
            section_name TEXT,
            display_order INTEGER,
            sign_convention TEXT,
            active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
            UNIQUE(report_name, line_code)
        );

        CREATE TABLE IF NOT EXISTS scenarios (
            scenario_id INTEGER PRIMARY KEY,
            scenario_name TEXT NOT NULL UNIQUE,
            description TEXT,
            active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            location TEXT,
            level TEXT,
            role_type TEXT,
            base_salary REAL NOT NULL,
            bonus_formula_type TEXT,
            social_insurance_flag INTEGER NOT NULL DEFAULT 0 CHECK (social_insurance_flag IN (0, 1)),
            housing_fund_flag INTEGER NOT NULL DEFAULT 0 CHECK (housing_fund_flag IN (0, 1)),
            medical_flag INTEGER NOT NULL DEFAULT 0 CHECK (medical_flag IN (0, 1)),
            start_date TEXT,
            end_date TEXT,
            active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
        );

        CREATE TABLE IF NOT EXISTS travel_policy (
            role_type TEXT NOT NULL,
            trip_category TEXT NOT NULL,
            est_trips REAL NOT NULL DEFAULT 0,
            cost_per_trip REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (role_type, trip_category)
        );

        CREATE TABLE IF NOT EXISTS travel_allocation (
            trip_category TEXT NOT NULL,
            account_code TEXT NOT NULL,
            allocation_pct REAL NOT NULL,
            PRIMARY KEY (trip_category, account_code),
            FOREIGN KEY (account_code) REFERENCES account_map(account_code)
        );

        CREATE TABLE IF NOT EXISTS prof_fee_assumptions (
            row_id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            vendor TEXT,
            account_code TEXT NOT NULL,
            fee_name TEXT NOT NULL,
            details TEXT,
            basis_type TEXT,
            currency TEXT,
            assumption_value REAL NOT NULL,
            start_date TEXT,
            end_date TEXT,
            scenario_id INTEGER NOT NULL,
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (account_code) REFERENCES account_map(account_code),
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
        );

        CREATE TABLE IF NOT EXISTS other_exp_assumptions (
            row_id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            vendor TEXT,
            account_code TEXT NOT NULL,
            expense_name TEXT NOT NULL,
            details TEXT,
            basis_type TEXT,
            currency TEXT,
            assumption_value REAL NOT NULL,
            start_date TEXT,
            end_date TEXT,
            scenario_id INTEGER NOT NULL,
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (account_code) REFERENCES account_map(account_code),
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
        );

        CREATE TABLE IF NOT EXISTS medical_assumptions (
            row_id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            medical_type TEXT NOT NULL,
            annual_cost REAL NOT NULL,
            scenario_id INTEGER NOT NULL,
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
        );

        CREATE TABLE IF NOT EXISTS manual_cashflow_items (
            row_id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            cashflow_line_name TEXT NOT NULL,
            month TEXT NOT NULL,
            amount REAL NOT NULL,
            scenario_id INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
        );

        CREATE TABLE IF NOT EXISTS monthly_postings (
            posting_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            account_code TEXT NOT NULL,
            source_module TEXT NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id),
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
            FOREIGN KEY (account_code) REFERENCES account_map(account_code)
        );

        CREATE TABLE IF NOT EXISTS forecast_runs (
            run_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            run_timestamp TEXT NOT NULL,
            start_month TEXT NOT NULL,
            end_month TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
        );

        CREATE INDEX IF NOT EXISTS idx_monthly_postings_core
            ON monthly_postings(scenario_id, entity_id, month, account_code);

        CREATE INDEX IF NOT EXISTS idx_prof_fee_assumptions_core
            ON prof_fee_assumptions(scenario_id, entity_id, account_code);

        CREATE INDEX IF NOT EXISTS idx_other_exp_assumptions_core
            ON other_exp_assumptions(scenario_id, entity_id, account_code);

        CREATE TABLE IF NOT EXISTS income_revenue_policies (
            policy_id INTEGER PRIMARY KEY,
            policy_name TEXT UNIQUE NOT NULL,
            revenue_type TEXT NOT NULL,
            rate REAL NOT NULL DEFAULT 0,
            vat_rate REAL NOT NULL DEFAULT 0,
            cit_rate REAL NOT NULL DEFAULT 0,
            active_flag INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS capacity_assumptions (
            row_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            project_group TEXT NOT NULL,
            month TEXT NOT NULL,
            new_capacity_w REAL NOT NULL DEFAULT 0,
            addition_timing_factor REAL NOT NULL DEFAULT 0,
            avg_equity_price_per_w REAL NOT NULL DEFAULT 0.2,
            manual_project_count_override REAL,
            manual_region_count_override REAL,
            notes TEXT,
            UNIQUE (scenario_id, project_group, month)
        );

        CREATE TABLE IF NOT EXISTS capacity_rollforward (
            row_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            project_group TEXT NOT NULL,
            month TEXT NOT NULL,
            new_capacity_w REAL NOT NULL DEFAULT 0,
            month_end_capacity_w REAL NOT NULL DEFAULT 0,
            weighted_avg_capacity_w REAL NOT NULL DEFAULT 0,
            new_project_count INTEGER NOT NULL DEFAULT 0,
            month_end_project_count INTEGER NOT NULL DEFAULT 0,
            new_region_count INTEGER NOT NULL DEFAULT 0,
            month_end_region_count INTEGER NOT NULL DEFAULT 0,
            jv_equity_new_contribution REAL NOT NULL DEFAULT 0,
            jv_equity_cumulative_contribution REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS maa_assumptions (
            row_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            project_group TEXT NOT NULL,
            month TEXT NOT NULL,
            incentive_1_flag INTEGER NOT NULL DEFAULT 0,
            incentive_2_flag INTEGER NOT NULL DEFAULT 0,
            reimbursed_cost_ex_vat REAL NOT NULL DEFAULT 0,
            notes TEXT,
            UNIQUE (scenario_id, project_group, month)
        );

        CREATE TABLE IF NOT EXISTS revenue_allocation_rules (
            rule_id INTEGER PRIMARY KEY,
            revenue_type TEXT NOT NULL,
            recipient_entity_code TEXT NOT NULL,
            allocation_pct REAL NOT NULL DEFAULT 0,
            haircut_pct REAL NOT NULL DEFAULT 0,
            active_flag INTEGER NOT NULL DEFAULT 1,
            UNIQUE (revenue_type, recipient_entity_code)
        );

        CREATE TABLE IF NOT EXISTS cash_collection_rules (
            rule_id INTEGER PRIMARY KEY,
            revenue_type TEXT NOT NULL,
            collection_method TEXT NOT NULL,
            collection_months TEXT,
            settlement_month TEXT,
            active_flag INTEGER NOT NULL DEFAULT 1,
            UNIQUE (revenue_type, collection_method, collection_months, settlement_month)
        );

        CREATE TABLE IF NOT EXISTS fund_assumptions (
            row_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            fund_name TEXT NOT NULL,
            month TEXT NOT NULL,
            initial_fund_equity_contribution REAL NOT NULL DEFAULT 0,
            fixed_expense_contribution REAL NOT NULL DEFAULT 0,
            gp_commitment_pct REAL,
            lp_commitment_pct REAL,
            management_fee_rate REAL NOT NULL DEFAULT 0,
            vat_rate REAL NOT NULL DEFAULT 0,
            cit_rate REAL NOT NULL DEFAULT 0,
            incentive_flag INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            UNIQUE (scenario_id, fund_name, month)
        );

        CREATE TABLE IF NOT EXISTS fund_rollforward (
            row_id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL,
            fund_name TEXT NOT NULL,
            month TEXT NOT NULL,
            fund_equity_new_contribution REAL NOT NULL DEFAULT 0,
            fund_equity_cumulative_contribution REAL NOT NULL DEFAULT 0,
            fund_expense_new_contribution REAL NOT NULL DEFAULT 0,
            fund_expense_cumulative_contribution REAL NOT NULL DEFAULT 0,
            gp_new_contribution REAL NOT NULL DEFAULT 0,
            gp_cumulative_contribution REAL NOT NULL DEFAULT 0,
            lp_new_contribution REAL NOT NULL DEFAULT 0,
            lp_cumulative_contribution REAL NOT NULL DEFAULT 0,
            base_management_fee REAL NOT NULL DEFAULT 0,
            incentive_management_fee REAL NOT NULL DEFAULT 0
        );
        """
    )
    _add_column_if_missing(conn, "monthly_postings", "posting_type", "TEXT")
    _add_column_if_missing(conn, "monthly_postings", "revenue_type", "TEXT")
    _add_column_if_missing(conn, "monthly_postings", "counterparty", "TEXT")
    conn.commit()


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    column_type: str,
) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _insert_row(conn: sqlite3.Connection, table: str, payload: dict[str, Any]) -> int:
    columns = ", ".join(payload.keys())
    placeholders = ", ".join(["?"] * len(payload))
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(payload.values()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def insert_entity(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    return _insert_row(conn, "entities", payload)


def get_entity_by_code(conn: sqlite3.Connection, entity_code: str) -> sqlite3.Row | None:
    cursor = conn.execute("SELECT * FROM entities WHERE entity_code = ?", (entity_code,))
    return cursor.fetchone()


def insert_scenario(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    return _insert_row(conn, "scenarios", payload)


def insert_account_map(conn: sqlite3.Connection, payload: dict[str, Any]) -> str:
    _insert_row(conn, "account_map", payload)
    return str(payload["account_code"])


def insert_monthly_posting(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    return _insert_row(conn, "monthly_postings", payload)


def fetch_monthly_postings(
    conn: sqlite3.Connection,
    scenario_id: int,
    entity_id: int,
) -> list[sqlite3.Row]:
    cursor = conn.execute(
        """
        SELECT *
        FROM monthly_postings
        WHERE scenario_id = ? AND entity_id = ?
        ORDER BY month, account_code, posting_id
        """,
        (scenario_id, entity_id),
    )
    return list(cursor.fetchall())


def insert_forecast_run(
    conn: sqlite3.Connection,
    scenario_id: int,
    start_month: str,
    end_month: str,
    notes: str | None = None,
) -> int:
    return _insert_row(
        conn,
        "forecast_runs",
        {
            "scenario_id": scenario_id,
            "run_timestamp": datetime.utcnow().isoformat(timespec="seconds"),
            "start_month": start_month,
            "end_month": end_month,
            "notes": notes,
        },
    )
