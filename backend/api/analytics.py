from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter

from backend.container import container

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/controls")
def control_analytics() -> dict:
    claims = container.repository.list_claims()
    statuses: dict[str, Counter] = defaultdict(Counter)
    latency = []
    cost = []
    for claim in claims:
        state = claim.get("state") or {}
        for result in state.get("control_results", []):
            statuses[result["control_id"]][result["status"]] += 1
        metadata = state.get("execution_metadata", {})
        if metadata:
            latency.append(metadata.get("latency_ms", 0))
            cost.append(metadata.get("estimated_cost_usd", 0))
    return {
        "claims_processed": len(claims),
        "controls": [{"control_id": key, **counts} for key, counts in sorted(statuses.items())],
        "average_latency_ms": round(sum(latency) / len(latency), 2) if latency else 0,
        "average_ai_cost_usd": round(sum(cost) / len(cost), 6) if cost else 0,
    }


@router.get("/exceptions")
def exception_analytics() -> dict:
    claims = container.repository.list_claims()
    recommendations = Counter(claim["recommendation"] or "processing" for claim in claims)
    departments: Counter = Counter()
    overrides = 0
    for claim in claims:
        state = claim.get("state") or {}
        employee = (state.get("enterprise_context") or {}).get("employee") or {}
        if claim["recommendation"] == "human_review":
            departments[employee.get("department", "Unknown")] += 1
        if claim["final_decision"] and (
            (claim["recommendation"] == "approve" and claim["final_decision"] != "approved")
            or (claim["recommendation"] == "reject" and claim["final_decision"] != "rejected")
        ):
            overrides += 1
    total = len(claims)
    return {
        "total_claims": total,
        "recommendations": dict(recommendations),
        "exception_rate": round(recommendations["human_review"] / total, 4) if total else 0,
        "human_review_rate": round(recommendations["human_review"] / total, 4) if total else 0,
        "human_override_rate": round(overrides / total, 4) if total else 0,
        "exceptions_by_department": dict(departments),
    }
