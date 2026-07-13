# ADR-0006: Partitioned Postgres for log events in v1

**Status:** Accepted · 2026-07-09

## Context

Log intelligence needs durable event storage with time-range + fingerprint queries. Purpose-built stores (ClickHouse, Loki) are the "correct" answer at high volume, but each is another stateful cluster to operate before we have a single customer, and our query pattern is narrow (fingerprint/service-scoped time ranges — no ad-hoc full-text analytics).

## Decision

`log_events` in Postgres (`codeintel` schema): native daily range partitions, `(org_id, fingerprint_id, ts)` and `(org_id, service, severity, ts)` indexes, per-org retention dropping whole partitions, cold archive to MinIO as Parquet. All access through a `LogStorePort`.

## Consequences

- Comfortable to roughly tens of GB/day per deployment; beyond that, ClickHouse is the planned adapter swap — the port and the Parquet archive (replayable) are the escape hatch, so this is a reversible decision by design.
- Fingerprint-first design keeps Postgres viable far longer than raw-text storage would: hot queries hit fingerprint aggregates, not message scans; full-text needs go through template search in Qdrant.
- We must enforce the discipline that nothing queries `log_events` outside the port, or the swap stops being cheap.
