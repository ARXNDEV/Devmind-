"""CodeGraphPort interface and its value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..parsing.ir import SymbolDef

# Field separator for composite ids. Unit Separator (0x1f) cannot appear in a
# path or an identifier, so ids are collision-free without escaping.
_SEP = "\x1f"

MODULE_FQN = "<module>"
CALLABLE_KINDS = ("function", "method")
TYPE_KINDS = ("class", "interface")


def symbol_id(repo_id: str, path: str, fqn: str) -> str:
    return f"{repo_id}{_SEP}{path}{_SEP}{fqn}"


def file_id(repo_id: str, path: str) -> str:
    return f"{repo_id}{_SEP}{path}"


@dataclass(frozen=True, slots=True)
class GraphFile:
    path: str
    language: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class CallRef:
    caller_path: str
    caller_fqn: str
    callee_name: str


@dataclass(frozen=True, slots=True)
class InheritRef:
    subclass_path: str
    subclass_fqn: str
    base_name: str
    kind: str  # "inherits" | "implements"


@dataclass(frozen=True, slots=True)
class ImportRef:
    path: str
    module: str


class CodeGraphPort(Protocol):
    async def ensure_constraints(self) -> None: ...

    async def delete_files(self, repo_id: str, paths: list[str]) -> None: ...

    async def write_files_and_symbols(
        self,
        repo_id: str,
        files: list[GraphFile],
        symbols_by_path: dict[str, list[SymbolDef]],
    ) -> None: ...

    async def resolve_calls(self, repo_id: str, calls: list[CallRef]) -> None: ...

    async def resolve_inheritance(
        self, repo_id: str, edges: list[InheritRef]
    ) -> None: ...

    async def write_imports(self, repo_id: str, imports: list[ImportRef]) -> None: ...

    async def neighborhood(
        self, repo_id: str, fqn_path: tuple[str, str], depth: int
    ) -> dict[str, Any]: ...

    async def impact_analysis(
        self, repo_id: str, fqn_path: tuple[str, str], depth: int
    ) -> dict[str, Any]: ...

    async def repo_stats(self, repo_id: str) -> dict[str, int]: ...

    async def purge_repo(self, repo_id: str) -> None: ...

    async def close(self) -> None: ...
