from __future__ import annotations

from backend.database.repository import Repository
from backend.graph.workflow import ControlLedgerWorkflow
from backend.mcp_server.client import MCPClientGateway
from backend.mcp_server.tools import EnterpriseTools
from backend.services.ai import AIService


class Container:
    def __init__(self, repository: Repository | None = None):
        self.repository = repository or Repository()
        self.tools = EnterpriseTools(repository=self.repository)
        self.ai = AIService()
        self.mcp_client = MCPClientGateway(self.repository)
        self.workflow = ControlLedgerWorkflow(
            repository=self.repository,
            mcp_client=self.mcp_client,
            ai_service=self.ai,
        )


container = Container()
