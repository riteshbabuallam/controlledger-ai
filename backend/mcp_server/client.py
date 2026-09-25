from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client

from backend.database.repository import Repository
from backend.mcp_server.tools import EnterpriseTools


class MCPClientGateway:
    """Calls the enterprise server through MCP stdio transport in application runtime."""

    def __init__(
        self,
        repository: Repository,
        direct_tools: EnterpriseTools | None = None,
        transport: str | None = None,
    ):
        self.repository = repository
        self.direct_tools = direct_tools
        self.transport = transport or ("direct" if direct_tools else "stdio")

    def fetch_claim_context(self, claim: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        calls = [
            ("get_employee_profile", {"employee_id": claim.employee_id}),
            ("get_cost_center_budget", {"cost_center": claim.cost_center}),
            (
                "get_exchange_rate",
                {"currency": claim.currency, "expense_date": str(claim.expense_date)},
            ),
            (
                "find_duplicate_claim",
                {
                    "employee_id": claim.employee_id,
                    "merchant": claim.merchant,
                    "amount": claim.amount,
                    "expense_date": str(claim.expense_date),
                },
            ),
        ]
        if claim.trip_id:
            calls.insert(1, ("get_travel_preapproval", {"trip_id": claim.trip_id}))
        evidence = self.call_many(calls)
        keys = {
            "get_employee_profile": "employee",
            "get_travel_preapproval": "travel",
            "get_cost_center_budget": "budget",
            "get_exchange_rate": "exchange_rate",
            "find_duplicate_claim": "duplicate",
        }
        context = {keys[item["tool_name"]]: item["result"] for item in evidence}
        context.setdefault("travel", None)
        return context, evidence

    def record_final_decision(
        self,
        claim_id: str,
        decision: str,
        reviewer: str,
        override_reason: str | None,
        explicit_authorization: bool,
    ) -> dict[str, Any]:
        evidence = self.call_many(
            [
                (
                    "record_final_decision",
                    {
                        "claim_id": claim_id,
                        "decision": decision,
                        "reviewer": reviewer,
                        "override_reason": override_reason,
                        "explicit_authorization": explicit_authorization,
                    },
                )
            ]
        )[0]
        if evidence["error"]:
            if "authorization" in evidence["error"].lower():
                raise PermissionError(evidence["error"])
            raise RuntimeError(evidence["error"])
        return evidence["result"]

    def call_many(self, calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        if self.transport == "direct":
            return self._call_direct(calls)
        return anyio.run(self._call_stdio, calls)

    def _call_direct(self, calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        assert self.direct_tools is not None
        evidence = []
        for name, arguments in calls:
            try:
                result = getattr(self.direct_tools, name)(**arguments)
                value = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
                evidence.append(self._evidence(name, arguments, value, None))
            except Exception as exc:
                evidence.append(self._evidence(name, arguments, None, str(exc)))
        return evidence

    async def _call_stdio(self, calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        environment = os.environ.copy()
        environment["CONTROLLEDGER_DB_PATH"] = str(Path(self.repository.path).resolve())
        environment["CONTROLLEDGER_MCP_SERVER_TRANSPORT"] = "stdio"
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "backend.mcp_server.server"],
            env=environment,
        )
        evidence: list[dict[str, Any]] = []
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                listed = await session.list_tools()
                allowlist = {tool.name for tool in listed.tools}
                for name, arguments in calls:
                    if name not in allowlist:
                        evidence.append(
                            self._evidence(name, arguments, None, "Tool is not allowlisted")
                        )
                        continue
                    try:
                        response = await session.call_tool(name, arguments)
                        if response.isError:
                            message = self._text_content(response.content) or "MCP tool error"
                            evidence.append(self._evidence(name, arguments, None, message))
                            continue
                        value = response.structuredContent
                        if isinstance(value, dict) and set(value) == {"result"}:
                            value = value["result"]
                        if value is None:
                            raw = self._text_content(response.content)
                            value = json.loads(raw) if raw else None
                        evidence.append(self._evidence(name, arguments, value, None))
                    except Exception as exc:
                        evidence.append(self._evidence(name, arguments, None, str(exc)))
        return evidence

    @staticmethod
    def _text_content(content: list[Any]) -> str:
        return "".join(getattr(item, "text", "") for item in content)

    @staticmethod
    def _evidence(
        name: str,
        arguments: dict[str, Any],
        result: Any,
        error: str | None,
    ) -> dict[str, Any]:
        return {
            "tool_name": name,
            "arguments": arguments,
            "result": result,
            "error": error,
            "called_at": datetime.now(timezone.utc).isoformat(),
            "transport": "mcp",
        }
