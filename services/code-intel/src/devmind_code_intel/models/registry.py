"""Provider factories — the single place that maps backend config to an adapter.

Adding a backend (e.g. vLLM) means adding a branch here and an adapter module;
no caller changes.
"""

from __future__ import annotations

from ..config import Settings, get_settings
from .base import EmbeddingProvider, ModelProvider
from .ollama import OllamaEmbeddingProvider, OllamaModelProvider


def build_model_provider(settings: Settings | None = None) -> ModelProvider:
    settings = settings or get_settings()
    if settings.model_backend == "ollama":
        return OllamaModelProvider(settings)
    raise ValueError(f"Unsupported CI_MODEL_BACKEND: {settings.model_backend!r}")


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.model_backend == "ollama":
        return OllamaEmbeddingProvider(settings)
    raise ValueError(f"Unsupported CI_MODEL_BACKEND: {settings.model_backend!r}")
