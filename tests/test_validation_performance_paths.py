"""Correctness constraints for validation fast paths and per-pass caches."""
from collections import UserDict
from collections.abc import Mapping
import copy
from types import SimpleNamespace
import unittest

import esprima
from esprima import nodes
from esprima.validation import _get, _children, validate_program


def mapping_node(node_type, **fields):
    return {"type": node_type, **fields}


class VirtualMapping(Mapping):
    def __init__(self, content):
        self.content = content
        self.type = "IncorrectAttributeType"
    def __getitem__(self, key):
        return self.content[key]
    def __iter__(self):
        return iter(self.content)
    def __len__(self):
        return len(self.content)


class OverriddenGet(dict):
    def get(self, key, default=None):
        return "CustomGetType" if key == "type" else super().get(key, default)


class ValidationPerformancePathsTests(unittest.TestCase):
    def test_exact_native_and_mapping_explicit_nulls(self):
        native = nodes.ReturnStatement(None)
        self.assertIsNone(_get(native, "argument", "fallback"))
        self.assertIsNone(_get({"argument": None}, "argument", "fallback"))
        self.assertEqual(_get({}, "missing", "fallback"), "fallback")
        self.assertEqual(_get(SimpleNamespace(), "missing", "fallback"), "fallback")

    def test_custom_mapping_get_semantics_and_attribute_precedence(self):
        custom = VirtualMapping({"type": "Identifier", "name": "x", "nullable": None})
        self.assertEqual(_get(custom, "type"), "Identifier")
        self.assertIsNone(_get(custom, "nullable", "fallback"))
        self.assertEqual(_get(custom, "missing", "fallback"), "fallback")
        self.assertEqual(_get(OverriddenGet(type="Identifier"), "type"), "CustomGetType")
        self.assertEqual(_get(UserDict({"type": "Literal"}), "type"), "Literal")

    def test_native_subclass_properties_and_dynamic_fields_are_honored(self):
        class Custom(nodes.Node):
            @property
            def type(self):
                return "Identifier"
            @property
            def name(self):
                return "custom"
        native = Custom()
        self.assertEqual(_get(native, "type"), "Identifier")
        self.assertEqual(_get(native, "name"), "custom")

    def test_child_iteration_is_semantic_and_identity_preserving(self):
        child = nodes.Identifier("x")
        custom = VirtualMapping({"type": "Identifier", "name": "y"})
        root = mapping_node("UnknownExtension", first=child, sequence=[None, custom],
            loc=mapping_node("Identifier", name="metadata"), _hidden=child, value="text")
        result = list(_children(root))
        self.assertEqual(len(result), 2)
        self.assertIs(result[0], child)
        self.assertIs(result[1], custom)
        self.assertEqual(list(_children(nodes.ReturnStatement(child))), [child])

    def test_scope_cache_is_per_validation_and_retains_original_nodes(self):
        binding = mapping_node("Identifier", name="x")
        lexical = mapping_node("VariableDeclaration", kind="let", declarations=[
            mapping_node("VariableDeclarator", id=binding, init=None)])
        variable = mapping_node("VariableDeclaration", kind="var", declarations=[
            mapping_node("VariableDeclarator", id=mapping_node("Identifier", name="x"), init=None)])
        nested = mapping_node("BlockStatement", body=[variable])
        root = mapping_node("Program", sourceType="script", body=[lexical, nested])
        original = copy.deepcopy(root)
        errors = []
        validate_program(root, lambda message, node: errors.append((message, node)))
        self.assertEqual(root, original)
        self.assertTrue(errors)
        self.assertIs(errors[0][1], variable["declarations"][0]["id"])
        # A new pass must observe subsequent caller changes rather than a
        # global cached result from the old shape/binding name.
        variable["declarations"][0]["id"]["name"] = "y"
        errors = []
        validate_program(root, lambda message, node: errors.append(message))
        self.assertFalse(errors)

    def test_unknown_extension_children_do_not_omit_var_conflicts(self):
        lexical = mapping_node("VariableDeclaration", kind="let", declarations=[
            mapping_node("VariableDeclarator", id=mapping_node("Identifier", name="x"), init=None)])
        variable = mapping_node("VariableDeclaration", kind="var", declarations=[
            mapping_node("VariableDeclarator", id=mapping_node("Identifier", name="x"), init=None)])
        extension = VirtualMapping(mapping_node("UnknownExtension", nested=variable))
        root = mapping_node("Program", sourceType="script", body=[lexical, extension])
        errors = []
        validate_program(root, lambda message, node: errors.append(message))
        self.assertTrue(errors)

    def test_all_statement_var_containers_and_function_boundaries(self):
        sources = [
            "let x; if(a){var x;}", "let x; while(a){var x;}", "let x; do{var x;}while(a);",
            "let x; for(var x;;){}", "let x; for(var x in a){}", "let x; for(var x of a){}",
            "let x; switch(a){case 1:var x;}", "let x; try{var x;}finally{}",
            "let x; try{}catch(e){var x;}", "let x; label:{var x;}", "let x; with(a){var x;}",
        ]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)
        for source in ("let x; function f(){var x;}", "let x; class C{static{var x;}}",
                "let x; const f=()=>{var x;};"):
            with self.subTest(source=source):
                esprima.parseScript(source)


if __name__ == "__main__":
    unittest.main()
