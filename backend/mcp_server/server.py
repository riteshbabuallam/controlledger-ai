from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from backend.mcp_server.tools import EnterpriseTools

mcp = FastMCP("enterprise_context_server")
tools = EnterpriseTools()


@mcp.tool()
def get_employee_profile(employee_id: str) -> dict | None:
    """Return the employee profile required for expense-control evaluation."""
    result = tools.get_employee_profile(employee_id)
    return result.model_dump(mode="json") if result else None


@mcp.tool()
def get_travel_preapproval(trip_id: str) -> dict | None:
    """Return the approved trip record for a travel expense."""
    result = tools.get_travel_preapproval(trip_id)
    return result.model_dump(mode="json") if result else None


@mcp.tool()
def get_cost_center_budget(cost_center: str) -> dict | None:
    """Return budget availability for a cost center."""
    result = tools.get_cost_center_budget(cost_center)
    return result.model_dump(mode="json") if result else None


@mcp.tool()
def get_exchange_rate(currency: str, expense_date: str) -> dict | None:
    """Return the corporate currency rate applicable on an expense date."""
    result = tools.get_exchange_rate(currency, expense_date)
    return result.model_dump(mode="json") if result else None


@mcp.tool()
def find_duplicate_claim(employee_id: str, merchant: str, amount: float, expense_date: str) -> dict:
    """Find exact duplicate or threshold-splitting patterns."""
    return tools.find_duplicate_claim(employee_id, merchant, amount, expense_date).model_dump(
        mode="json"
    )


@mcp.tool()
def record_final_decision(
    claim_id: str,
    decision: str,
    reviewer: str,
    override_reason: str | None,
    explicit_authorization: bool,
) -> dict:
    """Record one final decision only after explicit human authorization."""
    return tools.record_final_decision(
        claim_id, decision, reviewer, override_reason, explicit_authorization
    ).model_dump(mode="json")


if __name__ == "__main__":
    mcp.run(transport=os.getenv("CONTROLLEDGER_MCP_SERVER_TRANSPORT", "stdio"))
