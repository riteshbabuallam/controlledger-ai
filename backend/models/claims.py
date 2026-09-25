from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ExpenseCategory = Literal["meals", "hotel", "transport", "equipment", "miscellaneous"]


class ClaimSubmission(BaseModel):
    employee_id: str = Field(min_length=2, max_length=40)
    merchant: str = Field(min_length=1, max_length=160)
    expense_date: date
    amount: float = Field(gt=0, le=1_000_000)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    category: str
    cost_center: str = Field(min_length=2, max_length=40)
    trip_id: str | None = None
    receipt_text: str | None = None
    receipt_image_data_url: str | None = Field(default=None, max_length=12_000_000)
    receipt_total: float | None = Field(default=None, gt=0)
    receipt_currency: str | None = None
    receipt_quality: float = Field(default=1.0, ge=0, le=1)
    fx_rate_used: float | None = Field(default=None, gt=0)
    claimed_base_amount: float | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=1000)
    synthetic_label: str | None = None

    @field_validator("receipt_image_data_url")
    @classmethod
    def validate_receipt_image(cls, value: str | None) -> str | None:
        if value and not value.startswith(
            ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
        ):
            raise ValueError("Receipt image must be a JPEG, PNG, or WebP data URL")
        return value

    @field_validator("currency", "receipt_currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ExtractedReceipt(BaseModel):
    merchant: str | None
    expense_date: date | None
    total: float | None
    currency: str | None
    category: str | None
    confidence: float = Field(ge=0, le=1)
    source: Literal["structured", "text", "unavailable"]


class ClaimRecord(BaseModel):
    claim_id: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "submitted"
    recommendation: str | None = None
    risk_score: int | None = None
    review_status: str = "not_required"
    final_decision: str | None = None
    submission: ClaimSubmission


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: str = Field(min_length=2, max_length=100)
    override_reason: str | None = Field(default=None, max_length=1000)
    explicit_authorization: bool = False


class PolicyCreate(BaseModel):
    name: str
    version: str
    effective_date: date
    content: str = Field(min_length=20)
    category: str = "general"
    jurisdiction: str = "global"


class ControlDraftApproval(BaseModel):
    reviewer: str = Field(min_length=2, max_length=100)
    explicit_authorization: bool = False


class SimulationRequest(BaseModel):
    scenario_a: dict[str, float]
    scenario_b: dict[str, float]
    claim_ids: list[str] | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, Any] | None = None
