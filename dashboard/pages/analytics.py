from __future__ import annotations

import streamlit as st

from dashboard.client import request

st.title("Control analytics")
st.caption("Portfolio-level operational and governance indicators.")

try:
    controls = request("GET", "/analytics/controls")
    exceptions = request("GET", "/analytics/exceptions")
except Exception as exc:
    st.error(str(exc))
    st.stop()

a, b, c, d = st.columns(4)
a.metric("Claims processed", controls["claims_processed"])
b.metric("Exception rate", f"{exceptions['exception_rate']:.0%}")
c.metric("Avg. latency", f"{controls['average_latency_ms']:.0f} ms")
d.metric("AI cost / claim", f"${controls['average_ai_cost_usd']:.4f}")

left, right = st.columns(2)
with left:
    st.subheader("Recommendation mix")
    if exceptions["recommendations"]:
        st.bar_chart(exceptions["recommendations"])
    else:
        st.info("No data")
with right:
    st.subheader("Exceptions by department")
    if exceptions["exceptions_by_department"]:
        st.bar_chart(exceptions["exceptions_by_department"])
    else:
        st.info("No data")

st.subheader("Control outcomes")
st.dataframe(controls["controls"], hide_index=True, width="stretch")
