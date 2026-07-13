# 03 — Code Intelligence

The indexing pipeline turns a git repository into four queryable structures: a **code graph** (Neo4j), **hybrid search indexes** (Qdrant dense + sparse), **file/symbol metadata** (Postgres `codeintel`), and **snapshots** (MinIO). Everything downstream — retrieval, impact analysis, debugging, documentation — reads these; nothing downstream re-parses code.

## Pipeline

```
acquire → snapshot → detect → parse → extract → resolve → persist-graph → chunk → embed → index → finalize
```

Each stage is an idempotent arq task with per-stage metrics; a failed run resumes from the last completed stage. Stages `parse → embed` fan out per file across workers.

1. **Acquire** — clone/fetch with provider credentials (never written to disk unencrypted; injected via git credential helper). Shallow-then-deepen strategy: blobless clone (`--filter=blob:none`) for the graph of history, full checkout of the target commit for parsing.
2. **Snapshot** — the checked-out tree is archived to MinIO keyed by `{repo_id}/{commit_sha}`. All later stages read from the snapshot, making the pipeline reproducible and clone-free on retry.
3. **Detect** — language + framework detection per file (extension + shebang + content heuristics), binary/vendored/generated exclusion (`.devmindignore` + built-in rules: `node_modules`, `vendor`, minified assets, lockfiles).
4. **Parse** — Tree-sitter per file. One parser pool per language, reused across files. Files > 2 MB or with > N parse errors are indexed lexically only and flagged.
5. **Extract** — per-language extractors walk the CST and emit a **language-neutral IR**: `SymbolDef` (function/class/method/interface/variable/type, with span, signature, docstring), `ImportEdge`, `CallSite`, `InheritanceEdge`, `Reference`. Extractors are the only language-specific code; adding a language = adding one extractor module. Launch languages: Java, C#, Python, TypeScript/JavaScript, Go (legacy-enterprise-first ordering), with COBOL/PL-SQL extractors as a later commercial differentiator.
6. **Resolve** — link call sites and references to symbol definitions. Static resolution where the language allows (Java, C#, Go); heuristic resolution (import-scoped name matching, arity checks) for dynamic languages, with a `confidence` property on every resolved edge so downstream consumers can filter. Unresolved calls are kept as `CALLS_UNRESOLVED` edges to a name node — absence of an edge must mean "no call," not "we couldn't tell."
7. **Persist graph** — batched `UNWIND` upserts into Neo4j.
8. **Chunk** — structure-aware chunking: one chunk per symbol (function/method/class-header), prefixed with a context header (`repo › path › enclosing class › signature`), plus file-level chunks for imports/config. Never fixed-size sliding windows over code.
9. **Embed** — code-tuned embedding model behind an `EmbeddingProvider` port (config-driven; batched, rate-limited, cached by content hash so re-index of unchanged content costs zero tokens).
10. **Index** — upsert to Qdrant: dense vector + BM25 sparse vector per chunk in one collection (named vectors), payload carries `{org_id, repo_id, path, symbol_id, language, kind, commit_sha}` for filtered search.
11. **Finalize** — write `index_runs` stats, flip `repositories.index_status → ready`, emit completion callback.

## Code graph model (Neo4j)

```
(:Repository {id})
(:File {repo_id, path, language, content_hash})
(:Module {repo_id, name})                        // package/namespace/directory grouping
(:Symbol {id, repo_id, fqn, name, kind, path, span_start, span_end, signature})
(:Name {repo_id, name})                          // unresolved call targets

(:Repository)-[:CONTAINS]->(:File)-[:DEFINES]->(:Symbol)
(:Module)-[:CONTAINS]->(:File)
(:File)-[:IMPORTS]->(:File|:Module)
(:Symbol)-[:CALLS {confidence, call_site_span}]->(:Symbol)
(:Symbol)-[:CALLS_UNRESOLVED]->(:Name)
(:Symbol)-[:INHERITS|:IMPLEMENTS]->(:Symbol)
(:Symbol)-[:REFERENCES {confidence}]->(:Symbol)
(:Module)-[:DEPENDS_ON {weight}]->(:Module)      // aggregated from file-level edges
```

Why a graph database at all (vs. recursive CTEs in Postgres): impact analysis and root-cause tracing are variable-depth traversals — "all transitive callers of `X` up to depth n, grouped by module, intersected with files changed in the last 30 days." At multi-MLOC scale these are Neo4j's home game and Postgres's worst case. Tradeoffs and the exit hatch are in [ADR-0004](../adr/0004-neo4j-for-code-graph.md). All access goes through a `CodeGraphPort` interface — no Cypher outside the adapter.

**Impact analysis** is a pure graph computation: given a symbol/file, traverse reverse `CALLS`/`IMPORTS`/`DEPENDS_ON` edges with depth-decayed weights, join against test files, API route symbols, and job entry points (tagged during extraction), and emit a risk score = f(fan-in, depth, confidence, historical churn from git).

## Incremental indexing

Full re-index of a multi-MLOC repo on every push is a non-starter. Incremental runs:

1. `git diff --name-status <indexed_commit> <head>` → changed/deleted/renamed files.
2. Cross-check `file_states.content_hash` (defends against force-pushes and diff edge cases).
3. Re-run stages 4–10 for changed files only; delete graph nodes/edges and Qdrant points for deleted files (`detach delete` by `path`, point-delete by payload filter).
4. **Re-resolution ripple:** a changed file can change resolution *targets* in other files. We re-resolve only files that import (directly) a changed file — bounded by the import graph, not the whole repo.
5. Update module-level `DEPENDS_ON` aggregates for touched modules.

A nightly consistency job samples files and verifies graph/index agreement with the snapshot, alerting on drift — incremental systems rot silently without this.

## Scale posture

- Parse/extract/embed fan out per file across arq workers; a single 5 MLOC repo indexes in parallel, not serially.
- Embedding is the cost ceiling: content-hash caching plus symbol-level chunking (no overlapping windows) keeps token spend proportional to *changed* code.
- Neo4j writes are batched (5k rows/`UNWIND`); Qdrant upserts batched at 512 points.
- Back-pressure: indexing runs at lower queue priority than interactive retrieval so a big index never starves chat.
