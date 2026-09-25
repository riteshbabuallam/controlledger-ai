from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from backend.container import container
from backend.models.claims import ClaimSubmission, SimulationRequest
from backend.services.receipt_extraction import extract_receipt

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_simulation(request: SimulationRequest) -> dict:
    raw_claims = json.loads(Path("data/synthetic_claims/claims.json").read_text(encoding="utf-8"))
    if request.claim_ids:
        raw_claims = [item for item in raw_claims if item["claim_id"] in request.claim_ids]
    outcomes_a = _evaluate(raw_claims, request.scenario_a)
    outcomes_b = _evaluate(raw_claims, request.scenario_b)
    total = len(raw_claims)
    exceptions_a = sum(outcome["exception"] for outcome in outcomes_a)
    exceptions_b = sum(outcome["exception"] for outcome in outcomes_b)
    affected = [
        after["claim_id"]
        for before, after in zip(outcomes_a, outcomes_b, strict=True)
        if before["exception"] != after["exception"]
        or before["failed_controls"] != after["failed_controls"]
    ]
    result = {
        "portfolio_size": total,
        "scenario_a": {
            "exception_count": exceptions_a,
            "exception_rate": round(exceptions_a / total, 4) if total else 0,
        },
        "scenario_b": {
            "exception_count": exceptions_b,
            "exception_rate": round(exceptions_b / total, 4) if total else 0,
        },
        "additional_reviews": exceptions_b - exceptions_a,
        "estimated_reviewer_hours_change": round((exceptions_b - exceptions_a) * 0.2, 2),
        "affected_claim_ids": affected,
        "controls_with_largest_impact": _control_deltas(outcomes_a, outcomes_b),
    }
    simulation_id = f"SIM-{uuid4().hex[:8].upper()}"
    container.repository.save_simulation(simulation_id, request.model_dump(mode="json"), result)
    return {"simulation_id": simulation_id, **result}


@router.get("/{simulation_id}")
def get_simulation(simulation_id: str) -> dict:
    result = container.repository.get_simulation(simulation_id)
    if not result:
        raise HTTPException(404, "Simulation not found")
    return result


def _evaluate(raw_claims: list[dict], overrides: dict[str, float]) -> list[dict]:
    outcomes = []
    for item in raw_claims:
        claim = ClaimSubmission.model_validate(item["submission"])
        context = _context(claim)
        results = container.workflow.nodes.controls.evaluate(
            claim, extract_receipt(claim), context, overrides
        )
        non_pass = [result.control_id for result in results if result.status != "pass"]
        outcomes.append(
            {"claim_id": item["claim_id"], "exception": bool(non_pass), "failed_controls": non_pass}
        )
    return outcomes


def _context(claim: ClaimSubmission) -> dict:
    def safe(call, *args):
        try:
            result = call(*args)
            return result.model_dump(mode="json") if result else None
        except Exception:
            return None

    return {
        "employee": safe(container.tools.get_employee_profile, claim.employee_id),
        "travel": safe(container.tools.get_travel_preapproval, claim.trip_id)
        if claim.trip_id
        else None,
        "budget": safe(container.tools.get_cost_center_budget, claim.cost_center),
        "exchange_rate": safe(
            container.tools.get_exchange_rate, claim.currency, str(claim.expense_date)
        ),
        "duplicate": safe(
            container.tools.find_duplicate_claim,
            claim.employee_id,
            claim.merchant,
            claim.amount,
            str(claim.expense_date),
        ),
    }


def _control_deltas(a: list[dict], b: list[dict]) -> list[dict]:
    identifiers = sorted({identifier for item in a + b for identifier in item["failed_controls"]})
    rows = []
    for identifier in identifiers:
        before = sum(identifier in item["failed_controls"] for item in a)
        after = sum(identifier in item["failed_controls"] for item in b)
        if before != after:
            rows.append(
                {
                    "control_id": identifier,
                    "scenario_a": before,
                    "scenario_b": after,
                    "delta": after - before,
                }
            )
    return sorted(rows, key=lambda row: abs(row["delta"]), reverse=True)
