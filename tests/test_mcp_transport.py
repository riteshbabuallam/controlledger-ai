from __future__ import annotations

from backend.mcp_server.client import MCPClientGateway


def test_stdio_mcp_transport_calls_registered_server(repository):
    gateway = MCPClientGateway(repository)
    result = gateway.call_many([("get_employee_profile", {"employee_id": "E001"})])[0]
    assert result["error"] is None
    assert result["result"]["department"] == "Consulting"
    assert result["transport"] == "mcp"
