"""Tree-sitter parsing and language-neutral IR extraction.

Code is never treated as plain text here: each supported language has an
extractor that walks the concrete syntax tree and emits the shared IR in
`ir.py`. Extractors are the only language-specific code in the engine — adding
a language means adding one extractor module (03-code-intelligence.md).
"""

from .extractor import EXTRACTORS, extract_file
from .ir import (
    CallSite,
    FileIR,
    ImportEdge,
    InheritanceEdge,
    Reference,
    SymbolDef,
    SymbolKind,
)
from .languages import detect_language

__all__ = [
    "EXTRACTORS",
    "CallSite",
    "FileIR",
    "ImportEdge",
    "InheritanceEdge",
    "Reference",
    "SymbolDef",
    "SymbolKind",
    "detect_language",
    "extract_file",
]
