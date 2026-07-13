# ADR-0001: Single monorepo for all services

**Status:** Accepted · 2026-07-09

## Context

Three applications (Next.js web, NestJS api, Python code-intel) share one contract and evolve together. Team size is small; atomic cross-service changes (API + client + UI) will be the norm for the first year.

## Decision

One repository. pnpm workspaces for the TypeScript side (`apps/web`, `apps/api`, `packages/shared-types`); `uv` for `services/code-intel`; Turborepo for task orchestration/caching across workspaces. Generated OpenAPI clients live in `packages/shared-types` and are regenerated in CI.

## Consequences

- Contract changes are atomic: spec, server, client, and UI update in one PR; drift is impossible to merge.
- CI must be path-filtered so unrelated workspaces don't run each other's suites.
- If a component later needs an independent release cadence (e.g., an on-prem agent shipped to customers), it can be extracted; nothing in the layout prevents that.
