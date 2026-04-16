from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.budget_engine import (
    BudgetWorkbook,
    default_template,
    export_dashboard_workbook,
)

st.set_page_config(page_title="ACPL Budget Automation", layout="wide")
st.title("ACPL Budget Forecasting Automation")
st.caption("Upload your workbook, edit forecasts by company, and export scenario dashboards.")

with st.sidebar:
    st.header("Workbook Input")
    uploaded_file = st.file_uploader("Upload budget workbook", type=["xlsx"])
    opening_cash = st.number_input("Opening cash balance", value=0.0, step=1000.0)
    st.markdown("If you don't have a workbook ready, use a template starter file.")

    if st.button("Download template workbook"):
        template_bytes = default_template()
        st.download_button(
            label="Save template",
            data=template_bytes,
            file_name="acpl_budget_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

if not uploaded_file:
    st.info("Upload an Excel workbook to begin. Expected sheet: `Expenses`.")
    st.stop()

workbook = BudgetWorkbook.from_excel(uploaded_file)

st.subheader("Editable Forecast Grid")
companies = sorted(workbook.expenses["company"].dropna().unique().tolist())
selected_company = st.selectbox("Company", companies)
company_df = workbook.expenses[workbook.expenses["company"] == selected_company].copy()

edited_company_df = st.data_editor(
    company_df,
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "month": st.column_config.DateColumn("Month"),
        "budget": st.column_config.NumberColumn("Budget", format="$%.2f"),
        "expense": st.column_config.NumberColumn("Expense", format="$%.2f"),
    },
)

if st.button("Apply edits for selected company"):
    workbook.apply_company_updates(selected_company, edited_company_df)
    st.success("Forecast updated in memory.")

scenario_options = sorted(workbook.expenses["scenario"].dropna().unique().tolist())
selected_scenarios = st.multiselect(
    "Scenarios to include in dashboard/report",
    options=scenario_options,
    default=scenario_options[:2] if len(scenario_options) >= 2 else scenario_options,
)

if not selected_scenarios:
    st.warning("Select at least one scenario.")
    st.stop()

company_summary = workbook.company_summary(scenarios=selected_scenarios)
consolidated = workbook.consolidated_summary(scenarios=selected_scenarios)
cash_flow = workbook.cash_flow(scenarios=selected_scenarios, opening_cash=opening_cash)
scenario_reports = workbook.scenario_reports(scenarios=selected_scenarios, opening_cash=opening_cash)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Company Summary")
    st.dataframe(company_summary, use_container_width=True)
with col2:
    st.subheader("Consolidated Summary")
    st.dataframe(consolidated, use_container_width=True)

st.subheader("Cash Flow Projection")
st.line_chart(
    cash_flow,
    x="month",
    y="closing_cash",
    color="scenario",
    use_container_width=True,
)
st.dataframe(cash_flow, use_container_width=True)

st.subheader("Scenario Reports")
for scenario_name, report_df in scenario_reports.items():
    st.markdown(f"#### {scenario_name}")
    st.dataframe(report_df, use_container_width=True)

export_buffer = BytesIO()
export_dashboard_workbook(
    export_buffer,
    workbook.expenses,
    opening_cash=opening_cash,
    scenarios=selected_scenarios,
)

st.download_button(
    label="Export dashboard workbook",
    data=export_buffer.getvalue(),
    file_name="acpl_budget_dashboard.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
