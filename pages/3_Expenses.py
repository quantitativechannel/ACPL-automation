from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.ui.components import render_hero
from src.ui.navigation import render_app_sidebar
from src.ui.scenario_controls import render_scenario_selector
from src.ui.table_editor import render_editable_table
from src.ui.theme import apply_theme

st.set_page_config(page_title="Expense Forecast", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn

render_hero(
    "Expense Forecast",
    "Maintain recurring and one-off expense assumptions by scenario, entity, account, vendor, and timing basis.",
)

scenario_id, scenario_name = render_scenario_selector(conn, key="expense_scenario")
st.caption(f"Editing assumptions for {scenario_name}. Scenario IDs are controlled by the scenario manager.")
tab_prof, tab_other, tab_medical, tab_manual = st.tabs(
    ["Professional Fees", "Other Expenses", "Medical Benefits", "Manual Overrides"]
)

with tab_prof:
    df = pd.read_sql_query("SELECT * FROM prof_fee_assumptions WHERE scenario_id = ? LIMIT 1000", conn, params=(scenario_id,))
    render_editable_table(
        conn,
        title="Professional Fee Assumptions",
        table="prof_fee_assumptions",
        df=df,
        key="expenses_prof_fee",
        subtitle="Vendors, fee names, currency, basis type, amount, and active dates.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_other:
    df = pd.read_sql_query("SELECT * FROM other_exp_assumptions WHERE scenario_id = ? LIMIT 1000", conn, params=(scenario_id,))
    render_editable_table(
        conn,
        title="Other Expense Assumptions",
        table="other_exp_assumptions",
        df=df,
        key="expenses_other_exp",
        subtitle="Add or maintain operating expenses that are not professional fee or people driven.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_medical:
    df = pd.read_sql_query("SELECT * FROM medical_assumptions WHERE scenario_id = ? LIMIT 1000", conn, params=(scenario_id,))
    render_editable_table(
        conn,
        title="Medical Benefit Assumptions",
        table="medical_assumptions",
        df=df,
        key="expenses_medical",
        subtitle="Medical benefit cost by entity, type, and scenario.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )

with tab_manual:
    df = pd.read_sql_query("SELECT * FROM manual_cashflow_items WHERE scenario_id = ? LIMIT 1000", conn, params=(scenario_id,))
    render_editable_table(
        conn,
        title="Manual Cashflow Overrides",
        table="manual_cashflow_items",
        df=df,
        key="expenses_manual",
        subtitle="One-off cashflow adjustments that should flow into treasury and forecast outputs.",
        default_values={"scenario_id": scenario_id},
        hidden_columns=["scenario_id"],
    )
