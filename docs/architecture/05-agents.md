# 05 — Agent Orchestration

Agents live in `code-intel`, orchestrated with LangGraph. The design goal is a **registry of independently extensible capabilities** under one supervisor — not a swarm of free-running processes.

## Topology

One supervisor graph (the **Planner**) routes to specialist subgraphs. Each specialist is a self-contained LangGraph subgraph with its own state schema, tool allowlist, and prompt pack.

```
                         ┌─ Retrieval agent      (hybrid retrieval, context assembly)
                         ├─ Repository agent     (index status, metadata, re-index triggers)
                         ├─ Debug agent          (stack traces, log correlation, hypothesis loop)
Planner (supervisor) ────┼─ Root-Cause agent     (debug + graph + git evidence → ranked causes)
                         ├─ Patch agent          (diff generation, risk notes, test generation)
                         ├─ Verification agent   (sandboxed test/lint/build execution)
                         ├─ Documentation agent  (module/API/architecture docs, diagrams)
                         ├─ Security agent       (vuln patterns, dependency advisories)
                         ├─ Performance agent    (hotspot heuristics over graph + logs)
                         ├─ Git agent            (blame, history, PR analysis)
                         └─ Knowledge agent      (runbooks, org conventions, bug history)
```

The Planner decomposes the request, invokes specialists (sequentially or in parallel branches), and synthesizes. Specialists do not call each other directly — composition is the Planner's job. This keeps each specialist testable in isolation and prevents hidden coupling.

## Agent registry

Each agent registers a manifest:

```python
class AgentManifest(BaseModel):
    name: str                    # "debug"
    description: str             # used by the Planner for routing
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    tools: list[str]             # allowlist, enforced at runtime
    model_tier: ModelTier        # REASONING | STANDARD | FAST
    max_steps: int
    max_tokens_budget: int
```

Adding an agent = adding a package under `agents/` with a manifest, a subgraph, and tests. The Planner discovers agents from the registry; no supervisor code changes.

## Tools

Tools are thin, typed adapters over the engine — retrieval, graph queries, git operations, log queries, file reads from snapshots. Tools are pure reads except for three write tools (`propose_patch`, `record_finding`, `request_verification`), each of which creates product artifacts via the `api` contract — agents never write to databases directly.

## Model strategy

All model access goes through a `ModelProvider` port (Anthropic first; the port exists for enterprise bring-your-own-model demands, not speculative multi-provider support). Routing by tier:

- **REASONING** (root-cause synthesis, patch generation, planning): top-tier model.
- **STANDARD** (documentation, review summaries): mid-tier.
- **FAST** (query understanding, log classification, routing): small model.

Tier → model-ID mapping is configuration. Prompt caching for the static prompt pack + repo context prefix; token usage recorded per step in `agent_steps.tokens` and rolled up to `agent_runs.model_usage` for per-org cost accounting (a billing prerequisite).

## Guardrails and observability

- Hard budgets per run: max steps, max tokens, wall-clock timeout — a stuck agent fails loudly, never spins.
- Every run persisted: `agent_runs` + ordered `agent_steps` with tool calls and I/O summaries. This is the replay/debug/audit trail, and later the eval dataset.
- LangGraph checkpointing to Redis: long runs survive worker restarts; runs are resumable and cancellable (checked between nodes).
- Streaming: node-level progress + token streams published to Redis pub/sub, relayed by `api` over SSE.
- Determinism discipline: temperature 0 for structured outputs; every structured output validated against the agent's `output_schema` with one bounded repair retry.

## The verification sandbox

The Verification agent is the only component that executes customer code, and it never does so in-process: it launches an ephemeral, network-isolated container (resource-capped, read-only snapshot mount + patch applied to a tmpfs overlay), runs the project's test/lint/build commands, and captures the report. Container escape hatches (docker socket, host mounts) are never exposed to it. Full policy in [08 — Security](08-security.md).
