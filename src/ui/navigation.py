from __future__ import annotations

import streamlit as st

APP_NAV_GROUPS = [
    (
        "General",
        [
            ("Dashboard", "acpl.py", "grid"),
            ("Run Forecast", "pages/5_Run_Forecast.py", "play"),
            ("Reports", "pages/6_Reports.py", "chart"),
        ],
    ),
    (
        "Inputs",
        [
            ("Income Forecast", "pages/2_Income.py", "trend"),
            ("Expense Forecast", "pages/3_Expenses.py", "wallet"),
            ("Treasury & Cash", "pages/7_Treasury.py", "bank"),
        ],
    ),
    (
        "Configuration",
        [
            ("Entities & Mapping", "pages/1_Setup.py", "settings"),
            ("People", "pages/4_Personnel_Travel.py", "users"),
            ("Travel", "pages/9_Travel_Config.py", "plane"),
        ],
    ),
    (
        "Migration",
        [
            ("Workbook Audit", "pages/8_Legacy_Workbook_Audit.py", "file"),
        ],
    ),
]

def render_app_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="acpl-brand">
              <div class="acpl-brand-mark">A</div>
              <div>
                <div class="acpl-brand-name">ACPL</div>
                <div class="acpl-brand-subtitle">Forecasting OS</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for group, pages in APP_NAV_GROUPS:
            st.markdown(f"<div class='acpl-nav-group'>{group}</div>", unsafe_allow_html=True)
            for label, path, icon in pages:
                st.page_link(path, label=label, icon=_icon(icon))
def _icon(name: str) -> str:
    return {
        "grid": ":material/dashboard:",
        "play": ":material/play_arrow:",
        "chart": ":material/bar_chart:",
        "trend": ":material/trending_up:",
        "wallet": ":material/account_balance_wallet:",
        "bank": ":material/account_balance:",
        "settings": ":material/tune:",
        "users": ":material/group:",
        "plane": ":material/flight:",
        "file": ":material/file_present:",
    }.get(name, ":material/circle:")
