"""Provider ports and shared value objects.

These Protocols are the contract the rest of the engine depends on. Adapters
(Ollama today, vLLM/others later) implement them; callers never see a backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ModelTier(StrEnum):
    """Capability tiers from the agent design (05-agents.md).

    On a constrained VM every tier may resolve to the same model; on a GPU
    host they differentiate. The mapping is configuration, not code.
    """

    REASONING = "reasoning"
    STANDARD = "standard"
    FAST = "fast"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class CompletionResult:
    text: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)


class ProviderError(RuntimeError):
    """Raised when a model backend fails after exhausting retries."""


@runtime_checkable
class ModelProvider(Protocol):
    """Text generation."""

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tier: ModelTier = ModelTier.STANDARD,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> CompletionResult: ...

    async def health(self) -> bool:
        """True if the backend is reachable and the tier models are present."""
        ...

    async def aclose(self) -> None:
        """Release the underlying transport."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Dense text embeddings."""

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def health(self) -> bool: ...

    async def aclose(self) -> None: ...
