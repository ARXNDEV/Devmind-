# Glossary

| Term | Meaning |
| --- | --- |
| Snapshot | An immutable, indexed state of a repository at one commit. |
| Symbol | A named code entity (function, class, method) extracted by Tree-sitter. |
| Code graph | Neo4j graph of files, modules and symbols with DEFINES/CALLS/IMPORTS/EXTENDS edges. |
| Chunk | A symbol-aware slice of source used for embedding and citation. |
| Job | A tracked, resumable background task with SSE progress. |
