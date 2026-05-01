from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from src.services.setup_import import import_table_frame, table_columns
from src.ui.components import render_section_header


def _empty_row(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{col: None for col in columns}])


def render_editable_table(
    conn: sqlite3.Connection,
    *,
    title: str,
    table: str,
    df: pd.DataFrame,
    key: str,
    subtitle: str | None = None,
    default_values: dict[str, object] | None = None,
) -> pd.DataFrame:
    render_section_header(title, subtitle)

    columns = table_columns(conn, table)
    display = df.copy()
    if display.empty:
        display = _empty_row(columns)
        for col, value in (default_values or {}).items():
            if col in display.columns:
                display[col] = value

    edited = st.data_editor(
        display,
        key=key,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
    )

    if st.button(f"Save {title}", key=f"save_{key}"):
        try:
            for col, value in (default_values or {}).items():
                if col in edited.columns:
                    edited[col] = edited[col].fillna(value)
            count = import_table_frame(conn, table, edited)
            st.success(f"Saved {count} row(s) to {table}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Save failed: {exc}")

    return edited
