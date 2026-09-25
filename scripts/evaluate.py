from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path

from backend.database.repository import Repository
from backend.graph.workflow import ControlLedgerWorkflow
from backend.models.claims import ClaimSubmission
from backend.services.ai import AIService


def evaluate() -> dict:
    fixtures = json.loads(Path("data/synthetic_claims/claims.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as temp_dir:
        repository = Repository(Path(temp_dir) / "evaluation.db")
        workflow = ControlLedgerWorkflow(
            repository=repository,
            ai_service=AIService(mode="offline"),
        )
        completed = 0
        passports = 0
        correct = 0
        citation_valid = 0
        citation_eligible = 0
        unauthorized_writes = 0
        mcp_protocol_calls = 0
        outcomes: Counter[str] = Counter()
        scenario_results = []
        for item in fixtures:
            claim = ClaimSubmission.model_validate(item["submission"])
            repository.create_claim(item["claim_id"], claim.model_dump(mode="json"))
            try:
                result = workflow.run(item["claim_id"], claim)
                completed += 1
                passports += bool(result.get("decision_passport"))
                correct += result["recommendation"] == item["expected_recommendation"]
                citation_valid += bool(result["verification_result"]["valid"])
                citation_eligible += bool(result["retrieved_policy_chunks"])
                outcomes[result["recommendation"]] += 1
                mcp_protocol_calls += sum(
                    call.get("transport") == "mcp" for call in result["mcp_calls"]
                )
                scenario_results.append(
                    {
                        "claim_id": item["claim_id"],
                        "scenario": item["scenario"],
                        "expected": item["expected_recommendation"],
                        "actual": result["recommendation"],
                        "citation_valid": result["verification_result"]["valid"],
                        "passport_generated": bool(result.get("decision_passport")),
                    }
                )
            except Exception as exc:
                scenario_results.append(
                    {"claim_id": item["claim_id"], "scenario": item["scenario"], "error": str(exc)}
                )
        for item in repository.list_claims():
            unauthorized_writes += sum(
                event["event_type"] == "unauthorized_write"
                for event in repository.events_for_claim(item["claim_id"])
            )
        total = len(fixtures)
        return {
            "portfolio_size": total,
            "workflow_completion": completed,
            "workflow_completion_rate": round(completed / total, 4),
            "decision_passports": passports,
            "decision_accuracy": round(correct / total, 4),
            "citation_correctness": round(citation_valid / citation_eligible, 4)
            if citation_eligible
            else 0,
            "citation_eligible_claims": citation_eligible,
            "citation_failures_routed_to_review": total - citation_eligible,
            "governed_outcomes": dict(outcomes),
            "unauthorized_write_actions": unauthorized_writes,
            "workflow_nodes": len(workflow.node_names),
            "mcp_tools": 6,
            "mcp_protocol_calls": mcp_protocol_calls,
            "rag_backend": type(workflow.nodes.retriever).__name__,
            "ai_provider": workflow.nodes.ai_service.provider,
            "ai_live": workflow.nodes.ai_service.live,
            "controls": 6,
            "scenarios": scenario_results,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate()
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
