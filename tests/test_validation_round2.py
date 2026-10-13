"""Observable contracts for combined validator dispatch/context optimizations."""
import copy
import unittest
from collections.abc import Mapping

from esprima import nodes
from esprima.regexp_validator import RegExpSyntaxError
from esprima.validation import validate_program


def node(kind, **fields):
    return {'type': kind, **fields}


class ValidationRound2Tests(unittest.TestCase):
    def test_duplicate_ordinary_parameters_keep_second_binding_identity(self):
        first = node('Identifier', name='ordinary')
        second = node('Identifier', name='ordinary')
        function = node('FunctionDeclaration', id=node('Identifier', name='f'), params=[first, second],
                        body=node('BlockStatement', body=[]), generator=False, **{'async': False})
        program = node('Program', sourceType='module', body=[function])
        before = copy.deepcopy(program)
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)))
        self.assertEqual(program, before)
        self.assertTrue(any('already been declared' in message and original is second for message, original in errors))

    def test_module_reserved_references_and_nonstandard_child_are_visited(self):
        reference = node('Identifier', name='await')
        literal = node('Literal', value=1, raw='1', extra=reference)
        program = node('Program', sourceType='module', body=[node('ExpressionStatement', expression=literal)])
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)))
        self.assertTrue(any('await is a reserved word' in message and original is reference for message, original in errors))

    def test_latest_edition_retains_regex_syntax_and_older_edition_gates(self):
        literal = node('Literal', value=None, regex={'pattern': '(?i:a)', 'flags': ''})
        program = node('Program', sourceType='script', body=[node('ExpressionStatement', expression=literal)])
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)), 2024)
        self.assertTrue(any('2025' in message and original is literal for message, original in errors))
        errors.clear()
        validate_program(program, lambda message, original: errors.append((message, original)), 2026)
        self.assertEqual(errors, [])
        literal['regex']['pattern'] = '(?'
        with self.assertRaises(RegExpSyntaxError):
            validate_program(program, lambda *args: None, 2026)

    def test_custom_native_descriptor_exceptions_are_not_suppressed(self):
        class Custom(nodes.Node):
            @property
            def type(self):
                return 'Identifier'
            @property
            def name(self):
                return 'ordinary'
            @property
            def attributes(self):
                raise RuntimeError('descriptor failure')
        program = node('Program', sourceType='script', body=[node('ExpressionStatement', expression=Custom())])
        with self.assertRaisesRegex(RuntimeError, 'descriptor failure'):
            validate_program(program, lambda *args: None)

    def test_custom_mapping_field_semantics_remain_authoritative(self):
        class Custom(Mapping):
            def __init__(self):
                self.type = 'Literal'
                self.name = 'ordinary'
                self.data = {'type': 'Identifier', 'name': 'await'}
            def __getitem__(self, key):
                return self.data[key]
            def __iter__(self):
                return iter(self.data)
            def __len__(self):
                return len(self.data)
        reference = Custom()
        program = node('Program', sourceType='module', body=[node('ExpressionStatement', expression=reference)])
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)))
        self.assertTrue(any('await' in message and original is reference for message, original in errors))

    def test_callback_exception_propagates_without_mutating_ast(self):
        program = node('Program', sourceType='module', body=[node('ExpressionStatement', expression=node('Identifier', name='yield'))])
        before = copy.deepcopy(program)
        def report(message, original):
            raise RuntimeError('callback failure')
        with self.assertRaisesRegex(RuntimeError, 'callback failure'):
            validate_program(program, report)
        self.assertEqual(program, before)


if __name__ == '__main__':
    unittest.main()
