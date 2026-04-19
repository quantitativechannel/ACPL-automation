from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.budget_engine import (
    BudgetWorkbook,
    default_template,
    export_dashboard_workbook,
    generate_annual_projection,
)

st.set_page_config(page_title="ACPL Budget Automation", layout="wide")
<<<<<<< ours
st.title("ACPL Budgeting Portal")
st.caption("Configure mappings, manage subsidiary budgets, run annual projections, and consolidate outputs.")


def _init_state() -> None:
    st.session_state.setdefault("mapping_df", pd.DataFrame(columns=["expense_item", "cashflow_item"]))
    st.session_state.setdefault("personnel_df", pd.DataFrame(columns=["person", "location", "salary"]))
    st.session_state.setdefault("subsidiary_base_inputs", {})
    st.session_state.setdefault("subsidiary_projections", {})


_init_state()
=======
st.title("ACPL Budget Forecasting Automation")
st.caption("Upload your workbook, edit annual expense assumptions, and export scenario dashboards.")
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs

with st.sidebar:
    st.header("Configuration")

    mapping_upload = st.file_uploader(
        "1) Upload expense-to-cashflow mapping",
        type=["xlsx", "csv"],
        help="Columns expected: expense_item, cashflow_item",
    )
    if mapping_upload is not None:
        mapping_df = pd.read_excel(mapping_upload) if mapping_upload.name.endswith("xlsx") else pd.read_csv(mapping_upload)
        mapping_df.columns = [str(c).strip().lower() for c in mapping_df.columns]
        if {"expense_item", "cashflow_item"}.issubset(mapping_df.columns):
            st.session_state.mapping_df = mapping_df[["expense_item", "cashflow_item"]].dropna().drop_duplicates()
            st.success("Mapping file loaded.")
        else:
            st.error("Mapping file must include: expense_item, cashflow_item")

    personnel_upload = st.file_uploader(
        "2) Upload personnel data",
        type=["xlsx", "csv"],
        help="Columns expected: person, location, salary",
    )
    if personnel_upload is not None:
        personnel_df = (
            pd.read_excel(personnel_upload) if personnel_upload.name.endswith("xlsx") else pd.read_csv(personnel_upload)
        )
        personnel_df.columns = [str(c).strip().lower() for c in personnel_df.columns]
        required = {"person", "location", "salary"}
        if required.issubset(personnel_df.columns):
            normalized = personnel_df[["person", "location", "salary"]].copy()
            normalized["salary"] = pd.to_numeric(normalized["salary"], errors="coerce").fillna(0.0)
            st.session_state.personnel_df = normalized
            st.success("Personnel file loaded.")
        else:
            st.error("Personnel file must include: person, location, salary")

    st.divider()
    st.markdown("### Optional legacy workflow")
    uploaded_file = st.file_uploader("Upload existing Expenses workbook", type=["xlsx"])
    opening_cash = st.number_input("Opening cash balance", value=0.0, step=1000.0)

    if st.button("Download template workbook"):
        template_bytes = default_template()
        st.download_button(
            label="Save template",
            data=template_bytes,
            file_name="acpl_budget_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

<<<<<<< ours
tab_subs, tab_people, tab_master, tab_legacy = st.tabs(
    ["Subsidiaries", "Personnel", "Master Consolidation", "Legacy Workbook"]
)

with tab_subs:
    st.subheader("Subsidiary Budget Input + Annual Projection")

    known_items = st.session_state.mapping_df["expense_item"].tolist() if not st.session_state.mapping_df.empty else []
    default_subs = ["ACPL", "ACPLHK", "ACPSZL", "ACPLSZ", "ACPLGZ", "Yixing"]

    subsidiaries_input = st.text_area(
        "Subsidiary list (comma-separated)",
        value=", ".join(default_subs),
        help="Each subsidiary will have its own budgeting workspace.",
    )
    subsidiaries = [s.strip() for s in subsidiaries_input.split(",") if s.strip()]
    if not subsidiaries:
        st.warning("Add at least one subsidiary to continue.")
        st.stop()

    selected_sub = st.selectbox("Select subsidiary", options=subsidiaries)

    st.markdown("#### 3) Subsidiary expense inputs")
    base_grid = st.session_state.subsidiary_base_inputs.get(selected_sub)
    if base_grid is None:
        seed_items = known_items if known_items else ["Rent", "Utilities", "Travel"]
        base_grid = pd.DataFrame(
            {
                "item": seed_items,
                "monthly_budget": [0.0] * len(seed_items),
                "monthly_expense": [0.0] * len(seed_items),
            }
        )
=======
if not uploaded_file:
    st.info("Upload an Excel workbook to begin. Expected sheet: `Expenses`.")
    st.stop()

workbook = BudgetWorkbook.from_excel(uploaded_file)

st.subheader("Expense Assumptions Upload (auto applies to all subsidiaries)")
expense_upload = st.file_uploader(
    "Upload assumptions file (xlsx/csv) with columns: code, expense_item, cashflow_item, scenario, annual_cost, allocation_method",
    type=["xlsx", "csv"],
    key="expense_upload",
)

if expense_upload is not None:
    try:
        if expense_upload.name.lower().endswith(".csv"):
            assumptions_df = pd.read_csv(expense_upload)
        else:
            assumptions_df = pd.read_excel(expense_upload)
        workbook.upload_expense_assumptions(assumptions_df)
        st.success("Expense assumptions uploaded and allocated for all subsidiaries.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not process upload: {exc}")

st.subheader("Editable Expense Grid")
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
        "annual_cost": st.column_config.NumberColumn("Annual Cost", format="$%.2f"),
        "expense": st.column_config.NumberColumn("Allocated Expense", format="$%.2f"),
        "allocation_month": st.column_config.NumberColumn("Allocation Month"),
    },
)

if st.button("Apply edits for selected company"):
    workbook.apply_company_updates(selected_company, edited_company_df)
    st.success("Expense forecast updated in memory.")
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs

    sub_upload = st.file_uploader(
        f"Upload {selected_sub} expense input",
        type=["xlsx", "csv"],
        help="Columns expected: item, monthly_budget, monthly_expense",
        key=f"upload_{selected_sub}",
    )
    if sub_upload is not None:
        uploaded_sub = pd.read_excel(sub_upload) if sub_upload.name.endswith("xlsx") else pd.read_csv(sub_upload)
        uploaded_sub.columns = [str(c).strip().lower() for c in uploaded_sub.columns]
        if {"item", "monthly_budget", "monthly_expense"}.issubset(uploaded_sub.columns):
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

    st.markdown("#### 4) Annual projection settings")
    c1, c2, c3 = st.columns(3)
    with c1:
        base_year = st.number_input("Budget base year", min_value=2000, max_value=2100, value=2026, step=1)
    with c2:
        end_year = st.number_input("Projection end year", min_value=2000, max_value=2100, value=2029, step=1)
    with c3:
        growth_pct = st.number_input(
            "Annual growth %",
            value=5.0,
            step=0.5,
            help="Applies from next year onward. Within each year, monthly values stay flat.",
        )

<<<<<<< ours
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
        st.markdown("#### Projected monthly output")
        st.dataframe(sub_projection, use_container_width=True)

with tab_people:
    st.subheader("Personnel")
    st.dataframe(st.session_state.personnel_df, use_container_width=True)

with tab_master:
    st.subheader("6) Master Consolidation")
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

        st.markdown("#### Consolidated budgeting table")
        st.dataframe(consolidated, use_container_width=True)

        st.markdown("#### Consolidated budget trend")
        trend = consolidated.groupby("month", as_index=False)["total_budget"].sum()
        st.line_chart(trend, x="month", y="total_budget", use_container_width=True)

with tab_legacy:
    st.subheader("Legacy workbook flow")
    if not uploaded_file:
        st.info("Upload an Excel workbook in sidebar to use this legacy flow.")
    else:
        workbook = BudgetWorkbook.from_excel(uploaded_file)
        scenario_options = sorted(workbook.expenses["scenario"].dropna().unique().tolist())
        selected_scenarios = st.multiselect(
            "Scenarios to include in dashboard/report",
            options=scenario_options,
            default=scenario_options[:2] if len(scenario_options) >= 2 else scenario_options,
        )
=======
if not selected_scenarios:
    st.warning("Select at least one scenario.")
    st.stop()

company_summary = workbook.company_summary(scenarios=selected_scenarios)
consolidated = workbook.consolidated_summary(scenarios=selected_scenarios)
cash_flow = workbook.cash_flow(scenarios=selected_scenarios, opening_cash=opening_cash)
scenario_reports = workbook.scenario_reports(scenarios=selected_scenarios, opening_cash=opening_cash)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Company Expense Summary")
    st.dataframe(company_summary, use_container_width=True)
with col2:
    st.subheader("Consolidated Expense Summary")
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
>>>>>>> theirs

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
            st.line_chart(cash_flow, x="month", y="closing_cash", color="scenario", use_container_width=True)

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
