-- codeintel schema - owned by the Python service (ADR-0003).
-- The codeintel_service role has CREATE on this schema, so the engine manages
-- its own migrations independently of the api service.

CREATE TABLE IF NOT EXISTS codeintel.index_runs (
    id              uuid PRIMARY KEY,
    repository_id   uuid NOT NULL,
    org_id          uuid NOT NULL,
    commit_sha      text NOT NULL,
    base_commit_sha text,                         -- null = full index
    mode            text NOT NULL,                -- 'full' | 'incremental'
    status          text NOT NULL DEFAULT 'running',
    stats           jsonb NOT NULL DEFAULT '{}',
    error           jsonb,
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz
);

CREATE INDEX IF NOT EXISTS index_runs_repo_idx
    ON codeintel.index_runs (repository_id, started_at DESC);

-- One row per indexed file; content_hash drives incremental re-index and
-- defends against diff edge cases (force-push, renames).
CREATE TABLE IF NOT EXISTS codeintel.file_states (
    repository_id       uuid NOT NULL,
    path                text NOT NULL,
    content_hash        text NOT NULL,
    language            text NOT NULL,
    symbol_count        integer NOT NULL DEFAULT 0,
    last_indexed_run_id uuid NOT NULL,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (repository_id, path)
);
