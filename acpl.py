from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.ui.components import render_dataframe_card, render_hero, render_metric_card
from src.ui.navigation import render_app_sidebar
from src.ui.theme import apply_theme

st.set_page_config(page_title="ACPL Forecasting OS", layout="wide")
apply_theme()
render_app_sidebar()

DB_PATH = Path("acpl.sqlite")
if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db(str(DB_PATH))
create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn


def _count(table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


render_hero(
    "Dashboard",
    "Maintain assumptions, run forecast scenarios, and review budget, cashflow, and income outputs in one place.",
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("Entities", f"{_count('entities'):,}", "Companies and planning entities")
with col2:
    render_metric_card("Scenarios", f"{_count('scenarios'):,}", "Budget, forecast, and flash cases")
with col3:
    render_metric_card("Employees", f"{_count('employees'):,}", "People records for salary planning")
with col4:
    render_metric_card("Forecast Runs", f"{_count('forecast_runs'):,}", "Append-only run history")

left, right = st.columns([1.35, 1])
with left:
    st.markdown("### Planning Console")
    st.markdown(
        """
        <div class="acpl-panel">
          <div class="acpl-card-title">Start with configuration, then maintain inputs</div>
          <div class="acpl-card-caption">Static mapping lives under Configuration. Forecast numbers live under Inputs. Use Run Forecast after saving edits.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.page_link("pages/1_Setup.py", label="Entities & Mapping", icon=":material/tune:")
        st.caption("Entity list, scenarios, accounts, report lines")
    with c2:
        st.page_link("pages/2_Income.py", label="Income Forecast", icon=":material/trending_up:")
        st.caption("Capacity, MAA, fund, allocation rules")
    with c3:
        st.page_link("pages/3_Expenses.py", label="Expense Forecast", icon=":material/account_balance_wallet:")
        st.caption("Professional fee, other expense, medical, overrides")

with right:
    st.markdown("### Latest Runs")
    runs = pd.read_sql_query(
        """
        SELECT run_id, scenario_id, run_timestamp, start_month, end_month
        FROM forecast_runs
        ORDER BY run_id DESC
        LIMIT 6
        """,
        conn,
    )
    render_dataframe_card("Run history", runs, "Most recent forecast executions")

st.markdown("### Configuration Shortcuts")
cfg1, cfg2, cfg3 = st.columns(3)
with cfg1:
    st.page_link("pages/4_Personnel_Travel.py", label="People", icon=":material/group:")
with cfg2:
    st.page_link("pages/9_Travel_Config.py", label="Travel", icon=":material/flight:")
with cfg3:
    st.page_link("pages/7_Treasury.py", label="Treasury & Cash", icon=":material/account_balance:")
