from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.reports.budget_reports import build_group_budget_report
from src.reports.cashflow_reports import build_group_cashflow_report
from src.reports.income_reports import build_income_statement_revenue_report
from src.ui.components import render_dataframe_card, render_download_button_for_df, render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.theme import apply_theme

st.set_page_config(page_title="Reports", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn
create_schema(conn)

render_hero(
    "Reports",
    "Review income, budget, cashflow, and flash-style outputs from saved forecast postings.",
)

control1, control2 = st.columns([0.25, 0.25])
with control1:
    scenario_id = st.number_input("Scenario ID", min_value=1, value=1)
with control2:
    selected_month = st.text_input("Selected month (YYYY-MM)", value="2026-01")

postings = pd.read_sql_query("SELECT * FROM monthly_postings WHERE scenario_id = ?", conn, params=(scenario_id,))
account_map = pd.read_sql_query("SELECT * FROM account_map", conn)
report_lines = pd.read_sql_query("SELECT * FROM report_lines WHERE report_name='budget'", conn)

income = build_income_statement_revenue_report(postings, selected_month)
budget = build_group_budget_report(postings, account_map, report_lines, scenario_id, selected_month)
cash = build_group_cashflow_report(postings, account_map, scenario_id, selected_month)
flash = pd.DataFrame(columns=["metric", "value"])

tab_income, tab_budget, tab_cash, tab_flash = st.tabs(["Income", "Budget", "Cashflow", "Flash"])
for tab, title, df in [
    (tab_income, "Income report", income),
    (tab_budget, "Budget report", budget),
    (tab_cash, "Cashflow report", cash),
    (tab_flash, "Flash report", flash),
]:
    with tab:
        render_dataframe_card(title, df)
        render_download_button_for_df(df, f"Download {title}", f"{title.lower().replace(' ', '_')}.xlsx")
