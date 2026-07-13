# DevMind Code Intelligence

Internal-only engine service: parsing, code graphs, retrieval, log
intelligence, and agent execution. See `docs/architecture/` at the repo root.

```bash
uv sync                                            # install
uv run uvicorn devmind_code_intel.main:app --reload --port 8000
uv run arq devmind_code_intel.worker.WorkerSettings  # background worker
uv run pytest                                      # tests
uv run ruff check src tests                        # lint
uv run mypy                                         # strict type check
```

## Local models (ADR-0008)

All inference is local via Ollama — no API keys. Pull the models the service
expects (the Compose `ollama-init` one-shot does this automatically):

```bash
ollama pull nomic-embed-text          # embeddings (768-dim)
ollama pull qwen2.5-coder:7b          # generation (:3b / :1.5b on CPU-only)
```

`GET /internal/v1/models` reports the configured models and whether each is
pulled and ready. Backend and model tags are configured via `CI_MODEL_BACKEND`,
`CI_LLM_MODEL`, and `CI_EMBED_MODEL` (see `.env.example`).
