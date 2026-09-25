from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.database.repository import Repository


class EmployeeProfile(BaseModel):
    employee_id: str
    name: str
    department: str
    cost_center: str
    active: bool
    risk_tier: str


class TravelPreapproval(BaseModel):
    trip_id: str
    employee_id: str
    approved: bool
    start_date: str
    end_date: str
    destination: str


class BudgetContext(BaseModel):
    cost_center: str
    budget: float
    spent: float
    available: float


class ExchangeRate(BaseModel):
    currency: str
    date: str
    rate_to_inr: float


class DuplicateResult(BaseModel):
    duplicate_found: bool
    split_pattern: bool = False
    matched_claim_id: str | None = None
    reason: str


class FinalDecisionResult(BaseModel):
    claim_id: str
    decision: str
    reviewer: str
    recorded_at: str


class EnterpriseTools:
    """Typed implementations exposed by the MCP server and used in-process in tests."""

    def __init__(
        self,
        fixture_dir: str | Path = "data/enterprise_fixtures",
        repository: Repository | None = None,
    ):
        root = Path(fixture_dir)
        self.employees = self._load(root / "employees.json")
        self.trips = self._load(root / "trips.json")
        self.budgets = self._load(root / "budgets.json")
        self.rates = self._load(root / "exchange_rates.json")
        self.duplicates = self._load(root / "duplicate_claims.json")
        self.repository = repository or Repository()

    @staticmethod
    def _load(path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def get_employee_profile(self, employee_id: str) -> EmployeeProfile | None:
        if employee_id == "E_UNAVAILABLE":
            raise ConnectionError("Employee service unavailable")
        match = next((row for row in self.employees if row["employee_id"] == employee_id), None)
        return EmployeeProfile.model_validate(match) if match else None

    def get_travel_preapproval(self, trip_id: str) -> TravelPreapproval | None:
        if trip_id == "T_UNAVAILABLE":
            raise ConnectionError("Travel service unavailable")
        match = next((row for row in self.trips if row["trip_id"] == trip_id), None)
        return TravelPreapproval.model_validate(match) if match else None

    def get_cost_center_budget(self, cost_center: str) -> BudgetContext | None:
        match = next((row for row in self.budgets if row["cost_center"] == cost_center), None)
        return BudgetContext.model_validate(match) if match else None

    def get_exchange_rate(self, currency: str, expense_date: str) -> ExchangeRate | None:
        if currency.upper() == "INR":
            return ExchangeRate(currency="INR", date=expense_date, rate_to_inr=1.0)
        matches = [row for row in self.rates if row["currency"] == currency.upper()]
        if not matches:
            return None
        exact = next((row for row in matches if row["date"] == expense_date), None)
        if exact:
            return ExchangeRate.model_validate(exact)
        target = date.fromisoformat(expense_date)
        closest = min(matches, key=lambda row: abs((date.fromisoformat(row["date"]) - target).days))
        return ExchangeRate.model_validate(closest)

    def find_duplicate_claim(
        self, employee_id: str, merchant: str, amount: float, expense_date: str
    ) -> DuplicateResult:
        normalized = merchant.strip().lower()
        exact = next(
            (
                row
                for row in self.duplicates
                if row["employee_id"] == employee_id
                and row["merchant"].strip().lower() == normalized
                and abs(float(row["amount"]) - amount) <= 0.01
                and row["date"] == expense_date
            ),
            None,
        )
        split = next(
            (
                row
                for row in self.duplicates
                if row["employee_id"] == employee_id
                and row["merchant"].strip().lower() == normalized
                and row["date"] == expense_date
                and abs(float(row["amount"]) + amount - 1500) <= 100
            ),
            None,
        )
        if exact:
            return DuplicateResult(
                duplicate_found=True,
                matched_claim_id=exact["source_claim_id"],
                reason="Exact employee, merchant, amount, and date match",
            )
        if split:
            return DuplicateResult(
                duplicate_found=False,
                split_pattern=True,
                matched_claim_id=split["source_claim_id"],
                reason="Same-day merchant claims form a threshold-adjacent split",
            )
        return DuplicateResult(duplicate_found=False, reason="No matching historical claim")

    def record_final_decision(
        self,
        claim_id: str,
        decision: str,
        reviewer: str,
        override_reason: str | None,
        explicit_authorization: bool,
    ) -> FinalDecisionResult:
        result = self.repository.record_final_decision(
            claim_id, decision, reviewer, override_reason, explicit_authorization
        )
        return FinalDecisionResult.model_validate(result)


def evidence_call(
    tool_name: str,
    arguments: dict[str, Any],
    result: BaseModel | None = None,
    error: Exception | None = None,
) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result.model_dump(mode="json") if result else None,
        "error": str(error) if error else None,
        "called_at": datetime.now(timezone.utc).isoformat(),
    }
