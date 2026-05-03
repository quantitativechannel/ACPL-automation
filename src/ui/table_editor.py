from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from src.services.setup_import import generated_primary_key_columns, import_table_frame, table_columns
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
    locked_columns: list[str] | None = None,
    hidden_columns: list[str] | None = None,
) -> pd.DataFrame:
    render_section_header(title, subtitle)

    columns = table_columns(conn, table)
    generated_keys = generated_primary_key_columns(conn, table)
    display = df.copy()
    if display.empty:
        display = _empty_row(columns)
        for col, value in (default_values or {}).items():
            if col in display.columns:
                display[col] = value

    hidden = set(hidden_columns or [])
    editor_hidden = hidden | set(generated_keys)
    default_hidden = hidden - set(generated_keys)
    editor_display = display.drop(columns=[col for col in default_hidden if col in display.columns], errors="ignore")
    column_config = {col: None for col in editor_hidden if col in editor_display.columns}

    edited = st.data_editor(
        editor_display,
        key=key,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=locked_columns or False,
        column_config=column_config or None,
    )

    if st.button(f"Save {title}", key=f"save_{key}"):
        try:
            for col in generated_keys:
                if col not in edited.columns and col in display.columns:
                    edited[col] = display[col].reindex(edited.index)
            for col, value in (default_values or {}).items():
                if col not in edited.columns:
                    edited[col] = value
                else:
                    edited[col] = edited[col].fillna(value)
            count = import_table_frame(conn, table, edited)
            st.success(f"Saved {count} row(s) to {table}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Save failed: {exc}")

    return edited
