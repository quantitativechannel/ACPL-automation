from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.budget_engine import (
    TRAVEL_EXPENSE_ITEMS,
    TRIP_CATEGORIES,
    BudgetWorkbook,
    allocate_expenses_to_companies,
    build_travel_assumptions_from_people,
    default_template,
    export_dashboard_workbook,
    generate_forecast_table,
    sync_trip_type_config,
)

st.set_page_config(page_title="ACPL Budget Automation", layout="wide")
st.title("ACPL Budgeting Portal")
st.caption("Configure subsidiary inputs, run projections, and export consolidated legacy reports.")

if "subsidiary_base_inputs" not in st.session_state:
    st.session_state.subsidiary_base_inputs = {}
if "people_data" not in st.session_state:
    st.session_state.people_data = pd.DataFrame(columns=["name", "location", "company", "base_salary", "type"])
if "master_budget_config" not in st.session_state:
    st.session_state.master_budget_config = pd.DataFrame(
        columns=["code", "expense_item", "cashflow_item", "expense_type"]
    )
if "trip_type_config" not in st.session_state:
    st.session_state.trip_type_config = pd.DataFrame(columns=["type", "category", "est_trips", "cost_per_trip"])
if "trip_cost_allocation_config" not in st.session_state:
    st.session_state.trip_cost_allocation_config = pd.DataFrame(
        [{"category": cat, "expense_item": item, "allocation_pct": 0.0} for cat in TRIP_CATEGORIES for item in TRAVEL_EXPENSE_ITEMS]
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


st.session_state.trip_type_config = sync_trip_type_config(
    st.session_state.people_data,
    st.session_state.trip_type_config,
)


with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload existing Expenses workbook", type=["xlsx"])
    opening_cash = st.number_input("Opening cash balance", value=0.0, step=1000.0)

    st.markdown("### Master budget expense list")
    config_upload = st.file_uploader(
        "Upload one config file",
        type=["xlsx", "csv"],
        help="Required columns: code, expense_item, cashflow_item, expense_type",
        key="config_upload",
    )
    if config_upload is not None:
        config_df = pd.read_excel(config_upload) if config_upload.name.endswith("xlsx") else pd.read_csv(config_upload)
        config_df.columns = [str(c).strip().lower() for c in config_df.columns]
        required = {"code", "expense_item", "cashflow_item", "expense_type"}
        if required.issubset(config_df.columns):
            st.session_state.master_budget_config = config_df[
                ["code", "expense_item", "cashflow_item", "expense_type"]
            ].copy()
            st.success("Master config accepted.")
        else:
            st.error("Config must include: code, expense_item, cashflow_item, expense_type")

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
            key=f"base_editor_{selected_sub}",
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

        travel_assumptions = build_travel_assumptions_from_people(
            people_df=st.session_state.people_data,
            trip_config_df=st.session_state.trip_type_config,
            allocation_df=st.session_state.trip_cost_allocation_config,
            master_config_df=st.session_state.master_budget_config,
            scenario="Base",
            year=pd.Timestamp.today().year,
        )
        sub_travel = travel_assumptions[travel_assumptions["company"] == selected_sub].copy() if not travel_assumptions.empty else pd.DataFrame()
        if not sub_travel.empty:
            st.markdown("### Annualized trip cost assumptions from People configuration")
            st.dataframe(
                sub_travel[["code", "expense_item", "cashflow_item", "annual_cost", "allocation_method", "allocation_month"]],
                use_container_width=True,
            )
            if st.button(f"Apply annualized trip assumptions to {selected_sub}", key=f"apply_travel_{selected_sub}"):
                merge_cols = ["code", "expense_item", "cashflow_item", "scenario", "year"]
                clean_grid = edited_base_grid.copy()
                merged = clean_grid.merge(sub_travel[merge_cols], on=merge_cols, how="left", indicator=True)
                clean_grid = merged[merged["_merge"] == "left_only"][edited_base_grid.columns].copy()
                to_append = sub_travel[
                    ["code", "expense_item", "cashflow_item", "scenario", "year", "annual_cost", "allocation_method", "allocation_month"]
                ].copy()
                updated = pd.concat([clean_grid, to_append], ignore_index=True)
                st.session_state.subsidiary_base_inputs[selected_sub] = updated
                st.success(f"Annualized trip assumptions updated for {selected_sub}.")
                st.rerun()

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

        st.markdown("### Forecast")
        current_year = pd.Timestamp.today().year
        end_year = st.selectbox(
            "Forecast end year",
            options=list(range(current_year, current_year + 11)),
            index=2,
            key=f"forecast_end_year_{selected_sub}",
        )
        annual_growth = st.number_input(
            "Annual growth estimate (%)",
            value=0.0,
            step=0.5,
            key=f"forecast_growth_{selected_sub}",
        )
        try:
            forecast_wide = generate_forecast_table(
                assumptions_df=edited_base_grid,
                company=selected_sub,
                end_year=end_year,
                annual_growth_pct=annual_growth,
                start_year=current_year,
            )
            st.session_state.subsidiary_base_inputs[f"{selected_sub}__forecast"] = forecast_wide
        except ValueError as exc:
            st.error(str(exc))
            forecast_wide = pd.DataFrame()

        if not forecast_wide.empty:
            st.dataframe(forecast_wide, use_container_width=True)
            _download_excel_button(
                forecast_wide,
                f"Download {selected_sub} forecast as Excel",
                f"{selected_sub.lower()}_forecast.xlsx",
                f"dl_forecast_{selected_sub}",
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

with tab_people:
    st.subheader("People Upload and Travel Cost Configuration")
    people_upload = st.file_uploader(
        "Upload people file",
        type=["xlsx", "csv"],
        help="Columns expected: name, location, company, base_salary, type",
        key="people_upload",
    )
    if people_upload is not None:
        people_df = pd.read_excel(people_upload) if people_upload.name.endswith("xlsx") else pd.read_csv(people_upload)
        people_df.columns = [str(c).strip().lower() for c in people_df.columns]
        if "person" in people_df.columns and "name" not in people_df.columns:
            people_df["name"] = people_df["person"]
        required = {"name", "location", "company", "base_salary", "type"}
        if required.issubset(people_df.columns):
            people_df = people_df[["name", "location", "company", "base_salary", "type"]].copy()
            people_df["base_salary"] = pd.to_numeric(people_df["base_salary"], errors="coerce").fillna(0.0)
            st.session_state.people_data = people_df
            st.success("People data uploaded.")
        else:
            st.error("People upload must include: name, location, company, base_salary, type")

    edited_people = st.data_editor(
        st.session_state.people_data, hide_index=True, num_rows="dynamic", use_container_width=True
    )
    st.session_state.people_data = edited_people
    st.session_state.trip_type_config = sync_trip_type_config(
        st.session_state.people_data,
        st.session_state.trip_type_config,
    )
    st.caption("People table stores name, location, company, base salary, and travel type assumptions.")
    _download_excel_button(edited_people, "Download people table as Excel", "people_assumptions.xlsx", "dl_people")

    st.markdown("### Configuration 1: Estimated trips and cost per trip by type")
    st.caption("Types are auto-loaded from the People table and each type always includes all four trip categories.")
    edited_trip_config = st.data_editor(
        st.session_state.trip_type_config,
        hide_index=True,
        num_rows="fixed",
        use_container_width=True,
        disabled=["type", "category"],
        column_config={
            "type": st.column_config.TextColumn("type", required=True),
            "category": st.column_config.TextColumn("category", required=True),
            "est_trips": st.column_config.NumberColumn("est_trips", min_value=0.0, step=1.0),
            "cost_per_trip": st.column_config.NumberColumn("cost_per_trip", min_value=0.0, step=100.0),
        },
    )
    st.session_state.trip_type_config = sync_trip_type_config(
        st.session_state.people_data,
        edited_trip_config,
    )

    st.markdown("### Configuration 2: Cost allocation % by trip category and expense item")
    expense_item_options = TRAVEL_EXPENSE_ITEMS
    if not st.session_state.master_budget_config.empty:
        expense_item_options = sorted(st.session_state.master_budget_config["expense_item"].dropna().astype(str).str.strip().unique())
    edited_alloc_config = st.data_editor(
        st.session_state.trip_cost_allocation_config,
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "category": st.column_config.SelectboxColumn("category", options=TRIP_CATEGORIES, required=True),
            "expense_item": st.column_config.SelectboxColumn("expense_item", options=expense_item_options, required=True),
            "allocation_pct": st.column_config.NumberColumn("allocation_pct", min_value=0.0, max_value=100.0, step=1.0),
        },
    )
    st.session_state.trip_cost_allocation_config = edited_alloc_config

    alloc_check = (
        edited_alloc_config.groupby("category", as_index=False).agg(total_allocation_pct=("allocation_pct", "sum"))
        if not edited_alloc_config.empty
        else pd.DataFrame(columns=["category", "total_allocation_pct"])
    )
    if not alloc_check.empty:
        st.caption("Allocation % by category should total 100.")
        st.dataframe(alloc_check, use_container_width=True)
        invalid_categories = alloc_check[alloc_check["total_allocation_pct"].round(2) != 100.0]["category"].tolist()
        if invalid_categories:
            st.warning(f"These categories do not sum to 100%: {', '.join(invalid_categories)}")

    derived_assumptions = build_travel_assumptions_from_people(
        people_df=st.session_state.people_data,
        trip_config_df=st.session_state.trip_type_config,
        allocation_df=st.session_state.trip_cost_allocation_config,
        master_config_df=st.session_state.master_budget_config,
        scenario="Base",
        year=pd.Timestamp.today().year,
    )
    st.markdown("### Derived annual cost assumptions for budgeting")
    if derived_assumptions.empty:
        st.info("Populate people + configuration tables to generate annualized travel cost assumptions.")
    else:
        st.dataframe(derived_assumptions, use_container_width=True)
        _download_excel_button(
            derived_assumptions,
            "Download annualized travel assumptions as Excel",
            "annualized_travel_assumptions.xlsx",
            "dl_annualized_travel",
        )

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
