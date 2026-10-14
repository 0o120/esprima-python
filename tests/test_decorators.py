"""Decorator proposal API, native/mapping semantics, and lexical contracts."""
import copy
import json
import subprocess
import unittest

import esprima
from esprima.validation import validate_program


OPTIONS = {'decorators': True, 'range': True, 'loc': True}


class DecoratorTests(unittest.TestCase):
    def test_explicit_gate_and_edition(self):
        for code in ('@d class C {}', 'class C { accessor x; }'):
            with self.subTest(code=code):
                with self.assertRaises(esprima.Error):
                    esprima.parseScript(code)
                with self.assertRaises(esprima.Error):
                    esprima.parseScript(code, {'decorators': True, 'ecmaVersion': 2025})
                esprima.parseScript(code, OPTIONS)
        with self.assertRaises(esprima.Error):
            esprima.tokenize('@d class C {}')
        with self.assertRaises(esprima.Error):
            esprima.tokenize('@d class C {}', {'decorators': True, 'ecmaVersion': 2025})

    def test_class_and_member_shapes_nullable_values(self):
        ast = esprima.parseScript('@first @factory(1) class C { @d accessor #value; @d static x = 1; @d get y() {} @d set y(v) {} }', OPTIONS)
        mapping = ast.toDict()
        cls = mapping['body'][0]
        self.assertEqual([d['type'] for d in cls['decorators']], ['Decorator', 'Decorator'])
        self.assertEqual(cls['decorators'][1]['expression']['type'], 'CallExpression')
        fields = cls['body']['body']
        self.assertEqual(fields[0]['type'], 'AccessorProperty')
        self.assertEqual(fields[0]['key'], {'type': 'PrivateIdentifier', 'name': 'value', 'range': fields[0]['key']['range'], 'loc': fields[0]['key']['loc']})
        self.assertIn('value', fields[0])
        self.assertIsNone(fields[0]['value'])
        self.assertEqual([member['kind'] for member in fields[2:]], ['get', 'set'])
        self.assertTrue(fields[1]['static'])
        errors = []
        before = copy.deepcopy(mapping)
        validate_program(mapping, lambda message, node: errors.append(message))
        self.assertEqual(errors, [])
        self.assertEqual(mapping, before)

    def test_valid_arbitrary_expression_and_call_arguments(self):
        positives = (
            '@(a,b) class C {}', '@(() => value) class C {}',
            '@(new Factory()) class C {}', '@(obj?.x) class C {}',
            '@factory(...args, arg => arg) class C {}',
            'const C = @d class extends Base { @d static *m() { yield 1; } };',
            'async function f(){ @(await factory()) class C {} }',
            'function* f(){ @(yield factory) class C {} }',
            'class Outer { #d; m(){ @(this.#d) class C {} } }',
        )
        for code in positives:
            with self.subTest(code=code):
                esprima.parseScript(code, OPTIONS)

    def test_illegal_targets_and_restricted_expressions(self):
        negatives = (
            '@d function f() {}', '@d const x=1;', '@d x;',
            'class C { @d constructor(){} }', 'class C { @d static {} }',
            'class C { m(@d x){} }', '@obj[x] class C {}',
            '@obj?.x class C {}', '@factory().x class C {}',
            '@factory()() class C {}', '@this.x class C {}',
            '@(a,) class C {}', '@() class C {}',
            'class C { accessor x(){} }', 'class C { accessor constructor; }',
            'class C { static accessor prototype; }',
            'class C { @d accessor #x; #x; }',
            'class C { @d accessor x = arguments; }',
            'class C { @d accessor x = await y; }',
            'class C { @d accessor x = yield y; }',
            'class C { @d accessor x = super(); }',
            'class C { @missing.#x m(){} }',
        )
        for code in negatives:
            with self.subTest(code=code), self.assertRaises(esprima.Error):
                esprima.parseScript(code, OPTIONS)

    def test_export_ranges_and_mixed_positions(self):
        for code, cls_start, export_start in (
            ('@d export class C {}', 0, 3),
            ('export @d class C {}', 7, 0),
            ('@d export default class {}', 0, 3),
            ('export default @d class {}', 15, 0),
        ):
            with self.subTest(code=code):
                node = esprima.parseModule(code, OPTIONS).toDict()['body'][0]
                self.assertEqual(node['range'][0], export_start)
                self.assertEqual(node['declaration']['range'][0], cls_start)
        for code in ('@a export @b class C {}', '@a export default @b class {}', 'export @d function f(){}'):
            with self.subTest(code=code), self.assertRaises(esprima.Error):
                esprima.parseModule(code, OPTIONS)

    def test_tokens_comments_utf16_delegate_and_tolerant_errors(self):
        code = '// 😀\n@d("😀") class C { @d accessor x; }'
        options = {**OPTIONS, 'tokens': True, 'comment': True}
        seen = []
        native = esprima.parseScript(code, options, lambda node, metadata: seen.append(node))
        mapping = native.toDict()
        standalone = esprima.toDict(esprima.tokenize(code, OPTIONS))
        self.assertEqual(mapping['tokens'], standalone)
        self.assertEqual(mapping['body'][0]['decorators'][0]['range'][0], len('// 😀\n'.encode('utf-16-le')) // 2)
        self.assertTrue(any(node.type == 'Decorator' for node in seen))
        self.assertTrue(any(node.type == 'AccessorProperty' for node in seen))
        self.assertEqual(options, {**OPTIONS, 'tokens': True, 'comment': True})
        recovered = esprima.parseScript('class C { @d x = arguments; }', {**OPTIONS, 'tolerant': True})
        self.assertGreater(len(recovered.errors), 0)

    def test_cli_option(self):
        import sys
        result = subprocess.run([sys.executable, '-I', '-B', '-m', 'esprima', '--decorators'], input='@d class C {}', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['body'][0]['decorators'][0]['type'], 'Decorator')

    def test_supplied_and_delegate_ast_decorators_are_validated(self):
        base = esprima.parseScript('@d class C {}', OPTIONS).toDict()
        for decorators in (['bad'], [{'type': 'Decorator', 'expression': None}],
                           [{'type': 'Decorator', 'expression': {'type': 'VariableDeclaration', 'kind': 'var', 'declarations': []}}],
                           {'type': 'Decorator', 'expression': {'type': 'Identifier', 'name': 'd'}}):
            mapping = copy.deepcopy(base)
            mapping['body'][0]['decorators'] = decorators
            before = copy.deepcopy(mapping)
            errors = []
            validate_program(mapping, lambda message, node: errors.append(message))
            self.assertTrue(errors, decorators)
            self.assertEqual(mapping, before)
        def replace(node, metadata):
            if node.type == 'Decorator':
                node.expression = None
        with self.assertRaises(esprima.Error):
            esprima.parseScript('@d class C {}', OPTIONS, replace)


if __name__ == '__main__':
    unittest.main()
