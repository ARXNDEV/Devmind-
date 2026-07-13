"""Semantic code search: embed the query, retrieve chunks, enrich with graph.

This is the dense leg of hybrid retrieval (04-hybrid-retrieval) plus graph
enrichment — sparse/BM25 and rank fusion land later; the response shape
already carries everything the context assembler and UI need (citations via
path + line range, structural context via callers/callees).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import structlog

from ..graph.neo4j_graph import Neo4jCodeGraph
from ..models.base import EmbeddingProvider
from .vector_store import QdrantVectorStore

logger = structlog.get_logger(__name__)

# Graph round-trips are per-hit; only the head of the ranking is worth them.
_ENRICH_TOP_N = 3


@dataclass(frozen=True, slots=True)
class SearchResult:
    score: float
    path: str
    language: str
    fqn: str | None
    kind: str
    start_line: int
    end_line: int
    text: str
    graph_context: dict[str, Any] | None = None


class SemanticSearch:
    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        vectors: QdrantVectorStore,
        graph: Neo4jCodeGraph,
    ) -> None:
        self._embedder = embedder
        self._vectors = vectors
        self._graph = graph

    async def search(
        self, repo_id: str, query: str, *, limit: int = 10
    ) -> list[SearchResult]:
        [vector] = await self._embedder.embed([query])
        hits = await self._vectors.search(repo_id, vector, limit=limit)

        results: list[SearchResult] = []
        for rank, hit in enumerate(hits):
            graph_context: dict[str, Any] | None = None
            if rank < _ENRICH_TOP_N and hit.fqn is not None:
                graph_context = await self._neighborhood(repo_id, hit.fqn, hit.path)
            results.append(SearchResult(**asdict(hit), graph_context=graph_context))
        return results

    async def _neighborhood(
        self, repo_id: str, fqn: str, path: str
    ) -> dict[str, Any] | None:
        """Best-effort structural context; a graph miss must not fail search."""
        try:
            context: dict[str, Any] = await self._graph.neighborhood(
                repo_id, (fqn, path), 1
            )
            return context
        except Exception:  # noqa: BLE001
            logger.warning("graph enrichment failed", fqn=fqn, path=path)
            return None
