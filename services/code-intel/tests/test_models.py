"""Model provider tests.

Unit tests mock the Ollama HTTP surface so they run anywhere. The live test
exercises real embeddings and self-skips when the model server or model is
unavailable, so CI without Ollama stays green while local runs get real proof.
"""

import httpx
import pytest

from devmind_code_intel.config import Settings, get_settings
from devmind_code_intel.models import (
    ChatMessage,
    ModelTier,
    build_embedding_provider,
    build_model_provider,
)
from devmind_code_intel.models.base import ProviderError
from devmind_code_intel.models.ollama import OllamaEmbeddingProvider


def _settings(**overrides) -> Settings:
    base = get_settings()
    return base.model_copy(update=overrides)


def _mock_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _install(provider, handler) -> None:
    """Swap the adapter's httpx client for one backed by a mock transport."""
    provider._http._client = httpx.AsyncClient(
        base_url=provider._http._base_url, transport=_mock_transport(handler)
    )


def test_tier_resolution_falls_back_to_default() -> None:
    s = _settings(
        llm_model="qwen2.5-coder:7b",
        llm_model_fast="qwen2.5-coder:1.5b",
        llm_model_reasoning=None,
    )
    assert s.model_for_tier("fast") == "qwen2.5-coder:1.5b"
    assert s.model_for_tier("reasoning") == "qwen2.5-coder:7b"
    assert s.model_for_tier("standard") == "qwen2.5-coder:7b"


async def test_chat_parses_response_and_usage() -> None:
    provider = build_model_provider(_settings())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "hello world"},
                "prompt_eval_count": 11,
                "eval_count": 3,
            },
        )

    _install(provider, handler)
    result = await provider.chat(
        [ChatMessage(role="user", content="hi")], tier=ModelTier.FAST
    )
    assert result.text == "hello world"
    assert result.usage.total_tokens == 14
    await provider.aclose()


async def test_chat_retries_then_raises_provider_error() -> None:
    provider = build_model_provider(_settings())
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"error": "loading"})

    _install(provider, handler)
    with pytest.raises(ProviderError):
        await provider.chat([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 3  # retried up to the cap
    await provider.aclose()


async def test_embed_validates_dimension() -> None:
    provider = OllamaEmbeddingProvider(_settings(embed_dim=768))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[0.1] * 4]})  # wrong dim

    _install(provider, handler)
    with pytest.raises(ProviderError, match="dim mismatch"):
        await provider.embed(["text"])
    await provider.aclose()


async def test_embed_empty_input_short_circuits() -> None:
    provider = build_embedding_provider(_settings())
    assert await provider.embed([]) == []
    await provider.aclose()


@pytest.mark.asyncio
async def test_live_embedding_when_available() -> None:
    """Real embedding round-trip; skips cleanly if Ollama/model absent."""
    provider = build_embedding_provider()
    try:
        if not await provider.health():
            pytest.skip("Ollama embedding model not available")
        vectors = await provider.embed(["def add(a, b): return a + b"])
        assert len(vectors) == 1
        assert len(vectors[0]) == provider.dimension
    finally:
        await provider.aclose()
