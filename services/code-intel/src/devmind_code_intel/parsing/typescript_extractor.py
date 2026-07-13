"""TypeScript / JavaScript / TSX extractor.

One extractor covers all three: the tree-sitter-typescript and
tree-sitter-javascript grammars share the node types used here. TS-only
constructs (interface, type alias, enum) are handled when present and simply
never appear in JS trees.

Traversal model mirrors the Python extractor: `_visit` inspects each node then
recurses, with scope handlers driving their own child recursion.
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
_FUNC_VALUE_TYPES = {"arrow_function", "function", "function_expression"}
_NAMED_SYMBOL_KINDS = {
    "interface_declaration": SymbolKind.INTERFACE,
    "type_alias_declaration": SymbolKind.TYPE,
    "enum_declaration": SymbolKind.ENUM,
}


class TypeScriptExtractor:
    def extract(self, path: str, source: bytes, root: Node) -> FileIR:
        ir = FileIR(path=path, language="typescript", parse_errors=count_errors(root))
        self._visit(root, ir, scope_fqn=None, caller=_MODULE_CALLER, in_function=False)
        return ir

    def _visit(
        self,
        node: Node,
        ir: FileIR,
        *,
        scope_fqn: str | None,
        caller: str,
        in_function: bool,
    ) -> None:
        kind = node.type
        if kind in ("function_declaration", "generator_function_declaration"):
            self._function(node, ir, scope_fqn, is_method=False)
            return
        if kind == "method_definition":
            self._function(node, ir, scope_fqn, is_method=True)
            return
        if kind == "class_declaration":
            self._class(node, ir, scope_fqn)
            return
        if kind in _NAMED_SYMBOL_KINDS:
            self._named_symbol(node, ir, scope_fqn, _NAMED_SYMBOL_KINDS[kind])
            return
        if kind in ("lexical_declaration", "variable_declaration"):
            self._declaration(node, ir, scope_fqn, caller, in_function)
            return
        if kind == "import_statement":
            self._import(node, ir)
            return
        if kind == "call_expression":
            self._call(node, ir, caller)
            # fall through to recurse arguments for nested calls

        for child in node.children:
            self._visit(child, ir, scope_fqn=scope_fqn, caller=caller,
                        in_function=in_function)

    def _function(
        self, node: Node, ir: FileIR, scope_fqn: str | None, *, is_method: bool
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = join_fqn(scope_fqn, name)
        params = node.child_by_field_name("parameters")
        signature = f"{name}{node_text(params)}" if params else name
        ir.symbols.append(
            SymbolDef(
                fqn=fqn,
                name=name,
                kind=SymbolKind.METHOD if is_method else SymbolKind.FUNCTION,
                span=span_of(node),
                signature=signature,
                parent_fqn=scope_fqn,
            )
        )
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(body, ir, scope_fqn=fqn, caller=fqn, in_function=True)

    def _class(self, node: Node, ir: FileIR, scope_fqn: str | None) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = join_fqn(scope_fqn, name)
        ir.symbols.append(
            SymbolDef(
                fqn=fqn, name=name, kind=SymbolKind.CLASS,
                span=span_of(node), signature=name, parent_fqn=scope_fqn,
            )
        )
        for child in node.children:
            if child.type == "class_heritage":
                self._heritage(child, ir, fqn)
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(body, ir, scope_fqn=fqn, caller=_MODULE_CALLER,
                        in_function=False)

    def _heritage(self, heritage: Node, ir: FileIR, subclass_fqn: str) -> None:
        def base_names(container: Node) -> list[str]:
            return [
                node_text(c)
                for c in container.children
                if c.type in ("identifier", "member_expression", "type_identifier",
                              "generic_type")
            ]

        saw_clause = False
        for child in heritage.children:
            if child.type == "extends_clause":
                saw_clause = True
                for base in base_names(child):
                    ir.inheritance.append(
                        InheritanceEdge(subclass_fqn, base, kind="inherits")
                    )
            elif child.type == "implements_clause":
                saw_clause = True
                for base in base_names(child):
                    ir.inheritance.append(
                        InheritanceEdge(subclass_fqn, base, kind="implements")
                    )
        if not saw_clause:  # JavaScript: `extends <expr>` directly under heritage
            for base in base_names(heritage):
                ir.inheritance.append(
                    InheritanceEdge(subclass_fqn, base, kind="inherits")
                )

    def _declaration(
        self,
        node: Node,
        ir: FileIR,
        scope_fqn: str | None,
        caller: str,
        in_function: bool,
    ) -> None:
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue
            name_node = declarator.child_by_field_name("name")
            value = declarator.child_by_field_name("value")
            if name_node is None or name_node.type != "identifier":
                continue
            name = node_text(name_node)
            fqn = join_fqn(scope_fqn, name)
            if value is not None and value.type in _FUNC_VALUE_TYPES:
                params = value.child_by_field_name("parameters")
                ir.symbols.append(
                    SymbolDef(
                        fqn=fqn, name=name, kind=SymbolKind.FUNCTION,
                        span=span_of(declarator),
                        signature=f"{name}{node_text(params)}" if params else name,
                        parent_fqn=scope_fqn,
                    )
                )
                body = value.child_by_field_name("body")
                if body is not None:
                    self._visit(body, ir, scope_fqn=fqn, caller=fqn, in_function=True)
                continue
            if not in_function:
                ir.symbols.append(
                    SymbolDef(
                        fqn=fqn, name=name, kind=SymbolKind.VARIABLE,
                        span=span_of(declarator), parent_fqn=scope_fqn,
                    )
                )
            if value is not None:
                self._visit(value, ir, scope_fqn=scope_fqn, caller=caller,
                            in_function=in_function)

    def _call(self, node: Node, ir: FileIR, caller: str) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        if fn.type == "member_expression":
            prop = fn.child_by_field_name("property")
            callee = node_text(prop) if prop else node_text(fn)
        else:
            callee = node_text(fn)
        ir.calls.append(
            CallSite(caller_fqn=caller, callee_name=callee, span=span_of(node))
        )

    def _named_symbol(
        self, node: Node, ir: FileIR, scope_fqn: str | None, kind: SymbolKind
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        ir.symbols.append(
            SymbolDef(
                fqn=join_fqn(scope_fqn, name), name=name, kind=kind,
                span=span_of(node), signature=name, parent_fqn=scope_fqn,
            )
        )

    def _import(self, node: Node, ir: FileIR) -> None:
        source = node.child_by_field_name("source")
        module = node_text(source).strip("'\"") if source else ""
        symbols: list[str] = []
        alias: str | None = None
        for clause in node.children:
            if clause.type != "import_clause":
                continue
            for spec in clause.children:
                if spec.type == "named_imports":
                    for item in spec.children:
                        if item.type == "import_specifier":
                            n = item.child_by_field_name("name")
                            if n is not None:
                                symbols.append(node_text(n))
                elif spec.type == "namespace_import":
                    for item in spec.children:
                        if item.type == "identifier":
                            alias = node_text(item)
                elif spec.type == "identifier":
                    symbols.append(node_text(spec))  # default import
        ir.imports.append(
            ImportEdge(module=module, symbols=tuple(symbols), alias=alias)
        )
