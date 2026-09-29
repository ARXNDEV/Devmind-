# Glossary

| Term | Meaning |
| --- | --- |
| Snapshot | An immutable, indexed state of a repository at one commit. |
| Symbol | A named code entity (function, class, method) extracted by Tree-sitter. |
| Code graph | Neo4j graph of files, modules and symbols with DEFINES/CALLS/IMPORTS/EXTENDS edges. |
| Chunk | A symbol-aware slice of source used for embedding and citation. |
| Job | A tracked, resumable background task with SSE progress. |
| Retriever | A component that returns ranked chunks for a query (dense, sparse, graph, path). |
| RRF | Reciprocal rank fusion, used to merge retriever result lists. |
| Golden set | Hand-verified question/answer pairs used by the retrieval eval harness. |
| Fingerprint | A Drain-derived template id grouping similar log lines. |
| Deploy marker | A timestamped event used to separate pre/post-deploy anomaly baselines. |
| Incident | An opened investigation tied to one or more anomalous fingerprints. |
