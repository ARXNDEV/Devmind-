# 09 — Deployment & Operations

## Docker Compose topology

Compose is the dev and pilot deployment target (single-host, up to ~25 concurrent engineers); the service shape is Kubernetes-ready by construction (12-factor, stateless app containers, health probes), but we do not carry K8s manifests before a customer requires them.

```yaml
# infra/docker-compose.yml (shape, not final file)
services:
  web:          # Next.js, standalone output
  api:          # NestJS, node:22-slim, distroless-final
  api-worker:   # same image as api, command: worker  (BullMQ)
  code-intel:   # FastAPI, uvicorn, python:3.12-slim
  ci-worker:    # same image, command: arq worker      (scale: replicas)
  postgres:     # 16, wal_level=logical, scheduled pg_dump to MinIO
  redis:        # 7, AOF everysec
  qdrant:
  neo4j:        # 5.x community to start
  minio:
```

Profiles: `dev` (hot reload, exposed DB ports, seeded data), `pilot` (TLS via Caddy/Traefik front, no exposed internals). Same-image-different-command for workers keeps API and worker code in lockstep — version skew between them is a classic outage source.

## Configuration

12-factor, env-only, validated at boot (fail-fast): NestJS `ConfigModule` + zod schema; Pydantic `Settings` in Python. Every variable documented in `.env.example`. No config values in code, no secrets in images, no "works because my shell has it."

## Observability

- **Tracing**: OpenTelemetry in both services from Phase 1. Trace context propagates browser → api → code-intel → workers (job IDs carry trace links), so "why was this answer slow" is a single trace: retrieval fan-out, model latency, graph queries, all visible. Export OTLP → self-hosted collector (dev: Jaeger; pilots: customer's backend or ours).
- **Logs**: structured JSON (pino / structlog), correlation IDs on every line. DevMind's own logs are also fed into its ingest pipeline in staging — we dogfood the log-intelligence engine on ourselves.
- **Metrics**: Prometheus endpoints. Golden signals per service plus domain metrics: index throughput (files/s), queue depths + consumer lag (Redis Streams, arq, BullMQQ), retrieval latency by retriever, model token spend per org, SSE connection counts.
- **Health**: `/healthz` (liveness) and `/readyz` (checks dependencies) on every service; Compose `depends_on: condition: service_healthy` ordering.

## Capacity model for the 25-engineer target

The load profile is spiky-interactive (chat, search) over heavy-background (indexing, agents):

- Interactive search path is sync and must hold a p95 < 2s SLO → retrieval fan-out parallelism and Qdrant/Neo4j on adequate memory (Neo4j page cache sized to the graph; Qdrant mmap'd).
- Everything else is queued. Scaling knob #1 is `ci-worker` replicas; queues are priority-tiered (interactive agent runs > incident investigations > indexing > backfills).
- One primary Postgres with tuned pools (PgBouncer when connection counts demand it). Read replicas are a later knob; nothing in the design assumes single-writer beyond Postgres itself.

## Data operations

- Backups: nightly `pg_dump` + MinIO versioning; Neo4j and Qdrant are **rebuildable projections** of (snapshot + pipeline), so their DR story is "re-index," with weekly snapshots only to shorten recovery time. This is a deliberate architectural property: derived stores can be dropped and rebuilt.
- Retention: log partitions dropped per org policy (default 30d hot, archived to MinIO); repo snapshots keep last N indexed commits.
- Migrations: SQL migration files, forward-only, run as a release step (`migrate` one-shot container), never at app boot in multi-replica setups.

## CI/CD (GitHub Actions)

- PR pipeline: lint + typecheck + unit tests per workspace (path-filtered so a web-only change doesn't run Python suites), contract check (OpenAPI diff — breaking change fails), integration tests against ephemeral Compose services, image build.
- Main pipeline: everything above + retrieval eval suite ([04](04-hybrid-retrieval.md)) + image push (SBOM + Trivy scan) + staged deploy.
- Release discipline: images tagged by git SHA; `latest` is never deployed anywhere.
