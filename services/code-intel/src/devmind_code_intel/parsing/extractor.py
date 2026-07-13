"""Extractor registry and the single public entry point, `extract_file`."""

from __future__ import annotations

from typing import Protocol

import structlog
from tree_sitter import Node

from .go_extractor import GoExtractor
from .ir import FileIR
from .java_extractor import JavaExtractor
from .languages import detect_language, get_parser
from .python_extractor import PythonExtractor
from .typescript_extractor import TypeScriptExtractor

logger = structlog.get_logger(__name__)

# Files larger than this are indexed lexically only (03-code-intelligence.md).
MAX_PARSE_BYTES = 2 * 1024 * 1024


class Extractor(Protocol):
    def extract(self, path: str, source: bytes, root: Node) -> FileIR: ...


_python = PythonExtractor()
_typescript = TypeScriptExtractor()
_java = JavaExtractor()
_go = GoExtractor()

# Canonical language name → extractor. JS and TSX reuse the TS extractor: the
# grammars share the node types the extractor relies on.
EXTRACTORS: dict[str, Extractor] = {
    "python": _python,
    "typescript": _typescript,
    "javascript": _typescript,
    "tsx": _typescript,
    "java": _java,
    "go": _go,
}


def extract_file(path: str, source: bytes) -> FileIR | None:
    """Parse and extract IR for one file, or None if the language is unsupported.

    Never raises on malformed input: a parse failure yields a FileIR with
    parse_errors set and whatever partial IR was recoverable.
    """
    language = detect_language(path)
    if language is None or language not in EXTRACTORS:
        return None

    if len(source) > MAX_PARSE_BYTES:
        logger.info("file too large for AST parse; lexical-only", path=path)
        return FileIR(path=path, language=language, parse_errors=1)

    try:
        parser = get_parser(language)
        tree = parser.parse(source)
        return EXTRACTORS[language].extract(path, source, tree.root_node)
    except Exception:  # noqa: BLE001 - one bad file must not kill an index run
        logger.exception("extraction failed", path=path, language=language)
        return FileIR(path=path, language=language, parse_errors=1)
