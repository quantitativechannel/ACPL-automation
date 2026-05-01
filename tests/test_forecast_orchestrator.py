import pandas as pd

from src.services.forecast_orchestrator import run_forecast_orchestration


def _income_inputs():
    return {
        "capacity_assumptions": pd.DataFrame([
            {"scenario_id": 1, "project_group": "A", "month": "2026-01", "new_capacity_w": 100, "addition_timing_factor": 0.5, "avg_equity_price_per_w": 2}
        ]),
        "maa_assumptions": pd.DataFrame([
            {"scenario_id": 1, "project_group": "A", "month": "2026-01", "reimbursed_cost_ex_vat": 0, "incentive_1_flag": 0, "incentive_2_flag": 0}
        ]),
        "revenue_policies": pd.DataFrame([{"revenue_type": "MAA_BASE", "rate": 0.1, "vat_rate": 0, "cit_rate": 0}]),
        "revenue_allocation_rules": pd.DataFrame([{"revenue_type": "MAA_BASE", "recipient_entity_code": "E1", "allocation_pct": 1.0, "haircut_pct": 0.0}]),
        "cash_collection_rules": pd.DataFrame([{"revenue_type": "MAA_BASE", "collection_method": "annual_settlement"}])
    }


def _expense_inputs():
    return {
        "prof_fee_assumptions": pd.DataFrame([{"scenario_id": 1, "entity_id": "E1", "vendor": "V", "account_code": "6001", "fee_name": "F", "details": "D", "basis_type": "monthly", "currency": "RMB", "assumption_value": 100, "start_date": "2026-01-01", "end_date": "2026-01-31"}]),
        "other_exp_assumptions": pd.DataFrame([{"scenario_id": 1, "entity_id": "E1", "vendor": "V", "expense_name": "x", "account_code": "6002", "details": "D", "basis_type": "monthly", "currency": "RMB", "assumption_value": 200, "start_date": "2026-01-01", "end_date": "2026-01-31"}]),
        "employees": pd.DataFrame([{"scenario_id": 1, "employee_id": "P1", "employee_name": "A", "entity_id": "E1", "location": "CN", "level": "L1", "role_type": "consultant", "base_salary": 1000, "social_insurance_flag": 0, "housing_fund_flag": 0, "employer_tax_flag": 0, "medical_flag": 0, "start_date": "2026-01-01", "end_date": "2026-01-31", "active_flag": 1}]),
        "burden_rules": pd.DataFrame([{"location": "CN", "social_insurance_rate": 0.1, "housing_fund_rate": 0.1, "employer_tax_rate": 0.1, "salary_account_code": "7001", "social_insurance_account_code": "7002", "housing_fund_account_code": "7003", "employer_tax_account_code": "7004"}]),
        "travel_policy": pd.DataFrame([{"role_type": "consultant", "trip_category": "dom", "est_trips": 12, "cost_per_trip": 100}]),
        "travel_allocation": pd.DataFrame([{"trip_category": "dom", "account_code": "7100", "allocation_pct": 1.0}]),
        "manual_overrides": pd.DataFrame([{"scenario_id": 1, "entity_id": "E1", "month": "2026-01", "account_code": "9999", "description": "manual", "amount": 55}]),
    }


def test_income_only_runs():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", _income_inputs())
    assert not out["postings"].empty
    assert (out["postings"]["source_module"] == "maa_revenue").any()


def test_expense_only_runs():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", _expense_inputs())
    assert {"prof_fee", "other_exp", "personnel", "travel"}.issubset(set(out["postings"]["source_module"].dropna().unique()))


def test_combined_income_expense_runs():
    i = _income_inputs(); i.update(_expense_inputs())
    out = run_forecast_orchestration(1, "2026-01", "2026-01", i)
    assert len(out["postings"]) > 3


def test_missing_optional_inputs_warn_not_fail():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", {})
    assert isinstance(out["validation_warnings"], list)
    assert out["postings"].empty


def test_driver_summaries_expected_rows():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", _expense_inputs())
    assert {"source_module", "posting_type", "row_count", "total_amount"}.issubset(out["driver_summaries"].columns)


def test_required_standard_columns_present():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", _expense_inputs())
    for col in ["scenario_id", "month", "account_code", "posting_type", "source_module", "reference_id", "description", "amount", "revenue_type", "counterparty"]:
        assert col in out["postings"].columns


def test_travel_uses_personnel_headcount():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", _expense_inputs())
    travel = out["postings"][out["postings"]["source_module"] == "travel"]
    assert not travel.empty
    assert travel["amount"].sum() == 100.0


def test_manual_overrides_included():
    out = run_forecast_orchestration(1, "2026-01", "2026-01", _expense_inputs())
    assert (out["postings"]["account_code"] == "9999").any()
