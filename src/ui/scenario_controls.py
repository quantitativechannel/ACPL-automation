from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from src.scenarios import clone_scenario, create_scenario, list_active_scenarios
from src.ui.components import render_dataframe_card, render_section_header


def _scenario_label(row: pd.Series) -> str:
    return str(row["scenario_name"])


def ensure_base_scenario(conn: sqlite3.Connection) -> None:
    scenarios = list_active_scenarios(conn)
    if scenarios.empty:
        create_scenario(conn, "Base", "Initial controlled base scenario")


def render_scenario_selector(conn: sqlite3.Connection, *, key: str, label: str = "Scenario") -> tuple[int, str]:
    ensure_base_scenario(conn)
    scenarios = list_active_scenarios(conn)
    labels = [_scenario_label(row) for _, row in scenarios.iterrows()]
    default_idx = labels.index("Base") if "Base" in labels else 0
    selected = st.selectbox(label, labels, index=default_idx, key=key)
    row = scenarios.iloc[labels.index(selected)]
    st.caption(f"System scenario ID: {int(row['scenario_id'])}")
    return int(row["scenario_id"]), str(row["scenario_name"])


def render_scenario_admin(conn: sqlite3.Connection) -> None:
    ensure_base_scenario(conn)
    scenarios = list_active_scenarios(conn)

    render_section_header(
        "Scenario Control",
        "Create every new scenario by copying an existing scenario, then edit assumptions inside that scenario.",
    )

    source_labels = [_scenario_label(row) for _, row in scenarios.iterrows()]
    col1, col2 = st.columns([0.45, 0.55])
    with col1:
        source_label = st.selectbox("Copy from scenario", source_labels, key="scenario_clone_source")
        new_name = st.text_input("New scenario name", placeholder="e.g. FY2026 Upside")
    with col2:
        description = st.text_area("Scenario notes", placeholder="What changed versus the source scenario?")

    if st.button("Create Scenario From Copy", type="primary"):
        source_row = scenarios.iloc[source_labels.index(source_label)]
        if not new_name.strip():
            st.error("Enter a scenario name before creating it.")
        else:
            try:
                new_id = clone_scenario(
                    conn,
                    source_scenario_id=int(source_row["scenario_id"]),
                    new_scenario_name=new_name.strip(),
                    description=description or None,
                )
                st.success(f"Created scenario #{new_id}: {new_name.strip()}")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create scenario: {exc}")

    render_dataframe_card(
        "Active scenarios",
        scenarios,
        "Scenario IDs are system identifiers. Choose scenarios by name in the input pages.",
    )
