from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_model import connect_db, create_schema
from src.services.setup_import import (
    SETUP_IMPORT_TABLES,
    build_template_workbook,
    import_setup_workbook,
    import_table_frame,
)
from src.ui.components import render_hero, render_section_header
from src.ui.navigation import render_app_sidebar
from src.ui.scenario_controls import render_scenario_admin
from src.ui.table_editor import render_editable_table
from src.ui.theme import apply_theme

st.set_page_config(page_title="Entities & Mapping", layout="wide")
apply_theme()
render_app_sidebar()

if "acpl_conn" not in st.session_state:
    st.session_state.acpl_conn = connect_db("acpl.sqlite")
    create_schema(st.session_state.acpl_conn)
conn = st.session_state.acpl_conn

render_hero(
    "Entities & Mapping",
    "Maintain the static structure used by every forecast: entities, scenarios, chart of accounts, and report lines.",
)

tab_entities, tab_scenarios, tab_accounts, tab_reports, tab_import = st.tabs(
    ["Entities", "Scenarios", "Account Mapping", "Report Lines", "Bulk Import"]
)

with tab_entities:
    entities = pd.read_sql_query("SELECT * FROM entities LIMIT 500", conn)
    render_editable_table(
        conn,
        title="Entities",
        table="entities",
        df=entities,
        key="setup_entities",
        subtitle="Companies, country, base currency, and active status.",
    )

with tab_scenarios:
    render_scenario_admin(conn)

with tab_accounts:
    account_map = pd.read_sql_query("SELECT * FROM account_map LIMIT 1000", conn)
    render_editable_table(
        conn,
        title="Account Map",
        table="account_map",
        df=account_map,
        key="setup_account_map",
        subtitle="Map account codes to budget lines, cashflow lines, and expense types.",
    )

with tab_reports:
    report_lines = pd.read_sql_query("SELECT * FROM report_lines LIMIT 1000", conn)
    render_editable_table(
        conn,
        title="Report Lines",
        table="report_lines",
        df=report_lines,
        key="setup_report_lines",
        subtitle="Presentation line definitions and ordering for budget/cashflow reports.",
    )

with tab_import:
    render_section_header(
        "Bulk Import",
        "Use this only for initial migration or a controlled bulk refresh. Normal maintenance should happen in the editable tabs.",
    )
    st.markdown(
        """
Upload a multi-sheet `.xlsx` where sheet names match the supported table names, or upload one `.csv` and choose its destination table.
"""
    )
    st.code(", ".join(SETUP_IMPORT_TABLES), language="text")
    st.download_button(
        "Download blank setup workbook template",
        build_template_workbook(conn),
        file_name="acpl_setup_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    mock_config = Path("examples/acpl_master_config_mock.xlsx")
    if mock_config.exists():
        st.download_button(
            "Download ACPL mock master config",
            mock_config.read_bytes(),
            file_name="acpl_master_config_mock.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    upload = st.file_uploader("Upload setup workbook (.xlsx) or single table (.csv)", type=["csv", "xlsx"])
    if upload is not None:
        try:
            if upload.name.lower().endswith(".xlsx"):
                imported = import_setup_workbook(conn, upload.getvalue())
            else:
                table = st.selectbox("Destination table for CSV", SETUP_IMPORT_TABLES)
                imported = {table: import_table_frame(conn, table, pd.read_csv(upload))}

            if imported:
                st.success("Imported " + ", ".join(f"{count} row(s) into {table}" for table, count in imported.items()))
            else:
                st.warning("No matching non-empty sheets were found in the upload.")
        except Exception as exc:
            st.error(f"Import failed: {exc}")
