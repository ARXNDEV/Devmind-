"""arq worker — executes the engine's background tasks.

Long-lived resources (DB pool, graph driver, pipeline, a pub/sub Redis client)
are created once at startup and shared via the task context.

Run with: uv run arq devmind_code_intel.worker.WorkerSettings
"""

from typing import Any

import redis.asyncio as aioredis
import structlog
from arq.connections import RedisSettings

from .config import get_settings
from .graph.neo4j_graph import Neo4jCodeGraph
from .indexing import IndexingPipeline
from .logging import configure_logging
from .models import build_embedding_provider
from .retrieval import QdrantVectorStore
from .store.db import Database
from .tasks import index_repository

logger = structlog.get_logger()


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.environment)
    db = await Database.connect(settings)
    await db.migrate()
    graph = Neo4jCodeGraph(settings)
    await graph.ensure_constraints()
    embedder = build_embedding_provider(settings)
    vectors = QdrantVectorStore(settings)
    await vectors.ensure_collection()
    ctx["db"] = db
    ctx["graph"] = graph
    ctx["embedder"] = embedder
    ctx["vectors"] = vectors
    ctx["pipeline"] = IndexingPipeline(
        db=db, graph=graph, settings=settings, embedder=embedder, vectors=vectors
    )
    ctx["redis_pub"] = aioredis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    logger.info("worker started")


async def shutdown(ctx: dict[str, Any]) -> None:
    if graph := ctx.get("graph"):
        await graph.close()
    if db := ctx.get("db"):
        await db.close()
    if embedder := ctx.get("embedder"):
        await embedder.aclose()
    if vectors := ctx.get("vectors"):
        await vectors.aclose()
    if pub := ctx.get("redis_pub"):
        await pub.aclose()
    logger.info("worker stopped")


async def ping(ctx: dict[str, Any], payload: str) -> str:
    """Queue-path smoke task."""
    logger.info("ping received", payload=payload)
    return f"pong:{payload}"


class WorkerSettings:
    functions = [ping, index_repository]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 1800  # large repos can take minutes
