"""asyncpg connection pool and a minimal forward-only migration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg
import structlog

from ..config import Settings, get_settings

logger = structlog.get_logger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    """Owns the asyncpg pool for the codeintel schema."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, settings: Settings | None = None) -> Database:
        settings = settings or get_settings()
        pool = await asyncpg.create_pool(
            settings.database_url.get_secret_value(),
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
        return cls(pool)

    @property
    def pool(self) -> asyncpg.Pool:
        return self._pool

    async def close(self) -> None:
        await self._pool.close()

    async def migrate(self) -> None:
        """Apply pending .sql migrations in filename order, once each."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS codeintel.__migrations (
                    name text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            applied = {
                r["name"]
                for r in await conn.fetch("SELECT name FROM codeintel.__migrations")
            }
            migration_files = sorted(
                p
                for p in _MIGRATIONS_DIR.glob("*.sql")
                # Ignore macOS AppleDouble sidecars (._*) and other dotfiles that
                # can ride along in archives and are not real migrations.
                if not p.name.startswith(".")
            )
            for path in migration_files:
                if path.name in applied:
                    continue
                logger.info("applying migration", name=path.name)
                async with conn.transaction():
                    # Explicit UTF-8: container locales may default to ASCII.
                    await conn.execute(path.read_text(encoding="utf-8"))
                    await conn.execute(
                        "INSERT INTO codeintel.__migrations (name) VALUES ($1)",
                        path.name,
                    )

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        async with self._pool.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, *args)
            return rows

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        async with self._pool.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(query, *args)
            return row

    async def execute(self, query: str, *args: Any) -> str:
        async with self._pool.acquire() as conn:
            status: str = await conn.execute(query, *args)
            return status
