from __future__ import annotations

import tempfile

import streamlit as st

from src.migration.workbook_audit import export_migration_audit_report, render_audit_markdown
from src.ui.components import render_hero, render_section_header
from src.ui.navigation import render_app_sidebar
from src.ui.theme import apply_theme

st.set_page_config(page_title="Workbook Audit", layout="wide")
apply_theme()
render_app_sidebar()

render_hero(
    "Workbook Audit",
    "Audit legacy workbook dependencies, external links, and broken references before migration.",
)

upload = st.file_uploader("Upload legacy workbook", type=["xlsx", "xlsm"])
if upload is not None and st.button("Run workbook audit", type="primary"):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(upload.getbuffer())
        path = tmp.name
    result = export_migration_audit_report(path)
    tab_summary, tab_links, tab_broken, tab_notes = st.tabs(["Sheets", "External Links", "Broken References", "Markdown"])
    with tab_summary:
        render_section_header("Sheet summary")
        st.dataframe(result["sheet_summary"], use_container_width=True, hide_index=True)
    with tab_links:
        render_section_header("External links")
        st.dataframe(result["external_links"], use_container_width=True, hide_index=True)
    with tab_broken:
        render_section_header("Broken references")
        st.dataframe(result["broken_refs"], use_container_width=True, hide_index=True)
    with tab_notes:
        render_section_header("Audit markdown")
        st.markdown(render_audit_markdown(result))
