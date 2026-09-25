from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from backend.container import container
from backend.models.claims import ControlDraftApproval, PolicyCreate
from backend.services.ai import AIConfigurationError

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_policy(policy: PolicyCreate) -> dict:
    policy_id = f"POL-{uuid4().hex[:8].upper()}"
    container.repository.create_policy(policy_id, policy.model_dump(mode="json"))
    return {"policy_id": policy_id, "status": "draft"}


@router.get("")
def list_policies() -> list[dict]:
    return container.repository.list_policies()


@router.get("/{policy_id}")
def get_policy(policy_id: str) -> dict:
    policy = container.repository.get_policy(policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy


@router.post("/{policy_id}/activate")
def activate_policy(policy_id: str) -> dict:
    if not container.repository.activate_policy(policy_id):
        raise HTTPException(404, "Policy not found")
    return {"policy_id": policy_id, "active": True}


@router.post("/{policy_id}/draft-controls", status_code=status.HTTP_201_CREATED)
def draft_policy_controls(policy_id: str) -> dict:
    policy = container.repository.get_policy(policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")
    try:
        result = container.ai.draft_controls(policy["content"])
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    draft_id = f"DRF-{uuid4().hex[:8].upper()}"
    draft = result.value.model_dump(mode="json")
    container.repository.save_control_draft(draft_id, policy_id, draft)
    return {
        "draft_id": draft_id,
        "policy_id": policy_id,
        "status": "requires_human_approval",
        "draft": draft,
        "ai_execution": result.metadata,
    }


@router.get("/control-drafts/{draft_id}")
def get_control_draft(draft_id: str) -> dict:
    draft = container.repository.get_control_draft(draft_id)
    if not draft:
        raise HTTPException(404, "Control draft not found")
    return draft


@router.post("/control-drafts/{draft_id}/approve")
def approve_control_draft(draft_id: str, approval: ControlDraftApproval) -> dict:
    if not approval.explicit_authorization:
        raise HTTPException(403, "Explicit policy-owner authorization is required")
    if not container.repository.get_control_draft(draft_id):
        raise HTTPException(404, "Control draft not found")
    if not container.repository.approve_control_draft(
        draft_id, approval.reviewer, approval.explicit_authorization
    ):
        raise HTTPException(409, "Control draft is already approved")
    return {"draft_id": draft_id, "status": "approved", "reviewer": approval.reviewer}
