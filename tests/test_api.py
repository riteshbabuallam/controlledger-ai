from __future__ import annotations

from fastapi.testclient import TestClient

from backend.container import container
from backend.main import app


def test_claim_submission_and_human_gated_review(repository, tools, workflow):
    container.repository = repository
    container.tools = tools
    container.workflow = workflow
    client = TestClient(app)
    response = client.post(
        "/claims",
        json={
            "employee_id": "E001",
            "merchant": "Green Table",
            "expense_date": "2026-09-21",
            "amount": 850,
            "currency": "INR",
            "category": "meals",
            "cost_center": "CC100",
            "receipt_total": 850,
        },
    )
    assert response.status_code == 201
    claim_id = response.json()["claim_id"]
    assert client.get(f"/claims/{claim_id}/decision-passport").status_code == 200
    denied = client.post(
        f"/claims/{claim_id}/review",
        json={"decision": "approved", "reviewer": "Reviewer", "explicit_authorization": False},
    )
    assert denied.status_code == 403
    accepted = client.post(
        f"/claims/{claim_id}/review",
        json={"decision": "approved", "reviewer": "Reviewer", "explicit_authorization": True},
    )
    assert accepted.status_code == 200
    assert accepted.json()["write_action"] == "authorized"
    revisions = client.get(f"/claims/{claim_id}/decision-passport/revisions")
    assert revisions.status_code == 200
    assert [item["revision"] for item in revisions.json()] == [1, 2]


def test_operations_endpoints(repository, tools, workflow):
    container.repository = repository
    container.tools = tools
    container.workflow = workflow
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"
