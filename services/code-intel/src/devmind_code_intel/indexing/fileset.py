"""Walk a checked-out tree and yield the supported source files to index.

Applies built-in exclusion rules (VCS, dependency, build, and generated
directories; lockfiles; minified assets) so the index reflects authored code,
not vendored or generated artifacts.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from dataclasses import dataclass

from ..parsing.languages import detect_language

_IGNORED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
        "out", ".next", "__pycache__", ".venv", "venv", ".turbo", "coverage",
        ".mypy_cache", ".ruff_cache", ".pytest_cache", ".idea", ".gradle",
        "target", "bin", "obj",
    }
)

_IGNORED_FILE_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".map", ".lock")
_IGNORED_FILE_NAMES = frozenset(
    {"pnpm-lock.yaml", "package-lock.json", "yarn.lock", "poetry.lock", "uv.lock"}
)

# Read cap: files larger than this are not read into memory here; the parser
# also caps AST parsing separately.
_MAX_READ_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str  # repo-relative, forward-slashed
    language: str
    content: bytes
    content_hash: str


def _is_ignored_file(name: str) -> bool:
    if name in _IGNORED_FILE_NAMES:
        return True
    return any(name.endswith(sfx) for sfx in _IGNORED_FILE_SUFFIXES)


def walk_source_files(root: str) -> Iterator[SourceFile]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in place so os.walk doesn't descend them.
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
        for filename in filenames:
            if _is_ignored_file(filename):
                continue
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, root).replace(os.sep, "/")
            language = detect_language(rel_path)
            if language is None:
                continue
            try:
                if os.path.getsize(abs_path) > _MAX_READ_BYTES:
                    continue
                with open(abs_path, "rb") as fh:
                    content = fh.read()
            except OSError:
                continue
            yield SourceFile(
                path=rel_path,
                language=language,
                content=content,
                content_hash=hashlib.sha256(content).hexdigest(),
            )
