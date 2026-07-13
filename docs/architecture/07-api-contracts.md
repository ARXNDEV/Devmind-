# 07 — API Contracts

Two contracts exist. Both are OpenAPI-first: the spec is the artifact, clients are generated (`packages/shared-types`), and breaking changes fail CI via spec diffing.

## 1. Public API (`api`, NestJS) — `/api/v1`

Versioned, org-scoped REST. Representative surface (full spec evolves per phase):

```
Auth        POST /auth/login | /auth/refresh | /auth/logout        (session; SSO in Phase 8)
Orgs/Users  GET/PATCH /org · GET/POST/PATCH /org/members · POST /org/api-keys
Projects    CRUD /projects · CRUD /projects/{id}/repositories
Indexing    POST /repositories/{id}/index                          → 202 { jobId }
            GET  /repositories/{id}/index-status
Search      POST /projects/{id}/search                             (hybrid; sync, <2s SLO)
Explorer    GET  /repositories/{id}/tree · /file?path= · /symbols?query=
Graph       GET  /repositories/{id}/graph/neighborhood?symbolId=&depth=
            POST /repositories/{id}/impact-analysis                → 202 { jobId }
Chat        POST /conversations · POST /conversations/{id}/messages → SSE stream
Incidents   GET/POST /incidents · GET /incidents/{id}/timeline
            POST /incidents/{id}/investigate                       → 202 { jobId }
Patches     GET /patches · GET /patches/{id} (diff, risks, files)
            POST /patches/{id}/review  { approve|reject|comment }
            POST /patches/{id}/verify                              → 202 { jobId }
Jobs        GET /jobs/{id} · GET /jobs/{id}/events                 → SSE
Logs        GET /projects/{id}/log-sources · POST … · GET /logs/search
Knowledge   CRUD /knowledge-items
Admin/Audit GET /audit-log
```

Conventions: cursor pagination everywhere; RFC 9457 `application/problem+json` errors with stable machine-readable `code`; idempotency keys on all `202` job-creating endpoints; every long-running operation is a `Job` with a uniform status/events shape.

**Ingest plane** is separate from the control plane: `POST /ingest/v1/logs` uses per-source tokens, aggressive rate limits, and no session auth — it can be scaled and hardened independently.

## 2. Internal contract (`api ↔ code-intel`)

`code-intel` is internal-only. Service-token auth (rotatable, per-environment; mTLS when we outgrow Compose). Every request carries `X-DevMind-Org-Id` (+ project/repo scope) — `code-intel` trusts these headers only from authenticated service traffic and scopes all reads/writes by them.

```
api → code-intel (commands & queries)
  POST /internal/v1/index-runs                 { repoId, cloneRef, commit, mode: full|incremental }
  POST /internal/v1/agent-runs                 { kind, input, budgets }   → { taskId }
  POST /internal/v1/retrieval/query            (sync)
  GET  /internal/v1/graph/neighborhood | /impact
  DELETE /internal/v1/repositories/{id}        (purge: graph, vectors, snapshots, state)

code-intel → api (callbacks, HMAC-signed, idempotent)
  POST /internal/v1/callbacks/job-status       { taskId, status, result|error }
  POST /internal/v1/callbacks/incidents        { fingerprint, evidence, … }      (anomaly → incident)
  POST /internal/v1/callbacks/artifacts        { kind: patch|root_cause|doc, payload }
```

Progress/token streams flow over Redis pub/sub (`events:job:{id}`), relayed by `api` to browsers via SSE. Callbacks are the durable record; pub/sub is best-effort UX. `api` treats the `jobs` table as truth and reconciles: a watchdog re-polls `code-intel` task status for jobs whose events go quiet, so a dropped callback degrades to eventual consistency, never a stuck-forever spinner.

## Streaming to the browser

SSE endpoints: job events, chat token streams, incident dashboard updates. One event envelope everywhere:

```json
{ "id": "evt_…", "type": "job.progress | chat.token | incident.updated | …",
  "ts": "…", "data": { } }
```

`Last-Event-ID` resume supported on job streams (events buffered briefly in Redis). WebSockets are reserved for a future collaborative-editing need; nothing current requires bidirectional transport.
