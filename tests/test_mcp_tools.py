from __future__ import annotations

import pytest


def test_all_five_read_tools_return_typed_context(tools):
    assert tools.get_employee_profile("E001").employee_id == "E001"
    assert tools.get_travel_preapproval("T100").approved is True
    assert tools.get_cost_center_budget("CC100").available == 290000
    assert tools.get_exchange_rate("USD", "2026-09-21").rate_to_inr == 83.75
    assert (
        tools.find_duplicate_claim("E001", "Metro Bistro", 1250, "2026-09-21").duplicate_found
        is True
    )


def test_write_tool_requires_explicit_human_authorization(repository, tools):
    repository.create_claim("CLM-X", {"employee_id": "E001"})
    with pytest.raises(PermissionError):
        tools.record_final_decision("CLM-X", "approved", "Reviewer", None, False)
    result = tools.record_final_decision("CLM-X", "approved", "Reviewer", None, True)
    assert result.decision == "approved"


def test_policy_control_drafts_require_human_approval(repository):
    repository.save_control_draft(
        "DRF-1", "POL-1", {"controls": [{"id": "LIMIT"}], "confidence": 0.9}
    )
    with pytest.raises(PermissionError):
        repository.approve_control_draft("DRF-1", "Owner", False)
    assert repository.approve_control_draft("DRF-1", "Owner", True)
    assert repository.get_control_draft("DRF-1")["status"] == "approved"
