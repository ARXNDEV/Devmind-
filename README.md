# DevMind AI

**The AI Software Engineer for Legacy Enterprise Systems.**

DevMind AI is an enterprise platform that understands entire legacy codebases — code, git history, documentation, logs, and bug history — and assists engineers across the software lifecycle: explaining code, monitoring production, finding root causes, proposing verified fixes, reviewing changes, and performing impact analysis.

This is not a RAG chatbot. It is a code-intelligence engine (parsing, graphs, hybrid retrieval) with a multi-agent reasoning layer on top, packaged as an enterprise product.

## Status

Architecture phase. No application code yet. The blueprint below is the source of truth for all implementation work.

## Architecture documentation

| Doc | Contents |
| --- | --- |
| [01 — System Overview](docs/architecture/01-system-overview.md) | Context, service topology, communication patterns |
| [02 — Domain Model](docs/architecture/02-domain-model.md) | Bounded contexts, aggregates, PostgreSQL schema |
| [03 — Code Intelligence](docs/architecture/03-code-intelligence.md) | Indexing pipeline, Tree-sitter, code graph, incremental indexing |
| [04 — Hybrid Retrieval](docs/architecture/04-hybrid-retrieval.md) | Retrievers, rank fusion, context assembly, retrieval evals |
| [05 — Agent Orchestration](docs/architecture/05-agents.md) | LangGraph topology, agent registry, model routing, guardrails |
| [06 — Log Intelligence & Incidents](docs/architecture/06-log-intelligence.md) | Ingestion, fingerprinting, anomaly detection, incident lifecycle |
| [07 — API Contracts](docs/architecture/07-api-contracts.md) | Public API, internal service contract, streaming |
| [08 — Security](docs/architecture/08-security.md) | AuthN/Z, secret handling, sandboxing, OWASP posture |
| [09 — Deployment & Operations](docs/architecture/09-deployment-and-operations.md) | Compose topology, config, observability, scaling |
| [10 — Roadmap](docs/architecture/10-roadmap.md) | Phases 1–8 with exit criteria |

## Architecture Decision Records

Significant, hard-to-reverse decisions live in [docs/adr](docs/adr). Start with [ADR-0002 (service topology)](docs/adr/0002-service-topology.md) and [ADR-0003 (domain boundary)](docs/adr/0003-product-vs-intelligence-boundary.md) — they define the shape of everything else. [ADR-0008 (local model serving)](docs/adr/0008-local-model-serving.md) records the keyless, self-hosted inference decision.

Deploying to a VM? See the [deployment runbook](docs/DEPLOYMENT.md).

## Planned repository layout

```
apps/
  web/          Next.js + React + TypeScript + Tailwind (Monaco, React Flow)
  api/          NestJS modular monolith — product domain, public API, BullMQ workers
services/
  code-intel/   Python FastAPI — parsing, graphs, embeddings, retrieval, agents
packages/
  shared-types/ Generated API clients and shared contract types
docs/           Architecture docs and ADRs
infra/          Docker Compose, service configs, CI
```
