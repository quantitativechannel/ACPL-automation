from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.services.input_loader import load_forecast_inputs_from_db
from src.services.run_forecast import run_forecast_and_persist
from src.ui.components import render_dataframe_card, render_hero, render_metric_card
from src.ui.navigation import render_app_sidebar
from src.ui.theme import apply_theme

st.set_page_config(page_title="Run Forecast", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn

render_hero(
    "Run Forecast",
    "Generate postings from saved assumptions and persist an auditable forecast run.",
)

left, right = st.columns([0.9, 1.25])
with left:
    st.markdown("### Run Settings")
    scenario_id = st.number_input("Scenario ID", min_value=1, value=1)
    start_month = st.text_input("Start month (YYYY-MM)", value="2026-01")
    end_month = st.text_input("End month (YYYY-MM)", value="2026-12")
    notes = st.text_area("Run notes", placeholder="Optional context for this run")

    inputs = load_forecast_inputs_from_db(conn, scenario_id=scenario_id)
    render_metric_card("Input Tables Loaded", str(len(inputs)), ", ".join(sorted(inputs)) or "No saved inputs found")

    if st.button("Run Forecast", type="primary"):
        result = run_forecast_and_persist(
            conn,
            scenario_id=scenario_id,
            start_month=start_month,
            end_month=end_month,
            inputs=inputs,
            notes=notes or None,
        )
        st.success(f"Forecast run completed: {result['run_id']}")
        render_dataframe_card("Driver summaries", result["driver_summaries"])
        render_dataframe_card("Warnings", pd.DataFrame({"warning": result["validation_warnings"]}))

with right:
    st.markdown("### Run History")
    runs = pd.read_sql_query("SELECT * FROM forecast_runs ORDER BY run_id DESC LIMIT 100", conn)
    render_dataframe_card("Forecast runs", runs)
