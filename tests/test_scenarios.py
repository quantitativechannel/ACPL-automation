from __future__ import annotations

import pandas as pd

from src.data_model import connect_db, create_schema
from src.scenarios import clone_scenario, create_scenario, deactivate_scenario, list_active_scenarios


def _setup_db():
    conn = connect_db()
    create_schema(conn)
    return conn


def test_create_scenario_returns_new_id() -> None:
    conn = _setup_db()
    scenario_id = create_scenario(conn, "Base", "Base case")
    assert scenario_id > 0


def test_list_active_scenarios_includes_created_scenario() -> None:
    conn = _setup_db()
    scenario_id = create_scenario(conn, "Plan A")
    active = list_active_scenarios(conn)

    assert scenario_id in set(active["scenario_id"].tolist())
    assert "Plan A" in set(active["scenario_name"].tolist())


def test_deactivate_scenario_hides_scenario_from_active_list() -> None:
    conn = _setup_db()
    scenario_id = create_scenario(conn, "To Deactivate")
    deactivate_scenario(conn, scenario_id)

    active = list_active_scenarios(conn)
    assert scenario_id not in set(active["scenario_id"].tolist())


def _seed_source_rows(conn, source_scenario_id: int) -> None:
    conn.execute(
        "INSERT INTO capacity_assumptions (scenario_id, project_group, month, new_capacity_w, addition_timing_factor, avg_equity_price_per_w) VALUES (?, 'A', '2026-01', 100, 1, 2)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO maa_assumptions (scenario_id, project_group, month, incentive_1_flag, incentive_2_flag, reimbursed_cost_ex_vat) VALUES (?, 'A', '2026-01', 1, 0, 10)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO fund_assumptions (scenario_id, fund_name, month, initial_fund_equity_contribution, fixed_expense_contribution, management_fee_rate, vat_rate, cit_rate) VALUES (?, 'Fund X', '2026-01', 1000, 100, 0.02, 0.06, 0.25)",
        (source_scenario_id,),
    )
    conn.execute("INSERT INTO entities (entity_code, entity_name, base_currency) VALUES ('E1', 'Entity 1', 'USD')")
    conn.execute("INSERT INTO account_map (account_code, account_name) VALUES ('6001', 'Fees')")
    conn.execute(
        "INSERT INTO prof_fee_assumptions (entity_id, vendor, account_code, fee_name, assumption_value, scenario_id) VALUES (1, 'V1', '6001', 'Fee', 12, ?)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO other_exp_assumptions (entity_id, vendor, account_code, expense_name, assumption_value, scenario_id) VALUES (1, 'V2', '6001', 'Exp', 5, ?)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO medical_assumptions (entity_id, medical_type, annual_cost, scenario_id) VALUES (1, 'basic', 1200, ?)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO manual_cashflow_items (entity_id, cashflow_line_name, month, amount, scenario_id) VALUES (1, 'manual', '2026-01', 42, ?)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO monthly_postings (scenario_id, entity_id, month, account_code, source_module, amount) VALUES (?, 1, '2026-01', '6001', 'test', 999)",
        (source_scenario_id,),
    )
    conn.execute(
        "INSERT INTO forecast_runs (scenario_id, run_timestamp, start_month, end_month) VALUES (?, '2026-01-01T00:00:00', '2026-01', '2026-12')",
        (source_scenario_id,),
    )
    conn.commit()




def test_clone_scenario_creates_new_scenario() -> None:
    conn = _setup_db()
    source_id = create_scenario(conn, "Base")
    new_id = clone_scenario(conn, source_id, "Cloned")

    row = conn.execute("SELECT scenario_name FROM scenarios WHERE scenario_id = ?", (new_id,)).fetchone()
    assert row is not None
    assert row[0] == "Cloned"


def test_clone_scenario_copies_assumption_rows() -> None:
    conn = _setup_db()
    source_id = create_scenario(conn, "Base")
    _seed_source_rows(conn, source_id)

    new_id = clone_scenario(conn, source_id, "Clone", "cloned")

    scenario = conn.execute("SELECT scenario_name FROM scenarios WHERE scenario_id = ?", (new_id,)).fetchone()
    assert scenario is not None
    assert scenario[0] == "Clone"

    for table in [
        "capacity_assumptions",
        "maa_assumptions",
        "fund_assumptions",
        "prof_fee_assumptions",
        "other_exp_assumptions",
        "medical_assumptions",
        "manual_cashflow_items",
    ]:
        copied = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE scenario_id = ?", (new_id,)).fetchone()[0]
        assert copied == 1


def test_clone_scenario_does_not_copy_output_rows() -> None:
    conn = _setup_db()
    source_id = create_scenario(conn, "Base")
    _seed_source_rows(conn, source_id)

    new_id = clone_scenario(conn, source_id, "No outputs")

    postings = conn.execute("SELECT COUNT(*) FROM monthly_postings WHERE scenario_id = ?", (new_id,)).fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM forecast_runs WHERE scenario_id = ?", (new_id,)).fetchone()[0]
    assert postings == 0
    assert runs == 0


def test_missing_optional_assumption_table_is_skipped_gracefully() -> None:
    conn = _setup_db()
    source_id = create_scenario(conn, "Base")

    conn.execute(
        "INSERT INTO capacity_assumptions (scenario_id, project_group, month, new_capacity_w, addition_timing_factor, avg_equity_price_per_w) VALUES (?, 'A', '2026-01', 100, 1, 1)",
        (source_id,),
    )
    conn.commit()

    conn.execute("DROP TABLE IF EXISTS manual_override_inputs")
    conn.commit()

    new_id = clone_scenario(conn, source_id, "Clone clean")
    copied = conn.execute("SELECT COUNT(*) FROM capacity_assumptions WHERE scenario_id = ?", (new_id,)).fetchone()[0]
    assert copied == 1

    active = list_active_scenarios(conn)
    assert new_id in set(active["scenario_id"])
    assert isinstance(active, pd.DataFrame)
