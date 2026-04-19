from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.budget_engine import (
    BudgetWorkbook,
    allocate_expenses_to_companies,
    default_template,
    export_dashboard_workbook,
    generate_forecast_table,
)

st.set_page_config(page_title="ACPL Budget Automation", layout="wide")
st.title("ACPL Budgeting Portal")
st.caption("Configure subsidiary inputs, run projections, and export consolidated legacy reports.")

if "subsidiary_base_inputs" not in st.session_state:
    st.session_state.subsidiary_base_inputs = {}
if "people_data" not in st.session_state:
    st.session_state.people_data = pd.DataFrame(columns=["person", "location", "base_salary"])
if "master_budget_config" not in st.session_state:
    st.session_state.master_budget_config = pd.DataFrame(
        columns=["code", "expense_item", "cashflow_item", "expense_type", "once_accept"]
    )


def _download_excel_button(df: pd.DataFrame, label: str, file_name: str, key: str) -> None:
    if df is None or df.empty:
        return
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
    st.download_button(
        label=label,
        data=buffer.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )


with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload existing Expenses workbook", type=["xlsx"])
    opening_cash = st.number_input("Opening cash balance", value=0.0, step=1000.0)

    st.markdown("### Master budget expense list")
    config_upload = st.file_uploader(
        "Upload one config file",
        type=["xlsx", "csv"],
        help="Required columns: code, expense_item, cashflow_item, expense_type, once_accept",
        key="config_upload",
    )
    if config_upload is not None:
        config_df = pd.read_excel(config_upload) if config_upload.name.endswith("xlsx") else pd.read_csv(config_upload)
        config_df.columns = [str(c).strip().lower() for c in config_df.columns]
        required = {"code", "expense_item", "cashflow_item", "expense_type", "once_accept"}
        if required.issubset(config_df.columns):
            st.session_state.master_budget_config = config_df[
                ["code", "expense_item", "cashflow_item", "expense_type", "once_accept"]
            ].copy()
            st.success("Master config accepted.")
        else:
            st.error("Config must include: code, expense_item, cashflow_item, expense_type, once_accept")

    if not st.session_state.master_budget_config.empty:
        st.caption("Current accepted config")
        st.dataframe(st.session_state.master_budget_config, use_container_width=True)
        _download_excel_button(
            st.session_state.master_budget_config,
            "Download master config as Excel",
            "master_budget_config.xlsx",
            "download_master_config",
        )

    template_bytes = default_template()
    st.download_button(
        label="Download template workbook",
        data=template_bytes,
        file_name="acpl_budget_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


tab_subs, tab_master, tab_forecast, tab_people, tab_legacy = st.tabs(
    ["Subsidiaries", "Master Consolidation", "Forecasting", "People", "Legacy Workbook"]
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
            if not st.session_state.master_budget_config.empty:
                base_grid = st.session_state.master_budget_config[["code", "expense_item", "cashflow_item"]].copy()
                base_grid["scenario"] = "Base"
                base_grid["year"] = pd.Timestamp.today().year
                base_grid["annual_cost"] = 0.0
                base_grid["allocation_method"] = "monthly_average"
                base_grid["allocation_month"] = 1
            else:
                base_grid = pd.DataFrame(
                    {
                        "code": ["OPS-RENT", "OPS-UTIL", "OPS-TRAVEL"],
                        "expense_item": ["Rent", "Utilities", "Travel"],
                        "cashflow_item": ["Operating Expense", "Operating Expense", "Operating Expense"],
                        "scenario": ["Base", "Base", "Base"],
                        "year": [pd.Timestamp.today().year] * 3,
                        "annual_cost": [0.0, 0.0, 0.0],
                        "allocation_method": ["monthly_average", "monthly_average", "quarterly_start"],
                        "allocation_month": [1, 1, 1],
                    }
                )

        if not st.session_state.master_budget_config.empty and st.button(
            f"Reset {selected_sub} to master config", key=f"reset_{selected_sub}"
        ):
            base_grid = st.session_state.master_budget_config[["code", "expense_item", "cashflow_item"]].copy()
            base_grid["scenario"] = "Base"
            base_grid["year"] = pd.Timestamp.today().year
            base_grid["annual_cost"] = 0.0
            base_grid["allocation_method"] = "monthly_average"
            base_grid["allocation_month"] = 1

        edited_base_grid = st.data_editor(
            base_grid,
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "annual_cost": st.column_config.NumberColumn("annual_cost", min_value=0.0, step=100.0),
                "allocation_method": st.column_config.SelectboxColumn(
                    "allocation_method",
                    options=["quarterly_start", "quarterly_end", "monthly_average", "specific_month"],
                    required=True,
                ),
                "allocation_month": st.column_config.NumberColumn("allocation_month", min_value=1, max_value=12, step=1),
            },
        )
        if "allocation_method" in edited_base_grid.columns and "allocation_month" in edited_base_grid.columns:
            non_specific = edited_base_grid["allocation_method"] != "specific_month"
            edited_base_grid.loc[non_specific, "allocation_month"] = 1

        st.session_state.subsidiary_base_inputs[selected_sub] = edited_base_grid
        _download_excel_button(
            edited_base_grid,
            f"Download {selected_sub} assumptions as Excel",
            f"{selected_sub.lower()}_assumptions.xlsx",
            f"dl_ass_{selected_sub}",
        )

        if st.button(f"Allocate annual costs for {selected_sub}"):
            allocated = allocate_expenses_to_companies(edited_base_grid, [selected_sub])
            st.session_state.subsidiary_base_inputs[f"{selected_sub}__allocated"] = allocated
            st.success(f"Allocated annual costs to months for {selected_sub}.")

        sub_allocation = st.session_state.subsidiary_base_inputs.get(f"{selected_sub}__allocated")
        if sub_allocation is not None and not sub_allocation.empty:
            st.dataframe(sub_allocation, use_container_width=True)
            _download_excel_button(
                sub_allocation,
                f"Download {selected_sub} allocated table as Excel",
                f"{selected_sub.lower()}_allocated.xlsx",
                f"dl_alloc_{selected_sub}",
            )

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
        _download_excel_button(
            consolidated,
            "Download consolidation as Excel",
            "master_consolidation.xlsx",
            "dl_master_consolidation",
        )

with tab_forecast:
    st.subheader("Forecasting Table")
    subsidiaries = [
        key
        for key, val in st.session_state.subsidiary_base_inputs.items()
        if isinstance(val, pd.DataFrame) and not key.endswith("__allocated")
    ]
    if not subsidiaries:
        st.info("Create at least one subsidiary assumption table first.")
    else:
        selected_sub = st.selectbox("Subsidiary for forecast", options=sorted(subsidiaries), key="forecast_sub")
        current_year = pd.Timestamp.today().year
        end_year = st.selectbox("Forecast end year", options=list(range(current_year, current_year + 11)), index=2)
        annual_growth = st.number_input("Annual growth estimate (%)", value=0.0, step=0.5)

        if st.button("Generate forecast table"):
            try:
                base_df = st.session_state.subsidiary_base_inputs[selected_sub]
                forecast_wide = generate_forecast_table(
                    assumptions_df=base_df,
                    company=selected_sub,
                    end_year=end_year,
                    annual_growth_pct=annual_growth,
                    start_year=current_year,
                )
                st.session_state.subsidiary_base_inputs[f"{selected_sub}__forecast"] = forecast_wide
            except ValueError as exc:
                st.error(str(exc))

        forecast_df = st.session_state.subsidiary_base_inputs.get(f"{selected_sub}__forecast")
        if isinstance(forecast_df, pd.DataFrame) and not forecast_df.empty:
            st.dataframe(forecast_df, use_container_width=True)
            _download_excel_button(
                forecast_df,
                f"Download {selected_sub} forecast as Excel",
                f"{selected_sub.lower()}_forecast.xlsx",
                f"dl_forecast_{selected_sub}",
            )

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
    _download_excel_button(edited_people, "Download people table as Excel", "people_assumptions.xlsx", "dl_people")

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
                _download_excel_button(company_summary, "Download company summary as Excel", "company_summary.xlsx", "dl_company")
            with col2:
                st.subheader("Consolidated Summary")
                st.dataframe(consolidated, use_container_width=True)
                _download_excel_button(consolidated, "Download consolidated summary as Excel", "consolidated_summary.xlsx", "dl_cons")

            st.subheader("Cash Flow Projection")
            st.dataframe(cash_flow, use_container_width=True)
            _download_excel_button(cash_flow, "Download cash flow as Excel", "cash_flow_projection.xlsx", "dl_cash")

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
