"""Outbound client to the api service (code-intel → api callbacks).

Callbacks are the durable record of async work; Redis pub/sub carries
best-effort progress for the UI. Every callback is authenticated with the
shared internal service token (07-api-contracts.md).
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class ApiCallbackClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.api_base_url.rstrip("/")
        self._token = settings.internal_service_token.get_secret_value()

    async def job_status(
        self,
        *,
        job_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        payload = {"jobId": job_id, "status": status,
                   "result": result, "error": error}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._base_url}/internal/v1/callbacks/job-status",
                    json=payload,
                    headers={"x-internal-token": self._token},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            # The api watchdog re-polls task status, so a dropped callback
            # degrades to eventual consistency rather than a stuck job.
            logger.warning("job-status callback failed", job_id=job_id, exc_info=True)
