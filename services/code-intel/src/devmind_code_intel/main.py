"""FastAPI application factory for the code-intelligence engine."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request
from pydantic import BaseModel

from . import __version__
from .config import get_settings
from .graph.neo4j_graph import Neo4jCodeGraph
from .health import router as health_router
from .logging import configure_logging
from .middleware import InternalAuthMiddleware
from .models import build_embedding_provider, build_model_provider


class IndexRunRequest(BaseModel):
    """Command from the api to start an index run (07-api-contracts.md)."""

    jobId: str  # noqa: N815 - matches the JSON contract with the api
    repoId: str  # noqa: N815
    orgId: str  # noqa: N815
    source: str
    ref: str | None = None
    token: str | None = None
    mode: str = "auto"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.environment)
    # Pool used to enqueue background work onto the worker's queue.
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    # Shared read-only graph driver for query endpoints.
    app.state.graph = Neo4jCodeGraph(settings)
    structlog.get_logger().info(
        "code-intel starting", version=__version__, environment=settings.environment
    )
    yield
    await app.state.arq.aclose()
    await app.state.graph.close()
    structlog.get_logger().info("code-intel stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DevMind Code Intelligence",
        version=__version__,
        # Internal service: interactive docs stay off outside development.
        docs_url="/docs" if get_settings().environment == "development" else None,
        redoc_url=None,
        openapi_url="/openapi.json"
        if get_settings().environment == "development"
        else None,
        lifespan=lifespan,
    )
    app.add_middleware(InternalAuthMiddleware)
    app.include_router(health_router)

    @app.get("/internal/v1/info")
    async def info() -> dict[str, str]:
        """Contract smoke endpoint."""
        return {"service": "code-intel", "version": __version__}

    @app.post("/internal/v1/index-runs", status_code=202)
    async def index_runs(body: IndexRunRequest, request: Request) -> dict[str, str]:
        """Enqueue an index run; returns the queue task id immediately.

        The api tracks status via the `jobId` it supplied (its Job row is the
        source of truth); the returned taskId lets it reconcile if a callback
        is lost.
        """
        job = await request.app.state.arq.enqueue_job(
            "index_repository",
            job_id=body.jobId,
            repo_id=body.repoId,
            org_id=body.orgId,
            source=body.source,
            ref=body.ref,
            token=body.token,
            mode=body.mode,
        )
        return {"taskId": job.job_id if job else ""}

    @app.get("/internal/v1/graph/neighborhood")
    async def graph_neighborhood(
        request: Request,
        repoId: str,  # noqa: N803 - matches the JSON contract
        fqn: str,
        path: str,
        depth: int = 2,
    ) -> dict[str, object]:
        result: dict[str, object] = await request.app.state.graph.neighborhood(
            repoId, (fqn, path), depth
        )
        return result

    @app.get("/internal/v1/repositories/{repo_id}/tree")
    async def repo_tree(repo_id: str, request: Request) -> dict[str, object]:
        files = await request.app.state.graph.list_files(repo_id)
        return {"files": files}

    @app.get("/internal/v1/repositories/{repo_id}/symbols")
    async def repo_symbols(
        repo_id: str, path: str, request: Request
    ) -> dict[str, object]:
        symbols = await request.app.state.graph.file_symbols(repo_id, path)
        return {"path": path, "symbols": symbols}

    @app.get("/internal/v1/graph/impact")
    async def graph_impact(
        request: Request,
        repoId: str,  # noqa: N803
        fqn: str,
        path: str,
        depth: int = 3,
    ) -> dict[str, object]:
        result: dict[str, object] = await request.app.state.graph.impact_analysis(
            repoId, (fqn, path), depth
        )
        return result

    @app.get("/internal/v1/models")
    async def models() -> dict[str, object]:
        """Reports the configured local models and whether they are pulled.

        Lets the API surface model-readiness to operators without exposing the
        model server, and confirms the no-API-key local backend end to end.
        """
        settings = get_settings()
        llm = build_model_provider(settings)
        embed = build_embedding_provider(settings)
        try:
            return {
                "backend": settings.model_backend,
                "generation": {
                    "reasoning": settings.model_for_tier("reasoning"),
                    "standard": settings.model_for_tier("standard"),
                    "fast": settings.model_for_tier("fast"),
                    "ready": await llm.health(),
                },
                "embedding": {
                    "model": settings.embed_model,
                    "dimension": embed.dimension,
                    "ready": await embed.health(),
                },
            }
        finally:
            await llm.aclose()
            await embed.aclose()

    return app


app = create_app()
