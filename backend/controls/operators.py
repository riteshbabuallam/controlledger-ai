from __future__ import annotations

from datetime import date, timedelta


def within_tolerance(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def within_date_window(value: date, start: date, end: date, grace_days: int = 0) -> bool:
    return start - timedelta(days=grace_days) <= value <= end + timedelta(days=grace_days)


def variance_percent(actual: float, expected: float) -> float:
    if expected == 0:
        return 0 if actual == 0 else 100
    return abs(actual - expected) / expected * 100
