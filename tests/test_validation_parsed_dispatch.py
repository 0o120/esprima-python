"""Parser-origin traversal preserves public extension/delegate contracts."""
import unittest

import esprima
from esprima import nodes
from esprima.validation import validate_program


class ParsedValidationDispatchTests(unittest.TestCase):
    def test_standalone_validation_observes_new_expression_children(self):
        program = esprima.parseModule('1;')
        reference = nodes.Identifier('await')
        program.body[0].expression.extension = reference
        before = program.toDict()
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)))
        self.assertTrue(any('await is a reserved word' in message and original is reference for message, original in errors))
        self.assertEqual(program.toDict(), before)

    def test_standalone_validation_observes_changed_native_node_type(self):
        program = esprima.parseScript('left + right;')
        expression = program.body[0].expression
        expression.type = 'AssignmentExpression'
        expression.operator = '='
        expression.left = nodes.Literal(1, '1')
        before = program.toDict()
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)))
        self.assertTrue(any('Invalid left-hand side' in message and original is expression.left for message, original in errors))
        self.assertEqual(program.toDict(), before)

    def test_delegate_added_child_receives_complete_validation(self):
        def delegate(node, metadata):
            if node.type == 'Literal':
                node.extension = nodes.Identifier('await')
        with self.assertRaisesRegex(esprima.Error, 'await is a reserved word'):
            esprima.parseModule('1;', delegate=delegate)

    def test_delegate_type_change_receives_complete_validation(self):
        def delegate(node, metadata):
            if node.type == 'BinaryExpression':
                node.type = 'AssignmentExpression'
                node.operator = '='
                node.left = nodes.Literal(1, '1')
        with self.assertRaisesRegex(esprima.Error, 'Invalid left-hand side'):
            esprima.parseScript('left + right;', delegate=delegate)

    def test_delegate_custom_mapping_replacement_is_fully_validated(self):
        def delegate(node, metadata):
            if node.type == 'Program':
                return {'type': 'Program', 'sourceType': 'module', 'body': [
                    {'type': 'ExpressionStatement', 'expression':
                        {'type': 'Literal', 'value': 1, 'extra': {'type': 'Identifier', 'name': 'await'}}}]}
        with self.assertRaisesRegex(esprima.Error, 'await is a reserved word'):
            esprima.parseModule('1;', delegate=delegate)

    def test_source_sensitive_expressions_keep_early_errors(self):
        cases = ['"use strict"; delete value;', 'super();', '#missing in value;',
                 'class C { method() { super(); } }', 'class C { field = arguments; }',
                 'function* f() { const arrow = (value = yield 1) => value; }']
        for source in cases:
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)

    def test_historical_edition_and_jsx_keep_complete_checks(self):
        with self.assertRaisesRegex(esprima.Error, '2016'):
            esprima.parseScript('left ** right;', {'ecmaVersion': 2015})
        with self.assertRaises(esprima.Error):
            esprima.parseModule('<box>{await}</box>;', {'jsx': True})

    def test_parser_tree_shape_and_metadata_are_unchanged(self):
        source = 'const list = [first + second, condition ? this.value : call(1)];'
        ordinary = esprima.parseScript(source, {'range': True, 'loc': True, 'comment': True}).toDict()
        delegated = esprima.parseScript(source, {'range': True, 'loc': True, 'comment': True}, delegate=lambda *args: None).toDict()
        self.assertEqual(ordinary, delegated)


if __name__ == '__main__':
    unittest.main()
