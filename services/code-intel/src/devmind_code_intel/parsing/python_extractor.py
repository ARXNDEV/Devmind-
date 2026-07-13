"""Python extractor.

Emits definitions (functions, methods, classes, module/class-level variables),
imports, calls, and inheritance. Locals inside function bodies are intentionally
not emitted as symbols — they add noise without aiding cross-file reasoning.

Traversal model: `_visit` inspects each node itself, then recurses. Handlers for
scope-introducing nodes drive their own child recursion with updated context, so
every node is examined exactly once regardless of how it is reached.
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


class PythonExtractor:
    def extract(self, path: str, source: bytes, root: Node) -> FileIR:
        ir = FileIR(path=path, language="python", parse_errors=count_errors(root))
        self._visit(
            root, ir, scope_fqn=None, caller=_MODULE_CALLER,
            in_function=False, in_class=False,
        )
        return ir

    def _visit(
        self,
        node: Node,
        ir: FileIR,
        *,
        scope_fqn: str | None,
        caller: str,
        in_function: bool,
        in_class: bool,
    ) -> None:
        kind = node.type
        if kind == "function_definition":
            self._function(node, ir, scope_fqn, in_class)
            return
        if kind == "class_definition":
            self._class(node, ir, scope_fqn)
            return
        if kind in ("import_statement", "import_from_statement"):
            self._import(node, ir)
            return
        if kind == "assignment" and not in_function:
            self._maybe_variable(node, ir, scope_fqn)
            # continue into RHS for nested calls
        elif kind == "call":
            self._call(node, ir, caller)

        for child in node.children:
            self._visit(
                child, ir, scope_fqn=scope_fqn, caller=caller,
                in_function=in_function, in_class=in_class,
            )

    def _function(
        self, node: Node, ir: FileIR, scope_fqn: str | None, in_class: bool
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
                kind=SymbolKind.METHOD if in_class else SymbolKind.FUNCTION,
                span=span_of(node),
                signature=signature,
                docstring=self._docstring(node.child_by_field_name("body")),
                parent_fqn=scope_fqn,
            )
        )
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(
                body, ir, scope_fqn=fqn, caller=fqn,
                in_function=True, in_class=False,
            )

    def _class(self, node: Node, ir: FileIR, scope_fqn: str | None) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = join_fqn(scope_fqn, name)
        ir.symbols.append(
            SymbolDef(
                fqn=fqn,
                name=name,
                kind=SymbolKind.CLASS,
                span=span_of(node),
                signature=name,
                docstring=self._docstring(node.child_by_field_name("body")),
                parent_fqn=scope_fqn,
            )
        )
        supers = node.child_by_field_name("superclasses")
        if supers is not None:
            for arg in supers.children:
                if arg.type in ("identifier", "attribute"):
                    ir.inheritance.append(
                        InheritanceEdge(fqn, node_text(arg), kind="inherits")
                    )
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(
                body, ir, scope_fqn=fqn, caller=_MODULE_CALLER,
                in_function=False, in_class=True,
            )

    def _call(self, node: Node, ir: FileIR, caller: str) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        if fn.type == "attribute":
            attr = fn.child_by_field_name("attribute")
            callee = node_text(attr) if attr else node_text(fn)
        else:
            callee = node_text(fn)
        ir.calls.append(
            CallSite(caller_fqn=caller, callee_name=callee, span=span_of(node))
        )

    def _import(self, node: Node, ir: FileIR) -> None:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    ir.imports.append(ImportEdge(module=node_text(child)))
                elif child.type == "aliased_import":
                    name = child.child_by_field_name("name")
                    alias = child.child_by_field_name("alias")
                    if name is not None:
                        ir.imports.append(
                            ImportEdge(
                                module=node_text(name),
                                alias=node_text(alias) if alias else None,
                            )
                        )
        else:  # import_from_statement
            module_node = node.child_by_field_name("module_name")
            module = node_text(module_node) if module_node else ""
            module_range = (
                (module_node.start_byte, module_node.end_byte)
                if module_node
                else None
            )
            names = tuple(
                node_text(c)
                for c in node.children
                if c.type in ("dotted_name", "aliased_import")
                and (c.start_byte, c.end_byte) != module_range
            )
            ir.imports.append(ImportEdge(module=module, symbols=names))

    def _maybe_variable(
        self, node: Node, ir: FileIR, scope_fqn: str | None
    ) -> None:
        target = node.child_by_field_name("left")
        if target is None or target.type != "identifier":
            return
        name = node_text(target)
        ir.symbols.append(
            SymbolDef(
                fqn=join_fqn(scope_fqn, name),
                name=name,
                kind=SymbolKind.VARIABLE,
                span=span_of(node),
                parent_fqn=scope_fqn,
            )
        )

    def _docstring(self, body: Node | None) -> str | None:
        if body is None:
            return None
        for child in body.children:
            if child.type == "expression_statement" and child.children:
                inner = child.children[0]
                if inner.type == "string":
                    return node_text(inner).strip()[:500]
            return None  # docstring must be the first statement
        return None
