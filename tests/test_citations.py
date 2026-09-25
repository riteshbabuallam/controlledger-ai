from __future__ import annotations

from backend.models.controls import ControlResult
from backend.models.decisions import PolicyClause
from backend.rag.verify import verify_citations


def clause(identifier: str) -> PolicyClause:
    return PolicyClause(
        clause_id=identifier,
        policy_name="Policy",
        version="1.0",
        effective_date="2026-01-01",
        category="meals",
        jurisdiction="global",
        text="Evidence",
        score=1,
    )


def control(identifier: str) -> ControlResult:
    return ControlResult(
        control_id="C1",
        control_name="Control",
        status="fail",
        actual_value=2,
        expected_value=1,
        severity="high",
        policy_clause_id=identifier,
        evidence={},
        explanation="Failed",
    )


def test_citation_verification_accepts_retrieved_material_clause():
    result = verify_citations(
        "Amount exceeds policy [MEALS-4.2]", [clause("MEALS-4.2")], [control("MEALS-4.2")]
    )
    assert result.valid
    assert result.coverage == 1


def test_citation_verification_rejects_unknown_citation():
    result = verify_citations(
        "Unsupported [TRAVEL-9.9]", [clause("MEALS-4.2")], [control("MEALS-4.2")]
    )
    assert not result.valid
    assert result.errors
