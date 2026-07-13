"""Model-serving layer.

All LLM and embedding access goes through the ports defined in `base`; the
only backend-specific code lives in the adapters (e.g. `ollama`). Nothing
elsewhere in the service imports a provider SDK directly (ADR-0008).
"""

from .base import (
    ChatMessage,
    CompletionResult,
    EmbeddingProvider,
    ModelProvider,
    ModelTier,
)
from .registry import build_embedding_provider, build_model_provider

__all__ = [
    "ChatMessage",
    "CompletionResult",
    "EmbeddingProvider",
    "ModelProvider",
    "ModelTier",
    "build_embedding_provider",
    "build_model_provider",
]
