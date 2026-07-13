"""DevMind code-intelligence engine.

Internal-only service (ADR-0003): owns parsing, graph construction,
retrieval, log intelligence, and agent execution. Never internet-facing;
all product state flows through apps/api via the internal contract.
"""

__version__ = "0.1.0"
