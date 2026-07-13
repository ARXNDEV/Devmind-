"""arq tasks — the background work the engine performs.

Each task publishes progress to Redis pub/sub (`events:job:{job_id}`) for the
UI and posts a durable status callback to the api on completion.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog

from .api_client import ApiCallbackClient
from .config import get_settings
from .indexing import IndexingPipeline, IndexRequest

logger = structlog.get_logger(__name__)


async def _publish(
    ctx: dict[str, Any], job_id: str, event_type: str, data: dict[str, Any]
) -> None:
    redis = ctx.get("redis_pub")
    if redis is None:
        return
    try:
        await redis.publish(
            f"events:job:{job_id}",
            json.dumps({"type": event_type, "data": data}),
        )
    except Exception:  # noqa: BLE001 - progress is best-effort
        logger.debug("progress publish failed", job_id=job_id)


async def index_repository(
    ctx: dict[str, Any],
    *,
    job_id: str,
    repo_id: str,
    org_id: str,
    source: str,
    ref: str | None = None,
    token: str | None = None,
    mode: str = "auto",
) -> dict[str, Any]:
    """Run an index pipeline and report status back to the api."""
    settings = get_settings()
    callback = ApiCallbackClient(settings)
    pipeline: IndexingPipeline = ctx["pipeline"]

    await _publish(ctx, job_id, "job.progress", {"stage": "started"})
    try:
        result = await pipeline.run(
            IndexRequest(
                repo_id=UUID(repo_id),
                org_id=UUID(org_id),
                source=source,
                ref=ref,
                token=token,
                mode=mode,
            )
        )
        payload = {
            "runId": str(result.run_id),
            "mode": result.mode,
            "commitSha": result.commit_sha,
            "filesIndexed": result.files_indexed,
            "filesDeleted": result.files_deleted,
            "stats": result.stats,
        }
        await _publish(ctx, job_id, "job.progress", {"stage": "finished", **payload})
        await callback.job_status(job_id=job_id, status="succeeded", result=payload)
        return payload
    except Exception as exc:
        error = {"message": str(exc)}
        await _publish(ctx, job_id, "job.failed", error)
        await callback.job_status(job_id=job_id, status="failed", error=error)
        raise
