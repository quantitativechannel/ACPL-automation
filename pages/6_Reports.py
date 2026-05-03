from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.reports.budget_reports import build_group_budget_report
from src.reports.cashflow_reports import build_group_cashflow_report
from src.reports.income_reports import build_income_statement_revenue_report
from src.services.input_loader import load_forecast_inputs_from_db
from src.services.run_forecast import run_forecast_and_persist
from src.ui.components import render_dataframe_card, render_download_button_for_df, render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.scenario_controls import render_scenario_selector
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

control1, control2 = st.columns([0.35, 0.25])
with control1:
    scenario_id, scenario_name = render_scenario_selector(conn, key="report_scenario")
with control2:
    selected_month = st.text_input("Selected month (YYYY-MM)", value="2026-01")

run_options = pd.read_sql_query(
    """
    SELECT run_id, run_timestamp, start_month, end_month
    FROM forecast_runs
    WHERE scenario_id = ?
    ORDER BY run_id DESC
    """,
    conn,
    params=(scenario_id,),
)

selected_run_id = None
if not run_options.empty:
    run_labels = [
        f"Run {int(row.run_id)} - {row.run_timestamp} ({row.start_month} to {row.end_month})"
        for row in run_options.itertuples(index=False)
    ]
    selected_run = st.selectbox("Forecast run", run_labels, key="report_run")
    selected_run_id = int(run_options.iloc[run_labels.index(selected_run)]["run_id"])

postings_sql = "SELECT * FROM monthly_postings WHERE scenario_id = ?"
params: tuple[object, ...] = (scenario_id,)
if selected_run_id is not None:
    postings_sql += " AND run_id = ?"
    params = (scenario_id, selected_run_id)
postings = pd.read_sql_query(postings_sql, conn, params=params)
account_map = pd.read_sql_query("SELECT * FROM account_map", conn)
report_lines = pd.read_sql_query("SELECT * FROM report_lines WHERE report_name='budget'", conn)

if postings.empty:
    st.warning(
        f"No forecast postings found for {scenario_name}. Bulk import loads assumptions only; run a forecast to generate report data."
    )
    inputs = load_forecast_inputs_from_db(conn, scenario_id=scenario_id)
    st.caption(f"Saved input tables available: {', '.join(sorted(inputs)) or 'none'}")
    col_run, _ = st.columns([0.25, 0.75])
    with col_run:
        if st.button("Run Forecast Now", type="primary"):
            result = run_forecast_and_persist(
                conn,
                scenario_id=scenario_id,
                start_month="2026-01",
                end_month="2026-12",
                inputs=inputs,
                notes="Auto-run from Reports page",
            )
            st.success(f"Forecast run completed: {result['run_id']}")
            st.rerun()

income = build_income_statement_revenue_report(postings, selected_month)
budget = build_group_budget_report(postings, account_map, report_lines, scenario_id, selected_month)
cash = build_group_cashflow_report(postings, account_map, scenario_id, selected_month)
flash = pd.DataFrame(
    [
        {"metric": "Scenario", "value": scenario_name},
        {"metric": "Selected month", "value": selected_month},
        {"metric": "Posting rows", "value": len(postings)},
        {"metric": "Total amount", "value": float(postings["amount"].sum()) if "amount" in postings.columns else 0.0},
    ]
)

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
