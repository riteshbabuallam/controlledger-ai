from __future__ import annotations

import json
from pathlib import Path

from backend.container import container
from backend.models.claims import ClaimSubmission


def main() -> None:
    claims = json.loads(Path("data/synthetic_claims/claims.json").read_text(encoding="utf-8"))
    completed = 0
    skipped = 0
    for item in claims:
        claim_id = item["claim_id"]
        if container.repository.get_claim(claim_id):
            skipped += 1
            continue
        submission = ClaimSubmission.model_validate(item["submission"])
        container.repository.create_claim(claim_id, submission.model_dump(mode="json"))
        container.workflow.run(claim_id, submission)
        completed += 1
    print(f"Seeded {completed} claims; skipped {skipped} existing claims.")


if __name__ == "__main__":
    main()
