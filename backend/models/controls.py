from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ControlResult(BaseModel):
    control_id: str
    control_name: str
    status: Literal["pass", "fail", "review"]
    actual_value: Any
    expected_value: Any
    severity: Literal["low", "medium", "high", "critical"]
    policy_clause_id: str
    evidence: dict[str, Any]
    explanation: str


class ControlDefinition(BaseModel):
    id: str
    name: str
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    policy_clause: str
    action: Literal["reject", "human_review"]
    parameters: dict[str, Any]
