# Contributing to DevMind AI

## Prerequisites

- Node.js >= 20 and pnpm 10 (`corepack enable`)
- Python 3.12 and `uv` (for `services/code-intel`)
- Docker (for the local infra stack: Postgres, Redis, Neo4j, Qdrant)

## Getting started

```bash
pnpm install
cp .env.example .env
pnpm infra:up
pnpm dev
```

## Workflow

1. Branch from `main` using `feat/`, `fix/`, `docs/` or `chore/` prefixes.
2. Keep commits small and use Conventional Commits (`feat(api): ...`, `fix(web): ...`).
3. Run `pnpm lint`, `pnpm typecheck` and `pnpm test` before opening a PR.
4. If you change a public API, run `pnpm codegen` and commit the regenerated `packages/shared-types`.
5. Significant, hard-to-reverse decisions need an ADR in `docs/adr`.

## Code style

- TypeScript: ESLint + Prettier (config in each app).
- Python: Ruff for lint and format, mypy for types.
- No secrets in the repo. `.env` is git-ignored; document new variables in `.env.example`.
