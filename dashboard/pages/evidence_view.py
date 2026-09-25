from __future__ import annotations

import json

import streamlit as st

from dashboard.client import request

st.title("Evidence view")
st.caption("One claim, its governing evidence, and the reviewer decision boundary.")

try:
    claims = request("GET", "/claims")
except Exception as exc:
    st.error(str(exc))
    st.stop()

if not claims:
    st.info("No claims are available.")
    st.stop()

identifiers = [item["claim_id"] for item in claims]
default_id = st.session_state.get("selected_claim_id")
default_index = identifiers.index(default_id) if default_id in identifiers else 0
claim_id = st.selectbox("Claim", identifiers, index=default_index)
summary = next(item for item in claims if item["claim_id"] == claim_id)

try:
    claim = request("GET", f"/claims/{claim_id}")
    evidence = request("GET", f"/claims/{claim_id}/evidence")
    passport = request("GET", f"/claims/{claim_id}/decision-passport")
except Exception as exc:
    st.error(str(exc))
    st.stop()

a, b, c, d = st.columns(4)
a.metric("Recommendation", summary["recommendation"].replace("_", " ").title())
b.metric("Risk score", summary["risk_score"])
c.metric("Confidence", f"{summary['confidence']:.0%}")
d.metric("Review", summary["review_status"].replace("_", " ").title())

overview, policy, enterprise, ai_execution, controls, trace = st.tabs(
    ["Overview", "Policy evidence", "Enterprise context", "AI execution", "Controls", "Trace"]
)
with overview:
    left, right = st.columns(2)
    left.subheader("Claim")
    left.json(claim["submission"], expanded=True)
    right.subheader("Extracted receipt")
    right.json(evidence["extracted_receipt"], expanded=True)
    st.subheader("Evidence-based explanation")
    st.info(evidence["explanation"])
    verification = evidence["citation_verification"]
    st.write(
        f"Citation verification: **{'Passed' if verification['valid'] else 'Failed'}** · Coverage: {verification['coverage']:.0%}"
    )
with policy:
    for clause in evidence["policy_clauses"]:
        with st.container(border=True):
            st.markdown(f"**{clause['clause_id']} · {clause['policy_name']} v{clause['version']}**")
            st.write(clause["text"])
with enterprise:
    for call in evidence["mcp_calls"]:
        label = f"{call['tool_name']} · {'Error' if call['error'] else 'Success'}"
        with st.expander(label):
            st.json(call)
with ai_execution:
    for call in evidence.get("ai_calls", []):
        provider = call.get("provider", "unknown")
        operation = call.get("operation", "AI operation")
        with st.container(border=True):
            st.markdown(f"**{operation.replace('_', ' ').title()} · {provider}**")
            st.json(call)
with controls:
    display_controls = [
        {
            **item,
            "actual_value": str(item["actual_value"]),
            "expected_value": str(item["expected_value"]),
        }
        for item in evidence["controls"]
    ]
    st.dataframe(
        display_controls,
        column_order=[
            "control_id",
            "control_name",
            "status",
            "actual_value",
            "expected_value",
            "severity",
            "policy_clause_id",
        ],
        hide_index=True,
        width="stretch",
    )
with trace:
    st.dataframe(evidence["workflow_trace"], hide_index=True, width="stretch")

st.divider()
left, right = st.columns([2, 1])
with left:
    st.subheader("Reviewer decision")
    if claim["final_decision"]:
        st.success(f"Final decision: {claim['final_decision']} · {claim['reviewer']}")
    else:
        with st.form("review"):
            decision = st.radio("Decision", ["approved", "rejected"], horizontal=True)
            reviewer = st.text_input("Reviewer", "Finance Reviewer")
            reason = st.text_area("Override reason (required if recommendation changes)")
            authorized = st.checkbox("I authorize this final write action")
            save = st.form_submit_button("Record final decision", type="primary")
        if save:
            try:
                result = request(
                    "POST",
                    f"/claims/{claim_id}/review",
                    json={
                        "decision": decision,
                        "reviewer": reviewer,
                        "override_reason": reason or None,
                        "explicit_authorization": authorized,
                    },
                )
                st.success(f"Decision recorded by {result['reviewer']}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
with right:
    st.subheader("Decision Passport")
    st.caption("Versioned JSON evidence package for audit and assurance testing.")
    st.download_button(
        "Download JSON",
        json.dumps(passport, indent=2),
        file_name=f"{claim_id}-decision-passport.json",
        mime="application/json",
        width="stretch",
    )
