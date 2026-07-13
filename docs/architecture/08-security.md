# 08 — Security

DevMind's threat model is unusual for a SaaS: the product ingests customers' **source code, credentials to source control, and production logs** — three of the most sensitive assets an enterprise owns — and additionally **executes customer code** in verification runs. Security is a sales gate in this market, not a compliance checkbox.

## Tenancy

- Every tenant-scoped table carries `org_id`; every repository access path is org-filtered at the data layer (a `TenantScopedRepository` base that makes forgetting the filter a type error, not a code-review hope).
- Qdrant: `org_id` payload filter mandatory on every query (enforced in the single search adapter). Neo4j: `org_id`/`repo_id` on every node + adapter-enforced scoping. MinIO: per-org key prefixes with bucket policies.
- Cross-tenant tests are part of the standard test suite: every list/read endpoint has a test proving org B cannot see org A.

## Authentication & authorization

- Sessions: short-lived access JWT + rotating refresh token (httpOnly, Secure, SameSite=strict). Argon2id password hashing. SSO (OIDC/SAML) in Phase 8 — the `sso_subject` column and Identity module interfaces exist from day one so it's an addition, not a refactor.
- API keys: hashed at rest, scoped (`read`, `ingest`, `admin`), prefix-identifiable for support (`dvm_live_…`).
- RBAC: `owner | admin | engineer | viewer` at org level, evaluated in NestJS guards, decorated per route (`@RequireRole`). Default-deny: a route without an explicit policy annotation fails CI.
- Internal plane: service tokens per environment; callbacks HMAC-signed with timestamp + replay window.

## Secrets & sensitive data

- Git credentials and integration tokens: encrypted at rest (AES-256-GCM via a `CredentialVault` port — env-key-backed in Compose, KMS/Vault adapter for production), write-only through the API (never returned, only replaced), decrypted only inside `code-intel` at clone time, injected via git credential helper (never argv, never on-disk config).
- Structured logging with a central redaction layer: known-sensitive keys (`authorization`, `token`, `password`, `set-cookie`…) stripped before emission; log-event ingestion runs a secret-pattern scrubber (AWS keys, JWTs, private key blocks) before persistence.
- LLM boundary: prompts may contain customer code (that's the product), but credentials never enter prompt assembly — the context assembler consumes only indexed artifacts, and the indexer excludes `.env`-class files by built-in rule.

## Code execution sandbox (verification runs)

The only place customer code executes:

- Ephemeral container per run; **no network** (default), read-only rootfs, snapshot mounted read-only + patch applied to tmpfs overlay, non-root user, CPU/memory/pids/disk quotas, hard wall-clock kill.
- Never receives: docker socket, host mounts, service tokens, model API keys, database access. Results come out via a mounted result file collected by the runner.
- Dependency installation (needed for real test runs) is the hard case: allowed only against an egress-allowlisted registry proxy, as a separately-cached layer, still credential-free.

## Input & upload hardening

- Validation at every boundary: `class-validator` DTOs in NestJS, Pydantic in FastAPI — nothing reaches a service unvalidated; unknown fields rejected.
- Uploads (docs, log archives): size caps, content-type sniffing (not extension trust), archive extraction with zip-bomb/path-traversal guards, stored in MinIO never on service disk.
- Standard web posture: parameterized queries only, CSP + security headers on `web`, per-route and per-org rate limits (Redis), CSRF-safe by construction (bearer/SameSite).

## Audit & accountability

Every state-changing action — human, API key, or **agent** — lands in `audit_log` with actor, resource, and metadata. Agent actions attribute to their `agent_run_id`, which links to the full step trace. "What did the AI do and why" must always be answerable; that trace is also the incident-response record if an agent misbehaves.
