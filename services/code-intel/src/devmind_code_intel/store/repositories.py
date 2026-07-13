"""Data-access for index-run and file-state bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .db import Database


@dataclass(frozen=True, slots=True)
class FileState:
    path: str
    content_hash: str
    language: str
    symbol_count: int


class IndexRunStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        run_id: UUID,
        repository_id: UUID,
        org_id: UUID,
        commit_sha: str,
        base_commit_sha: str | None,
        mode: str,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO codeintel.index_runs
                (id, repository_id, org_id, commit_sha, base_commit_sha, mode, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'running')
            """,
            run_id,
            repository_id,
            org_id,
            commit_sha,
            base_commit_sha,
            mode,
        )

    async def finish(
        self,
        run_id: UUID,
        *,
        status: str,
        stats: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        import json

        await self._db.execute(
            """
            UPDATE codeintel.index_runs
               SET status = $2,
                   stats = $3::jsonb,
                   error = $4::jsonb,
                   finished_at = now()
             WHERE id = $1
            """,
            run_id,
            status,
            json.dumps(stats or {}),
            json.dumps(error) if error is not None else None,
        )

    async def latest_indexed_commit(self, repository_id: UUID) -> str | None:
        row = await self._db.fetchrow(
            """
            SELECT commit_sha FROM codeintel.index_runs
             WHERE repository_id = $1 AND status = 'succeeded'
             ORDER BY finished_at DESC NULLS LAST
             LIMIT 1
            """,
            repository_id,
        )
        return row["commit_sha"] if row else None


class FileStateStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def all_for_repo(self, repository_id: UUID) -> dict[str, FileState]:
        rows = await self._db.fetch(
            """
            SELECT path, content_hash, language, symbol_count
              FROM codeintel.file_states
             WHERE repository_id = $1
            """,
            repository_id,
        )
        return {
            r["path"]: FileState(
                path=r["path"],
                content_hash=r["content_hash"],
                language=r["language"],
                symbol_count=r["symbol_count"],
            )
            for r in rows
        }

    async def upsert(
        self,
        *,
        repository_id: UUID,
        path: str,
        content_hash: str,
        language: str,
        symbol_count: int,
        run_id: UUID,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO codeintel.file_states
                (repository_id, path, content_hash, language, symbol_count,
                 last_indexed_run_id, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, now())
            ON CONFLICT (repository_id, path) DO UPDATE
               SET content_hash = EXCLUDED.content_hash,
                   language = EXCLUDED.language,
                   symbol_count = EXCLUDED.symbol_count,
                   last_indexed_run_id = EXCLUDED.last_indexed_run_id,
                   updated_at = now()
            """,
            repository_id,
            path,
            content_hash,
            language,
            symbol_count,
            run_id,
        )

    async def delete_paths(self, repository_id: UUID, paths: list[str]) -> None:
        if not paths:
            return
        await self._db.execute(
            "DELETE FROM codeintel.file_states WHERE repository_id = $1 AND path = ANY($2)",
            repository_id,
            paths,
        )
