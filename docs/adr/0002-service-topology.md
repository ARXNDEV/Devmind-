# ADR-0002: Modular-monolith product core + separate code-intelligence service

**Status:** Accepted · 2026-07-09

## Context

The spec asks for both "modular monolith initially" and "components independently deployable." Full microservices (per agent, per module) would maximize deployability at ruinous cost in operational complexity for a pre-customer product. A single process for everything would force Python AI workloads and Node product logic into one runtime.

## Decision

Four deployables: `web`, `api` (+ `api-worker`), `code-intel` (+ `ci-worker`). The product domain is a **modular monolith** inside `api` (NestJS modules with lint-enforced boundaries). Code intelligence is a **separate service** because it differs in runtime (Python), scaling profile (CPU-heavy parsing, long agent runs), and failure domain (an OOM during a 5 MLOC index must not take down auth).

Agents are packages inside `code-intel`, not services. "Independently deployable" is satisfied at the service level; "independently extensible" (per the spec) is satisfied by the agent registry.

## Consequences

- One internal contract to maintain instead of N; one hop for any user request.
- Splitting a NestJS module out later (e.g., Incidents at high ingest scale) is a known, bounded refactor because boundaries are enforced from day one.
- The risk to police: business logic leaking into `code-intel` because "the data is there." Mitigation: ADR-0003.
