from __future__ import annotations

import re

from backend.models.controls import ControlResult
from backend.models.decisions import CitationVerification, PolicyClause

CITATION = re.compile(r"\[([A-Z]+-\d+\.\d+)]")


def verify_citations(
    explanation: str,
    retrieved: list[PolicyClause],
    control_results: list[ControlResult],
) -> CitationVerification:
    retrieved_ids = {clause.clause_id for clause in retrieved}
    cited_ids = set(CITATION.findall(explanation))
    errors: list[str] = []
    unknown = cited_ids - retrieved_ids
    if unknown:
        errors.append(f"Citations were not retrieved: {', '.join(sorted(unknown))}")
    material_items = [
        result.policy_clause_id for result in control_results if result.status in {"fail", "review"}
    ]
    if not material_items:
        material_items = [
            result.policy_clause_id
            for result in control_results
            if result.status == "pass" and result.evidence.get("applicable", True)
        ][:2]
    material = set(material_items)
    supported_material = material & cited_ids & retrieved_ids
    coverage = len(supported_material) / len(material) if material else 1.0
    if coverage < 1:
        missing = material - supported_material
        errors.append(f"Material control citations missing: {', '.join(sorted(missing))}")
    return CitationVerification(valid=not errors, coverage=round(coverage, 4), errors=errors)
