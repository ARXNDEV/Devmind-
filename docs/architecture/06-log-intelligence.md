# 06 — Log Intelligence & Incidents

This subsystem turns raw production logs into structured signals (fingerprints, anomalies) and product artifacts (incidents with timelines). It is deliberately *not* a general observability platform — enterprises already own Datadog/Splunk/ELK. DevMind ingests enough log signal to debug with, and integrates with existing platforms rather than replacing them.

## Ingestion

- **Push endpoint**: `POST /ingest/v1/logs` on a dedicated ingest route (token-authenticated per `log_source`, batched NDJSON, gzip). Standard shippers (Vector, Fluent Bit, Filebeat) can target it with stock HTTP sinks — no custom agent to maintain.
- **Adapters** normalize source formats (app JSON logs, syslog, Docker, Kubernetes, Postgres/MySQL logs) into one event schema:

```
LogEvent { ts, org_id, source_id, service, severity, message, attributes{}, trace_id?, host?, k8s{}? }
```

- Ingest path: endpoint → Redis Stream (buffer, absorbs bursts) → arq consumers → fingerprint → persist. The stream decouples ingest availability from processing throughput; consumer lag is a first-class metric.

## Fingerprinting

Drain-style online template mining clusters events into templates (`Connection to {*} timed out after {*}ms`) stored in `log_fingerprints`. Fingerprints are the unit of everything downstream: dedup, counting, anomaly detection, incident grouping, "have we seen this bug before" lookups, and embedding (templates are embedded into Qdrant once, not every event — retrieval over logs stays cheap).

## Anomaly detection (v1: statistical, not ML)

Per fingerprint × service, sliding-window rate tracking with EWMA baselines:

- **Burst**: error-severity rate exceeds baseline by a configured multiple.
- **Novelty**: a never-seen fingerprint at warn+ severity.
- **Absence**: a heartbeat-class fingerprint stops (opt-in per fingerprint).

Deliberately simple, explainable, and tunable per org. ML-based detection is a Phase-later experiment gated on labeled data from real usage — shipping opaque anomaly scores to SREs on day one destroys trust.

## Incident lifecycle

Detection creates (or attaches to) an incident via the `api` contract:

1. Anomaly fires → `code-intel` calls `api`: create incident (or append to an open incident with the same fingerprint — no alert storms).
2. `api` persists the incident, emits SSE to dashboards, and (per org policy) auto-enqueues a **Root-Cause agent run** with the incident context: fingerprint, sample events, time window, recent deploy markers.
3. The agent correlates logs ↔ code (fingerprint → stack frames → symbols via the code graph) ↔ recent commits ↔ similar historical incidents, and files a `root_cause_report` with confidence and cited evidence.
4. Engineers work the incident in the UI: timeline, evidence, chat grounded in incident context, and optionally a Patch-agent proposal.
5. Resolution requires a human. On resolve, the incident + root cause + fix are written back to the Knowledge context — the platform's debugging memory compounds.

Deploy markers (via CI webhook or API) are appended to timelines; "what changed right before this" is usually the root cause, so the correlation is first-class.

## Storage

`log_events` in Postgres, native range partitions by day, with per-org retention (default 30 days hot; archived batches to MinIO as Parquet for replay). Indexes on `(org_id, fingerprint_id, ts)` and `(org_id, service, severity, ts)` — queries are always fingerprint- or service-scoped time ranges, never full-text scans (full-text needs go through fingerprint/template search in Qdrant).

**Honest ceiling:** Postgres handles the design target (tens of GB/day/org) but is the wrong long-term home above that. All access goes through a `LogStorePort`; ClickHouse is the planned swap when a customer's volume demands it ([ADR-0006](../adr/0006-postgres-log-store-v1.md)). We do not build on ClickHouse now — one more stateful cluster before we have users is exactly the overengineering the project principles prohibit.
