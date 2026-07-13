"""Go extractor.

Emits functions, methods (qualified by receiver type), structs (as classes),
interfaces, package-level vars/consts, imports, and calls. Go favors
composition over inheritance, so no inheritance edges are emitted.
"""

from __future__ import annotations

from tree_sitter import Node

from ._common import count_errors, join_fqn, node_text, span_of
from .ir import CallSite, FileIR, ImportEdge, SymbolDef, SymbolKind

_MODULE_CALLER = "<module>"


class GoExtractor:
    def extract(self, path: str, source: bytes, root: Node) -> FileIR:
        ir = FileIR(path=path, language="go", parse_errors=count_errors(root))
        self._visit(root, ir, caller=_MODULE_CALLER)
        return ir

    def _visit(self, node: Node, ir: FileIR, *, caller: str) -> None:
        kind = node.type
        if kind == "function_declaration":
            self._function(node, ir, receiver=None)
            return
        if kind == "method_declaration":
            self._function(node, ir, receiver=self._receiver_type(node))
            return
        if kind == "type_declaration":
            self._type_decl(node, ir)
            return
        if kind == "import_declaration":
            self._import(node, ir)
            return
        if kind == "call_expression":
            self._call(node, ir, caller)

        for child in node.children:
            self._visit(child, ir, caller=caller)

    def _function(self, node: Node, ir: FileIR, *, receiver: str | None) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = join_fqn(receiver, name)
        params = node.child_by_field_name("parameters")
        ir.symbols.append(
            SymbolDef(
                fqn=fqn, name=name, kind=SymbolKind.METHOD if receiver else
                SymbolKind.FUNCTION,
                span=span_of(node),
                signature=f"{name}{node_text(params)}" if params else name,
                parent_fqn=receiver,
            )
        )
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(body, ir, caller=fqn)

    def _receiver_type(self, node: Node) -> str | None:
        receiver = node.child_by_field_name("receiver")
        if receiver is None:
            return None
        for param in receiver.children:
            if param.type == "parameter_declaration":
                type_node = param.child_by_field_name("type")
                if type_node is not None:
                    # Strip a leading '*' for pointer receivers.
                    return node_text(type_node).lstrip("*")
        return None

    def _type_decl(self, node: Node, ir: FileIR) -> None:
        for spec in node.children:
            if spec.type != "type_spec":
                continue
            name_node = spec.child_by_field_name("name")
            type_node = spec.child_by_field_name("type")
            if name_node is None:
                continue
            name = node_text(name_node)
            kind = SymbolKind.CLASS
            if type_node is not None and type_node.type == "interface_type":
                kind = SymbolKind.INTERFACE
            ir.symbols.append(
                SymbolDef(fqn=name, name=name, kind=kind, span=span_of(spec),
                          signature=name, parent_fqn=None)
            )

    def _call(self, node: Node, ir: FileIR, caller: str) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        if fn.type == "selector_expression":
            field = fn.child_by_field_name("field")
            callee = node_text(field) if field else node_text(fn)
        else:
            callee = node_text(fn)
        ir.calls.append(CallSite(caller, callee, span_of(node)))

    def _import(self, node: Node, ir: FileIR) -> None:
        for spec in _import_specs(node):
            path_node = spec.child_by_field_name("path")
            if path_node is not None:
                ir.imports.append(
                    ImportEdge(module=node_text(path_node).strip('"'))
                )


def _import_specs(node: Node) -> list[Node]:
    specs: list[Node] = []
    stack = list(node.children)
    while stack:
        n = stack.pop()
        if n.type == "import_spec":
            specs.append(n)
        else:
            stack.extend(n.children)
    return specs
