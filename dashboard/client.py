from __future__ import annotations

import os
from typing import Any

import requests

API_URL = os.getenv("CONTROLLEDGER_API_URL", "http://localhost:8000").rstrip("/")


def request(method: str, path: str, **kwargs: Any) -> Any:
    response = requests.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
    if not response.ok:
        detail = (
            response.json().get("detail", response.text)
            if "application/json" in response.headers.get("content-type", "")
            else response.text
        )
        raise RuntimeError(f"{response.status_code}: {detail}")
    return response.json()


def api_online() -> bool:
    try:
        return request("GET", "/health").get("status") == "ok"
    except Exception:
        return False
