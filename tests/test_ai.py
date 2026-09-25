from __future__ import annotations

from types import SimpleNamespace

from backend.models.claims import ClaimSubmission, ExtractedReceipt
from backend.models.controls import ControlResult
from backend.models.decisions import (
    GroundedExplanation,
    PolicyClause,
    PolicyControlDraft,
    PolicyControlDraftSet,
)
from backend.services.ai import AIService


class FakeModels:
    def generate_content(self, *, config, **kwargs):
        schema = config.response_schema
        values = {
            ExtractedReceipt: ExtractedReceipt(
                merchant="AI Cafe",
                expense_date="2026-09-21",
                total=820,
                currency="INR",
                category="meals",
                confidence=0.97,
                source="text",
            ),
            GroundedExplanation: GroundedExplanation(
                explanation="The amount is within the allowance [MEALS-4.2].",
                cited_clause_ids=["MEALS-4.2"],
                confidence=0.94,
                known_limitations=[],
            ),
            PolicyControlDraftSet: PolicyControlDraftSet(
                controls=[
                    PolicyControlDraft(
                        id="MEAL_LIMIT_DRAFT",
                        name="Meal limit",
                        category="meals",
                        operator="less_than_or_equal",
                        threshold=1500,
                        currency="INR",
                        policy_clause_id="MEALS-4.2",
                        severity="medium",
                        action="human_review",
                        rationale="Explicit threshold",
                    )
                ],
                assumptions=[],
                confidence=0.95,
            ),
        }
        return SimpleNamespace(
            parsed=values[schema],
            response_id="gemini_test",
            usage_metadata=SimpleNamespace(
                prompt_token_count=100,
                candidates_token_count=30,
            ),
        )

    def embed_content(self, *, contents, **kwargs):
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[1.0, 0.0]) for _ in contents],
            usage_metadata=SimpleNamespace(prompt_token_count=10),
        )


class FakeGemini:
    def __init__(self):
        self.models = FakeModels()


def sample_claim() -> ClaimSubmission:
    return ClaimSubmission(
        employee_id="E001",
        merchant="AI Cafe",
        expense_date="2026-09-21",
        amount=820,
        currency="INR",
        category="meals",
        cost_center="CC100",
        receipt_text="AI Cafe total 820 INR",
    )


def test_gemini_structured_receipt_and_grounded_explanation():
    service = AIService(client=FakeGemini())
    extracted = service.extract_receipt(sample_claim())
    assert extracted.value.total == 820
    assert extracted.metadata["provider"] == "gemini"
    clause = PolicyClause(
        clause_id="MEALS-4.2",
        policy_name="Meals",
        version="1.0",
        effective_date="2026-01-01",
        category="meals",
        jurisdiction="global",
        text="Limit is INR 1,500",
        score=1,
    )
    control = ControlResult(
        control_id="ALLOWANCE_002",
        control_name="Allowance",
        status="pass",
        actual_value=820,
        expected_value=1500,
        severity="medium",
        policy_clause_id="MEALS-4.2",
        evidence={"applicable": True},
        explanation="Within limit",
    )
    explained = service.explain(sample_claim(), [clause], [control], [])
    assert explained.value.cited_clause_ids == ["MEALS-4.2"]
    assert explained.metadata["response_id"] == "gemini_test"


def test_gemini_embeddings_and_policy_control_drafting():
    service = AIService(client=FakeGemini())
    embedded = service.embed(["meal allowance", "hotel allowance"])
    assert embedded.value == [[1.0, 0.0], [1.0, 0.0]]
    assert embedded.metadata["model"] == "gemini-embedding-2"
    drafted = service.draft_controls("Meals may not exceed INR 1,500 [MEALS-4.2].")
    assert drafted.value.controls[0].threshold == 1500
    assert drafted.metadata["provider"] == "gemini"
