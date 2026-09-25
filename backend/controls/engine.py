from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from backend.controls.operators import variance_percent, within_date_window, within_tolerance
from backend.models.claims import ClaimSubmission, ExtractedReceipt
from backend.models.controls import ControlDefinition, ControlResult


class ControlEngine:
    def __init__(self, config_path: str | Path | None = None):
        path = Path(
            config_path
            or os.getenv("CONTROLLEDGER_CONTROLS_PATH", "data/controls/expense_controls.yaml")
        )
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.version = str(raw["version"])
        self.definitions = [ControlDefinition.model_validate(item) for item in raw["controls"]]

    def evaluate(
        self,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float] | None = None,
    ) -> list[ControlResult]:
        overrides = overrides or {}
        handlers = {
            "amount_match": self._amount_match,
            "category_allowance": self._category_allowance,
            "duplicate": self._duplicate,
            "travel_preapproval": self._travel_preapproval,
            "travel_dates": self._travel_dates,
            "fx_variance": self._fx_variance,
        }
        return [
            handlers[definition.type](definition, claim, receipt, context, overrides)
            for definition in self.definitions
        ]

    def _result(
        self,
        definition: ControlDefinition,
        status: str,
        actual: Any,
        expected: Any,
        evidence: dict[str, Any],
        explanation: str,
        policy_clause_id: str | None = None,
    ) -> ControlResult:
        return ControlResult(
            control_id=definition.id,
            control_name=definition.name,
            status=status,
            actual_value=actual,
            expected_value=expected,
            severity=definition.severity,
            policy_clause_id=policy_clause_id or definition.policy_clause,
            evidence=evidence,
            explanation=explanation,
        )

    def _amount_match(
        self,
        definition: ControlDefinition,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float],
    ) -> ControlResult:
        tolerance = overrides.get("amount_tolerance", definition.parameters["tolerance"])
        if receipt.total is None:
            return self._result(
                definition,
                "review",
                None,
                claim.amount,
                {"applicable": True, "receipt_available": False},
                "Receipt total is unavailable.",
            )
        passed = within_tolerance(receipt.total, claim.amount, tolerance)
        return self._result(
            definition,
            "pass" if passed else "fail",
            receipt.total,
            claim.amount,
            {"applicable": True, "tolerance": tolerance},
            "Receipt and claim totals agree."
            if passed
            else "Receipt and claim totals do not agree.",
        )

    def _category_allowance(
        self,
        definition: ControlDefinition,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float],
    ) -> ControlResult:
        threshold_key = f"{claim.category}_allowance"
        threshold = overrides.get(threshold_key, definition.parameters.get(claim.category))
        clause_by_category = {
            "meals": "MEALS-4.2",
            "hotel": "TRAVEL-4.1",
            "transport": "EQUIP-3.1",
            "equipment": "EQUIP-2.2",
            "miscellaneous": "EQUIP-3.1",
        }
        clause_id = clause_by_category.get(claim.category, definition.policy_clause)
        if threshold is None:
            return self._result(
                definition,
                "review",
                claim.amount,
                "supported category",
                {"applicable": True},
                "No allowance is configured for this category.",
                clause_id,
            )
        rate = (context.get("exchange_rate") or {}).get("rate_to_inr", 1.0)
        amount_inr = claim.amount * rate
        passed = amount_inr <= threshold
        return self._result(
            definition,
            "pass" if passed else "review",
            round(amount_inr, 2),
            threshold,
            {"applicable": True, "rate_to_inr": rate},
            "Amount is within the category allowance."
            if passed
            else "Amount exceeds the category allowance.",
            clause_id,
        )

    def _duplicate(
        self,
        definition: ControlDefinition,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float],
    ) -> ControlResult:
        duplicate = context.get("duplicate")
        if duplicate is None:
            return self._result(
                definition,
                "review",
                "unavailable",
                "no duplicate",
                {"applicable": True},
                "Duplicate service was unavailable.",
            )
        found = bool(duplicate.get("duplicate_found") or duplicate.get("split_pattern"))
        return self._result(
            definition,
            "fail" if found else "pass",
            found,
            False,
            {"applicable": True, **duplicate},
            "A duplicate or split pattern was found."
            if found
            else "No duplicate or split pattern was found.",
        )

    def _travel_preapproval(
        self,
        definition: ControlDefinition,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float],
    ) -> ControlResult:
        is_weekend = claim.expense_date.weekday() >= 5
        applicable = claim.category in definition.parameters["travel_categories"] and (
            bool(claim.trip_id) or is_weekend
        )
        if not applicable:
            return self._result(
                definition,
                "pass",
                "not applicable",
                "approved trip when travel-linked",
                {"applicable": False},
                "The claim is not linked to a trip.",
            )
        if not claim.trip_id:
            return self._result(
                definition,
                "fail",
                False,
                True,
                {"applicable": True, "weekend": True},
                "Weekend expense has no approved trip.",
            )
        trip = context.get("travel")
        if trip is None:
            return self._result(
                definition,
                "review",
                "unavailable",
                True,
                {"applicable": True},
                "Travel approval data was unavailable.",
            )
        approved = bool(trip.get("approved")) and trip.get("employee_id") == claim.employee_id
        return self._result(
            definition,
            "pass" if approved else "fail",
            approved,
            True,
            {"applicable": True, "trip_id": claim.trip_id},
            "Travel is approved." if approved else "Travel is not approved for this employee.",
        )

    def _travel_dates(
        self,
        definition: ControlDefinition,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float],
    ) -> ControlResult:
        if not claim.trip_id:
            return self._result(
                definition,
                "pass",
                "not applicable",
                "approved date window",
                {"applicable": False},
                "No trip date window applies.",
            )
        trip = context.get("travel")
        if not trip:
            return self._result(
                definition,
                "review",
                str(claim.expense_date),
                "available trip dates",
                {"applicable": True},
                "Travel dates were unavailable.",
            )
        grace = int(overrides.get("travel_grace_days", definition.parameters["grace_days"]))
        passed = within_date_window(
            claim.expense_date,
            date.fromisoformat(trip["start_date"]),
            date.fromisoformat(trip["end_date"]),
            grace,
        )
        expected = f"{trip['start_date']} through {trip['end_date']} (+/- {grace} day)"
        return self._result(
            definition,
            "pass" if passed else "fail",
            str(claim.expense_date),
            expected,
            {"applicable": True, "trip_id": claim.trip_id},
            "Expense is within the approved travel window."
            if passed
            else "Expense is outside the approved travel window.",
        )

    def _fx_variance(
        self,
        definition: ControlDefinition,
        claim: ClaimSubmission,
        receipt: ExtractedReceipt,
        context: dict[str, Any],
        overrides: dict[str, float],
    ) -> ControlResult:
        if claim.currency == "INR":
            return self._result(
                definition,
                "pass",
                0.0,
                definition.parameters["tolerance_percent"],
                {"applicable": False},
                "No currency conversion is required.",
            )
        exchange = context.get("exchange_rate")
        if not exchange or claim.fx_rate_used is None:
            return self._result(
                definition,
                "review",
                claim.fx_rate_used,
                "corporate rate",
                {"applicable": True},
                "Exchange-rate evidence was unavailable.",
            )
        expected = float(exchange["rate_to_inr"])
        variance = variance_percent(claim.fx_rate_used, expected)
        tolerance = overrides.get(
            "currency_variance_tolerance", definition.parameters["tolerance_percent"]
        )
        return self._result(
            definition,
            "pass" if variance <= tolerance else "review",
            round(variance, 3),
            tolerance,
            {"applicable": True, "used_rate": claim.fx_rate_used, "corporate_rate": expected},
            "Currency variance is within tolerance."
            if variance <= tolerance
            else "Currency variance exceeds tolerance.",
        )
