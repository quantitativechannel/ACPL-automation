from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.db import income_repositories as repo
from src.reports.income_reports import build_income_statement_revenue_report
from src.ui.components import render_dataframe_card, render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.scenario_controls import render_scenario_selector
from src.ui.table_editor import render_editable_table
from src.ui.theme import apply_theme

st.set_page_config(page_title="Income Forecast", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn
create_schema(conn)

render_hero(
    "Income Forecast",
    "Input capacity, MAA revenue, fund revenue, allocation, and cash collection assumptions.",
)

scenario_id, scenario_name = render_scenario_selector(conn, key="income_scenario")
st.caption(f"Editing assumptions for {scenario_name}. Scenario IDs are controlled by the scenario manager.")
tab_capacity, tab_maa, tab_fund, tab_rules, tab_preview = st.tabs(
    ["Capacity", "MAA Revenue", "Fund Revenue", "Policies & Rules", "Preview"]
)

with tab_capacity:
    render_editable_table(
        conn,
        title="Capacity Assumptions",
        table="capacity_assumptions",
        df=repo.list_capacity_assumptions(conn, scenario_id),
        key="income_capacity",
        subtitle="Monthly capacity additions, timing factor, equity price, and manual count overrides.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_maa:
    render_editable_table(
        conn,
        title="MAA Assumptions",
        table="maa_assumptions",
        df=repo.list_maa_assumptions(conn, scenario_id),
        key="income_maa",
        subtitle="Monthly MAA incentive flags and reimbursed costs for each project group.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_fund:
    render_editable_table(
        conn,
        title="Fund Assumptions",
        table="fund_assumptions",
        df=repo.list_fund_assumptions(conn, scenario_id),
        key="income_fund",
        subtitle="JV fund contributions, fee rates, tax rates, and incentive flags.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_rules:
    left, right = st.columns(2)
    with left:
        render_editable_table(
            conn,
            title="Revenue Policies",
            table="income_revenue_policies",
            df=repo.list_income_revenue_policies(conn),
            key="income_policies",
            subtitle="Rates and tax assumptions by revenue type.",
        )
        render_editable_table(
            conn,
            title="Cash Collection Rules",
            table="cash_collection_rules",
            df=repo.list_cash_collection_rules(conn),
            key="income_cash_rules",
            subtitle="Cash timing rules by revenue type.",
        )
    with right:
        render_editable_table(
            conn,
            title="Revenue Allocation Rules",
            table="revenue_allocation_rules",
            df=repo.list_revenue_allocation_rules(conn),
            key="income_allocations",
            subtitle="Recipient entity percentages and haircut assumptions.",
        )

with tab_preview:
    selected_month = st.text_input("Preview month (YYYY-MM)", value="2026-01")
    if st.button("Run income-only preview"):
        postings = pd.read_sql_query("SELECT * FROM monthly_postings WHERE scenario_id = ?", conn, params=(scenario_id,))
        preview = build_income_statement_revenue_report(postings, selected_month=selected_month)
        render_dataframe_card("Income preview report", preview)
