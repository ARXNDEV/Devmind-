"""Indexing orchestrator.

Full index rebuilds the repo's graph from scratch; incremental index re-parses
only files whose content hash changed and deletes those that disappeared,
re-resolving edges for the touched files. Index-run state and per-file hashes
persist to Postgres; symbols/edges to Neo4j.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID, uuid4

import structlog

from ..config import Settings, get_settings
from ..graph.base import CallRef, GraphFile, ImportRef, InheritRef
from ..graph.neo4j_graph import Neo4jCodeGraph
from ..parsing import extract_file
from ..parsing.ir import FileIR, SymbolDef
from ..store.db import Database
from ..store.repositories import FileStateStore, IndexRunStore
from .acquire import acquire
from .fileset import SourceFile, walk_source_files
from .snapshot import snapshot_tree

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IndexRequest:
    repo_id: UUID
    org_id: UUID
    source: str  # git URL or local path
    ref: str | None = None
    token: str | None = None
    mode: str = "auto"  # "auto" | "full" | "incremental"


@dataclass(frozen=True, slots=True)
class IndexResult:
    run_id: UUID
    mode: str
    commit_sha: str
    files_indexed: int
    files_deleted: int
    stats: dict[str, int]


class IndexingPipeline:
    def __init__(
        self,
        *,
        db: Database,
        graph: Neo4jCodeGraph,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._graph = graph
        self._settings = settings or get_settings()
        self._runs = IndexRunStore(db)
        self._files = FileStateStore(db)

    async def run(self, request: IndexRequest) -> IndexResult:
        repo_id_str = str(request.repo_id)
        acquired = await acquire(
            request.source, ref=request.ref, token=request.token
        )
        run_id = uuid4()
        started = time.monotonic()
        try:
            await self._graph.ensure_constraints()
            previous_commit = await self._runs.latest_indexed_commit(request.repo_id)
            mode = self._decide_mode(request.mode, previous_commit)

            await self._runs.create(
                run_id=run_id,
                repository_id=request.repo_id,
                org_id=request.org_id,
                commit_sha=acquired.commit_sha,
                base_commit_sha=previous_commit if mode == "incremental" else None,
                mode=mode,
            )

            # Snapshot is best-effort and must not block indexing in dev.
            await snapshot_tree(
                self._settings,
                repo_id=repo_id_str,
                commit_sha=acquired.commit_sha,
                local_dir=acquired.local_dir,
            )

            present = {sf.path: sf for sf in walk_source_files(acquired.local_dir)}
            changed, deleted = await self._diff(request.repo_id, present, mode)

            if mode == "full":
                await self._graph.purge_repo(repo_id_str)

            # Remove disappeared/changed files from the graph before rewriting.
            await self._graph.delete_files(repo_id_str, [*deleted, *changed])
            await self._files.delete_paths(request.repo_id, deleted)

            indexed = await self._index_files(
                repo_id_str, run_id, request.repo_id, [present[p] for p in changed]
            )

            stats = await self._graph.repo_stats(repo_id_str)
            stats["duration_ms"] = int((time.monotonic() - started) * 1000)
            await self._runs.finish(run_id, status="succeeded", stats=stats)

            logger.info(
                "index run complete",
                run_id=str(run_id), mode=mode, indexed=indexed,
                deleted=len(deleted), **stats,
            )
            return IndexResult(
                run_id=run_id,
                mode=mode,
                commit_sha=acquired.commit_sha,
                files_indexed=indexed,
                files_deleted=len(deleted),
                stats=stats,
            )
        except Exception as exc:
            await self._runs.finish(
                run_id, status="failed", error={"message": str(exc)}
            )
            logger.exception("index run failed", run_id=str(run_id))
            raise
        finally:
            await acquired.cleanup()

    def _decide_mode(self, requested: str, previous_commit: str | None) -> str:
        if requested == "full" or previous_commit is None:
            return "full"
        if requested == "incremental":
            return "incremental"
        return "incremental"  # auto with a prior successful run

    async def _diff(
        self, repo_id: UUID, present: dict[str, SourceFile], mode: str
    ) -> tuple[list[str], list[str]]:
        """Return (changed_or_new_paths, deleted_paths)."""
        if mode == "full":
            return list(present), []
        stored = await self._files.all_for_repo(repo_id)
        changed = [
            path
            for path, sf in present.items()
            if path not in stored or stored[path].content_hash != sf.content_hash
        ]
        deleted = [path for path in stored if path not in present]
        return changed, deleted

    async def _index_files(
        self,
        repo_id_str: str,
        run_id: UUID,
        repo_id: UUID,
        files: list[SourceFile],
    ) -> int:
        if not files:
            return 0

        graph_files: list[GraphFile] = []
        symbols_by_path: dict[str, list[SymbolDef]] = {}
        calls: list[CallRef] = []
        inherits: list[InheritRef] = []
        imports: list[ImportRef] = []
        irs: list[tuple[SourceFile, FileIR]] = []

        for sf in files:
            ir = extract_file(sf.path, sf.content)
            if ir is None:
                continue
            irs.append((sf, ir))
            graph_files.append(
                GraphFile(path=sf.path, language=sf.language,
                          content_hash=sf.content_hash)
            )
            symbols_by_path[sf.path] = ir.symbols
            for c in ir.calls:
                calls.append(CallRef(sf.path, c.caller_fqn, c.callee_name))
            for h in ir.inheritance:
                inherits.append(
                    InheritRef(sf.path, h.subclass_fqn, h.base_name, h.kind)
                )
            for imp in ir.imports:
                imports.append(ImportRef(sf.path, imp.module))

        # Persist symbols first so within-run and cross-file resolution can see
        # every definition before edges are resolved.
        await self._graph.write_files_and_symbols(
            repo_id_str, graph_files, symbols_by_path
        )
        await self._graph.resolve_calls(repo_id_str, calls)
        await self._graph.resolve_inheritance(repo_id_str, inherits)
        await self._graph.write_imports(repo_id_str, imports)

        for sf, ir in irs:
            await self._files.upsert(
                repository_id=repo_id,
                path=sf.path,
                content_hash=sf.content_hash,
                language=sf.language,
                symbol_count=len(ir.symbols),
                run_id=run_id,
            )
        return len(irs)
