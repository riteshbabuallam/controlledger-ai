from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.controls.engine import ControlEngine
from backend.database.repository import Repository
from backend.graph.state import WorkflowState
from backend.mcp_server.client import MCPClientGateway
from backend.mcp_server.tools import EnterpriseTools
from backend.rag.retrieve import PolicyRetriever, build_retriever
from backend.rag.verify import verify_citations
from backend.services.ai import AIService
from backend.services.cost_tracking import ExecutionTracker
from backend.services.passport import build_passport
from backend.services.receipt_extraction import contains_untrusted_instructions


def _trace(state: WorkflowState, node: str, outcome: str = "completed") -> list[dict[str, Any]]:
    return [
        *state.get("workflow_trace", []),
        {"node": node, "outcome": outcome, "timestamp": datetime.now(timezone.utc).isoformat()},
    ]


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    return value


class WorkflowNodes:
    def __init__(
        self,
        repository: Repository,
        tools: EnterpriseTools | None = None,
        retriever: PolicyRetriever | None = None,
        controls: ControlEngine | None = None,
        ai_service: AIService | None = None,
        mcp_client: MCPClientGateway | None = None,
    ):
        self.repository = repository
        self.tools = tools or EnterpriseTools(repository=repository)
        self.mcp_client = mcp_client or MCPClientGateway(
            repository, direct_tools=tools if tools is not None else None
        )
        self.ai_service = ai_service or AIService()
        self.retriever = retriever or build_retriever(self.ai_service)
        self.controls = controls or ControlEngine()
        self.trackers: dict[str, ExecutionTracker] = {}

    def validate_input(self, state: WorkflowState) -> dict[str, Any]:
        tracker = ExecutionTracker(
            model_identifier=(
                self.ai_service.model if self.ai_service.live else "deterministic-evidence-v1"
            )
        )
        tracker.start()
        self.trackers[state["claim_id"]] = tracker
        claim = state["claim"]
        errors = list(state.get("errors", []))
        if claim.category not in {"meals", "hotel", "transport", "equipment", "miscellaneous"}:
            errors.append("Unsupported expense category")
        return {"errors": errors, "workflow_trace": _trace(state, "validate_input")}

    def extract_receipt(self, state: WorkflowState) -> dict[str, Any]:
        result = self.ai_service.extract_receipt(state["claim"])
        self.trackers[state["claim_id"]].record_ai_call(result.metadata)
        return {
            "extracted_receipt": result.value,
            "ai_calls": [*state.get("ai_calls", []), result.metadata],
            "workflow_trace": _trace(state, "extract_receipt"),
        }

    def detect_untrusted_instructions(self, state: WorkflowState) -> dict[str, Any]:
        claim = state["claim"]
        found = contains_untrusted_instructions(
            claim.receipt_text
        ) or contains_untrusted_instructions(claim.notes)
        flags = list(state.get("safety_flags", []))
        if found:
            flags.append("untrusted_instruction_detected")
        return {
            "safety_flags": flags,
            "workflow_trace": _trace(
                state, "detect_untrusted_instructions", "flagged" if found else "clear"
            ),
        }

    def retrieve_policy(self, state: WorkflowState) -> dict[str, Any]:
        claim = state["claim"]
        query = (
            f"{claim.category} {claim.merchant} amount allowance receipt total claimed amount duplicate split "
            "travel preapproval approved travel dates currency conversion variance personal purchase eligible category"
        )
        supported = {"meals", "hotel", "transport", "equipment", "miscellaneous"}
        clauses = (
            self.retriever.retrieve(query, version="1.0", category=claim.category, top_k=10)
            if claim.category in supported
            else []
        )
        errors = list(state.get("errors", []))
        if not clauses:
            errors.append("No policy clause retrieved")
        result: dict[str, Any] = {
            "retrieved_policy_chunks": clauses,
            "errors": errors,
            "workflow_trace": _trace(state, "retrieve_policy"),
        }
        embedding_metadata = getattr(self.retriever, "embedding_metadata", None)
        if embedding_metadata:
            self.trackers[state["claim_id"]].record_ai_call(embedding_metadata)
            result["ai_calls"] = [*state.get("ai_calls", []), embedding_metadata]
        return result

    def fetch_enterprise_context(self, state: WorkflowState) -> dict[str, Any]:
        context, calls = self.mcp_client.fetch_claim_context(state["claim"])
        self.trackers[state["claim_id"]].tool_calls += len(calls)
        return {
            "enterprise_context": context,
            "mcp_calls": calls,
            "workflow_trace": _trace(state, "fetch_enterprise_context"),
        }

    def run_deterministic_controls(self, state: WorkflowState) -> dict[str, Any]:
        results = self.controls.evaluate(
            state["claim"], state["extracted_receipt"], state["enterprise_context"]
        )
        return {
            "control_results": results,
            "workflow_trace": _trace(state, "run_deterministic_controls"),
        }

    def generate_risk_assessment(self, state: WorkflowState) -> dict[str, Any]:
        results = state["control_results"]
        weights = {"low": 8, "medium": 16, "high": 25, "critical": 40}
        score = sum(weights[result.severity] for result in results if result.status == "fail")
        score += sum(
            weights[result.severity] // 2 for result in results if result.status == "review"
        )
        receipt = state["extracted_receipt"]
        flags = list(state.get("safety_flags", []))
        if receipt.confidence < 0.7:
            flags.append("low_extraction_confidence")
            score += 20
        employee = state["enterprise_context"].get("employee")
        if employee and employee.get("risk_tier") == "high":
            flags.append("high_risk_employee")
            score += 15
        budget = state["enterprise_context"].get("budget")
        if budget and state["claim"].amount > budget.get("available", 0):
            flags.append("insufficient_budget")
            score += 15
        notes = (state["claim"].notes or "").lower()
        if "personal" in notes:
            flags.append("personal_purchase")
            score += 40
        ai_result = self.ai_service.explain(
            state["claim"],
            state["retrieved_policy_chunks"],
            results,
            flags,
        )
        self.trackers[state["claim_id"]].record_ai_call(ai_result.metadata)
        grounded = ai_result.value
        extraction_confidence = max(
            0.2,
            min(
                receipt.confidence,
                1 - len([call for call in state["mcp_calls"] if call["error"]]) * 0.15,
            ),
        )
        confidence = min(extraction_confidence, grounded.confidence)
        return {
            "risk_score": min(score, 100),
            "confidence": round(confidence, 3),
            "explanation": grounded.explanation,
            "citations": grounded.cited_clause_ids,
            "ai_calls": [*state.get("ai_calls", []), ai_result.metadata],
            "safety_flags": flags,
            "workflow_trace": _trace(state, "generate_risk_assessment"),
        }

    def verify_citations(self, state: WorkflowState) -> dict[str, Any]:
        result = verify_citations(
            state["explanation"], state["retrieved_policy_chunks"], state["control_results"]
        )
        return {
            "verification_result": result.model_dump(mode="json"),
            "workflow_trace": _trace(
                state, "verify_citations", "valid" if result.valid else "invalid"
            ),
        }

    def route_decision(self, state: WorkflowState) -> dict[str, Any]:
        results = state["control_results"]
        hard_fail = any(
            result.status == "fail" and self._action(result.control_id) == "reject"
            for result in results
        )
        missing_context = (
            any(call["error"] for call in state["mcp_calls"])
            or state["enterprise_context"].get("employee") is None
        )
        flags = state.get("safety_flags", [])
        if "personal_purchase" in flags:
            recommendation = "reject"
        elif hard_fail:
            recommendation = "reject"
        elif (
            any(result.status == "review" for result in results)
            or missing_context
            or not state["verification_result"]["valid"]
            or bool(flags)
            or state["confidence"] < 0.7
            or state.get("errors")
        ):
            recommendation = "human_review"
        else:
            recommendation = "approve"
        return {
            "recommendation": recommendation,
            "workflow_trace": _trace(state, "route_decision", recommendation),
        }

    def _action(self, control_id: str) -> str:
        return next(
            definition.action
            for definition in self.controls.definitions
            if definition.id == control_id
        )

    def human_review(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "review_status": "pending",
            "workflow_trace": _trace(state, "human_review", "awaiting_human"),
        }

    def persist_decision(self, state: WorkflowState) -> dict[str, Any]:
        review_status = state.get("review_status", "not_required")
        self.repository.add_event(
            state["claim_id"],
            "workflow_recommendation",
            {
                "recommendation": state["recommendation"],
                "risk_score": state["risk_score"],
                "write_action": False,
            },
        )
        return {
            "review_status": review_status,
            "workflow_trace": _trace(state, "persist_decision", "recommendation_only"),
        }

    def generate_decision_passport(self, state: WorkflowState) -> dict[str, Any]:
        tracker = self.trackers[state["claim_id"]]
        metadata = tracker.metadata()
        passport_state = {
            **state,
            "execution_metadata": metadata,
            "workflow_trace": _trace(state, "generate_decision_passport"),
        }
        passport = build_passport(passport_state)
        passport_data = passport.model_dump(mode="json")
        serialized = _dump(passport_state)
        self.repository.update_claim(
            state["claim_id"],
            status="awaiting_review"
            if state["recommendation"] == "human_review"
            else "recommended",
            recommendation=state["recommendation"],
            risk_score=state["risk_score"],
            review_status=state.get("review_status", "not_required"),
            state_json=serialized,
        )
        revision = self.repository.append_passport_revision(
            state["claim_id"], passport_data, "workflow_completed"
        )
        passport_data["revision"] = revision
        return {
            "execution_metadata": metadata,
            "decision_passport": passport_data,
            "workflow_trace": passport_state["workflow_trace"],
        }
