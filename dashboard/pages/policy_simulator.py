from __future__ import annotations

import streamlit as st

from dashboard.client import request

st.title("Policy impact simulator")
st.caption(
    "Compare two deterministic policy configurations across the 30-claim synthetic portfolio."
)

with st.form("simulation"):
    a, b = st.columns(2)
    with a:
        st.subheader("Scenario A · Current")
        a_meal = st.number_input("Meal allowance", value=1500.0, key="a_meal")
        a_hotel = st.number_input("Hotel allowance", value=9000.0, key="a_hotel")
        a_receipt = st.number_input("Amount-match tolerance", value=1.0, key="a_receipt")
        a_fx = st.number_input("FX variance tolerance (%)", value=3.0, key="a_fx")
    with b:
        st.subheader("Scenario B · Proposed")
        b_meal = st.number_input("Meal allowance", value=2500.0, key="b_meal")
        b_hotel = st.number_input("Hotel allowance", value=12000.0, key="b_hotel")
        b_receipt = st.number_input("Amount-match tolerance", value=1.0, key="b_receipt")
        b_fx = st.number_input("FX variance tolerance (%)", value=10.0, key="b_fx")
    run = st.form_submit_button("Run two-scenario comparison", type="primary", width="stretch")

if run:
    payload = {
        "scenario_a": {
            "meals_allowance": a_meal,
            "hotel_allowance": a_hotel,
            "amount_tolerance": a_receipt,
            "currency_variance_tolerance": a_fx,
        },
        "scenario_b": {
            "meals_allowance": b_meal,
            "hotel_allowance": b_hotel,
            "amount_tolerance": b_receipt,
            "currency_variance_tolerance": b_fx,
        },
    }
    try:
        result = request("POST", "/simulations", json=payload)
        st.session_state["simulation_result"] = result
    except Exception as exc:
        st.error(str(exc))

result = st.session_state.get("simulation_result")
if result:
    a, b, c, d = st.columns(4)
    a.metric("Portfolio", result["portfolio_size"])
    b.metric("Current exception rate", f"{result['scenario_a']['exception_rate']:.0%}")
    c.metric("Proposed exception rate", f"{result['scenario_b']['exception_rate']:.0%}")
    d.metric("Review workload change", result["additional_reviews"])
    st.subheader("Controls with changed outcomes")
    if result["controls_with_largest_impact"]:
        st.dataframe(result["controls_with_largest_impact"], hide_index=True, width="stretch")
    else:
        st.info("The proposed values do not change any control outcomes in this portfolio.")
    st.caption(f"Affected claims: {', '.join(result['affected_claim_ids']) or 'None'}")
