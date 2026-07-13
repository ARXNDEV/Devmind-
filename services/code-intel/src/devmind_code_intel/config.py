"""Configuration — env-only, validated at import of the settings object.

Mirrors apps/api's fail-fast rule: a missing variable stops the process,
it never limps along on production-unsafe defaults.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # protected_namespaces=() lets us keep the documented CI_MODEL_* env names
    # without pydantic's "model_" namespace warning.
    model_config = SettingsConfigDict(
        env_prefix="CI_", frozen=True, protected_namespaces=()
    )

    environment: str = Field(default="development", alias="NODE_ENV")
    port: int = Field(default=8000, ge=1, le=65535)

    database_url: SecretStr
    redis_url: str
    qdrant_url: str
    neo4j_url: str
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_bucket_snapshots: str = "devmind-snapshots"
    s3_bucket_artifacts: str = "devmind-artifacts"

    # Shared secret for the api <-> code-intel internal plane (07-api-contracts).
    internal_service_token: SecretStr
    api_base_url: str = Field(alias="API_BASE_URL")

    # ── Local model serving (ADR-0008): self-hosted, no API keys ──────────────
    model_backend: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    # Default generation model; tier-specific overrides fall back to this when
    # unset, so a constrained VM can run everything on one small model.
    llm_model: str = "qwen2.5-coder:7b"
    llm_model_reasoning: str | None = None
    llm_model_fast: str | None = None
    # Embedding model + vector dimension. The dimension is fixed at first index;
    # changing the embedding model later requires a re-index (ADR-0008).
    embed_model: str = "nomic-embed-text"
    embed_dim: int = Field(default=768, gt=0)

    def model_for_tier(self, tier: str) -> str:
        """Resolve a model tier (reasoning|standard|fast) to a concrete tag."""
        if tier == "reasoning":
            return self.llm_model_reasoning or self.llm_model
        if tier == "fast":
            return self.llm_model_fast or self.llm_model
        return self.llm_model


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # populated from env
