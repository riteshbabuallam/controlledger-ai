from __future__ import annotations

from typing import Any, TypedDict

from backend.models.claims import ClaimSubmission, ExtractedReceipt
from backend.models.controls import ControlResult
from backend.models.decisions import PolicyClause


class WorkflowState(TypedDict, total=False):
    claim_id: str
    submitted_at: str
    claim: ClaimSubmission
    receipt_file_reference: str | None
    extracted_receipt: ExtractedReceipt
    retrieved_policy_chunks: list[PolicyClause]
    enterprise_context: dict[str, Any]
    mcp_calls: list[dict[str, Any]]
    ai_calls: list[dict[str, Any]]
    control_results: list[ControlResult]
    risk_score: int
    confidence: float
    explanation: str
    recommendation: str
    citations: list[str]
    verification_result: dict[str, Any]
    review_status: str
    reviewer_decision: str | None
    override_reason: str | None
    execution_metadata: dict[str, Any]
    errors: list[str]
    safety_flags: list[str]
    workflow_trace: list[dict[str, Any]]
    decision_passport: dict[str, Any]
