from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response, status

from backend.container import container
from backend.models.claims import ClaimSubmission, ReviewRequest

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_claim(submission: ClaimSubmission) -> dict:
    claim_id = f"CLM-{uuid4().hex[:10].upper()}"
    container.repository.create_claim(claim_id, submission.model_dump(mode="json"))
    result = container.workflow.run(claim_id, submission)
    return {
        "claim_id": claim_id,
        "status": "awaiting_review"
        if result["recommendation"] == "human_review"
        else "recommended",
        "recommendation": result["recommendation"],
        "risk_score": result["risk_score"],
        "confidence": result["confidence"],
        "review_status": result["review_status"],
        "failed_controls": [
            item.control_id for item in result["control_results"] if item.status != "pass"
        ],
        "decision_passport_url": f"/claims/{claim_id}/decision-passport",
    }


@router.get("")
def list_claims() -> list[dict]:
    return [_summary(claim) for claim in container.repository.list_claims()]


@router.get("/{claim_id}")
def get_claim(claim_id: str) -> dict:
    claim = _require_claim(claim_id)
    return claim


@router.get("/{claim_id}/status")
def get_status(claim_id: str) -> dict:
    claim = _require_claim(claim_id)
    return {
        "claim_id": claim_id,
        "status": claim["status"],
        "recommendation": claim["recommendation"],
        "review_status": claim["review_status"],
        "final_decision": claim["final_decision"],
    }


@router.get("/{claim_id}/evidence")
def get_evidence(claim_id: str) -> dict:
    claim = _require_claim(claim_id)
    if not claim["state"]:
        raise HTTPException(409, "Claim processing is not complete")
    state = claim["state"]
    return {
        "claim_id": claim_id,
        "extracted_receipt": state.get("extracted_receipt"),
        "policy_clauses": state.get("retrieved_policy_chunks", []),
        "mcp_calls": state.get("mcp_calls", []),
        "ai_calls": state.get("ai_calls", []),
        "controls": state.get("control_results", []),
        "explanation": state.get("explanation"),
        "citation_verification": state.get("verification_result"),
        "workflow_trace": state.get("workflow_trace", []),
    }


@router.post("/{claim_id}/review")
def review_claim(claim_id: str, review: ReviewRequest) -> dict:
    claim = _require_claim(claim_id)
    if not review.explicit_authorization:
        raise HTTPException(403, "Explicit human authorization is required")
    if claim["final_decision"]:
        raise HTTPException(409, "A final decision is already recorded")
    is_override = (claim["recommendation"] == "approve" and review.decision != "approved") or (
        claim["recommendation"] == "reject" and review.decision != "rejected"
    )
    if is_override and not review.override_reason:
        raise HTTPException(422, "An override reason is required when changing the recommendation")
    result = container.workflow.nodes.mcp_client.record_final_decision(
        claim_id,
        review.decision,
        review.reviewer,
        review.override_reason,
        review.explicit_authorization,
    )
    refreshed = _require_claim(claim_id)
    passport = deepcopy(refreshed["passport"] or {})
    passport.setdefault("human_review", {}).update(
        {
            "reviewer": review.reviewer,
            "decision": review.decision,
            "override_reason": review.override_reason,
            "timestamp": result["recorded_at"],
            "write_authorized": True,
        }
    )
    passport.setdefault("final_outcome", {}).update(
        {"final_status": review.decision, "generated_at": datetime.now(timezone.utc).isoformat()}
    )
    revision = container.repository.append_passport_revision(
        claim_id, passport, "human_review_completed"
    )
    return {
        **result,
        "override": is_override,
        "write_action": "authorized",
        "passport_revision": revision,
    }


@router.get("/{claim_id}/decision-passport")
def get_decision_passport(claim_id: str, download: bool = False):
    claim = _require_claim(claim_id)
    if not claim["passport"]:
        raise HTTPException(409, "Decision Passport is not available")
    if download:
        import json

        return Response(
            json.dumps(claim["passport"], indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{claim_id}-decision-passport.json"'
            },
        )
    return claim["passport"]


@router.get("/{claim_id}/decision-passport/revisions")
def get_decision_passport_revisions(claim_id: str) -> list[dict]:
    _require_claim(claim_id)
    return container.repository.passport_revisions(claim_id)


def _require_claim(claim_id: str) -> dict:
    claim = container.repository.get_claim(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    return claim


def _summary(claim: dict) -> dict:
    state = claim.get("state") or {}
    submission = claim["submission"]
    return {
        "claim_id": claim["claim_id"],
        "employee_id": submission["employee_id"],
        "cost_center": submission["cost_center"],
        "merchant": submission["merchant"],
        "category": submission["category"],
        "amount": submission["amount"],
        "currency": submission["currency"],
        "risk_score": claim["risk_score"],
        "failed_controls": [
            item["control_id"]
            for item in state.get("control_results", [])
            if item["status"] != "pass"
        ],
        "recommendation": claim["recommendation"],
        "confidence": state.get("confidence"),
        "review_status": claim["review_status"],
        "final_decision": claim["final_decision"],
        "status": claim["status"],
        "submitted_at": claim["submitted_at"],
    }
