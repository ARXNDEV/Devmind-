# ADR-0003: NestJS owns the product domain; Python owns code intelligence

**Status:** Accepted · 2026-07-09

## Context

Two runtimes share responsibility for "understanding repositories." Without a hard rule, features land wherever is convenient that week, and both services degrade into a distributed ball of mud. This is the single highest-leverage boundary decision in the system.

## Decision

- **`api` (NestJS) owns every product concept**: users, orgs, projects, incidents, conversations, patches, jobs, audit, authorization. It is the only internet-facing API and the only writer of product state.
- **`code-intel` (Python) owns every intelligence mechanism**: parsing, graphs, embeddings, retrieval, fingerprinting, agent execution. It holds no product state, resolves no permissions, and is never exposed publicly.
- Agents create product artifacts (patches, root-cause reports, incidents) **only** via the internal callback contract — never by writing to product storage.
- Litmus test for any new feature: *"Is this a fact about the customer's engineering organization (→ api) or a mechanism for deriving facts from their systems (→ code-intel)?"*

## Consequences

- Authorization is evaluated in exactly one place; `code-intel` compromise cannot mint product state outside the signed callback surface.
- Some flows cost an extra hop (agent → callback → api → SSE). Accepted: the hop is the audit point.
- The contract must be versioned and CI-checked from Phase 1, or this boundary becomes friction instead of structure.
