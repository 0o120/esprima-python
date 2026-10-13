"""Scope/context regressions for the current-edition early-error pass."""
import copy
from types import SimpleNamespace
import unittest

import esprima
from esprima.validation import validate_program


def node(node_type, **fields):
    return {"type": node_type, **fields}


def identifier(name="x"):
    return node("Identifier", name=name)


def declaration(kind, name="x", init=None):
    return node("VariableDeclaration", kind=kind, declarations=[node("VariableDeclarator", id=identifier(name), init=init)])


def program(*body, module=False):
    return node("Program", sourceType="module" if module else "script", body=list(body))


def errors(tree, edition=2026):
    result = []
    validate_program(tree, lambda message, node: result.append((message, node)), edition)
    return result


class EarlyErrorTests(unittest.TestCase):
    def test_direct_lexical_duplicates_and_recursive_var_conflicts(self):
        for tree in (program(declaration("let"), declaration("let")),
                program(declaration("const", init=node("Literal", value=1)), declaration("var")),
                program(declaration("let"), node("BlockStatement", body=[declaration("var")]))):
            with self.subTest(tree=tree):
                self.assertTrue(errors(tree))
        self.assertFalse(errors(program(declaration("let"), node("BlockStatement", body=[declaration("let")]))))

    def test_duplicate_diagnostic_node_is_original(self):
        first, second = declaration("let"), declaration("let")
        second["declarations"][0]["id"].update(_start=20, _line=2, _column=3)
        result = errors(program(first, second))
        self.assertIs(result[0][1], second["declarations"][0]["id"])

    def test_function_parameter_conflicts_and_duplicate_policy(self):
        function = lambda params, body: node("FunctionDeclaration", id=identifier("f"), params=params,
            body=node("BlockStatement", body=body), generator=False, **{"async": False})
        self.assertTrue(errors(program(function([identifier()], [declaration("let")]))))
        self.assertFalse(errors(program(function([identifier()], [node("BlockStatement", body=[declaration("let")])]))))
        duplicate = [identifier(), identifier()]
        self.assertFalse(errors(program(function(duplicate, []))))
        strict = node("ExpressionStatement", expression=node("Literal", value="use strict", raw="'use strict'"), directive="use strict")
        self.assertTrue(errors(program(function(duplicate, [strict]))))
        non_simple = [node("AssignmentPattern", left=identifier(), right=node("Literal", value=1))]
        self.assertTrue(errors(program(function(non_simple, [strict]))))
        self.assertTrue(errors(program(node("ArrowFunctionExpression", params=duplicate, body=node("Literal", value=1), expression=True))))

    def test_module_binding_and_export_rules(self):
        imports = node("ImportDeclaration", specifiers=[node("ImportDefaultSpecifier", local=identifier())],
            source=node("Literal", value="m"), attributes=[])
        export = node("ExportNamedDeclaration", declaration=None,
            specifiers=[node("ExportSpecifier", local=identifier(), exported=identifier("name"))], source=None, attributes=[])
        self.assertTrue(errors(program(imports, declaration("let"), module=True)))
        self.assertTrue(errors(program(export, module=True)))
        self.assertTrue(errors(program(declaration("let"), export, copy.deepcopy(export), module=True)))
        self.assertFalse(errors(program(declaration("let"), export, module=True)))
        reexport = copy.deepcopy(export)
        reexport["source"] = node("Literal", value="m")
        self.assertFalse(errors(program(reexport, module=True)))

    def test_callback_exceptions_and_no_mutation(self):
        tree = program(declaration("let"), declaration("let"))
        original = copy.deepcopy(tree)
        errors(tree)
        self.assertEqual(tree, original)
        def fail(message, node):
            raise RuntimeError("report callback")
        with self.assertRaisesRegex(RuntimeError, "report callback"):
            validate_program(tree, fail)

    def test_native_nodes(self):
        tree = SimpleNamespace(type="Program", sourceType="script", body=[
            SimpleNamespace(type="VariableDeclaration", kind="let", declarations=[
                SimpleNamespace(type="VariableDeclarator", id=SimpleNamespace(type="Identifier", name="x"), init=None)]),
            SimpleNamespace(type="VariableDeclaration", kind="var", declarations=[
                SimpleNamespace(type="VariableDeclarator", id=SimpleNamespace(type="Identifier", name="x"), init=None)])])
        self.assertTrue(errors(tree))

    def test_edition_feature_gates(self):
        cases = [
            (node("ArrowFunctionExpression", params=[], body=node("Literal", value=1), expression=True), 5),
            (node("BinaryExpression", operator="**", left=node("Literal", value=1), right=node("Literal", value=2)), 2015),
            (node("FunctionExpression", params=[], body=node("BlockStatement", body=[]), **{"async": True}), 2016),
            (node("ImportExpression", source=node("Literal", value="m"), options=None), 2019),
            (node("LogicalExpression", operator="??", left=identifier(), right=identifier()), 2019),
            (node("AssignmentExpression", operator="??=", left=identifier(), right=identifier()), 2020),
            (node("Literal", value=None, bigint="1", raw="1n"), 2019),
            (node("Literal", value=1000, raw="1_000"), 2020),
            (node("ClassExpression", id=None, body=node("ClassBody", body=[node("PropertyDefinition", key=identifier(), value=None, computed=False, static=False)])), 2021),
            (node("ImportExpression", source=node("Literal", value="m"), options=node("ObjectExpression", properties=[])), 2024),
        ]
        for feature, edition in cases:
            with self.subTest(feature=feature["type"], edition=edition):
                self.assertTrue(errors(program(node("ExpressionStatement", expression=feature)), edition))

    def test_assignment_pattern_and_context_negatives(self):
        sources = [
            "(a=b)=1;", "function f(){new.target=1;}", "function f(){++new.target;}",
            "function*g(){(yield)=1;}", "() => ({}) = 1;", "(async function(){})=1;", "(``)=1;",
            "var x; [...x=1]=[];", "var a,b; ({...a,b}=o);", "([...[x]=[]])=>0;",
            "'use strict'; for([arguments] of [[]]){}", "'use strict'; for({eval} in {}){}",
            "class C{static{await;}}", "class C{static{await:0;}}", "class C{static{let await;}}",
            "class C{static{(await=>0);}}", "class C{static{((x=await)=>0);}}",
            "class C{static{function await(){}}}", "class C{static{class await{}}}",
            "async(a=(await)=>{})=>{};", "async(x=await)=>{};", "function*g(x=yield){}",
            "function*g(){(x=yield)=>{};}", "({async #m(){}});", "class C{field={get #m(){}}}",
        ]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)

    def test_assignment_pattern_and_context_positives(self):
        sources = [
            "(a)=1;", "(obj.a)=1;", "({a}=o);", "([a]=o);", "var a; [...a]=o;",
            "({a:{b},...o.rest}=x);", "async function f(){()=>await; ()=>{var await;};}",
            "function*g(){()=>yield;}", "class C{static{()=>await;function f(){var await;return await;}}}",
            "function f(...[x]){}", "function f(...{length}){}",
        ]
        for source in sources:
            with self.subTest(source=source):
                esprima.parseScript(source)

    def test_duplicate_proto_is_deferred_until_expression_context(self):
        for source in ("({__proto__: null, __proto__: null});", "({['x']:1,__proto__:1,'__proto__':2});"):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)
        for source in ("({__proto__:a,__proto__:b}=obj);", "for({__proto__:a,__proto__:b} of xs);",
                "({__proto__, ['__proto__']:1, __proto__:null});", "({__proto__(){}, __proto__:null});"):
            with self.subTest(source=source):
                esprima.parseScript(source)
        second = node("Property", key=identifier("__proto__"), value=node("Literal", value=None),
            kind="init", computed=False, method=False, shorthand=False, _protoErrorStart=20)
        expression = node("ObjectExpression", properties=[copy.deepcopy(second), second])
        found = errors(program(node("ExpressionStatement", expression=expression)))
        self.assertIs(found[0][1], second)

    def test_scope_and_context_source_negatives(self):
        sources = [
            "let a; let a;", "let a; {var a;}", "{let a; var a;}",
            "function f(a){ let a; }", "function f(a=1){'use strict';}",
            "for(let a;;){var a;}", "switch(x){case 0: let a; break; default: let a;}",
            "try{}catch({a}){var a;}", "try{}catch(a){let a;}",
            "super.x;", "super();", "new.target;", "(()=>new.target)();",
            "class A { constructor(){super();} }", "class A extends B { m(){super();} }",
            "class A { m(){function f(){return super.x;}} }", "class A { #x; #x; }",
            "class A { #x; static #x; }", "class A { m(){return this.#missing;} }",
            "class A { #x; m(){delete this.#x;} }", "class A { x=arguments; }",
            "class A { static {return;} }", "class A { #constructor; }",
            "({__proto__: null, '__proto__': null});", "'use strict'; delete x;",
            "'use strict'; if(x) function f(){}", "if(x) async function f(){}",
            "while(0) function f(){}", "with(x) function f(){}", "if(x) label: function f(){}",
            "let f; label: function f(){}", "{let f; label: function f(){}}", "{label:function f(){} var f;}",
        ]
        for source in sources:
            with self.subTest(source=source):
                try:
                    tree = esprima.parseScript(source)
                except esprima.Error:
                    continue
                self.assertTrue(errors(tree), source)

    def test_valid_shadowing_annex_b_and_class_contexts(self):
        sources = [
            '("use strict"); with(x){}', '"foo"; ("use strict"); with(x){}',
            '("foo"); "use strict"; with(x){}',
            "var a; var a;", "function f(a,a){}", "async function f(a,a){}", "function* f(a,a){}",
            "async function await(){}", "function* yield(){}", "try{}catch([a,b]){}", "try{}catch([a=1]){}",
            "class A { static {function f(){} var f;} }", "class A { static {function f(){} function f(){}} }",
            "label: other: function f(){}", "let f; {label: function f(){}}",
            "{function f(){} function f(){}}", "let a; {function a(){}}", "if(x) function f(){}",
            "function f(a){var a; function a(){} {let a;}}", "try{}catch(a){var a;}",
            "function f(){return ()=>new.target;}", "class A { x=new.target; static {new.target;} }",
            "class A extends B { constructor(){(()=>super())();} m(){return ()=>super.x;} }",
            "class A { #x; m(){function f(){return this.#x;} return f;} }",
            "class A { get #x(){return 1;} set #x(v){} }", "class A { #x; m(){class B {m(o){return o.#x;}}} }",
            "({m(){return super.x;}, get x(){return super.x;}});",
            "({__proto__, ['__proto__']: 1, __proto__: null});",
        ]
        for source in sources:
            with self.subTest(source=source):
                tree = esprima.parseScript(source)
                self.assertFalse(errors(tree), source)


if __name__ == "__main__":
    unittest.main()
