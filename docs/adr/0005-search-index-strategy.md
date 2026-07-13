# ADR-0005: Qdrant dense+sparse hybrid; no OpenSearch in v1

**Status:** Accepted · 2026-07-09

## Context

The spec requires hybrid retrieval: semantic + BM25 keyword + symbol + fuzzy identifier search. The classic answer adds OpenSearch/Elasticsearch for BM25 — a heavy JVM cluster that duplicates every document into a second index and doubles ingest complexity.

## Decision

- **Semantic + BM25 in Qdrant**: each chunk stores a dense vector and a BM25-weighted sparse vector (named vectors, one collection); Qdrant's Query API runs both and fuses server-side. One store, one upsert path, one payload-filter model for tenancy.
- **Exact symbol lookup**: Neo4j name/fqn indexes (the graph already has every symbol).
- **Fuzzy identifier/path matching**: Postgres `pg_trgm` over `codeintel` symbol/path columns (typo-tolerant `PaymntServce` → `PaymentService`).
- All behind retriever interfaces; fusion happens in the retrieval layer regardless of backend.

## Consequences

- One fewer stateful cluster; log ingest and code indexing don't feed a search cluster nobody operates well.
- We give up Lucene's query DSL (proximity operators, exotic analyzers). If pilot evals show BM25-over-sparse-vectors underperforming on code tokens, the retriever interface localizes an OpenSearch (or Tantivy-embedded) swap to one adapter.
- Code-aware tokenization for the sparse vectors (identifier splitting: `getUserById` → `get`, `user`, `by`, `id` + original) is ours to own in the chunking layer — it is the make-or-break detail for code BM25.
