# FAQ

**Is this a RAG chatbot?**
No. Retrieval is one input to a code-intelligence engine that parses code into a graph and reasons over it with agents.

**Which languages are supported?**
TypeScript/JavaScript, Python and Java in the first extractors. More follow the Tree-sitter grammar list.

**Does it apply patches automatically?**
Never. Patches are reviewed artifacts (ADR-0007).

**Can it run fully on-prem?**
Yes. Model serving is local by default (ADR-0008).

**How long does indexing take?**
First index of a few hundred kLOC takes minutes; later runs are incremental and re-parse only changed files.

**Does source code leave the host?**
Not by default. Embeddings and completions go to the local gateway unless an org opts into a cloud model.
