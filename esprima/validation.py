"""Read-only scope and context early errors for parsed ESTree programs.

The parser owns grammar/lexical errors. This pass enforces cross-node static
semantics using original nodes so the caller can retain diagnostic locations.
References: dated ECMA-262 2026 clauses 14, 15, 16 and Annex B.3.2/B.3.3.
"""
from collections.abc import Mapping
from typing import NamedTuple
import re
from . import nodes as _nodes, jsx_nodes as _jsx_nodes

# Restrict direct field access to the parser's concrete classes. Custom Node
# subclasses may expose properties or dynamic attributes and retain normal
# attribute semantics; custom mappings retain their overridden get methods.
_NATIVE_TYPES = frozenset(value for module in (_nodes, _jsx_nodes)
    for value in vars(module).values() if isinstance(value, type) and issubclass(value, _nodes.Node))
_SCALAR_TYPES = frozenset((str, int, float, bool, bytes, complex))

_FUNCTIONS = {"FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"}
_CLASSES = {"ClassDeclaration", "ClassExpression"}
_STRICT_RESERVED = {"implements", "interface", "let", "package", "private", "protected", "public", "static", "yield"}
_BINDING_SPECIAL = frozenset(_STRICT_RESERVED | {"eval", "arguments", "await", "yield"})
_REFERENCE_SPECIAL = frozenset(("arguments", "await", "yield"))
_ES2015 = {"ArrowFunctionExpression", "ArrayPattern", "ObjectPattern", "AssignmentPattern",
    "RestElement", "SpreadElement", "ClassDeclaration", "ClassExpression", "Super",
    "TemplateLiteral", "TaggedTemplateExpression", "ForOfStatement", "MetaProperty",
    "ImportDeclaration", "ExportNamedDeclaration", "ExportDefaultDeclaration", "ExportAllDeclaration"}
_METADATA = {"loc", "range", "tokens", "comments", "leadingComments", "trailingComments", "innerComments", "errors"}

# These fields are complete only for a synchronous, delegate-free parser tree.
# Standalone/custom AST validation retains structural child discovery. Nodes
# whose static rules depend on context still use the normal dispatch below.
_PARSER_EXPR_FIELDS = {
    "Literal": (), "ThisExpression": (), "TemplateElement": (),
    "BinaryExpression": ("left", "right"), "LogicalExpression": ("left", "right"),
    "ConditionalExpression": ("test", "consequent", "alternate"),
    "SequenceExpression": ("expressions",), "ArrayExpression": ("elements",),
    "UnaryExpression": ("argument",), "CallExpression": ("callee", "arguments"),
    "NewExpression": ("callee", "arguments"), "ChainExpression": ("expression",),
    "SpreadElement": ("argument",), "TemplateLiteral": ("quasis", "expressions"),
    "TaggedTemplateExpression": ("tag", "quasi"),
}


def _get(node, field, default=None):
    if node is None:
        return default
    node_type = type(node)
    if node_type is dict:
        return node.get(field, default)
    if node_type in _NATIVE_TYPES:
        return node.__dict__.get(field, default)
    if isinstance(node, Mapping):
        return node.get(field, default)
    return getattr(node, field, default)


def _async(node):
    value = _get(node, "async")
    return bool(_get(node, "isAsync", _get(node, "async_", False)) if value is None else value)


def _await(node):
    value = _get(node, "await")
    return bool(_get(node, "allowAwait", _get(node, "await_", False)) if value is None else value)


def _kind(node):
    node_type = type(node)
    if node_type in _NATIVE_TYPES:
        return node.__dict__.get("type")
    if node_type is dict:
        return node.get("type")
    if node is None or node_type in _SCALAR_TYPES:
        return None
    return _get(node, "type")


def _children(node):
    node_type = type(node)
    if node_type in _NATIVE_TYPES:
        fields = node.__dict__.items()
    else:
        fields = node.items() if isinstance(node, Mapping) else vars(node).items()
    for name, value in fields:
        if name.startswith("_") or name in _METADATA:
            continue
        value_type = type(value)
        if value is None or value_type in _SCALAR_TYPES:
            continue
        if value_type is list or value_type is tuple:
            for item in value:
                if _kind(item):
                    yield item
        elif _kind(value):
            yield value
        elif isinstance(value, (list, tuple)):
            for item in value:
                if _kind(item):
                    yield item


def _bindings(pattern):
    """BoundNames, retaining the individual identifier's diagnostic node."""
    kind = _kind(pattern)
    if kind == "Identifier":
        yield _get(pattern, "name"), pattern
    elif kind in {"RestElement", "AssignmentPattern"}:
        yield from _bindings(_get(pattern, "argument" if kind == "RestElement" else "left"))
    elif kind == "ArrayPattern":
        for item in _get(pattern, "elements", ()) or ():
            yield from _bindings(item)
    elif kind == "ObjectPattern":
        for prop in _get(pattern, "properties", ()) or ():
            yield from _bindings(_get(prop, "argument") if _kind(prop) == "RestElement" else _get(prop, "value"))


def _declaration_names(node):
    kind = _kind(node)
    if kind == "VariableDeclaration":
        for declaration in _get(node, "declarations", ()) or ():
            yield from _bindings(_get(declaration, "id"))
    elif kind in {"FunctionDeclaration", "ClassDeclaration"}:
        yield from _bindings(_get(node, "id"))
    elif kind == "ImportDeclaration":
        for specifier in _get(node, "specifiers", ()) or ():
            yield from _bindings(_get(specifier, "local"))
    elif kind in {"ExportNamedDeclaration", "ExportDefaultDeclaration"}:
        yield from _declaration_names(_get(node, "declaration"))


def _unexport(node):
    return _get(node, "declaration") if _kind(node) in {"ExportNamedDeclaration", "ExportDefaultDeclaration"} else node


def _declaration_item(node):
    node = _unexport(node)
    while _kind(node) == "LabeledStatement":
        node = _get(node, "body")
    return node


_VAR_CHILD_FIELDS = {
    "Program": ("body",), "BlockStatement": ("body",), "StaticBlock": ("body",),
    "IfStatement": ("consequent", "alternate"), "LabeledStatement": ("body",),
    "WhileStatement": ("body",), "DoWhileStatement": ("body",), "WithStatement": ("body",),
    "ForStatement": ("init", "body"), "ForInStatement": ("left", "body"), "ForOfStatement": ("left", "body"),
    "SwitchStatement": ("cases",), "SwitchCase": ("consequent",),
    "TryStatement": ("block", "handler", "finalizer"), "CatchClause": ("body",),
    "ExportNamedDeclaration": ("declaration",), "ExportDefaultDeclaration": ("declaration",),
}
_VAR_LEAVES = frozenset({
    "ExpressionStatement", "EmptyStatement", "ReturnStatement", "ThrowStatement", "BreakStatement",
    "ContinueStatement", "DebuggerStatement", "ImportDeclaration", "ExportAllDeclaration",
})


def _var_names(node, cache=None):
    """VarDeclaredNames, with context-free results cached only within one pass.

    Expression children cannot declare vars outside nested functions/classes,
    which are scope boundaries. Unknown extension containers still receive the
    conservative structural traversal rather than silently losing declarations.
    """
    if node is None:
        return ()
    if cache is not None:
        cached = cache.get(id(node))
        if cached is not None:
            return cached[1]
    kind = _kind(node)
    if kind in _FUNCTIONS | _CLASSES:
        result = ()
    elif kind == "VariableDeclaration":
        result = tuple(_declaration_names(node)) if _get(node, "kind") == "var" else ()
    elif kind in _VAR_LEAVES:
        result = ()
    else:
        fields = _VAR_CHILD_FIELDS.get(kind)
        if fields is None:
            children = _children(node)
        else:
            children = (child for field in fields for value in (_get(node, field),)
                for child in (value if isinstance(value, (list, tuple)) else (value,)) if child is not None)
        result = tuple(binding for child in children for binding in _var_names(child, cache))
    if cache is not None:
        # Keep the node alive along with the result so dynamic custom mappings
        # cannot make id reuse confuse two different temporary node objects.
        cache[id(node)] = (node, result)
    return result


def _strict_directive(body):
    for statement in body:
        if _kind(statement) != "ExpressionStatement" or _kind(_get(statement, "expression")) != "Literal":
            break
        literal = _get(statement, "expression")
        if not isinstance(_get(literal, "value"), str):
            break
        if _get(literal, "_parenthesized", False):
            break
        directive = _get(statement, "directive")
        if directive == "use strict" or (directive is None and _get(literal, "raw") in {"'use strict'", '"use strict"'}):
            return True
    return False


def _key(node):
    if _get(node, "computed", False):
        return None
    key = _get(node, "key")
    return _get(key, "name") if _kind(key) in {"Identifier", "PrivateIdentifier"} else _get(key, "value")


def _export_name(node):
    return _get(node, "name") if _kind(node) == "Identifier" else _get(node, "value")


class _Context(NamedTuple):
    strict: bool = False
    module: bool = False
    in_function: bool = False
    allow_await: bool = False
    allow_yield: bool = False
    await_reserved: bool = False
    yield_reserved: bool = False
    new_target: bool = False
    super_property: bool = False
    super_call: bool = False
    parameters: bool = False
    forbid_arguments: bool = False
    iteration: int = 0
    switch: int = 0
    labels: tuple = ()
    private_scopes: tuple = ()
    uninitialized_const: bool = False


def replace(context, **changes):
    # The context is an immutable value; tuple construction avoids repeatedly
    # copying seventeen dataclass fields through setattr during traversal.
    return context._replace(**changes)



def _parsed_kind(node):
    return None if node is None else node.type


def _parsed_bindings(pattern):
    if pattern is None:
        return
    kind = pattern.type
    if kind == "Identifier":
        yield pattern.name, pattern
    elif kind == "RestElement":
        yield from _parsed_bindings(pattern.argument)
    elif kind == "AssignmentPattern":
        yield from _parsed_bindings(pattern.left)
    elif kind == "ArrayPattern":
        for item in pattern.elements:
            yield from _parsed_bindings(item)
    elif kind == "ObjectPattern":
        for prop in pattern.properties:
            yield from _parsed_bindings(prop.argument if prop.type == "RestElement" else prop.value)


def _parsed_declaration_names(node):
    if node is None:
        return
    kind = node.type
    if kind == "VariableDeclaration":
        for declaration in node.declarations:
            yield from _parsed_bindings(declaration.id)
    elif kind in {"FunctionDeclaration", "ClassDeclaration"}:
        yield from _parsed_bindings(node.id)
    elif kind == "ImportDeclaration":
        for specifier in node.specifiers:
            yield from _parsed_bindings(specifier.local)
    elif kind in {"ExportNamedDeclaration", "ExportDefaultDeclaration"}:
        yield from _parsed_declaration_names(node.declaration)


_PARSED_SCOPE_BOUNDARIES = _FUNCTIONS | _CLASSES


def _parsed_var_names(node, cache):
    if node is None:
        return ()
    kind = node.type
    # Source-owned leaves cannot declare vars in this enclosing scope. Keeping
    # them out of the cache avoids needless tuples, ids and managed dictionaries.
    if kind in _PARSED_SCOPE_BOUNDARIES or kind in _VAR_LEAVES:
        return ()
    cached = cache.get(node)
    if cached is not None:
        return cached
    if kind == "VariableDeclaration":
        result = tuple(_parsed_declaration_names(node)) if node.kind == "var" else ()
    else:
        fields = _VAR_CHILD_FIELDS.get(kind)
        if fields is None:
            # Conservatively retain existing traversal for any unlisted
            # extension container; its cache format remains the generic one.
            return _var_names(node)
        result = []
        for field in fields:
            value = getattr(node, field)
            children = value if type(value) is list else (value,)
            for child in children:
                result.extend(_parsed_var_names(child, cache))
        result = tuple(result)
    # Native objects have identity hash/equality; the key itself retains them.
    cache[node] = result
    return result

class _Validator:
    def __init__(self, report, edition, parser_tree=False, no_var=False):
        self.report = report
        self.edition = edition
        self._parser_tree = parser_tree
        self._no_var = parser_tree and no_var
        self._var_cache = {}
        self._read_kind = _parsed_kind if parser_tree else _kind
        self._read_bindings = _parsed_bindings if parser_tree else _bindings
        self._read_declaration_names = _parsed_declaration_names if parser_tree else _declaration_names
        self._read_var_names = _parsed_var_names if parser_tree else _var_names

    def error(self, message, node):
        self.report(message, node)

    def duplicate(self, name, node):
        self.error(f"Identifier '{name}' has already been declared", node)

    def require(self, edition, feature, node):
        if self.edition < edition:
            self.error(f"{feature} requires ECMAScript {edition}", node)

    def check_names(self, bindings, context, lexical=False, unique=False):
        seen = set()
        for name, node in bindings:
            if unique and name in seen:
                self.duplicate(name, node)
            seen.add(name)
            if type(name) is str and name not in _BINDING_SPECIAL:
                continue
            if context.strict and name in {"eval", "arguments"}:
                self.error("Binding eval or arguments is forbidden in strict mode", node)
            if context.strict and name in _STRICT_RESERVED:
                self.error(f"Reserved word '{name}' cannot be a binding in strict mode", node)
            if lexical and name == "let":
                self.error("let cannot be a lexical binding name", node)
            if context.module and name == "await":
                self.error("await cannot be a module binding name", node)
            if (context.allow_await or context.await_reserved) and name == "await":
                self.error("await cannot be a binding in this context", node)
            if (context.allow_yield or context.yield_reserved) and name == "yield":
                self.error("yield cannot be a binding in a generator", node)
        return seen

    def scope(self, statements, context, scope_kind, parameters=(), extra_lexical=()):
        lexical, var_names = {}, []
        for name, binding in extra_lexical:
            if name in lexical:
                self.duplicate(name, binding)
            lexical[name] = (binding, None)
        for statement in statements:
            statement_type = type(statement)
            if self._parser_tree:
                declaration = statement
                kind = statement.type
                if kind in {"ExportNamedDeclaration", "ExportDefaultDeclaration"}:
                    declaration = statement.declaration
                while declaration is not None and declaration.type == "LabeledStatement":
                    declaration = declaration.body
                kind = None if declaration is None else declaration.type
            elif statement_type is dict or statement_type in _NATIVE_TYPES:
                kind = self._read_kind(statement)
                if kind not in {"ExportNamedDeclaration", "ExportDefaultDeclaration", "LabeledStatement"}:
                    declaration = statement
                else:
                    declaration = _declaration_item(statement)
                    kind = self._read_kind(declaration)
            else:
                declaration = _declaration_item(statement)
                kind = self._read_kind(declaration)
            is_lexical = (kind == "VariableDeclaration" and _get(declaration, "kind") != "var"
                or kind in {"ClassDeclaration", "ImportDeclaration"}
                or kind == "FunctionDeclaration" and scope_kind not in {"script", "function", "static"})
            if is_lexical:
                for name, binding in self._read_declaration_names(declaration):
                    if name in lexical:
                        prior = lexical[name][1]
                        annex_b_duplicate = (not context.strict and scope_kind in {"block", "switch"}
                            and self._read_kind(prior) == "FunctionDeclaration" and kind == "FunctionDeclaration"
                            and not _async(prior) and not _async(declaration)
                            and not _get(prior, "generator", False) and not _get(declaration, "generator", False))
                        if not annex_b_duplicate:
                            self.duplicate(name, binding)
                    lexical[name] = (binding, declaration)
            elif kind == "FunctionDeclaration" and scope_kind in {"script", "function", "static"}:
                var_names.extend(self._read_declaration_names(declaration))
            if not self._no_var:
                var_names.extend(self._read_var_names(declaration, self._var_cache))
        for name, binding in var_names:
            if name in lexical:
                self.duplicate(name, binding)
        for name, binding in parameters:
            if name in lexical:
                self.duplicate(name, lexical[name][0])
        return set(lexical) | {name for name, _ in var_names}

    def editions(self, node, context, parent=None, kind=None):
        node_type = type(node)
        ordinary = node_type is dict or node_type in _NATIVE_TYPES
        if kind is None or not ordinary:
            kind = self._read_kind(node)
        # At the latest supported edition every version-only condition is a
        # no-op. Keep descriptor access for custom nodes/mappings, and retain
        # regexp grammar validation even at the modern default.
        if self.edition >= 2026 and ordinary:
            if kind == "Literal":
                regex = _get(node, "regex")
                if regex:
                    from .regexp_validator import regexp_features
                    regexp_features(_get(regex, "pattern", "") or "", _get(regex, "flags", "") or "")
            return
        if kind in _ES2015:
            self.require(2015, kind, node)
        if kind == "VariableDeclaration" and _get(node, "kind") != "var":
            self.require(2015, "Lexical declarations", node)
        if kind == "Property" and (_get(node, "method", False) or _get(node, "computed", False) or _get(node, "shorthand", False)):
            self.require(2015, "Modern object properties", node)
        if kind in {"MemberExpression", "CallExpression"} and _get(node, "optional", False):
            self.require(2020, "Optional chaining", node)
        if kind in _FUNCTIONS:
            if _get(node, "generator", False):
                self.require(2015, "Generators", node)
            if _async(node):
                self.require(2017, "Async functions", node)
            if _async(node) and _get(node, "generator", False):
                self.require(2018, "Async generators", node)
        if kind == "AwaitExpression":
            self.require(2017 if context.in_function else 2022, "Await expressions", node)
        if kind == "ForOfStatement" and _await(node):
            self.require(2018, "Async iteration", node)
        if kind in {"SpreadElement", "RestElement"} and parent in {"ObjectExpression", "ObjectPattern"}:
            self.require(2018, "Object rest/spread", node)
        if kind == "CatchClause" and _get(node, "param") is None:
            self.require(2019, "Optional catch binding", node)
        if kind in {"ChainExpression", "ImportExpression"}:
            self.require(2020, kind, node)
        if kind in {"PrivateIdentifier", "PropertyDefinition", "FieldDefinition", "StaticBlock"}:
            self.require(2022, kind, node)
        if kind == "LogicalExpression" and _get(node, "operator") == "??":
            self.require(2020, "Nullish coalescing", node)
        if kind in {"AssignmentExpression", "BinaryExpression"}:
            operator = _get(node, "operator")
            if operator in {"**", "**="}:
                self.require(2016, "Exponentiation", node)
            if operator in {"&&=", "||=", "??="}:
                self.require(2021, "Logical assignment", node)
        if kind == "ExportAllDeclaration" and _get(node, "exported") is not None:
            self.require(2020, "Namespace reexports", node)
            if self._read_kind(_get(node, "exported")) == "Literal":
                self.require(2022, "String module names", node)
        if kind == "TemplateElement" and _get(_get(node, "value"), "cooked") is None:
            self.require(2018, "Tagged invalid template escapes", node)
        if kind == "MetaProperty" and _get(_get(node, "meta"), "name") == "import":
            self.require(2020, "import.meta", node)
        if _get(node, "attributes"):
            self.require(2025, "Import attributes", node)
        if kind == "ImportExpression" and _get(node, "options") is not None:
            self.require(2025, "Dynamic import options", node)
        if kind == "Literal":
            raw = _get(node, "raw", "") or ""
            if _get(node, "bigint") is not None:
                self.require(2020, "BigInt literals", node)
            if raw and raw[0].isdigit() and "_" in raw:
                self.require(2021, "Numeric separators", node)
            if raw and raw[0] in "\"'" and any(ch in raw for ch in "\u2028\u2029"):
                self.require(2019, "JSON-superset string literals", node)
            regex = _get(node, "regex")
            if regex:
                flags, pattern = _get(regex, "flags", "") or "", _get(regex, "pattern", "") or ""
                from .regexp_validator import regexp_features
                for feature, edition in regexp_features(pattern, flags).items():
                    self.require(edition, feature, node)

    def module_exports(self, body, bindings):
        exported = set()
        def add(name, node):
            if name in exported:
                self.error(f"Duplicate export '{name}'", node)
            exported.add(name)
        for statement in body:
            kind = self._read_kind(statement)
            if kind == "ExportDefaultDeclaration":
                add("default", statement)
            elif kind == "ExportAllDeclaration":
                if _get(statement, "exported") is not None:
                    add(_export_name(_get(statement, "exported")), _get(statement, "exported"))
            elif kind == "ExportNamedDeclaration":
                for name, binding in self._read_declaration_names(_get(statement, "declaration")):
                    add(name, binding)
                for specifier in _get(statement, "specifiers", ()) or ():
                    add(_export_name(_get(specifier, "exported")), _get(specifier, "exported"))
                    local = _export_name(_get(specifier, "local"))
                    if _get(statement, "source") is None and self._read_kind(_get(specifier, "local")) == "Literal":
                        self.error("String export names require a reexport source", _get(specifier, "local"))
                    if _get(statement, "source") is None and local not in bindings:
                        self.error(f"Export '{local}' is not defined", _get(specifier, "local"))

    def pattern(self, pattern, context, binding=True):
        if self._parser_tree and pattern is not None and pattern.type == "Identifier":
            if not binding:
                self.assignment_target(pattern, context, False)
            return
        kind = self._read_kind(pattern)
        if pattern is None:
            return
        pattern_type = type(pattern)
        if self.edition < 2026 or pattern_type is not dict and pattern_type not in _NATIVE_TYPES or kind == "Literal":
            self.editions(pattern, context, kind=kind)
        if kind == "Identifier":
            if not binding:
                self.assignment_target(pattern, context, False)
            return
        if kind == "AssignmentPattern":
            self.pattern(_get(pattern, "left"), context, binding)
            self.visit(_get(pattern, "right"), context)
        elif kind == "RestElement":
            argument = _get(pattern, "argument")
            if _get(pattern, "_trailingComma", False):
                self.error("Rest elements may not have a trailing comma", pattern)
            if self._read_kind(argument) == "AssignmentPattern":
                self.error("Rest elements may not have an initializer", pattern)
            self.pattern(argument, context, binding)
        elif kind == "ArrayPattern":
            elements = _get(pattern, "elements", ()) or ()
            if elements and self._read_kind(elements[-1]) == "RestElement" and _get(pattern, "_trailingComma", False):
                self.error("Rest elements may not have a trailing comma", elements[-1])
            for index, item in enumerate(elements):
                if self._read_kind(item) == "RestElement" and index != len(elements) - 1:
                    self.error("Rest elements must be last in a pattern", item)
                self.pattern(item, context, binding)
        elif kind == "ObjectPattern":
            properties = _get(pattern, "properties", ()) or ()
            if properties and self._read_kind(properties[-1]) == "RestElement" and _get(pattern, "_trailingComma", False):
                self.error("Rest properties may not have a trailing comma", properties[-1])
            for index, prop in enumerate(properties):
                if self._read_kind(prop) == "RestElement":
                    if index != len(properties) - 1:
                        self.error("Rest properties must be last in a pattern", prop)
                    self.editions(prop, context, "ObjectPattern")
                    argument = _get(prop, "argument")
                    if self._read_kind(argument) not in ({"Identifier"} if binding else {"Identifier", "MemberExpression"}):
                        self.error("Object rest requires a binding identifier or simple assignment target", argument)
                    self.pattern(prop, context, binding)
                else:
                    if _get(prop, "computed", False):
                        self.visit(_get(prop, "key"), context)
                    self.pattern(_get(prop, "value"), context, binding)
        elif kind == "MemberExpression":
            if binding:
                self.error("A binding pattern cannot contain a member expression", pattern)
            self.visit(pattern, context)
        else:
            self.error("Invalid binding or assignment pattern", pattern)

    def assignment_target(self, target, context, allow_pattern):

        if self._parser_tree and target is not None:
            kind = target.type
            if kind == "Identifier":
                if context.strict and target.name in {"eval", "arguments"}:
                    self.error("Assigning to eval or arguments is forbidden in strict mode", target)
                self.visit(target, context)
                return
            if kind == "MemberExpression" and not target.optional:
                self.visit(target, context)
                return
        kind = self._read_kind(target)
        if kind == "Identifier":
            if context.strict and _get(target, "name") in {"eval", "arguments"}:
                self.error("Assigning to eval or arguments is forbidden in strict mode", target)
            self.visit(target, context)
        elif kind == "MemberExpression" and not _get(target, "optional", False):
            self.visit(target, context)
        elif kind in {"ArrayPattern", "ObjectPattern"} and allow_pattern and not _get(target, "_parenthesized", False):
            self.pattern(target, context, binding=False)
        elif kind == "CallExpression" and not context.strict and not context.module and not _get(target, "optional", False):
            # The web-compatibility CallExpression target is a runtime
            # ReferenceError rather than a sloppy-script early error (Annex B).
            self.visit(target, context)
        else:
            self.error("Invalid left-hand side in assignment", target)

    def function(self, node, context, method=False, super_property=False, super_call=False):
        arrow = self._read_kind(node) == "ArrowFunctionExpression"
        body = _get(node, "body")
        statements = _get(body, "body", ()) or () if self._read_kind(body) == "BlockStatement" else ()
        own_strict = _strict_directive(statements)
        strict = context.strict or own_strict
        params = _get(node, "params", ()) or ()
        simple = all(self._read_kind(param) == "Identifier" for param in params)
        function_context = replace(context, strict=strict, in_function=True,
            allow_await=_async(node), allow_yield=bool(_get(node, "generator", False)), parameters=False,
            await_reserved=False, yield_reserved=False,
            new_target=context.new_target if arrow else True,
            super_property=context.super_property if arrow else super_property,
            super_call=context.super_call if arrow else super_call,
            forbid_arguments=context.forbid_arguments if arrow else False,
            iteration=0, switch=0, labels=(), uninitialized_const=False)
        parameter_names = [binding for param in params for binding in self._read_bindings(param)]
        parameter_context = replace(function_context, parameters=True,
            await_reserved=arrow and (context.allow_await or context.await_reserved),
            yield_reserved=arrow and (context.allow_yield or context.yield_reserved))
        self.check_names(parameter_names, parameter_context, unique=strict or not simple or method or arrow)
        # Declaration names are parsed in the enclosing Await/Yield grammar;
        # named function expressions bind inside their own function grammar.
        name_context = (replace(function_context, allow_await=context.allow_await, allow_yield=context.allow_yield,
            await_reserved=context.await_reserved, yield_reserved=context.yield_reserved)
            if self._read_kind(node) == "FunctionDeclaration" else function_context)
        self.check_names(self._read_bindings(_get(node, "id")), name_context)
        if own_strict and not simple:
            self.error("Illegal 'use strict' directive in function with non-simple parameter list", node)
        for param in params:
            self.pattern(param, parameter_context)
            if self._read_kind(param) == "RestElement" and _get(param, "_trailingComma", False):
                self.error("Rest parameters may not have a trailing comma", param)
        if self._read_kind(body) == "BlockStatement":
            self.scope(statements, function_context, "function", parameter_names)
            for statement in statements:
                self.visit(statement, function_context, "FunctionBody")
        else:
            self.visit(body, function_context)

    def class_definition(self, node, context):
        self.check_names(self._read_bindings(_get(node, "id")), replace(context, strict=True))
        self.visit(_get(node, "superClass"), context)
        elements = _get(_get(node, "body"), "body", ()) or ()
        private_names, constructors = {}, 0
        for element in elements:
            kind, name = self._read_kind(element), _key(element)
            private = self._read_kind(_get(element, "key")) == "PrivateIdentifier"
            if private:
                if name == "constructor":
                    self.error("Class constructor may not be a private name", _get(element, "key"))
                form = _get(element, "kind") if kind == "MethodDefinition" else "field"
                previous = private_names.get(name)
                if previous is not None:
                    valid_pair = (previous[0] == bool(_get(element, "static", False))
                        and previous[1] in {"get", "set"} and form in {"get", "set"} and previous[1] != form)
                    if not valid_pair:
                        self.error(f"Duplicate private name '#{name}'", _get(element, "key"))
                    private_names[name] = (previous[0], "pair")
                else:
                    private_names[name] = (bool(_get(element, "static", False)), form)
            elif name == "prototype" and _get(element, "static", False):
                self.error("Classes may not have a static property named prototype", element)
            if kind in {"PropertyDefinition", "FieldDefinition"} and not private and name == "constructor":
                self.error("Class fields may not be named constructor", element)
            if kind == "MethodDefinition" and not private and not _get(element, "static", False) and name == "constructor":
                constructors += 1
                if constructors > 1:
                    self.error("A class may only have one constructor", element)
                value = _get(element, "value")
                if _get(element, "kind") != "constructor" or _async(value) or _get(value, "generator", False):
                    self.error("Class constructors cannot be async, generators or accessors", element)
        class_context = replace(context, strict=True, private_scopes=context.private_scopes + (frozenset(private_names),))
        derived = _get(node, "superClass") is not None
        for element in elements:
            self.editions(element, class_context)
            if _get(element, "computed", False):
                self.visit(_get(element, "key"), class_context)
            if self._read_kind(_get(element, "key")) == "PrivateIdentifier":
                self.require(2022, "Private class names", _get(element, "key"))
            if self._read_kind(element) == "MethodDefinition":
                value = _get(element, "value")
                self.accessor_arity(element)
                self.editions(value, class_context)
                self.function(value, class_context, method=True, super_property=True,
                    super_call=derived and _get(element, "kind") == "constructor" and not _get(element, "static", False))
            elif self._read_kind(element) in {"PropertyDefinition", "FieldDefinition"}:
                field_context = replace(class_context, in_function=False, allow_await=False, allow_yield=False,
                    await_reserved=False, yield_reserved=False,
                    new_target=True, super_property=True, super_call=False, forbid_arguments=True,
                    parameters=False, iteration=0, switch=0, labels=())
                self.visit(_get(element, "value"), field_context)
            elif self._read_kind(element) == "StaticBlock":
                static_context = replace(class_context, in_function=False, allow_await=False, allow_yield=False,
                    await_reserved=True, yield_reserved=False,
                    new_target=True, super_property=True, super_call=False, forbid_arguments=True,
                    parameters=False, iteration=0, switch=0, labels=())
                body = _get(element, "body", ()) or ()
                self.scope(body, static_context, "static")
                for statement in body:
                    self.visit(statement, static_context, "StaticBlock")

    def accessor_arity(self, node):
        kind = _get(node, "kind")
        params = _get(_get(node, "value"), "params", ()) or ()
        if kind == "get" and params:
            self.error("Getter must not have any formal parameters", node)
        elif kind == "set" and (len(params) != 1 or self._read_kind(params[0]) == "RestElement"):
            self.error("Setter must have exactly one non-rest formal parameter", node)

    def statement(self, node, context, annex_b=False, labels_allowed=False):
        target = node
        while self._read_kind(target) == "LabeledStatement":
            target = _get(target, "body")
        if target is not node and self._read_kind(target) == "FunctionDeclaration" and not labels_allowed:
            self.error("Labelled functions are not valid in this statement position", target)
        if self._read_kind(node) == "FunctionDeclaration":
            if not annex_b or context.strict or _async(node) or _get(node, "generator", False):
                self.error("Functions in statement position require the sloppy Annex B ordinary-function grammar", node)
        elif self._read_kind(node) == "ClassDeclaration" or self._read_kind(node) == "VariableDeclaration" and _get(node, "kind") != "var":
            self.error("Lexical declarations require a statement list or block", node)
        self.visit(node, context)

    def private_reference(self, node, context):
        name = _get(node, "name")
        if not any(name in scope for scope in context.private_scopes):
            self.error(f"Private name '#{name}' is not declared in an enclosing class", node)

    def visit(self, node, context, parent=None):
        if node is None:
            return

        # The facade alone attests this unexposed, canonical native graph.
        if self._parser_tree:
            kind = node.type
            if kind == "Identifier":
                name = node.name
                if context.forbid_arguments and name == "arguments":
                    self.error("arguments is forbidden in class field initializers and static blocks", node)
                if name == "await" and (context.module or context.allow_await or context.await_reserved):
                    self.error("await is a reserved word in this context", node)
                if name == "yield" and (context.strict or context.allow_yield or context.yield_reserved):
                    self.error("yield is a reserved word in this context", node)
                return
            if kind == "Literal":
                if type(node) is _nodes.RegexLiteral:
                    from .regexp_validator import regexp_features
                    regexp_features(node.regex.pattern, node.regex.flags)
                return
            if kind in {"ThisExpression", "TemplateElement"}:
                return
            if kind in {"BinaryExpression", "LogicalExpression"} and node.left.type != "PrivateIdentifier":
                self.visit(node.left, context, kind)
                self.visit(node.right, context, kind)
                return
            if kind == "MemberExpression" and node.object.type != "Super" and node.property.type != "PrivateIdentifier":
                self.visit(node.object, context)
                if node.computed:
                    self.visit(node.property, context)
                return
            if kind in {"CallExpression", "NewExpression"} and node.callee.type != "Super":
                self.visit(node.callee, context, kind)
                for argument in node.arguments:
                    self.visit(argument, context, kind)
                return
            if kind == "ConditionalExpression":
                self.visit(node.test, context, kind)
                self.visit(node.consequent, context, kind)
                self.visit(node.alternate, context, kind)
                return
            if kind in {"SequenceExpression", "ArrayExpression"}:
                for child in (node.expressions if kind == "SequenceExpression" else node.elements):
                    self.visit(child, context, kind)
                return
            if kind == "UnaryExpression" and node.operator != "delete":
                self.visit(node.argument, context, kind)
                return
            if kind in {"SpreadElement", "ChainExpression"}:
                self.visit(node.argument if kind == "SpreadElement" else node.expression, context, kind)
                return
            if kind == "TemplateLiteral":
                for child in node.quasis:
                    self.visit(child, context, kind)
                for child in node.expressions:
                    self.visit(child, context, kind)
                return
            if kind == "TaggedTemplateExpression":
                self.visit(node.tag, context, kind)
                self.visit(node.quasi, context, kind)
                return
            if kind == "ExpressionStatement":
                expression = node.expression
                if expression.type == "ClassExpression" and not expression._parenthesized:
                    self.error("A class expression statement requires parentheses", expression)
                self.visit(expression, context, kind)
                return
            if kind == "VariableDeclaration":
                declaration_kind = node.kind
                if declaration_kind not in {"var", "let", "const"}:
                    self.error(f"Unsupported declaration kind '{declaration_kind}'", node)
                self.check_names(self._read_declaration_names(node), context, lexical=declaration_kind != "var")
                for declaration in node.declarations:
                    self.pattern(declaration.id, context)
                    if declaration_kind == "const" and declaration.init is None and not context.uninitialized_const:
                        self.error("Missing initializer in const declaration", declaration)
                    self.visit(declaration.init, context)
                return
            if kind == "ReturnStatement":
                if not context.in_function:
                    self.error("Illegal return statement", node)
                self.visit(node.argument, context, kind)
                return
            if kind == "ThrowStatement":
                self.visit(node.argument, context, kind)
                return
        node_type = type(node)
        ordinary = node_type is dict or node_type in _NATIVE_TYPES
        if ordinary:
            get = (node if node_type is dict else node.__dict__).get
            kind = get("type")
        else:
            kind = self._read_kind(node)
            # Preserve overridden Mapping.get and inherited/dynamic descriptors.
            def get(field, default=None):
                return _get(node, field, default)
        if self.edition < 2026 or not ordinary or kind == "Literal":
            self.editions(node, context, parent, kind)
        if kind == "Identifier":
            name = get("name")
            if type(name) is str and name not in _REFERENCE_SPECIAL:
                return
            if context.forbid_arguments and name == "arguments":
                self.error("arguments is forbidden in class field initializers and static blocks", node)
            if name == "await" and (context.module or context.allow_await or context.await_reserved):
                self.error("await is a reserved word in this context", node)
            if name == "yield" and (context.strict or context.allow_yield or context.yield_reserved):
                self.error("yield is a reserved word in this context", node)
            return
        if self._parser_tree and node_type in _NATIVE_TYPES:
            fields = _PARSER_EXPR_FIELDS.get(kind)
            if (fields is not None and not (kind == "UnaryExpression" and get("operator") == "delete")
                    and not (kind == "BinaryExpression" and self._read_kind(get("left")) == "PrivateIdentifier")
                    and not (kind in {"CallExpression", "NewExpression"} and self._read_kind(get("callee")) == "Super")):
                for field in fields:
                    value = get(field)
                    if type(value) is list:
                        for child in value:
                            self.visit(child, context, kind)
                    else:
                        self.visit(value, context, kind)
                return
        if kind in _FUNCTIONS:
            self.function(node, context)
            return
        if kind in _CLASSES:
            self.class_definition(node, context)
            return
        if kind == "ExpressionStatement":
            expression = get("expression")
            if self._read_kind(expression) == "ClassExpression" and not _get(expression, "_parenthesized", False):
                self.error("A class expression statement requires parentheses", expression)
        if kind == "BlockStatement":
            body = get("body", ()) or ()
            self.scope(body, context, "block")
            for statement in body:
                self.visit(statement, context, "BlockStatement")
            return
        if kind == "VariableDeclaration":
            declaration_kind = get("kind")
            if declaration_kind not in {"var", "let", "const"}:
                self.error(f"Unsupported declaration kind '{declaration_kind}'", node)
            self.check_names(self._read_declaration_names(node), context, lexical=declaration_kind != "var")
            for declaration in get("declarations", ()) or ():
                self.pattern(_get(declaration, "id"), context)
                if declaration_kind == "const" and _get(declaration, "init") is None and not context.uninitialized_const:
                    self.error("Missing initializer in const declaration", declaration)
                self.visit(_get(declaration, "init"), context)
            return
        if kind in {"ForStatement", "ForInStatement", "ForOfStatement"}:
            initializer = get("init" if kind == "ForStatement" else "left")
            if self._read_kind(initializer) == "VariableDeclaration" and _get(initializer, "kind") != "var":
                self.scope([initializer, get("body")], context, "for")
            if kind != "ForStatement" and self._read_kind(initializer) == "VariableDeclaration":
                declarations = _get(initializer, "declarations", ()) or ()
                if len(declarations) != 1:
                    self.error("for-in/of requires exactly one binding", initializer)
                for declaration in declarations:
                    annex_b = (kind == "ForInStatement" and not context.strict and _get(initializer, "kind") == "var"
                        and self._read_kind(_get(declaration, "id")) == "Identifier")
                    if _get(declaration, "init") is not None and not annex_b:
                        self.error("for-in/of bindings must not have an initializer", declaration)
            if kind == "ForOfStatement" and _await(node) and not context.allow_await:
                self.error("for await is only valid in async functions or modules", node)
            self.visit(initializer, replace(context, uninitialized_const=kind != "ForStatement"))
            if kind != "ForStatement" and self._read_kind(initializer) != "VariableDeclaration":
                self.assignment_target(initializer, context, True)
            for field in (("test", "update") if kind == "ForStatement" else ("right",)):
                self.visit(get(field), context)
            self.statement(get("body"), replace(context, iteration=context.iteration + 1))
            return
        if kind == "SwitchStatement":
            self.visit(get("discriminant"), context)
            cases = get("cases", ()) or ()
            statements = [statement for case in cases for statement in _get(case, "consequent", ()) or ()]
            self.scope(statements, context, "switch")
            default_seen = False
            for case in cases:
                if _get(case, "test") is None:
                    if default_seen:
                        self.error("More than one default clause in switch", case)
                    default_seen = True
                self.visit(_get(case, "test"), context)
                for statement in _get(case, "consequent", ()) or ():
                    self.visit(statement, replace(context, switch=context.switch + 1), "SwitchCase")
            return
        if kind == "CatchClause":
            parameter = get("param")
            bindings = list(self._read_bindings(parameter))
            self.check_names(bindings, context, unique=True)
            self.pattern(parameter, context)
            body = _get(get("body"), "body", ()) or ()
            destructured = parameter is not None and self._read_kind(parameter) != "Identifier"
            self.scope(body, context, "catch", parameters=() if destructured else bindings,
                extra_lexical=bindings if destructured else ())
            for statement in body:
                self.visit(statement, context, "BlockStatement")
            return
        if kind == "IfStatement":
            self.visit(get("test"), context)
            self.statement(get("consequent"), context, annex_b=True)
            if get("alternate") is not None:
                self.statement(get("alternate"), context, annex_b=True)
            return
        if kind in {"WhileStatement", "DoWhileStatement"}:
            self.visit(get("test"), context)
            self.statement(get("body"), replace(context, iteration=context.iteration + 1))
            return
        if kind == "LabeledStatement":
            label = _get(get("label"), "name")
            if label == "await" and (context.module or context.await_reserved or context.allow_await):
                self.error("await cannot be a label in this context", get("label"))
            if any(name == label for name, iteration in context.labels):
                self.error(f"Label '{label}' has already been declared", get("label"))
            body = get("body")
            target = body
            while self._read_kind(target) == "LabeledStatement":
                target = _get(target, "body")
            iteration = self._read_kind(target) in {"WhileStatement", "DoWhileStatement", "ForStatement", "ForInStatement", "ForOfStatement"}
            self.statement(body, replace(context, labels=context.labels + ((label, iteration),)), annex_b=True, labels_allowed=True)
            return
        if kind in {"BreakStatement", "ContinueStatement"}:
            label = _get(get("label"), "name")
            if label is not None:
                targets = [iteration for name, iteration in context.labels if name == label]
                if not targets or kind == "ContinueStatement" and not targets[-1]:
                    self.error(f"Illegal {kind[:-9].lower()} target '{label}'", node)
            elif not context.iteration and (kind == "ContinueStatement" or not context.switch):
                self.error(f"Illegal {kind[:-9].lower()} statement", node)
            return
        if kind == "ReturnStatement" and not context.in_function:
            self.error("Illegal return statement", node)
        if kind == "WithStatement":
            if context.strict:
                self.error("Strict mode code may not contain a with statement", node)
            self.visit(get("object"), context)
            self.statement(get("body"), context)
            return
        if kind == "ObjectExpression":
            proto_seen = False
            for prop in get("properties", ()) or ():
                if (self._read_kind(prop) == "Property" and _key(prop) == "__proto__" and _get(prop, "kind") == "init"
                        and not _get(prop, "method", False) and not _get(prop, "shorthand", False)):
                    if proto_seen:
                        self.error("Duplicate __proto__ fields are not allowed in object literals", prop)
                    proto_seen = True
                self.visit(prop, context, "ObjectExpression")
            return
        if kind == "Property":
            key = get("key")
            if (self._read_kind(key) == "PrivateIdentifier" or self._read_kind(key) == "Identifier"
                    and isinstance(_get(key, "name"), str) and _get(key, "name").startswith("#")):
                self.error("Private methods and properties are only valid in class bodies", get("key"))
            if get("computed", False):
                self.visit(get("key"), context)
            value = get("value")
            method = get("method", False) or get("kind") in {"get", "set"}
            if method and self._read_kind(value) in _FUNCTIONS:
                self.accessor_arity(node)
                self.editions(value, context)
                self.function(value, context, method=True, super_property=True)
            else:
                self.visit(value, context)
            return
        if kind in {"ImportDeclaration", "ExportNamedDeclaration", "ExportDefaultDeclaration", "ExportAllDeclaration"}:
            if not context.module or parent != "Program":
                self.error("Import and export declarations are only valid at module top level", node)
            if kind == "ImportDeclaration":
                self.check_names(self._read_declaration_names(node), context, lexical=True)
                for specifier in get("specifiers", ()) or ():
                    if self._read_kind(_get(specifier, "imported")) == "Literal":
                        self.require(2022, "String module names", specifier)
            else:
                self.visit(get("declaration"), context, "Program")
                for specifier in get("specifiers", ()) or ():
                    if self._read_kind(_get(specifier, "exported")) == "Literal" or self._read_kind(_get(specifier, "local")) == "Literal":
                        self.require(2022, "String module names", specifier)
            attribute_names = set()
            for attribute in get("attributes", ()) or ():
                name = _export_name(_get(attribute, "key"))
                if name in attribute_names:
                    self.error(f"Duplicate import attribute '{name}'", attribute)
                attribute_names.add(name)
                if not isinstance(_get(_get(attribute, "value"), "value"), str):
                    self.error("Import attribute values must be strings", attribute)
            return
        if kind == "MemberExpression":
            obj, prop = get("object"), get("property")
            if self._read_kind(obj) == "Super":
                if not context.super_property or get("optional", False):
                    self.error("super property access is not valid in this context", obj)
                if self._read_kind(prop) == "PrivateIdentifier":
                    self.error("Private names cannot be accessed through super", prop)
            else:
                self.visit(obj, context)
            if self._read_kind(prop) == "PrivateIdentifier":
                self.editions(prop, context)
                self.private_reference(prop, context)
            elif get("computed", False):
                self.visit(prop, context)
            return
        if kind in {"CallExpression", "NewExpression"} and self._read_kind(get("callee")) == "Super":
            if kind != "CallExpression" or not context.super_call or get("optional", False):
                self.error("super() is only valid in a derived class constructor", get("callee"))
            for argument in get("arguments", ()) or ():
                self.visit(argument, context)
            return
        if kind == "Super":
            self.error("super must be a valid property access or constructor call", node)
            return
        if kind == "PrivateIdentifier":
            self.private_reference(node, context)
            if parent != "PrivateBrand":
                self.error("Private names are only valid as class keys, member properties or an in operand", node)
            return
        if kind == "BinaryExpression" and self._read_kind(get("left")) == "PrivateIdentifier":
            if get("operator") != "in":
                self.error("A private name expression requires the in operator", node)
            self.visit(get("left"), context, "PrivateBrand")
            self.visit(get("right"), context)
            return
        if kind == "MetaProperty":
            meta = _get(get("meta"), "name")
            prop = _get(get("property"), "name")
            if meta == "new" and prop == "target" and not context.new_target:
                self.error("new.target is only valid in functions or class initialization", node)
            if meta == "import" and prop == "meta" and not context.module:
                self.error("import.meta is only valid in modules", node)
            return
        if kind == "AwaitExpression" and (not context.allow_await or context.parameters):
            self.error("await is not valid in this context", node)
        if kind == "YieldExpression" and (not context.allow_yield or context.parameters):
            self.error("yield is not valid in this context", node)
        if kind == "UnaryExpression" and get("operator") == "delete":
            argument = get("argument")
            if self._read_kind(argument) == "ChainExpression":
                argument = _get(argument, "expression")
            if context.strict and self._read_kind(argument) == "Identifier":
                self.error("Deleting an unqualified identifier is forbidden in strict mode", argument)
            if self._read_kind(argument) == "MemberExpression" and self._read_kind(_get(argument, "property")) == "PrivateIdentifier":
                self.error("Private fields may not be deleted", argument)
        if kind in {"AssignmentExpression", "UpdateExpression"}:
            target = get("left" if kind == "AssignmentExpression" else "argument")
            self.assignment_target(target, context, kind == "AssignmentExpression" and get("operator") == "=")
            if kind == "AssignmentExpression":
                self.visit(get("right"), context)
            return
        for child in _children(node):
            self.visit(child, context, kind)

    def program(self, program):
        body = _get(program, "body", ()) or ()
        module = _get(program, "sourceType") == "module"
        context = _Context(module=module, strict=module or _strict_directive(body),
            allow_await=module and self.edition >= 2022)
        bindings = self.scope(body, context, "module" if module else "script")
        if module:
            self.require(2015, "Modules", program)
            self.module_exports(body, bindings)
        for statement in body:
            self.visit(statement, context, "Program")


def validate_program(program, report, ecma_version=2026):
    """Report each static error with ``report(message, original_node)``.

    The callback may raise immediately or collect tolerant diagnostics. The AST
    is never copied or mutated. Exceptions raised by the callback propagate.
    Grammar, token validity and unsupported proposal syntax remain parser work.
    """
    _Validator(report, ecma_version).program(program)


def _validate_parsed_program(program, report, ecma_version, source=None):
    """Private facade path for its own unexposed native parser tree.

    The facade attests an exact Parser, ECMAScript 2026 and no user delegate.
    No node flags or public options can enable canonical expression traversal.
    Historical editions keep all feature checks and structural traversal.

    A VarDeclaration requires the unescaped reserved keyword ``var``. If the
    exact source lacks that spelling, no var declaration can exist anywhere in
    the owned tree. Function declaration names are still collected by scope;
    only the separate VarDeclaredNames subtree scan becomes unnecessary.
    Comments/string occurrences cause harmless false positives. String
    subclasses can override containment, so they retain the complete scan.
    """
    parser_tree = ecma_version == 2026
    no_var = parser_tree and type(source) is str and "var" not in source
    _Validator(report, ecma_version, parser_tree=parser_tree, no_var=no_var).program(program)
