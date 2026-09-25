from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analytics, claims, policies, simulations
from backend.container import container
from backend.models.claims import HealthResponse

app = FastAPI(
    title="ControlLedger API",
    version="1.0.0",
    description="Continuous expense controls and reproducible decision evidence.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(claims.router)
app.include_router(policies.router)
app.include_router(simulations.router)
app.include_router(analytics.router)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@app.get("/ready", response_model=HealthResponse, tags=["operations"])
def ready() -> HealthResponse:
    checks = {
        "database": container.repository.path.exists(),
        "policies": bool(container.workflow.nodes.retriever.clauses),
        "controls": len(container.workflow.nodes.controls.definitions) == 6,
        "workflow_nodes": len(container.workflow.node_names) == 12,
        "rag_backend": type(container.workflow.nodes.retriever).__name__,
        "ai_live": container.ai.live,
        "ai_provider": container.ai.provider,
        "llm_model": container.ai.model,
        "embedding_model": container.ai.embedding_model,
        "mcp_transport": container.workflow.nodes.mcp_client.transport,
    }
    core_ready = all(checks[key] for key in ["database", "policies", "controls", "workflow_nodes"])
    return HealthResponse(
        status="ready" if core_ready else "not_ready", version="1.0.0", checks=checks
    )
