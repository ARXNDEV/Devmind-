"""Liveness and readiness probes.

readyz verifies every data-store dependency with a short timeout so
orchestrators gate traffic on real availability, not process liveness.
"""

import asyncio
from typing import Any

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Response
from neo4j import AsyncGraphDatabase

from .config import get_settings

router = APIRouter()

_CHECK_TIMEOUT_S = 3.0


async def _check_postgres() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(
        settings.database_url.get_secret_value(), timeout=_CHECK_TIMEOUT_S
    )
    try:
        await conn.fetchval("SELECT 1")
    finally:
        await conn.close()


async def _check_redis() -> None:
    # redis.asyncio.from_url is untyped in the shipped stubs.
    client = aioredis.from_url(get_settings().redis_url)  # type: ignore[no-untyped-call]
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _check_qdrant() -> None:
    async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S) as client:
        response = await client.get(f"{get_settings().qdrant_url}/readyz")
        response.raise_for_status()


async def _check_neo4j() -> None:
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_url,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    try:
        await driver.verify_connectivity()
    finally:
        await driver.close()


async def _check_minio() -> None:
    async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S) as client:
        response = await client.get(
            f"{get_settings().s3_endpoint}/minio/health/live"
        )
        response.raise_for_status()


async def _check_ollama() -> None:
    # Reachability only — model-presence is reported separately so a pending
    # `ollama pull` degrades gracefully instead of failing readiness outright.
    async with httpx.AsyncClient(timeout=_CHECK_TIMEOUT_S) as client:
        response = await client.get(f"{get_settings().ollama_url}/api/tags")
        response.raise_for_status()


_CHECKS = {
    "postgres": _check_postgres,
    "redis": _check_redis,
    "qdrant": _check_qdrant,
    "neo4j": _check_neo4j,
    "minio": _check_minio,
    "ollama": _check_ollama,
}


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    results: dict[str, str] = {}

    async def run(name: str) -> None:
        try:
            async with asyncio.timeout(_CHECK_TIMEOUT_S + 1):
                await _CHECKS[name]()
            results[name] = "ok"
        except Exception:
            results[name] = "unreachable"

    await asyncio.gather(*(run(name) for name in _CHECKS))

    healthy = all(v == "ok" for v in results.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", "checks": results}
