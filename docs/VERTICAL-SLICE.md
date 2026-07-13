# Vertical Slice — shortest path to the first real Q&A demo

Goal: a real repository, a real question, a correct answer with file:line
citations — as early as possible. Everything here reuses the existing
architecture; it only reorders the roadmap (pulls the core of Phase 3
forward, defers the rest).

## Where the code stands (audited 2026-07-13)

Working today:
- Indexing pipeline end-to-end: acquire -> snapshot -> parse -> Neo4j graph,
  with incremental mode. Extractors for Python, TypeScript/JS, Java, Go.
- Job pattern (api jobs module + arq worker + progress publish).
- Product shell: identity, projects, repositories, audit modules; web login,
  dashboard, projects, repository pages. Full compose stack healthy.
- Proof it runs: Neo4j holds 405 Symbols / 78 Modules / 33 Files from a
  test index run.

Missing for the slice:
- Chunking + embeddings (Qdrant has zero collections).
- Any retrieval endpoint, any ask/answer endpoint, any chat UI.
- Only Ollama model provider implemented — no frontier-model provider yet.

## Step 1 — Symbol-aware chunking + embeddings (services/code-intel)
- `indexing/chunking.py`: chunks from the parsing IR at function/class
  granularity; payload = repo, path, line range, symbol id.
- `retrieval/embeddings.py`: EmbeddingProvider port; first impl can be
  Ollama (nomic-embed-text) — embeddings are far less quality-sensitive
  than generation.
- New pipeline stage after graph build: embed + upsert to Qdrant
  collection `code_chunks`. Dense only; sparse/BM25 comes later.

## Step 2 — Retrieval endpoint
- `retrieval/search.py` + `POST /internal/retrieval/search`:
  dense top-k -> enrich each hit from Neo4j (containing symbol, direct
  callers/callees) -> return chunks + citations.
- Deliberately skip RRF fusion and rerankers for now: tuning, not proof.

## Step 3 — Ask endpoint (the demo itself)
- `POST /internal/ask {repository_id, question}`: retrieve -> assemble
  cited context -> call model -> return answer + citations. Blocking JSON
  is fine; SSE streaming later.
- Add an Anthropic (or other frontier API) provider behind the existing
  `models/registry.py` port and route the reasoning tier to it. Ollama
  stays as the keyless fallback. This is the single highest-leverage
  quality change in the plan (see ADR-0008 — record the amendment).

## Step 4 — Expose through api + one UI page
- api: `POST /projects/:projectId/ask` proxying to code-intel (auth,
  audit already exist).
- web: one page — question box, answer, clickable file:line citations.
  No conversation persistence yet.

## Step 5 — Index a real repository
- Pick one genuinely large repo (internal codebase or a big OSS project,
  ideally 100k+ LOC in a supported language). Index it. Ask ten real
  questions. Write down what was wrong.

## Step 6 — Golden-set benchmark (the moat number)
- `evals/golden.jsonl`: ~30 questions with known answer files/symbols.
- Runner executes two configs: (a) full pipeline with graph enrichment,
  (b) embeddings-only baseline. Metric: answer-file hit rate in citations.
- This one table is the evidence that the graph/hybrid approach is worth
  its complexity — for buyers, investors, and ourselves.

## Exit criterion
A stakeholder watches: real repo -> real question -> correct cited answer
in under ~10s; and the hit-rate table (hybrid vs naive) exists in CI.

## Deliberately deferred until the slice works
Sparse vectors + RRF, reranker, streaming, conversation persistence,
incremental re-embedding, all agents, log pipeline, dashboards.
