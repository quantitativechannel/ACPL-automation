from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_model import connect_db, create_schema
from src.db.income_repositories import (
    list_capacity_assumptions,
    list_cash_collection_rules,
    list_fund_assumptions,
    list_maa_assumptions,
    list_revenue_allocation_rules,
    upsert_capacity_assumptions,
    upsert_cash_collection_rules,
    upsert_fund_assumptions,
    upsert_maa_assumptions,
    upsert_revenue_allocation_rules,
)


MIGRATION_004 = Path("db/migrations/004_income_schema.sql")


def _setup_income_conn():
    conn = connect_db()
    create_schema(conn)
    conn.executescript(MIGRATION_004.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def test_capacity_assumptions_insert_and_list() -> None:
    conn = _setup_income_conn()
    upsert_capacity_assumptions(
        conn,
        pd.DataFrame(
            [
                {
                    "scenario_id": 1,
                    "project_group": "Solar",
                    "month": "2026-01-01",
                    "new_capacity_w": 500.0,
                    "addition_timing_factor": 0.6,
                    "avg_equity_price_per_w": 0.21,
                    "manual_project_count_override": 3,
                    "manual_region_count_override": 2,
                    "notes": "initial",
                }
            ]
        ),
    )

    rows = list_capacity_assumptions(conn, scenario_id=1)
    assert len(rows) == 1
    assert rows.iloc[0]["project_group"] == "Solar"
    assert rows.iloc[0]["new_capacity_w"] == 500.0


def test_maa_assumptions_insert_and_list() -> None:
    conn = _setup_income_conn()
    upsert_maa_assumptions(
        conn,
        [
            {
                "scenario_id": 2,
                "project_group": "Wind",
                "month": "2026-02-01",
                "incentive_1_flag": 1,
                "incentive_2_flag": 0,
                "reimbursed_cost_ex_vat": 88.5,
                "notes": "pilot",
            }
        ],
    )

    rows = list_maa_assumptions(conn, scenario_id=2)
    assert len(rows) == 1
    assert rows.iloc[0]["incentive_1_flag"] == 1
    assert rows.iloc[0]["reimbursed_cost_ex_vat"] == 88.5


def test_revenue_allocation_rules_insert_and_list() -> None:
    conn = _setup_income_conn()
    upsert_revenue_allocation_rules(
        conn,
        [
            {
                "revenue_type": "management_fee",
                "recipient_entity_code": "ACPL-CN",
                "allocation_pct": 0.75,
                "haircut_pct": 0.10,
                "active_flag": 1,
            }
        ],
    )

    rows = list_revenue_allocation_rules(conn)
    assert len(rows) == 1
    assert rows.iloc[0]["allocation_pct"] == 0.75


def test_cash_collection_rules_insert_and_list() -> None:
    conn = _setup_income_conn()
    upsert_cash_collection_rules(
        conn,
        [
            {
                "rule_id": 100,
                "revenue_type": "equity_incentive",
                "collection_method": "staggered",
                "collection_months": "M+1,M+2",
                "settlement_month": None,
                "active_flag": 1,
            }
        ],
    )

    rows = list_cash_collection_rules(conn)
    assert len(rows) == 1
    assert rows.iloc[0]["collection_method"] == "staggered"


def test_fund_assumptions_insert_and_list() -> None:
    conn = _setup_income_conn()
    upsert_fund_assumptions(
        conn,
        [
            {
                "scenario_id": 5,
                "fund_name": "Fund A",
                "month": "2026-03-01",
                "initial_fund_equity_contribution": 1000.0,
                "fixed_expense_contribution": 80.0,
                "gp_commitment_pct": 0.05,
                "lp_commitment_pct": 0.95,
                "management_fee_rate": 0.02,
                "vat_rate": 0.06,
                "cit_rate": 0.25,
                "incentive_flag": 1,
                "notes": "launch",
            }
        ],
    )

    rows = list_fund_assumptions(conn, scenario_id=5)
    assert len(rows) == 1
    assert rows.iloc[0]["fund_name"] == "Fund A"
    assert rows.iloc[0]["management_fee_rate"] == 0.02
