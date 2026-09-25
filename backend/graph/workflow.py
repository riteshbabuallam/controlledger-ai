from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.database.repository import Repository
from backend.graph.nodes import WorkflowNodes
from backend.graph.state import WorkflowState
from backend.mcp_server.client import MCPClientGateway
from backend.mcp_server.tools import EnterpriseTools
from backend.models.claims import ClaimSubmission
from backend.services.ai import AIService


class ControlLedgerWorkflow:
    def __init__(
        self,
        repository: Repository | None = None,
        tools: EnterpriseTools | None = None,
        mcp_client: MCPClientGateway | None = None,
        ai_service: AIService | None = None,
    ):
        self.repository = repository or Repository()
        self.nodes = WorkflowNodes(
            self.repository,
            tools=tools,
            mcp_client=mcp_client,
            ai_service=ai_service,
        )
        self.graph = self._build()

    def _build(self):
        graph = StateGraph(WorkflowState)
        ordered = [
            ("validate_input", self.nodes.validate_input),
            ("extract_receipt", self.nodes.extract_receipt),
            ("detect_untrusted_instructions", self.nodes.detect_untrusted_instructions),
            ("retrieve_policy", self.nodes.retrieve_policy),
            ("fetch_enterprise_context", self.nodes.fetch_enterprise_context),
            ("run_deterministic_controls", self.nodes.run_deterministic_controls),
            ("generate_risk_assessment", self.nodes.generate_risk_assessment),
            ("verify_citations", self.nodes.verify_citations),
            ("route_decision", self.nodes.route_decision),
            ("human_review", self.nodes.human_review),
            ("persist_decision", self.nodes.persist_decision),
            ("generate_decision_passport", self.nodes.generate_decision_passport),
        ]
        for name, function in ordered:
            graph.add_node(name, function)
        graph.add_edge(START, "validate_input")
        for current, following in zip(ordered[:8], ordered[1:9], strict=True):
            graph.add_edge(current[0], following[0])
        graph.add_conditional_edges(
            "route_decision",
            lambda state: (
                "human_review" if state["recommendation"] == "human_review" else "persist_decision"
            ),
            {"human_review": "human_review", "persist_decision": "persist_decision"},
        )
        graph.add_edge("human_review", "persist_decision")
        graph.add_edge("persist_decision", "generate_decision_passport")
        graph.add_edge("generate_decision_passport", END)
        return graph.compile()

    def run(self, claim_id: str, claim: ClaimSubmission) -> dict[str, Any]:
        initial: WorkflowState = {
            "claim_id": claim_id,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "claim": claim,
            "errors": [],
            "safety_flags": [],
            "mcp_calls": [],
            "ai_calls": [],
            "workflow_trace": [],
            "review_status": "not_required",
        }
        return self.graph.invoke(initial)

    @property
    def node_names(self) -> list[str]:
        return [
            name for name in self.graph.get_graph().nodes if name not in {"__start__", "__end__"}
        ]
