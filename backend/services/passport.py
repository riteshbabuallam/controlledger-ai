from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from backend.models.decisions import DecisionPassport


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def build_passport(
    state: dict[str, Any], persisted_claim: dict[str, Any] | None = None
) -> DecisionPassport:
    claim = state["claim"]
    receipt = state.get("extracted_receipt")
    clauses = state.get("retrieved_policy_chunks", [])
    controls = state.get("control_results", [])
    persisted_claim = persisted_claim or {}
    submission = claim.model_dump(mode="json") if hasattr(claim, "model_dump") else claim
    receipt_data = receipt.model_dump(mode="json") if hasattr(receipt, "model_dump") else receipt
    clause_data = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in clauses
    ]
    control_data = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in controls
    ]
    ai_calls = state.get("execution_metadata", {}).get("ai_calls", [])
    live_ai_used = any(call.get("provider") not in {"offline", "deterministic_fallback"} for call in ai_calls)
    limitations = ["Synthetic enterprise data", "MVP policy corpus"]
    if not live_ai_used:
        limitations.append("Offline deterministic AI fallback used for this execution")
    final_decision = persisted_claim.get("final_decision")
    return DecisionPassport(
        identification={
            "claim_id": state["claim_id"],
            "policy_tenant": "Synthetic Organization",
            "submission_time": state.get("submitted_at"),
            "processing_time_ms": state.get("execution_metadata", {}).get("latency_ms", 0),
        },
        input_evidence={
            "receipt_hash": _hash(claim.receipt_text or receipt_data),
            "claim_form_hash": _hash(submission),
            "extracted_fields": receipt_data,
            "extraction_confidence": receipt_data.get("confidence", 0) if receipt_data else 0,
        },
        policy_evidence={
            "policy_name": sorted({item["policy_name"] for item in clause_data}),
            "version": sorted({item["version"] for item in clause_data}),
            "effective_date": sorted({item["effective_date"] for item in clause_data}),
            "retrieved_clause_ids": [item["clause_id"] for item in clause_data],
            "relevant_clauses": clause_data,
            "citation_verification": state.get("verification_result"),
        },
        enterprise_context={
            "mcp_server": "enterprise_context_server",
            "calls": state.get("mcp_calls", []),
            "context": state.get("enterprise_context", {}),
        },
        control_execution={
            "control_version": "1.0",
            "controls": control_data,
            "passed": sum(item["status"] == "pass" for item in control_data),
            "failed": sum(item["status"] == "fail" for item in control_data),
            "review": sum(item["status"] == "review" for item in control_data),
        },
        ai_execution={
            **state.get("execution_metadata", {}),
            "explanation": state.get("explanation"),
            "output_confidence": state.get("confidence", 0),
        },
        human_review={
            "reviewer": persisted_claim.get("reviewer"),
            "decision": final_decision,
            "override_reason": persisted_claim.get("override_reason"),
            "timestamp": persisted_claim.get("reviewed_at"),
            "write_authorized": bool(final_decision),
        },
        final_outcome={
            "recommendation": state.get("recommendation"),
            "final_status": final_decision or state.get("recommendation"),
            "known_limitations": limitations,
            "follow_up_actions": ["Human review required"]
            if state.get("recommendation") == "human_review" and not final_decision
            else [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        workflow_trace=state.get("workflow_trace", []),
    )
