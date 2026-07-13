"""Qdrant adapter for code-chunk vectors.

One collection (`code_chunks`) holds every repository, partitioned by an
indexed `repo_id` payload field — the same multi-tenancy pattern as the graph.
The collection is created lazily with the configured embedding dimension;
changing the embedding model requires a re-index (ADR-0008).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client import models as qm

from ..config import Settings

if TYPE_CHECKING:
    # Type-only: importing the indexing package at runtime would be circular
    # (indexing.pipeline imports this module).
    from ..indexing.chunking import Chunk

logger = structlog.get_logger(__name__)

COLLECTION = "code_chunks"


@dataclass(frozen=True, slots=True)
class ChunkHit:
    score: float
    path: str
    language: str
    fqn: str | None
    kind: str
    start_line: int
    end_line: int
    text: str


class QdrantVectorStore:
    def __init__(self, settings: Settings) -> None:
        self._client = AsyncQdrantClient(url=settings.qdrant_url)
        self._dim = settings.embed_dim

    async def ensure_collection(self) -> None:
        if await self._client.collection_exists(COLLECTION):
            return
        await self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(
                size=self._dim, distance=qm.Distance.COSINE
            ),
        )
        for field in ("repo_id", "path"):
            await self._client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        logger.info("qdrant collection created", collection=COLLECTION, dim=self._dim)

    async def upsert_chunks(
        self, repo_id: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunk/vector count mismatch: {len(chunks)} != {len(vectors)}"
            )
        points = [
            qm.PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    "repo_id": repo_id,
                    "path": chunk.path,
                    "language": chunk.language,
                    "fqn": chunk.fqn,
                    "kind": chunk.kind,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "text": chunk.text,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self._client.upsert(collection_name=COLLECTION, points=points)

    async def delete_paths(self, repo_id: str, paths: list[str]) -> None:
        if not paths:
            return
        await self._client.delete(
            collection_name=COLLECTION,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="repo_id", match=qm.MatchValue(value=repo_id)
                        ),
                        qm.FieldCondition(key="path", match=qm.MatchAny(any=paths)),
                    ]
                )
            ),
        )

    async def purge_repo(self, repo_id: str) -> None:
        await self._client.delete(
            collection_name=COLLECTION,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="repo_id", match=qm.MatchValue(value=repo_id)
                        )
                    ]
                )
            ),
        )

    async def search(
        self, repo_id: str, vector: list[float], *, limit: int = 10
    ) -> list[ChunkHit]:
        response = await self._client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=limit,
            with_payload=True,
            query_filter=qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="repo_id", match=qm.MatchValue(value=repo_id)
                    )
                ]
            ),
        )
        hits: list[ChunkHit] = []
        for point in response.points:
            payload: dict[str, Any] = point.payload or {}
            hits.append(
                ChunkHit(
                    score=point.score,
                    path=payload.get("path", ""),
                    language=payload.get("language", ""),
                    fqn=payload.get("fqn"),
                    kind=payload.get("kind", ""),
                    start_line=payload.get("start_line", 0),
                    end_line=payload.get("end_line", 0),
                    text=payload.get("text", ""),
                )
            )
        return hits

    async def count(self, repo_id: str) -> int:
        result = await self._client.count(
            collection_name=COLLECTION,
            count_filter=qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="repo_id", match=qm.MatchValue(value=repo_id)
                    )
                ]
            ),
            exact=True,
        )
        return result.count

    async def health(self) -> bool:
        try:
            await self._client.get_collections()
        except Exception:  # noqa: BLE001 - any transport failure means unhealthy
            return False
        return True

    async def aclose(self) -> None:
        await self._client.close()
