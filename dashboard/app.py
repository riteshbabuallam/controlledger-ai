from __future__ import annotations

import streamlit as st

from dashboard.client import API_URL, api_online, request

st.set_page_config(page_title="ControlLedger", page_icon="✓", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1320px;}
      [data-testid="stMetric"] {background:#f8fafc;border:1px solid #e2e8f0;padding:14px;border-radius:8px;}
      [data-testid="stSidebar"] {border-right:1px solid #e2e8f0;}
      h1, h2, h3 {letter-spacing:-0.02em;}
      .status-ok {color:#047857;font-weight:600;}
      .muted {color:#64748b;font-size:.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("ControlLedger")
    st.caption("Continuous expense controls")
    if api_online():
        st.markdown('<span class="status-ok">● API connected</span>', unsafe_allow_html=True)
        try:
            readiness = request("GET", "/ready")
            checks = readiness.get("checks") or {}
            st.caption(
                f"AI: {str(checks.get('ai_provider', 'Gemini')).title() if checks.get('ai_live') else 'offline fallback'} · "
                f"RAG: {str(checks.get('rag_backend', '')).replace('PolicyRetriever', '')}"
            )
        except Exception:
            pass
    else:
        st.error(f"API unavailable at {API_URL}")
    st.divider()

navigation = st.navigation(
    [
        st.Page("pages/claims_review.py", title="Claims review", icon="📋", default=True),
        st.Page("pages/evidence_view.py", title="Evidence", icon="🔎"),
        st.Page("pages/analytics.py", title="Analytics", icon="📊"),
        st.Page("pages/policy_simulator.py", title="Policy simulator", icon="⚖️"),
    ]
)
navigation.run()
