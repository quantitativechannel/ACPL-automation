import pandas as pd

from src.drivers.personnel_driver import (
    HEADCOUNT_OUTPUT_COLUMNS,
    PERSONNEL_OUTPUT_COLUMNS,
    build_monthly_headcount,
    build_personnel_postings,
)


def _employees(**overrides):
    row = {
        "scenario_id": "Base",
        "employee_id": "E1",
        "employee_name": "Alice",
        "entity_id": "Ent1",
        "location": "CN-SH",
        "level": "L1",
        "role_type": "Ops",
        "base_salary": 10000,
        "social_insurance_flag": 1,
        "housing_fund_flag": 1,
        "employer_tax_flag": 1,
        "medical_flag": 0,
        "start_date": "2026-01-15",
        "end_date": "2026-03-10",
        "active_flag": 1,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def _burden():
    return pd.DataFrame([
        {
            "location": "CN-SH",
            "social_insurance_rate": 0.1,
            "housing_fund_rate": 0.05,
            "employer_tax_rate": 0.02,
            "salary_account_code": "6001",
            "social_insurance_account_code": "6002",
            "housing_fund_account_code": "6003",
            "employer_tax_account_code": "6004",
        }
    ])


def test_active_month_window_start_and_end() -> None:
    df = build_personnel_postings(_employees(), _burden(), "2026-01", "2026-03")
    months = sorted(df[df["cost_component"] == "salary"]["month"].unique().tolist())
    assert months == ["2026-01", "2026-02", "2026-03"]


def test_missing_start_date_defaults_to_start_month() -> None:
    df = build_personnel_postings(_employees(start_date=None), _burden(), "2026-01", "2026-02")
    assert sorted(df[df["cost_component"] == "salary"]["month"].unique().tolist()) == ["2026-01", "2026-02"]


def test_missing_end_date_defaults_to_end_month() -> None:
    df = build_personnel_postings(_employees(end_date=None), _burden(), "2026-01", "2026-02")
    assert sorted(df[df["cost_component"] == "salary"]["month"].unique().tolist()) == ["2026-01", "2026-02"]


def test_inactive_employee_has_no_postings() -> None:
    df = build_personnel_postings(_employees(active_flag=0), _burden(), "2026-01", "2026-02")
    assert df.empty


def test_salary_posts_every_active_month() -> None:
    df = build_personnel_postings(_employees(), _burden(), "2026-01", "2026-03")
    salary = df[df["cost_component"] == "salary"]
    assert salary["amount"].tolist() == [10000.0, 10000.0, 10000.0]


def test_social_housing_tax_flags_work() -> None:
    df = build_personnel_postings(_employees(), _burden(), "2026-01", "2026-01")
    by_component = df.set_index("cost_component")["amount"].to_dict()
    assert by_component["social_insurance"] == 1000.0
    assert by_component["housing_fund"] == 500.0
    assert by_component["employer_tax"] == 200.0


def test_bonus_posts_in_designated_month() -> None:
    emps = _employees(bonus_formula_type="STD")
    bonus_rules = pd.DataFrame([
        {"bonus_formula_type": "STD", "level": "L9", "role_type": "X", "bonus_month": "2026-02", "bonus_rate": 0.5, "bonus_account_code": "6010"}
    ])
    df = build_personnel_postings(emps, _burden(), "2026-01", "2026-03", bonus_rules_df=bonus_rules)
    bonus = df[df["cost_component"] == "bonus"]
    assert bonus["month"].tolist() == ["2026-02"]
    assert bonus["amount"].tolist() == [5000.0]


def test_medical_posts_when_enabled() -> None:
    med_rules = pd.DataFrame([{"location": "CN-SH", "monthly_medical_cost": 300, "medical_account_code": "6020"}])
    df = build_personnel_postings(_employees(medical_flag=1), _burden(), "2026-01", "2026-02", medical_rules_df=med_rules)
    med = df[df["cost_component"] == "medical"]
    assert med["amount"].tolist() == [300.0, 300.0]


def test_monthly_headcount_by_role_type() -> None:
    employees = pd.concat([
        _employees(employee_id="E1", role_type="Ops"),
        _employees(employee_id="E2", role_type="Ops"),
        _employees(employee_id="E3", role_type="Sales", start_date="2026-02-01"),
    ], ignore_index=True)
    hc = build_monthly_headcount(employees, "2026-01", "2026-02")
    jan_ops = hc[(hc["month"] == "2026-01") & (hc["role_type"] == "Ops")]["active_headcount"].iloc[0]
    feb_sales = hc[(hc["month"] == "2026-02") & (hc["role_type"] == "Sales")]["active_headcount"].iloc[0]
    assert jan_ops == 2
    assert feb_sales == 1


def test_empty_input_returns_expected_columns() -> None:
    empty_emps = pd.DataFrame(columns=[
        "scenario_id", "employee_id", "employee_name", "entity_id", "location", "level", "role_type", "base_salary",
        "social_insurance_flag", "housing_fund_flag", "employer_tax_flag", "medical_flag", "start_date", "end_date", "active_flag",
    ])
    postings = build_personnel_postings(empty_emps, _burden(), "2026-01", "2026-01")
    headcount = build_monthly_headcount(empty_emps, "2026-01", "2026-01")
    assert list(postings.columns) == PERSONNEL_OUTPUT_COLUMNS
    assert list(headcount.columns) == HEADCOUNT_OUTPUT_COLUMNS
