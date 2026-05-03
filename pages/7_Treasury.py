from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.drivers.treasury_driver import build_treasury_rollforward
from src.ui.components import render_dataframe_card, render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.scenario_controls import render_scenario_selector
from src.ui.table_editor import render_editable_table
from src.ui.theme import apply_theme

st.set_page_config(page_title="Treasury & Cash", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn

render_hero(
    "Treasury & Cash",
    "Maintain manual cashflow items and generate a cash rollforward view.",
)

scenario_id, scenario_name = render_scenario_selector(conn, key="treasury_scenario")
st.caption(f"Editing treasury inputs for {scenario_name}. Scenario IDs are controlled by the scenario manager.")
tab_manual, tab_rollforward = st.tabs(["Manual Cashflow", "Rollforward"])

with tab_manual:
    manual = pd.read_sql_query("SELECT * FROM manual_cashflow_items WHERE scenario_id = ? LIMIT 1000", conn, params=(scenario_id,))
    render_editable_table(
        conn,
        title="Manual Cashflow Inputs",
        table="manual_cashflow_items",
        df=manual,
        key="treasury_manual_cashflow",
        subtitle="Add one-off cash items by entity, month, and scenario.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_rollforward:
    start_month = st.text_input("Start month (YYYY-MM)", value="2026-01")
    end_month = st.text_input("End month (YYYY-MM)", value="2026-12")
    if st.button("Generate treasury rollforward"):
        manual = pd.read_sql_query(
            "SELECT * FROM manual_cashflow_items WHERE scenario_id = ? LIMIT 1000",
            conn,
            params=(scenario_id,),
        )
        opening = pd.DataFrame(columns=["entity_id", "month", "opening_cash"])
        operating = pd.DataFrame(columns=["entity_id", "month", "operating_inflow", "operating_outflow"])
        transfers = pd.DataFrame(columns=["from_entity_id", "to_entity_id", "month", "amount"])
        injections = pd.DataFrame(columns=["entity_id", "month", "amount"])
        rf = build_treasury_rollforward(opening, operating, start_month, end_month, manual, transfers, injections)
        render_dataframe_card("Treasury rollforward", rf)
