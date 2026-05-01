import pandas as pd

from src.data_model import connect_db, create_schema, insert_account_map, insert_entity, insert_scenario
from src.services import run_forecast as svc


def _fake_output() -> dict:
    postings = pd.DataFrame(
        [
            {
                "scenario_id": 1,
                "entity_id": 101,
                "month": "2026-01",
                "account_code": "7001",
                "source_module": "personnel",
                "amount": 100.0,
                "posting_type": "expense",
                "entity_code": "E1",
                "reference_id": "ref-1",
                "description": "salary",
                "revenue_type": None,
                "counterparty": None,
            }
        ]
    )
    warnings = ["Some postings have zero or null amount"]
    summaries = pd.DataFrame(
        [{"source_module": "personnel", "posting_type": "expense", "row_count": 1, "total_amount": 100.0}]
    )
    return {"postings": postings, "validation_warnings": warnings, "driver_summaries": summaries}


def test_run_forecast_and_persist_append_only(monkeypatch):
    conn = connect_db()
    create_schema(conn)
    scenario_id = insert_scenario(conn, {"scenario_name": "Base", "description": "d", "active_flag": 1})
    insert_entity(
        conn,
        {"entity_id": 101, "entity_code": "E1", "entity_name": "Entity 1", "base_currency": "CNY", "active_flag": 1},
    )
    insert_account_map(
        conn,
        {"account_code": "7001", "account_name": "Salary", "active_flag": 1},
    )

    monkeypatch.setattr(svc, "run_forecast_orchestration", lambda *args, **kwargs: _fake_output())

    out1 = svc.run_forecast_and_persist(conn, scenario_id, "2026-01", "2026-01", inputs={}, notes="run 1")
    out2 = svc.run_forecast_and_persist(conn, scenario_id, "2026-01", "2026-01", inputs={}, notes="run 2")

    assert out1["run_id"] != out2["run_id"]

    run_rows = conn.execute("SELECT * FROM forecast_runs ORDER BY run_id").fetchall()
    assert len(run_rows) == 2
    assert run_rows[0]["notes"] == "run 1"

    postings = conn.execute("SELECT * FROM monthly_postings ORDER BY posting_id").fetchall()
    assert len(postings) == 2
    assert postings[0]["run_id"] == out1["run_id"]
    assert postings[1]["run_id"] == out2["run_id"]

    warnings = conn.execute("SELECT * FROM forecast_warnings ORDER BY warning_id").fetchall()
    assert len(warnings) == 2
    assert warnings[0]["run_id"] == out1["run_id"]
    assert warnings[0]["warning_message"] == "Some postings have zero or null amount"

    summaries = conn.execute("SELECT * FROM forecast_driver_summaries ORDER BY row_id").fetchall()
    assert len(summaries) == 2
    assert summaries[0]["run_id"] == out1["run_id"]
    assert summaries[0]["source_module"] == "personnel"

    assert set(out1.keys()) == {"run_id", "postings", "validation_warnings", "driver_summaries"}
    assert isinstance(out1["postings"], pd.DataFrame)
    assert out1["validation_warnings"] == ["Some postings have zero or null amount"]
