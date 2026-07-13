# ADR-0008: Local model serving (Ollama), no external API keys

**Status:** Accepted · 2026-07-09 · supersedes the "Anthropic first" default noted in [05-agents](../architecture/05-agents.md)

## Context

Deployment target is an enterprise VM with no outbound model API access and no API keys. Customer source code must not leave the customer network — a common hard requirement in legacy-enterprise procurement. The original plan defaulted the `ModelProvider`/`EmbeddingProvider` ports to a hosted API; the ports stay, the default backend changes.

## Decision

- **Serving backend: Ollama**, self-hosted as a Compose service. Zero API keys, OpenAI-ish local HTTP API, GPU auto-detected, CPU fallback. Selected over vLLM (heavier, GPU-oriented) and llama.cpp-direct (lower-level) for operational simplicity on a single VM; `CI_MODEL_BACKEND` leaves room for a `vllm` adapter later.
- **Generation model: `qwen2.5-coder`** — default tag `7b`, configurable down to `3b`/`1.5b` for CPU-only hosts. Strong code reasoning at small sizes.
- **Embedding model: `nomic-embed-text`** (768-dim) on the same server — one serving stack to operate.
- **Model tiers** (REASONING/STANDARD/FAST from the agent design) map to configurable model tags; on a constrained VM they may all point at one model. The tier abstraction stays so a GPU host can differentiate without code change.
- All access remains behind `ModelProvider` and `EmbeddingProvider` ports. No provider SDK is imported outside its adapter.

## Consequences

- **Data never leaves the network** — a selling point, and it removes the API-key attack surface entirely.
- Quality/latency are bounded by local hardware. The tier→model map and Qdrant embedding dimension are config, so upgrading models (or moving to GPU/vLLM) is a settings change plus a re-index, not a code change.
- Embedding dimension is now a deployment decision fixed at first index (`CI_EMBED_DIM`); changing the embedding model later requires re-indexing. Documented as an operational constraint.
- Ollama adds one stateful-ish service (model volume). Models are a rebuildable cache (re-pull), not precious data — no backup burden.
