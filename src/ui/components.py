from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st


def render_hero(title: str, subtitle: str, eyebrow: str | None = None) -> None:
    eyebrow_html = f"<div class='acpl-eyebrow'>{eyebrow}</div>" if eyebrow else ""
    st.markdown(
        f"<section class='acpl-hero'>{eyebrow_html}<h1>{title}</h1><p class='acpl-subtitle'>{subtitle}</p></section>",
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str | None = None, eyebrow: str | None = None) -> None:
    if eyebrow:
        st.markdown(f"<div class='acpl-eyebrow'>{eyebrow}</div>", unsafe_allow_html=True)
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)


def render_metric_card(label: str, value: str, help_text: str | None = None) -> None:
    help_html = f"<div class='acpl-card-caption'>{help_text}</div>" if help_text else ""
    st.markdown(
        f"<div class='acpl-card'><div class='acpl-metric-label'>{label}</div><div class='acpl-metric-value'>{value}</div>{help_html}</div>",
        unsafe_allow_html=True,
    )


def render_status_pill(label: str, status: str) -> None:
    css = {"complete": "ok", "in progress": "warn"}.get(status.lower(), "off")
    st.markdown(f"**{label}:** <span class='acpl-pill {css}'>{status}</span>", unsafe_allow_html=True)


def render_dataframe_card(title: str, df: pd.DataFrame, subtitle: str | None = None) -> None:
    st.markdown(f"<div class='acpl-card-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_download_button_for_df(df: pd.DataFrame, label: str, file_name: str) -> None:
    if df.empty:
        st.info("No rows available for download.")
        return
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    st.download_button(label, buffer.getvalue(), file_name=file_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
