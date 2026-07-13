# 04 — Hybrid Retrieval

Retrieval quality bounds the quality of every agent. The design principle: **structure first, semantics second** — exact symbol and graph signals outrank fuzzy similarity whenever they fire, and embeddings are never the only path to an answer.

## Query pipeline

```
query → understand → fan-out retrievers (parallel) → fuse (RRF) → rerank → assemble context
```

### 1. Understand

A fast model pass (Haiku-class, behind the `ModelProvider` port) classifies the query and extracts anchors: identifiers (`PaymentService.settle`), file paths, error signatures, ticket IDs, time ranges. Cheap, cached, and skippable — if extraction fails, all retrievers still run with the raw query.

### 2. Fan-out retrievers

All run in parallel with a shared timeout; a slow retriever degrades results, never blocks them.

| Retriever | Backend | Fires on |
| --- | --- | --- |
| Dense semantic | Qdrant (dense vectors) | always |
| BM25 lexical | Qdrant (sparse vectors, same collection) | always |
| Exact symbol | Neo4j (`fqn`/`name` index) | extracted identifiers |
| Identifier fuzzy | Postgres `pg_trgm` over symbol names/paths | identifier-ish tokens |
| Graph expansion | Neo4j neighborhood of top symbol hits (callers, callees, siblings) | after first-round hits |
| Git history | Indexed commit messages + `git log -S` style pickaxe over anchors | "when/why did X change" intents |
| Docs & knowledge | Qdrant (docs collection) + knowledge items | always |
| Bug/incident history | Postgres incidents + fingerprints | error signatures, debug intents |
| Log search | `log_events` by fingerprint/time window | incident context, time ranges |

Search-index consolidation decision (why Qdrant sparse vectors instead of OpenSearch, and where Postgres FTS fits): [ADR-0005](../adr/0005-search-index-strategy.md).

### 3. Fuse

Reciprocal Rank Fusion across retriever result lists — rank-based, so it needs no score normalization across heterogeneous backends. Retriever weights are config, not code: exact-symbol hits get a strong prior (a user who names a symbol almost always wants that symbol), graph-expansion results inherit a fraction of their seed's weight.

### 4. Rerank

Cross-encoder reranker over the top ~50 fused candidates → top ~15. Behind a `Reranker` port: start with a hosted reranker API, keep the option of a local model for air-gapped enterprise deployments (a known sales requirement for this market).

### 5. Assemble

The context assembler builds the final prompt block under an explicit token budget:

- Dedupe by symbol/file span; prefer the symbol chunk over overlapping file chunk.
- Attach one-line graph context to each code chunk (`called by 14 symbols across 3 modules; last changed in a4f2c1 "fix rounding"`), which is routinely the detail that lets the model reason structurally.
- Every context item carries a stable citation ref (`chunk_id`/`symbol_id`/`commit_sha`) — these flow through to `messages.citations` so every AI claim in the UI links to its evidence.

## Evaluation harness (built in Phase 3, not later)

Retrieval regressions are invisible without measurement. We maintain a golden dataset per pilot repo — (query → expected files/symbols) triples harvested from real usage and hand-labeled — and CI runs recall@k / MRR on every change to retrievers, chunking, or fusion weights. Chunking-strategy changes especially: they look harmless and routinely tank recall.

## What we deliberately do not do

- No LLM-generated multi-query expansion in v1 (latency + cost for marginal gain; revisit with eval data).
- No agentic retrieval loops inside the retrieval layer — agents may *call* retrieval repeatedly ([05](05-agents.md)), but retrieval itself stays a bounded, cacheable, testable function.
