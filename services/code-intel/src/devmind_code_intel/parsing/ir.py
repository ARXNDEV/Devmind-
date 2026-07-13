"""Language-neutral intermediate representation.

Every extractor emits these types regardless of source language, so the graph
builder and all downstream consumers stay language-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SymbolKind(StrEnum):
    MODULE = "module"
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    TYPE = "type"
    ENUM = "enum"


@dataclass(frozen=True, slots=True)
class Span:
    start_line: int  # 1-based, inclusive
    end_line: int
    start_byte: int
    end_byte: int


@dataclass(frozen=True, slots=True)
class SymbolDef:
    """A definition site. `fqn` is unique within a file's IR."""

    fqn: str  # fully-qualified within the file, e.g. "PaymentService.settle"
    name: str
    kind: SymbolKind
    span: Span
    signature: str | None = None
    docstring: str | None = None
    parent_fqn: str | None = None  # enclosing class/function, if any


@dataclass(frozen=True, slots=True)
class CallSite:
    """A call observed inside `caller_fqn`. Resolution happens later."""

    caller_fqn: str
    callee_name: str  # textual target, e.g. "settle" or "self.settle"
    span: Span


@dataclass(frozen=True, slots=True)
class ImportEdge:
    """An import statement; `module` is the imported module/path as written."""

    module: str
    symbols: tuple[str, ...] = ()  # named imports, if any
    alias: str | None = None


@dataclass(frozen=True, slots=True)
class InheritanceEdge:
    subclass_fqn: str
    base_name: str  # textual base, resolved later
    kind: str = "inherits"  # "inherits" | "implements"


@dataclass(frozen=True, slots=True)
class Reference:
    """A non-call identifier reference from within `from_fqn`."""

    from_fqn: str
    name: str
    span: Span


@dataclass(slots=True)
class FileIR:
    """Everything extracted from a single source file."""

    path: str
    language: str
    symbols: list[SymbolDef] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    imports: list[ImportEdge] = field(default_factory=list)
    inheritance: list[InheritanceEdge] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    parse_errors: int = 0
