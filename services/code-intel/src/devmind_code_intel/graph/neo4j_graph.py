"""Neo4j implementation of CodeGraphPort.

Writes are batched with UNWIND. Resolution is name-based within a repository:
a call/inheritance target that matches one or more symbols becomes a resolved
edge; a target with no match becomes an edge to a :Name node, so "no edge" means
"no such reference" while "unresolved edge" means "referenced, target unknown".
"""

from __future__ import annotations

from typing import Any

import structlog
from neo4j import AsyncGraphDatabase

from ..config import Settings, get_settings
from ..parsing.ir import SymbolDef
from .base import (
    CALLABLE_KINDS,
    MODULE_FQN,
    TYPE_KINDS,
    CallRef,
    GraphFile,
    ImportRef,
    InheritRef,
    file_id,
    symbol_id,
)

logger = structlog.get_logger(__name__)

_BATCH = 1000


def _clamp_depth(depth: int) -> int:
    # Depth is interpolated into the Cypher pattern (var-length bounds cannot be
    # parameterized), so it must be a validated int, never user text.
    return max(1, min(int(depth), 10))


class Neo4jCodeGraph:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_url,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        )

    async def close(self) -> None:
        await self._driver.close()

    async def ensure_constraints(self) -> None:
        stmts = [
            "CREATE CONSTRAINT symbol_id IF NOT EXISTS "
            "FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT file_id IF NOT EXISTS "
            "FOR (f:File) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT name_id IF NOT EXISTS "
            "FOR (n:Name) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT module_id IF NOT EXISTS "
            "FOR (m:Module) REQUIRE m.id IS UNIQUE",
            "CREATE INDEX symbol_repo_name IF NOT EXISTS "
            "FOR (s:Symbol) ON (s.repo_id, s.name)",
            "CREATE INDEX symbol_repo_fqn IF NOT EXISTS "
            "FOR (s:Symbol) ON (s.repo_id, s.fqn)",
        ]
        async with self._driver.session() as session:
            for stmt in stmts:
                await session.run(stmt)

    # ── writes ────────────────────────────────────────────────────────────────
    async def delete_files(self, repo_id: str, paths: list[str]) -> None:
        if not paths:
            return
        ids = [file_id(repo_id, p) for p in paths]
        async with self._driver.session() as session:
            for chunk in _chunks(ids, _BATCH):
                await session.run(
                    """
                    UNWIND $ids AS fid
                    MATCH (f:File {id: fid})
                    OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
                    DETACH DELETE s, f
                    """,
                    ids=chunk,
                )

    async def write_files_and_symbols(
        self,
        repo_id: str,
        files: list[GraphFile],
        symbols_by_path: dict[str, list[SymbolDef]],
    ) -> None:
        file_rows = [
            {
                "id": file_id(repo_id, f.path),
                "repo_id": repo_id,
                "path": f.path,
                "language": f.language,
                "content_hash": f.content_hash,
                "module_id": symbol_id(repo_id, f.path, MODULE_FQN),
            }
            for f in files
        ]
        async with self._driver.session() as session:
            for chunk in _chunks(file_rows, _BATCH):
                # Each file carries a companion `<module>` symbol so module-level
                # calls have a Symbol to originate from.
                await session.run(
                    """
                    UNWIND $rows AS r
                    MERGE (f:File {id: r.id})
                      SET f.repo_id = r.repo_id, f.path = r.path,
                          f.language = r.language, f.content_hash = r.content_hash
                    MERGE (m:Symbol {id: r.module_id})
                      SET m.repo_id = r.repo_id, m.path = r.path,
                          m.fqn = '<module>', m.name = r.path,
                          m.kind = 'module'
                    MERGE (f)-[:DEFINES]->(m)
                    """,
                    rows=chunk,
                )

            symbol_rows = [
                {
                    "id": symbol_id(repo_id, path, s.fqn),
                    "repo_id": repo_id,
                    "path": path,
                    "file_id": file_id(repo_id, path),
                    "fqn": s.fqn,
                    "name": s.name,
                    "kind": s.kind.value,
                    "signature": s.signature,
                    "docstring": s.docstring,
                    "start_line": s.span.start_line,
                    "end_line": s.span.end_line,
                }
                for path, symbols in symbols_by_path.items()
                for s in symbols
            ]
            for chunk in _chunks(symbol_rows, _BATCH):
                await session.run(
                    """
                    UNWIND $rows AS r
                    MATCH (f:File {id: r.file_id})
                    MERGE (s:Symbol {id: r.id})
                      SET s.repo_id = r.repo_id, s.path = r.path, s.fqn = r.fqn,
                          s.name = r.name, s.kind = r.kind, s.signature = r.signature,
                          s.docstring = r.docstring, s.start_line = r.start_line,
                          s.end_line = r.end_line
                    MERGE (f)-[:DEFINES]->(s)
                    """,
                    rows=chunk,
                )

    async def resolve_calls(self, repo_id: str, calls: list[CallRef]) -> None:
        rows = [
            {
                "caller_id": symbol_id(repo_id, c.caller_path, c.caller_fqn),
                "callee_name": c.callee_name,
            }
            for c in calls
        ]
        async with self._driver.session() as session:
            for chunk in _chunks(rows, _BATCH):
                # Resolved: link to every callable symbol sharing the name, with
                # confidence inversely proportional to candidate count.
                await session.run(
                    """
                    UNWIND $rows AS r
                    MATCH (caller:Symbol {id: r.caller_id})
                    MATCH (callee:Symbol {repo_id: $repo, name: r.callee_name})
                    WHERE callee.kind IN $callable AND callee.id <> caller.id
                    WITH caller, r, collect(callee) AS callees
                    UNWIND callees AS callee
                    MERGE (caller)-[rel:CALLS]->(callee)
                      SET rel.confidence = 1.0 / size(callees)
                    """,
                    rows=chunk,
                    repo=repo_id,
                    callable=list(CALLABLE_KINDS),
                )
                # Unresolved: no callable of that name in the repo.
                await session.run(
                    """
                    UNWIND $rows AS r
                    MATCH (caller:Symbol {id: r.caller_id})
                    WHERE NOT EXISTS {
                      MATCH (x:Symbol {repo_id: $repo, name: r.callee_name})
                      WHERE x.kind IN $callable AND x.id <> caller.id
                    }
                    MERGE (n:Name {id: $repo + '\x1f' + r.callee_name})
                      ON CREATE SET n.repo_id = $repo, n.name = r.callee_name
                    MERGE (caller)-[:CALLS_UNRESOLVED]->(n)
                    """,
                    rows=chunk,
                    repo=repo_id,
                    callable=list(CALLABLE_KINDS),
                )

    async def resolve_inheritance(
        self, repo_id: str, edges: list[InheritRef]
    ) -> None:
        rows = [
            {
                "sub_id": symbol_id(repo_id, e.subclass_path, e.subclass_fqn),
                "base_name": e.base_name,
                "rel": "IMPLEMENTS" if e.kind == "implements" else "INHERITS",
            }
            for e in edges
        ]
        async with self._driver.session() as session:
            for rel in ("INHERITS", "IMPLEMENTS"):
                subset = [r for r in rows if r["rel"] == rel]
                for chunk in _chunks(subset, _BATCH):
                    await session.run(
                        f"""
                        UNWIND $rows AS r
                        MATCH (sub:Symbol {{id: r.sub_id}})
                        OPTIONAL MATCH (base:Symbol {{repo_id: $repo, name: r.base_name}})
                          WHERE base.kind IN $types AND base.id <> sub.id
                        FOREACH (_ IN CASE WHEN base IS NOT NULL THEN [1] ELSE [] END |
                          MERGE (sub)-[:{rel}]->(base))
                        FOREACH (_ IN CASE WHEN base IS NULL THEN [1] ELSE [] END |
                          MERGE (n:Name {{id: $repo + '\x1f' + r.base_name}})
                            ON CREATE SET n.repo_id = $repo, n.name = r.base_name
                          MERGE (sub)-[:{rel}]->(n))
                        """,
                        rows=chunk,
                        repo=repo_id,
                        types=list(TYPE_KINDS),
                    )

    async def write_imports(self, repo_id: str, imports: list[ImportRef]) -> None:
        rows = [
            {
                "file_id": file_id(repo_id, i.path),
                "module_id": f"{repo_id}\x1f{i.module}",
                "module": i.module,
            }
            for i in imports
        ]
        async with self._driver.session() as session:
            for chunk in _chunks(rows, _BATCH):
                await session.run(
                    """
                    UNWIND $rows AS r
                    MATCH (f:File {id: r.file_id})
                    MERGE (m:Module {id: r.module_id})
                      ON CREATE SET m.repo_id = $repo, m.name = r.module
                    MERGE (f)-[:IMPORTS]->(m)
                    """,
                    rows=chunk,
                    repo=repo_id,
                )

    # ── queries ─────────────────────────────────────────────────────────────
    async def neighborhood(
        self, repo_id: str, fqn_path: tuple[str, str], depth: int
    ) -> dict[str, Any]:
        fqn, path = fqn_path
        sid = symbol_id(repo_id, path, fqn)
        d = _clamp_depth(depth)
        async with self._driver.session() as session:
            result = await session.run(
                f"""
                MATCH (s:Symbol {{id: $sid}})
                OPTIONAL MATCH (s)-[:CALLS*1..{d}]->(callee:Symbol)
                WITH s, collect(DISTINCT callee {{.fqn, .name, .kind, .path}}) AS callees
                OPTIONAL MATCH (caller:Symbol)-[:CALLS*1..{d}]->(s)
                RETURN s {{.fqn, .name, .kind, .path, .signature}} AS root,
                       callees,
                       collect(DISTINCT caller {{.fqn, .name, .kind, .path}}) AS callers
                """,
                sid=sid,
            )
            record = await result.single()
            if record is None or record["root"] is None:
                return {"found": False}
            return {
                "found": True,
                "symbol": record["root"],
                "callees": record["callees"],
                "callers": record["callers"],
            }

    async def impact_analysis(
        self, repo_id: str, fqn_path: tuple[str, str], depth: int
    ) -> dict[str, Any]:
        fqn, path = fqn_path
        sid = symbol_id(repo_id, path, fqn)
        d = _clamp_depth(depth)
        async with self._driver.session() as session:
            result = await session.run(
                f"""
                MATCH (s:Symbol {{id: $sid}})
                OPTIONAL MATCH (caller:Symbol)-[:CALLS*1..{d}]->(s)
                WITH s, collect(DISTINCT caller) AS callers
                RETURN s {{.fqn, .name, .kind, .path}} AS root,
                       size(callers) AS dependent_count,
                       [c IN callers | c {{.fqn, .name, .kind, .path}}] AS dependents,
                       size([c IN callers WHERE c.path <> s.path]) AS cross_file_count
                """,
                sid=sid,
            )
            record = await result.single()
            if record is None or record["root"] is None:
                return {"found": False}
            dependent = record["dependent_count"]
            cross = record["cross_file_count"]
            # Simple, explainable risk score in [0,1]: fan-in with a cross-file
            # premium, saturating. Refined in later phases with churn/tests.
            risk = min(1.0, (dependent + cross) / 50.0)
            return {
                "found": True,
                "symbol": record["root"],
                "dependent_count": dependent,
                "cross_file_count": cross,
                "risk_score": round(risk, 3),
                "dependents": record["dependents"][:100],
            }

    async def list_files(self, repo_id: str) -> list[dict[str, Any]]:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (f:File {repo_id: $repo})
                OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
                WHERE s.kind <> 'module'
                RETURN f.path AS path, f.language AS language,
                       count(s) AS symbol_count
                ORDER BY f.path
                """,
                repo=repo_id,
            )
            return [dict(record) async for record in result]

    async def file_symbols(self, repo_id: str, path: str) -> list[dict[str, Any]]:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (:File {id: $repo + '\x1f' + $path})-[:DEFINES]->(s:Symbol)
                WHERE s.kind <> 'module'
                RETURN s.fqn AS fqn, s.name AS name, s.kind AS kind,
                       s.signature AS signature, s.start_line AS start_line,
                       s.end_line AS end_line
                ORDER BY s.start_line
                """,
                repo=repo_id,
                path=path,
            )
            return [dict(record) async for record in result]

    async def repo_stats(self, repo_id: str) -> dict[str, int]:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (s:Symbol {repo_id: $repo})
                WITH count(s) AS symbols
                MATCH (f:File {repo_id: $repo})
                WITH symbols, count(f) AS files
                OPTIONAL MATCH (:Symbol {repo_id: $repo})-[c:CALLS]->()
                WITH symbols, files, count(c) AS calls
                OPTIONAL MATCH (:Symbol {repo_id: $repo})-[u:CALLS_UNRESOLVED]->()
                RETURN symbols, files, calls, count(u) AS unresolved_calls
                """,
                repo=repo_id,
            )
            record = await result.single()
            if record is None:
                return {"files": 0, "symbols": 0, "calls": 0, "unresolved_calls": 0}
            return {
                "files": record["files"],
                "symbols": record["symbols"],
                "calls": record["calls"],
                "unresolved_calls": record["unresolved_calls"],
            }

    async def purge_repo(self, repo_id: str) -> None:
        async with self._driver.session() as session:
            for label in ("Symbol", "File", "Module", "Name"):
                await session.run(
                    f"MATCH (n:{label} {{repo_id: $repo}}) DETACH DELETE n",
                    repo=repo_id,
                )


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
