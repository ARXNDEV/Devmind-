"""Indexing pipeline: repository → code graph.

Orchestrates acquire → snapshot → walk → parse/extract → persist-graph →
resolve, with content-hash-based incremental re-indexing. See
03-code-intelligence.md.
"""

from .pipeline import IndexingPipeline, IndexRequest, IndexResult

__all__ = ["IndexRequest", "IndexResult", "IndexingPipeline"]
