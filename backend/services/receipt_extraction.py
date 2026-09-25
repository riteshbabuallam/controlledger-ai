from __future__ import annotations

import re
from datetime import date

from backend.models.claims import ClaimSubmission, ExtractedReceipt

INSTRUCTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore (all|any|the) (previous|prior|system) instructions",
        r"system prompt",
        r"call (the )?tool",
        r"approve this claim",
        r"bypass (the )?(policy|control|review)",
    ]
]


def contains_untrusted_instructions(text: str | None) -> bool:
    return bool(text and any(pattern.search(text) for pattern in INSTRUCTION_PATTERNS))


def extract_receipt(claim: ClaimSubmission) -> ExtractedReceipt:
    if claim.receipt_total is not None:
        confidence = min(claim.receipt_quality, 0.99)
        return ExtractedReceipt(
            merchant=claim.merchant,
            expense_date=claim.expense_date,
            total=claim.receipt_total,
            currency=claim.receipt_currency or claim.currency,
            category=claim.category,
            confidence=confidence,
            source="structured",
        )
    text = claim.receipt_text or ""
    amount = re.search(
        r"(?:total|amount)\s*[:=]\s*(?:[A-Z]{3}\s*)?([0-9]+(?:\.[0-9]{1,2})?)", text, re.IGNORECASE
    )
    currency = re.search(r"\b(INR|USD|EUR|GBP|SGD)\b", text.upper())
    parsed_date = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if amount:
        return ExtractedReceipt(
            merchant=claim.merchant,
            expense_date=date.fromisoformat(parsed_date.group(1))
            if parsed_date
            else claim.expense_date,
            total=float(amount.group(1)),
            currency=currency.group(1) if currency else claim.currency,
            category=claim.category,
            confidence=min(claim.receipt_quality, 0.86),
            source="text",
        )
    return ExtractedReceipt(
        merchant=claim.merchant,
        expense_date=claim.expense_date,
        total=None,
        currency=None,
        category=claim.category,
        confidence=0.15 * claim.receipt_quality,
        source="unavailable",
    )
