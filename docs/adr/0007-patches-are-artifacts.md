# ADR-0007: Patches are reviewable artifacts; the platform never mutates customer systems

**Status:** Accepted · 2026-07-09

## Context

The product generates fixes for production incidents. The trust ceiling for an AI platform inside a legacy enterprise is set by the worst thing it could do autonomously. A platform that can write to customer repositories or production systems is a platform a CISO will veto.

## Decision

- The Patch agent emits **unified diff artifacts** stored in MinIO and registered as immutable `patch_proposals` (new revision per change), each carrying rationale, per-change explanation, risk notes, affected files, generated tests, and rollback instructions.
- Verification applies the patch only inside the ephemeral sandbox (ADR-scoped in [08 — Security](../architecture/08-security.md)); results attach to the proposal.
- Human review (approve/reject) is a hard gate in the workflow state machine. The platform's outbound git capability is limited, at most, to opening a pull request on an approved patch (Phase 6+, per-org opt-in) — never pushing to protected branches, never touching runtime systems.

## Consequences

- "Time to resolution" always includes a human in the loop; we compete on how good the proposal and its evidence are, not on autonomy theater.
- Auditability is structural: every applied fix traces to a proposal, an agent run, its evidence, and a human approval.
- If the market later demands auto-remediation for narrow cases, it must arrive as a new, separately-gated capability with its own ADR — not a relaxation of this one.
