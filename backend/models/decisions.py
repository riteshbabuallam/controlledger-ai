from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PolicyClause(BaseModel):
    clause_id: str
    policy_name: str
    version: str
    effective_date: str
    category: str
    jurisdiction: str
    text: str
    score: float = Field(ge=0, le=1)


class MCPCallEvidence(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    called_at: datetime


class CitationVerification(BaseModel):
    valid: bool
    coverage: float = Field(ge=0, le=1)
    errors: list[str] = Field(default_factory=list)


class GroundedExplanation(BaseModel):
    explanation: str = Field(min_length=10, max_length=4000)
    cited_clause_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    known_limitations: list[str] = Field(default_factory=list)


class PolicyControlDraft(BaseModel):
    id: str
    name: str
    category: str
    operator: str
    threshold: float | None
    currency: str | None
    policy_clause_id: str
    severity: str
    action: str
    rationale: str


class PolicyControlDraftSet(BaseModel):
    controls: list[PolicyControlDraft]
    assumptions: list[str]
    confidence: float = Field(ge=0, le=1)


class DecisionPassport(BaseModel):
    schema_version: str = "1.0"
    identification: dict[str, Any]
    input_evidence: dict[str, Any]
    policy_evidence: dict[str, Any]
    enterprise_context: dict[str, Any]
    control_execution: dict[str, Any]
    ai_execution: dict[str, Any]
    human_review: dict[str, Any]
    final_outcome: dict[str, Any]
    workflow_trace: list[dict[str, Any]]
