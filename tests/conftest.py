from __future__ import annotations

from pathlib import Path

import pytest

from backend.database.repository import Repository
from backend.graph.workflow import ControlLedgerWorkflow
from backend.mcp_server.tools import EnterpriseTools
from backend.services.ai import AIService


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "test.db")


@pytest.fixture
def tools(repository: Repository) -> EnterpriseTools:
    return EnterpriseTools(repository=repository)


@pytest.fixture
def workflow(repository: Repository, tools: EnterpriseTools) -> ControlLedgerWorkflow:
    return ControlLedgerWorkflow(
        repository=repository,
        tools=tools,
        ai_service=AIService(mode="offline"),
    )
