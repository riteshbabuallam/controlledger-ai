from __future__ import annotations

import base64
from datetime import date

import streamlit as st

from dashboard.client import request

st.title("Claims review")
st.caption("Submit a claim or review the governed work queue.")

with st.expander("Submit a claim", expanded=False):
    with st.form("new_claim"):
        left, middle, right = st.columns(3)
        employee_id = left.text_input("Employee ID", "E001")
        merchant = middle.text_input("Merchant", "Green Table")
        expense_date = right.date_input("Expense date", date(2026, 9, 21))
        amount = left.number_input("Amount", min_value=0.01, value=850.0)
        currency = middle.selectbox("Currency", ["INR", "USD", "EUR", "GBP", "SGD"])
        category = right.selectbox(
            "Category", ["meals", "hotel", "transport", "equipment", "miscellaneous"]
        )
        cost_center = left.text_input("Cost center", "CC100")
        trip_id = middle.text_input("Trip ID (optional)")
        receipt_total = right.number_input("Receipt total", min_value=0.0, value=850.0)
        receipt_image = st.file_uploader(
            "Receipt image (optional AI extraction)", type=["png", "jpg", "jpeg", "webp"]
        )
        notes = st.text_area("Business purpose / notes", "Client workshop lunch")
        submitted = st.form_submit_button("Run controls", type="primary", width="stretch")
    if submitted:
        image_data_url = None
        if receipt_image:
            encoded = base64.b64encode(receipt_image.getvalue()).decode()
            image_data_url = f"data:{receipt_image.type};base64,{encoded}"
        payload = {
            "employee_id": employee_id,
            "merchant": merchant,
            "expense_date": str(expense_date),
            "amount": amount,
            "currency": currency,
            "category": category,
            "cost_center": cost_center,
            "trip_id": trip_id or None,
            "receipt_total": receipt_total or None,
            "receipt_currency": currency,
            "receipt_image_data_url": image_data_url,
            "notes": notes or None,
        }
        try:
            result = request("POST", "/claims", json=payload)
            st.success(
                f"{result['claim_id']} processed: {result['recommendation'].replace('_', ' ')}"
            )
            st.session_state["selected_claim_id"] = result["claim_id"]
        except Exception as exc:
            st.error(str(exc))

try:
    claims = request("GET", "/claims")
except Exception as exc:
    st.error(str(exc))
    st.stop()

if not claims:
    st.info(
        "No claims yet. Submit one above or run `python scripts/seed_demo.py` for the 30-claim portfolio."
    )
    st.stop()

metric_a, metric_b, metric_c, metric_d = st.columns(4)
metric_a.metric("Claims", len(claims))
metric_b.metric("Human review", sum(item["recommendation"] == "human_review" for item in claims))
metric_c.metric("Recommended reject", sum(item["recommendation"] == "reject" for item in claims))
metric_d.metric("Completed", sum(bool(item["final_decision"]) for item in claims))

filters, _ = st.columns([1, 2])
filter_value = filters.selectbox(
    "Queue", ["All", "Needs review", "Recommended approval", "Recommended rejection"]
)
if filter_value == "Needs review":
    claims = [item for item in claims if item["recommendation"] == "human_review"]
elif filter_value == "Recommended approval":
    claims = [item for item in claims if item["recommendation"] == "approve"]
elif filter_value == "Recommended rejection":
    claims = [item for item in claims if item["recommendation"] == "reject"]

st.dataframe(
    claims,
    column_order=[
        "claim_id",
        "merchant",
        "employee_id",
        "category",
        "amount",
        "currency",
        "risk_score",
        "recommendation",
        "review_status",
    ],
    column_config={
        "claim_id": "Claim",
        "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100),
        "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
    },
    hide_index=True,
    width="stretch",
)

selected = st.selectbox("Open claim", [item["claim_id"] for item in claims])
if st.button("View evidence", type="primary"):
    st.session_state["selected_claim_id"] = selected
    st.switch_page("pages/evidence_view.py")
