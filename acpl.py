from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.budget_engine import BudgetWorkbook, default_template, export_dashboard_workbook, generate_annual_projection

st.set_page_config(page_title="ACPL Budget Automation", layout="wide")
st.title("ACPL Budgeting Portal")
st.caption("Configure subsidiary inputs, run projections, and export consolidated legacy reports.")

if "subsidiary_base_inputs" not in st.session_state:
    st.session_state.subsidiary_base_inputs = {}
if "subsidiary_projections" not in st.session_state:
    st.session_state.subsidiary_projections = {}

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


tab_subs, tab_master, tab_legacy = st.tabs(["Subsidiaries", "Master Consolidation", "Legacy Workbook"])

with tab_subs:
    st.subheader("Subsidiary Budget Input + Annual Projection")
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
                    "item": ["Rent", "Utilities", "Travel"],
                    "monthly_budget": [0.0, 0.0, 0.0],
                    "monthly_expense": [0.0, 0.0, 0.0],
                }
            )

        sub_upload = st.file_uploader(
            f"Upload {selected_sub} expense input",
            type=["xlsx", "csv"],
            help="Columns expected: item, monthly_budget, monthly_expense",
            key=f"upload_{selected_sub}",
        )
        if sub_upload is not None:
            uploaded_sub = pd.read_excel(sub_upload) if sub_upload.name.endswith("xlsx") else pd.read_csv(sub_upload)
            uploaded_sub.columns = [str(c).strip().lower() for c in uploaded_sub.columns]
            required = {"item", "monthly_budget", "monthly_expense"}
            if required.issubset(uploaded_sub.columns):
                uploaded_sub = uploaded_sub[["item", "monthly_budget", "monthly_expense"]].copy()
                base_grid = (
                    pd.concat([base_grid, uploaded_sub], ignore_index=True)
                    .drop_duplicates(subset=["item"], keep="last")
                    .reset_index(drop=True)
                )
                st.success(f"Imported expense inputs for {selected_sub}.")
            else:
                st.error("Subsidiary upload must include: item, monthly_budget, monthly_expense")

        edited_base_grid = st.data_editor(base_grid, hide_index=True, num_rows="dynamic", use_container_width=True)
        st.session_state.subsidiary_base_inputs[selected_sub] = edited_base_grid

        c1, c2, c3 = st.columns(3)
        with c1:
            base_year = st.number_input("Budget base year", min_value=2000, max_value=2100, value=2026, step=1)
        with c2:
            end_year = st.number_input("Projection end year", min_value=2000, max_value=2100, value=2029, step=1)
        with c3:
            growth_pct = st.number_input("Annual growth %", value=5.0, step=0.5)

        if st.button(f"Generate projection for {selected_sub}"):
            projection = generate_annual_projection(
                base_inputs=edited_base_grid,
                company=selected_sub,
                base_year=int(base_year),
                end_year=int(end_year),
                growth_rate_pct=float(growth_pct),
                scenario="Budget",
            )
            st.session_state.subsidiary_projections[selected_sub] = projection
            st.success(f"Projection generated for {selected_sub}.")

        sub_projection = st.session_state.subsidiary_projections.get(selected_sub)
        if sub_projection is not None and not sub_projection.empty:
            st.dataframe(sub_projection, use_container_width=True)

with tab_master:
    st.subheader("Master Consolidation")
    projection_frames = [df for df in st.session_state.subsidiary_projections.values() if not df.empty]
    if not projection_frames:
        st.info("Generate at least one subsidiary projection to see consolidation.")
    else:
        master_df = pd.concat(projection_frames, ignore_index=True)
        consolidated = (
            master_df.groupby(["month", "item"], as_index=False)
            .agg(total_budget=("budget", "sum"), total_expense=("expense", "sum"))
            .sort_values(["month", "item"])
        )
        consolidated["variance"] = consolidated["total_budget"] - consolidated["total_expense"]
        st.dataframe(consolidated, use_container_width=True)

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
