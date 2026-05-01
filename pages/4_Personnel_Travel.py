from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.drivers.personnel_driver import build_monthly_headcount, build_personnel_postings
from src.ui.components import render_dataframe_card, render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.table_editor import render_editable_table
from src.ui.theme import apply_theme

st.set_page_config(page_title="People", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn

render_hero(
    "People",
    "Maintain employee master data and salary assumptions. Travel configuration has its own page under Configuration.",
)

scenario_id = st.number_input("Scenario ID for preview", min_value=1, value=1)
tab_employees, tab_preview = st.tabs(["Employee Records", "Personnel Preview"])

with tab_employees:
    employees = pd.read_sql_query("SELECT * FROM employees LIMIT 1000", conn)
    render_editable_table(
        conn,
        title="Employees",
        table="employees",
        df=employees,
        key="people_employees",
        subtitle="Change salary, role, entity, dates, and benefit flags here; save before running the forecast.",
        default_values={"scenario_id": scenario_id},
    )

with tab_preview:
    start_month = st.text_input("Start month (YYYY-MM)", value="2026-01")
    end_month = st.text_input("End month (YYYY-MM)", value="2026-12")
    if st.button("Preview personnel postings"):
        employees = pd.read_sql_query("SELECT * FROM employees WHERE active_flag = 1 LIMIT 1000", conn)
        if "scenario_id" not in employees.columns:
            employees["scenario_id"] = scenario_id
        burden_rules = pd.DataFrame(
            columns=[
                "location",
                "salary_account_code",
                "social_insurance_rate",
                "social_insurance_account_code",
                "housing_fund_rate",
                "housing_fund_account_code",
                "employer_tax_rate",
                "employer_tax_flag",
                "employer_tax_account_code",
            ]
        )
        personnel = build_personnel_postings(employees, burden_rules, start_month, end_month)
        headcount = build_monthly_headcount(employees, start_month, end_month)
        render_dataframe_card("Personnel postings", personnel)
        render_dataframe_card("Monthly headcount", headcount)
