# 02 — Domain Model

The `api` service is a modular monolith organized by bounded context. Each context is a NestJS module with its own controllers, services, repositories, and DTOs; cross-context calls go through the owning module's public service interface, never through another module's repository. Module boundary violations are lint-enforced (`eslint-plugin-boundaries`).

## Bounded contexts

| Context | Owns | Key invariants |
| --- | --- | --- |
| **Identity & Access** | Organizations, users, memberships, roles, API keys, sessions | Every resource is org-scoped; role checks happen at the guard layer, never in controllers. |
| **Projects** | Projects, repository connections, integration credentials | A repository belongs to exactly one project; credentials are stored encrypted, write-only via API. |
| **Ingestion** | Index runs, sync schedules, job tracking | One active index run per repository; `Job` rows are the source of truth for async work status. |
| **Incidents** | Incidents, incident events, timelines, root-cause reports | Incidents are append-only timelines; state machine `open → investigating → mitigated → resolved` with audited transitions. |
| **Patches** | Patch proposals, reviews, verification runs | A patch is immutable once proposed; changes create a new revision. A patch cannot be marked `verified` without a passing verification run. |
| **Conversations** | Chat sessions, messages, message citations | Every AI answer stores its citations (chunk/symbol/commit refs) for provenance. |
| **Knowledge** | Documents, runbooks, bug-history records | External knowledge (Jira, docs) is imported with source lineage, never mutated in place. |
| **Audit** | Audit log | Append-only; written via an interceptor, not by feature code. |

## Core PostgreSQL schema (`product`)

Key tables and columns (full DDL lands with Phase 1 migrations; TypeORM is not used — we use Drizzle/Kysely-style explicit SQL migrations for auditability — final pick at scaffold time):

```
organizations   (id, name, slug, settings jsonb, created_at)
users           (id, org_id, email, name, password_hash nullable, sso_subject nullable, created_at)
memberships     (user_id, org_id, role enum[owner|admin|engineer|viewer])
api_keys        (id, org_id, name, key_hash, scopes text[], last_used_at, expires_at)

projects        (id, org_id, name, slug, description, created_at)
repositories    (id, project_id, provider enum[github|gitlab|bitbucket|generic_git],
                 clone_url, default_branch, credentials_ref, indexed_commit_sha,
                 index_status enum[pending|indexing|ready|failed|stale], created_at)

jobs            (id, org_id, kind enum[index|agent_run|patch_gen|verification|log_import|...],
                 subject_type, subject_id, status enum[queued|running|succeeded|failed|cancelled],
                 progress jsonb, error jsonb, external_task_id, created_at, started_at, finished_at)

incidents       (id, org_id, project_id, title, status enum, severity enum[sev1..sev4],
                 fingerprint_id nullable, source enum[log_anomaly|manual|webhook],
                 opened_at, resolved_at)
incident_events (id, incident_id, kind enum[detection|log_burst|deploy|comment|agent_finding|status_change],
                 payload jsonb, occurred_at)                    -- append-only timeline
root_cause_reports (id, incident_id, agent_run_id, summary, confidence numeric,
                    evidence jsonb, affected_modules jsonb, created_at)

patch_proposals (id, org_id, project_id, incident_id nullable, revision int,
                 title, rationale, diff_ref, risk_notes jsonb, affected_files text[],
                 status enum[proposed|in_review|approved|rejected|verified], created_by_agent_run_id)
verification_runs (id, patch_id, job_id, result enum[passed|failed|error],
                   report jsonb, created_at)

conversations   (id, org_id, project_id, repository_id nullable, title, created_by, created_at)
messages        (id, conversation_id, role enum[user|assistant|system], content,
                 agent_run_id nullable, citations jsonb, created_at)

knowledge_items (id, org_id, project_id nullable, kind enum[doc|runbook|adr|bug_report|ticket],
                 source enum[upload|jira|confluence|repo], source_ref, title, content_ref,
                 metadata jsonb, indexed_at)

audit_log       (id, org_id, actor_type enum[user|api_key|agent|system], actor_id,
                 action, resource_type, resource_id, metadata jsonb, created_at)
```

Conventions: UUIDv7 primary keys (time-ordered, index-friendly); `org_id` denormalized onto every tenant-scoped table so row-level tenancy checks never require joins; soft deletes only where the product needs undo (conversations), hard deletes elsewhere with audit entries.

## `codeintel` schema (owned by the Python service)

```
index_runs      (id, repository_id, commit_sha, base_commit_sha nullable,  -- null = full index
                 status, stats jsonb, started_at, finished_at)
file_states     (repository_id, path, content_hash, language, symbol_count,
                 last_indexed_run_id)                           -- drives incremental indexing
log_events      (id, org_id, source_id, ts, severity, service, fingerprint_id,
                 message, attributes jsonb)                     -- partitioned by day, see 06
log_fingerprints(id, org_id, template, first_seen, last_seen, occurrence_count, sample_event_id)
log_sources     (id, org_id, project_id, kind enum[app|linux|docker|kubernetes|database],
                 ingest_token_hash, created_at)
agent_runs      (id, org_id, kind, input jsonb, status, model_usage jsonb,
                 started_at, finished_at)
agent_steps     (id, agent_run_id, seq, node, input_summary, output_summary,
                 tool_calls jsonb, tokens jsonb, duration_ms)   -- full trace for replay/audit
```

The graph itself (symbols, calls, dependencies) lives in Neo4j — Postgres holds only operational state. See [03](03-code-intelligence.md) for the graph model.

## Cross-service identity

`code-intel` never resolves users or permissions. Every internal request from `api` carries the acting `org_id` (and `project_id` where relevant) as verified context; `code-intel` scopes all storage by it. Authorization decisions happen exactly once, in `api`.
