from __future__ import annotations

import re
from pathlib import Path

from backend.models.decisions import PolicyClause

HEADING = re.compile(r"^## \[(?P<id>[^]]+)] (?P<title>.+)$", re.MULTILINE)
METADATA = {
    "Policy": "policy_name",
    "Version": "version",
    "Effective date": "effective_date",
    "Jurisdiction": "jurisdiction",
}


def load_policy_clauses(policy_dir: str | Path = "data/policies") -> list[PolicyClause]:
    clauses: list[PolicyClause] = []
    for path in sorted(Path(policy_dir).glob("*.md")):
        content = path.read_text(encoding="utf-8")
        metadata: dict[str, str] = {
            "policy_name": path.stem,
            "version": "1.0",
            "effective_date": "",
            "jurisdiction": "global",
        }
        for label, key in METADATA.items():
            match = re.search(rf"^{re.escape(label)}:\s*(.+)$", content, re.MULTILINE)
            if match:
                metadata[key] = match.group(1).strip()
        matches = list(HEADING.finditer(content))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            body = content[match.end() : end].strip()
            clause_id = match.group("id")
            clauses.append(
                PolicyClause(
                    clause_id=clause_id,
                    policy_name=metadata["policy_name"],
                    version=metadata["version"],
                    effective_date=metadata["effective_date"],
                    category=_category_for(clause_id),
                    jurisdiction=metadata["jurisdiction"],
                    text=f"{match.group('title')}: {body}",
                    score=0,
                )
            )
    return clauses


def _category_for(clause_id: str) -> str:
    prefix = clause_id.split("-", 1)[0]
    return {"MEALS": "meals", "TRAVEL": "travel", "EQUIP": "equipment"}.get(prefix, "general")
