"""Operational state for the engine (codeintel Postgres schema).

Holds only index-run bookkeeping and per-file hashes that drive incremental
indexing. The code graph itself lives in Neo4j, vectors in Qdrant.
"""
