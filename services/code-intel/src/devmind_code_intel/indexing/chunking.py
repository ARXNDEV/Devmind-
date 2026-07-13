"""Symbol-aware chunking (04-hybrid-retrieval).

Chunks follow code structure, never fixed character windows: one chunk per
function/method, a header chunk per class (its docstring and fields, without
the method bodies that get their own chunks), and a module-preamble chunk for
imports and module docstrings. Oversized spans are windowed by lines so no
chunk exceeds the embedding model's useful context.

Chunk ids are deterministic (UUIDv5 of repo:path:fqn:window) so re-indexing a
file upserts in place instead of accumulating duplicates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..parsing.ir import FileIR, SymbolDef, SymbolKind

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_DNS

# Container symbols get a header chunk; their members get leaf chunks.
_CONTAINER_KINDS = frozenset({SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM})
_LEAF_KINDS = frozenset({SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.TYPE})

_MAX_WINDOW_LINES = 120
_WINDOW_OVERLAP_LINES = 20
_MAX_PREAMBLE_LINES = 80
_MAX_CHUNK_CHARS = 8_000


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable unit of code with its provenance for citations."""

    id: str
    path: str
    language: str
    fqn: str | None  # None for module preamble
    kind: str
    start_line: int  # 1-based, inclusive
    end_line: int
    text: str


def chunk_id(repo_id: str, path: str, fqn: str | None, window: int) -> str:
    return str(
        uuid.uuid5(_NAMESPACE, f"{repo_id}:{path}:{fqn or '<module>'}:{window}")
    )


def chunk_file(
    repo_id: str, path: str, language: str, content: bytes, ir: FileIR
) -> list[Chunk]:
    lines = content.decode("utf-8", errors="replace").splitlines()
    if not lines:
        return []

    chunks: list[Chunk] = []
    # Only children that get their own chunks bound the container header —
    # field/variable symbols must stay inside it.
    children_by_parent: dict[str, list[SymbolDef]] = {}
    for sym in ir.symbols:
        if sym.parent_fqn is not None and sym.kind in (
            _LEAF_KINDS | _CONTAINER_KINDS
        ):
            children_by_parent.setdefault(sym.parent_fqn, []).append(sym)

    first_symbol_line = min(
        (s.span.start_line for s in ir.symbols), default=len(lines) + 1
    )

    # Module preamble: imports, module docstring, top-level constants.
    preamble_end = min(first_symbol_line - 1, _MAX_PREAMBLE_LINES)
    if preamble_end >= 1:
        chunks.extend(
            _emit(repo_id, path, language, None, "module", 1, preamble_end, lines)
        )

    for sym in ir.symbols:
        if sym.kind in _LEAF_KINDS:
            chunks.extend(
                _emit(
                    repo_id, path, language, sym.fqn, sym.kind.value,
                    sym.span.start_line, sym.span.end_line, lines,
                )
            )
        elif sym.kind in _CONTAINER_KINDS:
            # Header only: stop before the first member so method bodies are
            # not embedded twice.
            first_child = min(
                (c.span.start_line for c in children_by_parent.get(sym.fqn, [])),
                default=sym.span.end_line + 1,
            )
            header_end = min(first_child - 1, sym.span.end_line)
            if header_end >= sym.span.start_line:
                chunks.extend(
                    _emit(
                        repo_id, path, language, sym.fqn, sym.kind.value,
                        sym.span.start_line, header_end, lines,
                    )
                )
    return chunks


def _emit(
    repo_id: str,
    path: str,
    language: str,
    fqn: str | None,
    kind: str,
    start_line: int,
    end_line: int,
    lines: list[str],
) -> list[Chunk]:
    """Emit one chunk for the span, windowed if it exceeds the line budget."""
    start_line = max(start_line, 1)
    end_line = min(end_line, len(lines))
    if end_line < start_line:
        return []

    chunks: list[Chunk] = []
    window = 0
    cursor = start_line
    while cursor <= end_line:
        w_end = min(cursor + _MAX_WINDOW_LINES - 1, end_line)
        body = "\n".join(lines[cursor - 1 : w_end])[:_MAX_CHUNK_CHARS]
        # Provenance header gives the embedding (and later the LLM context)
        # the location even when the identifier is generic.
        header = f"{path}:{cursor}-{w_end} {kind} {fqn or ''}".rstrip()
        chunks.append(
            Chunk(
                id=chunk_id(repo_id, path, fqn, window),
                path=path,
                language=language,
                fqn=fqn,
                kind=kind,
                start_line=cursor,
                end_line=w_end,
                text=f"{header}\n{body}",
            )
        )
        if w_end == end_line:
            break
        window += 1
        cursor = w_end + 1 - _WINDOW_OVERLAP_LINES
    return chunks
