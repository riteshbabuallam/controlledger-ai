from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.database.models import SCHEMA


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, path: str | Path | None = None):
        configured = path or os.getenv("CONTROLLEDGER_DB_PATH", "data/controlledger.db")
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    def create_claim(self, claim_id: str, submission: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO claims (claim_id, submission_json, submitted_at, status) VALUES (?, ?, ?, ?)",
                (claim_id, json.dumps(submission, default=str), utc_now(), "submitted"),
            )
        self.add_event(claim_id, "claim_submitted", {"claim_id": claim_id})

    def update_claim(self, claim_id: str, **fields: Any) -> None:
        allowed = {
            "status",
            "recommendation",
            "risk_score",
            "review_status",
            "final_decision",
            "reviewer",
            "override_reason",
            "reviewed_at",
            "state_json",
            "passport_json",
        }
        clean = {key: value for key, value in fields.items() if key in allowed}
        if not clean:
            return
        assignments = ", ".join(f"{key} = ?" for key in clean)
        values = [
            json.dumps(value, default=str)
            if key.endswith("_json") and not isinstance(value, str)
            else value
            for key, value in clean.items()
        ]
        with self.connection() as connection:
            connection.execute(
                f"UPDATE claims SET {assignments} WHERE claim_id = ?",  # noqa: S608 - allowlisted columns
                (*values, claim_id),
            )

    def get_claim(self, claim_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        return self._claim_row(row) if row else None

    def list_claims(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM claims ORDER BY submitted_at DESC").fetchall()
        return [self._claim_row(row) for row in rows]

    def _claim_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["submission"] = json.loads(item.pop("submission_json"))
        item["state"] = json.loads(item.pop("state_json")) if item.get("state_json") else None
        item["passport"] = (
            json.loads(item.pop("passport_json")) if item.get("passport_json") else None
        )
        return item

    def add_event(self, claim_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO audit_events (claim_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (claim_id, event_type, json.dumps(payload, default=str), utc_now()),
            )

    def events_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT event_type, payload_json, created_at FROM audit_events WHERE claim_id = ? ORDER BY event_id",
                (claim_id,),
            ).fetchall()
        return [
            {
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def record_final_decision(
        self,
        claim_id: str,
        decision: str,
        reviewer: str,
        override_reason: str | None,
        authorized: bool,
    ) -> dict[str, Any]:
        if not authorized:
            raise PermissionError("Explicit human authorization is required for the write action")
        timestamp = utc_now()
        with self.connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO final_decisions VALUES (?, ?, ?, ?, ?, ?)",
                (claim_id, decision, reviewer, override_reason, 1, timestamp),
            )
        self.update_claim(
            claim_id,
            status="complete",
            review_status="completed",
            final_decision=decision,
            reviewer=reviewer,
            override_reason=override_reason,
            reviewed_at=timestamp,
        )
        self.add_event(
            claim_id, "human_authorized_write", {"decision": decision, "reviewer": reviewer}
        )
        return {
            "claim_id": claim_id,
            "decision": decision,
            "reviewer": reviewer,
            "recorded_at": timestamp,
        }

    def create_policy(self, policy_id: str, data: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO policies
                (policy_id, name, version, effective_date, category, jurisdiction, content, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    policy_id,
                    data["name"],
                    data["version"],
                    str(data["effective_date"]),
                    data["category"],
                    data["jurisdiction"],
                    data["content"],
                    utc_now(),
                ),
            )

    def list_policies(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM policies ORDER BY created_at DESC"
                ).fetchall()
            ]

    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM policies WHERE policy_id = ?", (policy_id,)
            ).fetchone()
        return dict(row) if row else None

    def activate_policy(self, policy_id: str) -> bool:
        with self.connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM policies WHERE policy_id = ?", (policy_id,)
            ).fetchone()
            if not exists:
                return False
            connection.execute("UPDATE policies SET active = 0")
            connection.execute("UPDATE policies SET active = 1 WHERE policy_id = ?", (policy_id,))
        return True

    def save_simulation(
        self, simulation_id: str, request: dict[str, Any], result: dict[str, Any]
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO simulations VALUES (?, ?, ?, ?)",
                (simulation_id, json.dumps(request), json.dumps(result), utc_now()),
            )

    def get_simulation(self, simulation_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM simulations WHERE simulation_id = ?", (simulation_id,)
            ).fetchone()
        if not row:
            return None
        return {
            **dict(row),
            "request": json.loads(row["request_json"]),
            "result": json.loads(row["result_json"]),
        }

    def append_passport_revision(self, claim_id: str, passport: dict[str, Any], reason: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(revision), 0) AS revision FROM passport_revisions WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
            revision = int(row["revision"]) + 1
            passport = {**passport, "revision": revision}
            connection.execute(
                "INSERT INTO passport_revisions VALUES (?, ?, ?, ?, ?)",
                (claim_id, revision, json.dumps(passport, default=str), reason, utc_now()),
            )
        self.update_claim(claim_id, passport_json=passport)
        return revision

    def passport_revisions(self, claim_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT revision, passport_json, reason, created_at FROM passport_revisions WHERE claim_id = ? ORDER BY revision",
                (claim_id,),
            ).fetchall()
        return [
            {
                "revision": row["revision"],
                "passport": json.loads(row["passport_json"]),
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_control_draft(self, draft_id: str, policy_id: str, draft: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO control_drafts VALUES (?, ?, ?, 'draft', NULL, ?, NULL)",
                (draft_id, policy_id, json.dumps(draft, default=str), utc_now()),
            )

    def get_control_draft(self, draft_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM control_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["draft"] = json.loads(item.pop("draft_json"))
        return item

    def approve_control_draft(
        self, draft_id: str, reviewer: str, explicit_authorization: bool
    ) -> bool:
        if not explicit_authorization:
            raise PermissionError("Explicit policy-owner authorization is required")
        with self.connection() as connection:
            updated = connection.execute(
                "UPDATE control_drafts SET status = 'approved', reviewer = ?, approved_at = ? WHERE draft_id = ? AND status = 'draft'",
                (reviewer, utc_now(), draft_id),
            ).rowcount
        if updated:
            self.add_event(
                None, "policy_control_draft_approved", {"draft_id": draft_id, "reviewer": reviewer}
            )
        return bool(updated)
