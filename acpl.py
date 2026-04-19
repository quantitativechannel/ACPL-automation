from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.budget_engine import (
    BudgetWorkbook,
    allocate_expenses_to_companies,
    default_template,
    export_dashboard_workbook,
)

st.set_page_config(page_title="ACPL Budget Automation", layout="wide")
st.title("ACPL Budgeting Portal")
st.caption("Configure subsidiary inputs, run projections, and export consolidated legacy reports.")

if "subsidiary_base_inputs" not in st.session_state:
    st.session_state.subsidiary_base_inputs = {}
if "people_data" not in st.session_state:
    st.session_state.people_data = pd.DataFrame(columns=["person", "location", "base_salary"])

with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload existing Expenses workbook", type=["xlsx"])
    opening_cash = st.number_input("Opening cash balance", value=0.0, step=1000.0)

    template_bytes = default_template()
    st.download_button(
        label="Download template workbook",
        data=template_bytes,
        file_name="acpl_budget_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


tab_subs, tab_master, tab_people, tab_legacy = st.tabs(
    ["Subsidiaries", "Master Consolidation", "People", "Legacy Workbook"]
)

with tab_subs:
    st.subheader("Subsidiary Expense Assumptions (Annual)")
    default_subs = ["ACPL", "ACPLHK", "ACPSZL", "ACPLSZ", "ACPLGZ", "Yixing"]
    subsidiaries_input = st.text_area("Subsidiary list (comma-separated)", value=", ".join(default_subs))
    subsidiaries = [s.strip() for s in subsidiaries_input.split(",") if s.strip()]

    if not subsidiaries:
        st.warning("Add at least one subsidiary to continue.")
    else:
        selected_sub = st.selectbox("Select subsidiary", options=subsidiaries)
        base_grid = st.session_state.subsidiary_base_inputs.get(selected_sub)
        if base_grid is None:
            base_grid = pd.DataFrame(
                {
                    "code": ["OPS-RENT", "OPS-UTIL", "OPS-TRAVEL"],
                    "expense_item": ["Rent", "Utilities", "Travel"],
                    "cashflow_item": ["Operating Expense", "Operating Expense", "Operating Expense"],
                    "scenario": ["Base", "Base", "Base"],
                    "year": [2026, 2026, 2026],
                    "annual_cost": [0.0, 0.0, 0.0],
                    "allocation_method": ["monthly_average", "monthly_average", "quarterly"],
                    "allocation_month": [1, 1, 1],
                }
            )

        sub_upload = st.file_uploader(
            f"Upload {selected_sub} expense input",
            type=["xlsx", "csv"],
            help=(
                "Columns expected: code, expense_item, cashflow_item. "
                "Optional: scenario, year, annual_cost, allocation_method, allocation_month"
            ),
            key=f"upload_{selected_sub}",
        )
        if sub_upload is not None:
            uploaded_sub = pd.read_excel(sub_upload) if sub_upload.name.endswith("xlsx") else pd.read_csv(sub_upload)
            uploaded_sub.columns = [str(c).strip().lower() for c in uploaded_sub.columns]
            required = {"code", "expense_item", "cashflow_item"}
            if required.issubset(uploaded_sub.columns):
                base_grid = (
                    pd.concat([base_grid, uploaded_sub], ignore_index=True)
                    .drop_duplicates(subset=["code", "expense_item"], keep="last")
                    .reset_index(drop=True)
                )
                st.success(f"Imported expense inputs for {selected_sub}.")
            else:
                st.error("Subsidiary upload must include: code, expense_item, cashflow_item")

        edited_base_grid = st.data_editor(base_grid, hide_index=True, num_rows="dynamic", use_container_width=True)
        st.session_state.subsidiary_base_inputs[selected_sub] = edited_base_grid

        if st.button(f"Allocate annual costs for {selected_sub}"):
            allocated = allocate_expenses_to_companies(edited_base_grid, [selected_sub])
            st.session_state.subsidiary_base_inputs[f"{selected_sub}__allocated"] = allocated
            st.success(f"Allocated annual costs to months for {selected_sub}.")

        sub_allocation = st.session_state.subsidiary_base_inputs.get(f"{selected_sub}__allocated")
        if sub_allocation is not None and not sub_allocation.empty:
            st.dataframe(sub_allocation, use_container_width=True)

        st.markdown("#### Upload one expense file and auto-populate across all subsidiaries")
        common_upload = st.file_uploader(
            "Upload shared expense assumptions",
            type=["xlsx", "csv"],
            help=(
                "Required: code, expense_item, cashflow_item. "
                "Optional: scenario, year, annual_cost, allocation_method, allocation_month."
            ),
            key="common_expense_upload",
        )
        if common_upload is not None:
            uploaded_common = (
                pd.read_excel(common_upload) if common_upload.name.endswith("xlsx") else pd.read_csv(common_upload)
            )
            if st.button("Apply shared expense upload to all subsidiaries"):
                try:
                    shared_allocated = allocate_expenses_to_companies(uploaded_common, subsidiaries)
                    for sub in subsidiaries:
                        sub_rows = shared_allocated[shared_allocated["company"] == sub].copy()
                        st.session_state.subsidiary_base_inputs[f"{sub}__allocated"] = sub_rows
                    st.success("Shared expense assumptions applied to all subsidiaries.")
                except ValueError as exc:
                    st.error(str(exc))

with tab_master:
    st.subheader("Master Consolidation")
    projection_frames = [
        df
        for key, df in st.session_state.subsidiary_base_inputs.items()
        if key.endswith("__allocated") and isinstance(df, pd.DataFrame) and not df.empty
    ]
    if not projection_frames:
        st.info("Allocate expenses for at least one subsidiary to see consolidation.")
    else:
        master_df = pd.concat(projection_frames, ignore_index=True)
        consolidated = (
            master_df.groupby(["month", "cashflow_item"], as_index=False)
            .agg(total_expense=("expense", "sum"))
            .sort_values(["month", "cashflow_item"])
        )
        st.dataframe(consolidated, use_container_width=True)

with tab_people:
    st.subheader("People Upload")
    people_upload = st.file_uploader(
        "Upload people file",
        type=["xlsx", "csv"],
        help="Columns expected: person, location, base_salary",
        key="people_upload",
    )
    if people_upload is not None:
        people_df = pd.read_excel(people_upload) if people_upload.name.endswith("xlsx") else pd.read_csv(people_upload)
        people_df.columns = [str(c).strip().lower() for c in people_df.columns]
        required = {"person", "location", "base_salary"}
        if required.issubset(people_df.columns):
            people_df = people_df[["person", "location", "base_salary"]].copy()
            people_df["base_salary"] = pd.to_numeric(people_df["base_salary"], errors="coerce").fillna(0.0)
            st.session_state.people_data = people_df
            st.success("People data uploaded.")
        else:
            st.error("People upload must include: person, location, base_salary")

    edited_people = st.data_editor(
        st.session_state.people_data, hide_index=True, num_rows="dynamic", use_container_width=True
    )
    st.session_state.people_data = edited_people
    st.caption("People table stores person, location, and base salary assumptions.")

with tab_legacy:
    st.subheader("Legacy workbook flow")
    if not uploaded_file:
        st.info("Upload an Excel workbook in sidebar to use this flow.")
    else:
        workbook = BudgetWorkbook.from_excel(uploaded_file)
        scenario_options = sorted(workbook.expenses["scenario"].dropna().unique().tolist())
        selected_scenarios = st.multiselect(
            "Scenarios to include",
            options=scenario_options,
            default=scenario_options[:2] if len(scenario_options) >= 2 else scenario_options,
        )

        if selected_scenarios:
            company_summary = workbook.company_summary(scenarios=selected_scenarios)
            consolidated = workbook.consolidated_summary(scenarios=selected_scenarios)
            cash_flow = workbook.cash_flow(scenarios=selected_scenarios, opening_cash=opening_cash)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Company Summary")
                st.dataframe(company_summary, use_container_width=True)
            with col2:
                st.subheader("Consolidated Summary")
                st.dataframe(consolidated, use_container_width=True)

            st.subheader("Cash Flow Projection")
            st.dataframe(cash_flow, use_container_width=True)

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
        else:
            st.warning("Select at least one scenario.")
