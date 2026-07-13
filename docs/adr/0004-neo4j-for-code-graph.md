# ADR-0004: Neo4j for the code graph

**Status:** Accepted · 2026-07-09

## Context

Call graphs, dependency graphs, and impact analysis need variable-depth traversals ("all transitive callers of X to depth n, grouped by module") over graphs with millions of nodes for large repos. Options: Postgres recursive CTEs, a dedicated graph database, or an in-process graph library rebuilt from Postgres edges.

## Decision

Neo4j, behind a `CodeGraphPort` adapter (no Cypher outside it).

- Recursive CTEs handle fixed-shape, shallow traversals fine but get slow and unmaintainable for the multi-hop, filtered, weighted traversals impact analysis needs at MLOC scale.
- In-process graphs (rustworkx et al.) are fast but push graph state into worker memory — wrong shape for multiple workers and repos.
- Neo4j is an explicit stack requirement and its query model matches the domain exactly.

## Consequences

- One more stateful service to operate (memory-hungry; page cache must be sized to the graph). Accepted for a component this central.
- The graph is a **rebuildable projection** of snapshots + pipeline: DR is "re-index," and swapping graph stores later (or dropping to Postgres for small deployments) stays possible because access is port-scoped.
- Community Edition to start; Enterprise/AuraDB is a licensing decision deferred until a customer's scale forces it.
