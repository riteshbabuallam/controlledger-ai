from __future__ import annotations

from backend.controls.engine import ControlEngine
from backend.models.claims import ClaimSubmission
from backend.services.receipt_extraction import extract_receipt


def claim(**updates) -> ClaimSubmission:
    values = {
        "employee_id": "E001",
        "merchant": "Green Table",
        "expense_date": "2026-09-21",
        "amount": 1000,
        "currency": "INR",
        "category": "meals",
        "cost_center": "CC100",
        "receipt_total": 1000,
    }
    values.update(updates)
    return ClaimSubmission.model_validate(values)


def context(**updates):
    values = {
        "travel": None,
        "exchange_rate": {"rate_to_inr": 1},
        "duplicate": {"duplicate_found": False, "split_pattern": False},
    }
    values.update(updates)
    return values


def result_for(control_id: str, item: ClaimSubmission, ctx: dict):
    results = ControlEngine().evaluate(item, extract_receipt(item), ctx)
    assert len(results) == 6
    return next(result for result in results if result.control_id == control_id)


def test_amount_match_control_fails_mismatch():
    item = claim(amount=1200, receipt_total=1000)
    assert result_for("AMOUNT_MATCH_001", item, context()).status == "fail"


def test_category_allowance_routes_review():
    item = claim(amount=2000, receipt_total=2000)
    assert result_for("ALLOWANCE_002", item, context()).status == "review"


def test_duplicate_control_rejects_match():
    duplicate = {"duplicate_found": True, "split_pattern": False, "matched_claim_id": "OLD-1"}
    assert result_for("DUPLICATE_003", claim(), context(duplicate=duplicate)).status == "fail"


def test_preapproval_control_rejects_unapproved_trip():
    item = claim(trip_id="T102")
    trip = {
        "trip_id": "T102",
        "employee_id": "E001",
        "approved": False,
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
    }
    assert result_for("PREAPPROVAL_004", item, context(travel=trip)).status == "fail"


def test_travel_date_control_rejects_outside_window():
    item = claim(trip_id="T100", expense_date="2026-09-29")
    trip = {
        "trip_id": "T100",
        "employee_id": "E001",
        "approved": True,
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
    }
    assert result_for("TRAVEL_DATES_005", item, context(travel=trip)).status == "fail"


def test_fx_variance_routes_review():
    item = claim(currency="USD", amount=15, receipt_total=15, fx_rate_used=90)
    assert (
        result_for("FX_VARIANCE_006", item, context(exchange_rate={"rate_to_inr": 83.75})).status
        == "review"
    )
