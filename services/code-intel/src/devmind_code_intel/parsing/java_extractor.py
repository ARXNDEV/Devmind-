"""Java extractor — the flagship legacy-enterprise language.

Emits classes, interfaces, enums, methods, constructors, fields, imports,
method/constructor calls, and extends/implements edges.
"""

from __future__ import annotations

from tree_sitter import Node

from ._common import count_errors, join_fqn, node_text, span_of
from .ir import (
    CallSite,
    FileIR,
    ImportEdge,
    InheritanceEdge,
    SymbolDef,
    SymbolKind,
)

_MODULE_CALLER = "<module>"
_TYPE_DECLS = {
    "class_declaration": SymbolKind.CLASS,
    "interface_declaration": SymbolKind.INTERFACE,
    "enum_declaration": SymbolKind.ENUM,
}


class JavaExtractor:
    def extract(self, path: str, source: bytes, root: Node) -> FileIR:
        ir = FileIR(path=path, language="java", parse_errors=count_errors(root))
        self._visit(root, ir, scope_fqn=None, caller=_MODULE_CALLER)
        return ir

    def _visit(
        self, node: Node, ir: FileIR, *, scope_fqn: str | None, caller: str
    ) -> None:
        kind = node.type
        if kind in _TYPE_DECLS:
            self._type_decl(node, ir, scope_fqn, _TYPE_DECLS[kind])
            return
        if kind in ("method_declaration", "constructor_declaration"):
            self._method(node, ir, scope_fqn)
            return
        if kind == "field_declaration":
            self._field(node, ir, scope_fqn)
            return
        if kind == "import_declaration":
            self._import(node, ir)
            return
        if kind == "method_invocation":
            name = node.child_by_field_name("name")
            if name is not None:
                ir.calls.append(
                    CallSite(caller, node_text(name), span_of(node))
                )
        elif kind == "object_creation_expression":
            type_node = node.child_by_field_name("type")
            if type_node is not None:
                ir.calls.append(
                    CallSite(caller, node_text(type_node), span_of(node))
                )

        for child in node.children:
            self._visit(child, ir, scope_fqn=scope_fqn, caller=caller)

    def _type_decl(
        self, node: Node, ir: FileIR, scope_fqn: str | None, kind: SymbolKind
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = join_fqn(scope_fqn, name)
        ir.symbols.append(
            SymbolDef(fqn=fqn, name=name, kind=kind, span=span_of(node),
                      signature=name, parent_fqn=scope_fqn)
        )
        superclass = node.child_by_field_name("superclass")
        if superclass is not None:
            for t in superclass.children:
                if t.type in ("type_identifier", "scoped_type_identifier",
                              "generic_type"):
                    ir.inheritance.append(
                        InheritanceEdge(fqn, node_text(t), kind="inherits")
                    )
        interfaces = node.child_by_field_name("interfaces")
        if interfaces is not None:
            for t in _descendants(interfaces):
                if t.type in ("type_identifier", "scoped_type_identifier"):
                    ir.inheritance.append(
                        InheritanceEdge(fqn, node_text(t), kind="implements")
                    )
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(body, ir, scope_fqn=fqn, caller=_MODULE_CALLER)

    def _method(self, node: Node, ir: FileIR, scope_fqn: str | None) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = join_fqn(scope_fqn, name)
        params = node.child_by_field_name("parameters")
        ir.symbols.append(
            SymbolDef(
                fqn=fqn, name=name, kind=SymbolKind.METHOD, span=span_of(node),
                signature=f"{name}{node_text(params)}" if params else name,
                parent_fqn=scope_fqn,
            )
        )
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(body, ir, scope_fqn=fqn, caller=fqn)

    def _field(self, node: Node, ir: FileIR, scope_fqn: str | None) -> None:
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue
            name_node = declarator.child_by_field_name("name")
            if name_node is None:
                continue
            name = node_text(name_node)
            ir.symbols.append(
                SymbolDef(
                    fqn=join_fqn(scope_fqn, name), name=name,
                    kind=SymbolKind.VARIABLE, span=span_of(declarator),
                    parent_fqn=scope_fqn,
                )
            )

    def _import(self, node: Node, ir: FileIR) -> None:
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                ir.imports.append(ImportEdge(module=node_text(child)))
                return


def _descendants(node: Node) -> list[Node]:
    out: list[Node] = []
    stack = list(node.children)
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(n.children)
    return out
