"""Language detection and Tree-sitter grammar access.

Grammars come from official per-language wheels (tree-sitter-python, etc.) with
the parser compiled into the wheel — no runtime download, which is required for
offline/air-gapped deployments. Parsers are cached per language and reused.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser

# Extension → canonical language name used throughout the engine.
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
}

# Canonical name → callable returning the grammar's PyCapsule. Each grammar is
# a self-contained wheel with the parser compiled in — no runtime download,
# which is a hard requirement for offline/air-gapped enterprise deployments.
_LANG_TO_GRAMMAR: dict[str, Callable[[], object]] = {
    "python": tree_sitter_python.language,
    "javascript": tree_sitter_javascript.language,
    "typescript": tree_sitter_typescript.language_typescript,
    "tsx": tree_sitter_typescript.language_tsx,
    "java": tree_sitter_java.language,
    "go": tree_sitter_go.language,
}

SUPPORTED_LANGUAGES = frozenset(_LANG_TO_GRAMMAR)


def detect_language(path: str) -> str | None:
    """Return the canonical language for a file path, or None if unsupported."""
    lower = path.lower()
    for ext, lang in _EXT_TO_LANG.items():
        if lower.endswith(ext):
            return lang
    return None


@cache
def _language(name: str) -> Language:
    return Language(_LANG_TO_GRAMMAR[name]())


@cache
def get_parser(name: str) -> Parser:
    """Cached Tree-sitter parser for a canonical language name."""
    return Parser(_language(name))
