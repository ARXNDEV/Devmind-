"""Ollama adapter — local, keyless inference (ADR-0008).

Wraps the Ollama HTTP API behind the ModelProvider/EmbeddingProvider ports.
Transient failures are retried with bounded backoff; a persistent failure
raises ProviderError so callers fail loudly rather than hang.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from ..config import Settings
from .base import (
    ChatMessage,
    CompletionResult,
    ModelTier,
    ProviderError,
    TokenUsage,
)

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE_S = 0.5


def _normalize_tag(name: str) -> str:
    """Ollama defaults an untagged name to ':latest'; normalize for matching."""
    return name if ":" in name else f"{name}:latest"


def _is_present(model: str, available: set[str]) -> bool:
    return _normalize_tag(model) in {_normalize_tag(a) for a in available}


class _OllamaHttp:
    """Shared HTTP plumbing: one client, uniform retry/error handling."""

    def __init__(self, base_url: str, *, timeout_s: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout_s
        )

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.post(path, json=payload)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
            except (httpx.HTTPError, httpx.TransportError) as exc:
                last_exc = exc
                # 4xx (except 429) are our fault — don't waste retries on them.
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and 400 <= exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    break
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE_S * 2 ** (attempt - 1))
                    logger.warning(
                        "ollama request retrying",
                        path=path,
                        attempt=attempt,
                        error=str(exc),
                    )
        raise ProviderError(f"Ollama request to {path} failed: {last_exc}")

    async def get(self, path: str) -> dict[str, Any]:
        response = await self._client.get(path)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    async def list_models(self) -> set[str]:
        data = await self.get("/api/tags")
        return {m["name"] for m in data.get("models", [])}

    async def aclose(self) -> None:
        await self._client.aclose()


class OllamaModelProvider:
    """Text generation via Ollama's /api/chat."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = _OllamaHttp(settings.ollama_url, timeout_s=300.0)

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tier: ModelTier = ModelTier.STANDARD,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        model = self._settings.model_for_tier(tier.value)
        options: dict[str, float | int] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": options,
        }
        data = await self._http.post("/api/chat", payload)
        return CompletionResult(
            text=data.get("message", {}).get("content", ""),
            model=model,
            usage=TokenUsage(
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
            ),
        )

    async def health(self) -> bool:
        try:
            available = await self._http.list_models()
        except (httpx.HTTPError, ProviderError):
            return False
        # Every configured tier must be pulled and ready.
        required = {self._settings.model_for_tier(t.value) for t in ModelTier}
        return all(_is_present(m, available) for m in required)

    async def aclose(self) -> None:
        await self._http.aclose()


class OllamaEmbeddingProvider:
    """Dense embeddings via Ollama's /api/embed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.embed_model
        self._dimension: int = settings.embed_dim
        self._http = _OllamaHttp(settings.ollama_url, timeout_s=120.0)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = await self._http.post(
            "/api/embed", {"model": self._model, "input": texts}
        )
        vectors: list[list[float]] = data.get("embeddings", [])
        if len(vectors) != len(texts):
            raise ProviderError(
                f"embedding count mismatch: got {len(vectors)} for {len(texts)} inputs"
            )
        # Guard the config invariant: a wrong CI_EMBED_DIM would silently
        # corrupt the vector store, so verify once against live output.
        if vectors and len(vectors[0]) != self._dimension:
            raise ProviderError(
                f"embedding dim mismatch: model returned {len(vectors[0])}, "
                f"CI_EMBED_DIM={self._dimension}"
            )
        return vectors

    async def health(self) -> bool:
        try:
            available = await self._http.list_models()
        except (httpx.HTTPError, ProviderError):
            return False
        return _is_present(self._model, available)

    async def aclose(self) -> None:
        await self._http.aclose()
