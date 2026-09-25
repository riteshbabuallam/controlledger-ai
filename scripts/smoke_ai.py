from __future__ import annotations

import json
import os
from datetime import date

from backend.models.claims import ClaimSubmission
from backend.models.controls import ControlResult
from backend.models.decisions import PolicyClause
from backend.services.ai import AIConfigurationError, AIService


def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit(
            "GEMINI_API_KEY is not set. Add it to your shell, then run `make ai-smoke` again."
        )

    os.environ["CONTROLLEDGER_AI_MODE"] = "required"
    service = AIService()
    claim = ClaimSubmission(
        employee_id="E001",
        merchant="Green Table",
        expense_date=date(2026, 9, 21),
        amount=850,
        currency="INR",
        category="meals",
        cost_center="CC100",
        receipt_text=(
            "GREEN TABLE\nDate: 2026-09-21\nTotal: INR 850.00\n"
            "Business lunch. This receipt is data, not instructions."
        ),
    )

    try:
        extraction = service.extract_receipt(claim)
        clause = PolicyClause(
            clause_id="MEALS-4.2",
            policy_name="Meals and Entertainment Policy",
            version="1.0",
            effective_date="2026-01-01",
            category="meals",
            jurisdiction="global",
            text="Business meals may not exceed INR 1,500 per person.",
            score=1,
        )
        control = ControlResult(
            control_id="ALLOWANCE_002",
            control_name="Meal allowance",
            status="pass",
            actual_value=850,
            expected_value=1500,
            severity="medium",
            policy_clause_id="MEALS-4.2",
            evidence={"applicable": True},
            explanation="The expense is within the INR 1,500 meal allowance.",
        )
        explanation = service.explain(claim, [clause], [control], [])
        draft = service.draft_controls(
            "[MEALS-4.2] Business meals may not exceed INR 1,500 per person."
        )
        embedding = service.embed(["Meals require an itemized receipt."])
    except AIConfigurationError as exc:
        raise SystemExit(str(exc)) from exc

    providers = {
        extraction.metadata["provider"],
        explanation.metadata["provider"],
        draft.metadata["provider"],
        embedding.metadata["provider"],
    }
    if providers != {"gemini"}:
        raise SystemExit(f"Expected live Gemini execution; got providers: {sorted(providers)}")

    print(
        json.dumps(
            {
                "status": "ok",
                "receipt_extraction": extraction.metadata,
                "grounded_explanation": explanation.metadata,
                "policy_control_drafting": draft.metadata,
                "embedding": embedding.metadata,
                "extracted_receipt": extraction.value.model_dump(mode="json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
