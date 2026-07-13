"""Small helpers shared by language extractors."""

from __future__ import annotations

from tree_sitter import Node

from .ir import Span


def node_text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def span_of(node: Node) -> Span:
    return Span(
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        start_byte=node.start_byte,
        end_byte=node.end_byte,
    )


def count_errors(root: Node) -> int:
    """Number of ERROR/MISSING nodes — a parse-quality signal."""
    if not root.has_error:
        return 0
    count = 0
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "ERROR" or n.is_missing:
            count += 1
        stack.extend(n.children)
    return count


def join_fqn(parent: str | None, name: str) -> str:
    return f"{parent}.{name}" if parent else name
