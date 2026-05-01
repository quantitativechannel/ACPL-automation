from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Inject the ACPL app theme for all pages."""
    st.markdown(
        """
        <style>
          :root {
            --bg: #f7f8fb;
            --surface: #ffffff;
            --surface-soft: #fbfcfe;
            --ink: #171821;
            --muted: #6d7280;
            --faint: #a3a8b3;
            --border: #e7e9ef;
            --accent: #6554dc;
            --accent-2: #16b8c4;
            --accent-3: #4f8ff7;
            --good: #10b981;
            --warn: #f59e0b;
            --bad: #ef476f;
          }
          .stApp { background: var(--bg); color: var(--ink); }
          h1, h2, h3, h4 { letter-spacing: 0; color: var(--ink); }
          h1 { font-size: 1.75rem !important; font-weight: 720 !important; }
          h2, h3 { font-weight: 680 !important; }
          .block-container { padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1280px; }

          [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--border); }
          [data-testid="stSidebarNav"] { display: none; }
          [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
          .acpl-brand { display:flex; align-items:center; gap:0.75rem; padding:0.25rem 0 1.1rem 0; }
          .acpl-brand-mark {
            width: 2rem; height: 2rem; border-radius: 0.5rem;
            display:flex; align-items:center; justify-content:center;
            color:#fff; font-weight:760; background: linear-gradient(135deg, var(--accent), var(--accent-2));
          }
          .acpl-brand-name { font-weight:760; font-size:1rem; line-height:1.1; }
          .acpl-brand-subtitle { color:var(--muted); font-size:0.75rem; line-height:1.15; }
          .acpl-nav-group {
            color: var(--faint); text-transform: uppercase; font-size: 0.68rem;
            letter-spacing: 0.08em; font-weight: 760; margin: 1.05rem 0 0.4rem 0;
          }
          [data-testid="stSidebar"] a {
            border-radius: 0.45rem; min-height: 2.15rem; color: var(--ink);
          }
          [data-testid="stSidebar"] a:hover { background: #f2f4f8; color: var(--ink); }

          .acpl-hero { padding: 0.3rem 0 1.15rem 0; margin-bottom: 0.85rem; }
          .acpl-hero h1 { margin-bottom: 0.25rem; }
          .acpl-eyebrow { text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.08em; color: var(--faint); font-weight: 760; }
          .acpl-subtitle { color: var(--muted); max-width: 62rem; font-size:0.95rem; }
          .acpl-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem;
            padding: 1rem; margin: 0.55rem 0; box-shadow: 0 1px 2px rgba(17, 24, 39, 0.025);
          }
          .acpl-card-title { display:flex; align-items:center; justify-content:space-between; gap:1rem; font-weight:680; }
          .acpl-card-caption { color:var(--muted); font-size:0.82rem; margin-top:0.15rem; }
          .acpl-metric-label { font-size: 0.78rem; color: var(--muted); display:flex; align-items:center; gap:0.35rem; }
          .acpl-metric-value { font-size: 1.65rem; font-weight: 720; margin-top:0.35rem; }
          .acpl-kicker { display:inline-flex; align-items:center; border-radius:0.35rem; padding:0.12rem 0.4rem; font-size:0.7rem; font-weight:720; background:#e9fbf5; color:#078761; }
          .acpl-pill { display: inline-block; border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.72rem; font-weight: 720; border:1px solid var(--border); }
          .acpl-pill.ok { color:#078761; background:#e9fbf5; border-color:#b9efdc; }
          .acpl-pill.warn { color:#9a6508; background:#fff7e6; border-color:#f9dfa9; }
          .acpl-pill.off { color:#c72c55; background:#fff0f4; border-color:#ffd0dc; }
          .acpl-panel {
            border:1px solid var(--border); border-radius:0.5rem; background:var(--surface);
            padding:0.9rem 1rem; margin:0.5rem 0 1rem 0;
          }
          div[data-testid="stMetric"] {
            background:var(--surface); border:1px solid var(--border); border-radius:0.5rem; padding:1rem;
          }
          div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border-radius:0.5rem; border:1px solid var(--border); overflow:hidden;
          }
          div[data-testid="stTabs"] button { font-weight: 650; }
          .stButton button, .stDownloadButton button {
            border-radius: 0.45rem; border: 1px solid var(--border); font-weight: 650;
          }
          .stButton button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
          .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius:0.45rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
