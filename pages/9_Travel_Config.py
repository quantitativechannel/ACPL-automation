from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.drivers.personnel_driver import build_monthly_headcount
from src.drivers.travel_driver import build_travel_postings
from src.ui.components import render_dataframe_card, render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.table_editor import render_editable_table
from src.ui.theme import apply_theme

st.set_page_config(page_title="Travel", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn

render_hero(
    "Travel",
    "Configure trip assumptions and account allocation rules used by the travel forecast driver.",
)

tab_policy, tab_allocation, tab_preview = st.tabs(["Trip Policy", "Allocation Mapping", "Travel Preview"])

with tab_policy:
    travel_policy = pd.read_sql_query("SELECT * FROM travel_policy LIMIT 1000", conn)
    render_editable_table(
        conn,
        title="Travel Policy",
        table="travel_policy",
        df=travel_policy,
        key="travel_policy",
        subtitle="Estimated trips and cost per trip by role type and trip category.",
    )

with tab_allocation:
    travel_alloc = pd.read_sql_query("SELECT * FROM travel_allocation LIMIT 1000", conn)
    render_editable_table(
        conn,
        title="Travel Allocation",
        table="travel_allocation",
        df=travel_alloc,
        key="travel_allocation",
        subtitle="Map each trip category into one or more expense account codes.",
    )

with tab_preview:
    scenario_id = st.number_input("Scenario ID", min_value=1, value=1)
    start_month = st.text_input("Start month (YYYY-MM)", value="2026-01")
    end_month = st.text_input("End month (YYYY-MM)", value="2026-12")
    if st.button("Preview travel postings"):
        employees = pd.read_sql_query("SELECT * FROM employees WHERE active_flag = 1 LIMIT 1000", conn)
        if "scenario_id" not in employees.columns:
            employees["scenario_id"] = scenario_id
        headcount = build_monthly_headcount(employees, start_month, end_month)
        travel_policy = pd.read_sql_query("SELECT * FROM travel_policy LIMIT 1000", conn)
        travel_alloc = pd.read_sql_query("SELECT * FROM travel_allocation LIMIT 1000", conn)
        travel = build_travel_postings(headcount, travel_policy, travel_alloc)
        render_dataframe_card("Travel postings", travel)
