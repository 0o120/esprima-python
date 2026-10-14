"""Frozen boundary cases from the independent Babel 2023-11 audit.

The external audit compares thousands of source-data cases and complete ESTree
positions. These regressions have no Node/Babel dependency in the normal suite.
"""
import unittest

import esprima


class DecoratorBoundaryTests(unittest.TestCase):
    @staticmethod
    def parse(source, source_type='script', **options):
        return esprima.parse(source, sourceType=source_type, decorators=True, **options)

    def test_class_decorators_inherit_sloppy_enclosing_context(self):
        for expression in ('yield', 'let', '(delete value)', 'dec(delete value)'):
            for wrapper in ('{}', 'function f() {{ {} }}', 'async function f() {{ {} }}'):
                source = wrapper.format(f'@{expression} class C {{}}')
                with self.subTest(source=source):
                    self.parse(source)
        tree = self.parse('@yield class C {}')
        self.assertEqual(tree.body[0].decorators[0].expression.name, 'yield')
        self.assertEqual(self.parse('@let class C {}').body[0].decorators[0].expression.name, 'let')

    def test_member_and_strict_class_decorators_retain_strict_rules(self):
        for expression in ('yield', 'let', '(delete value)', 'dec(delete value)'):
            for source_type, source in (
                ('module', f'@{expression} class C {{}}'),
                ('script', f'"use strict"; @{expression} class C {{}}'),
                ('script', f'class C {{ @{expression} method() {{}} }}'),
            ):
                with self.subTest(source=source), self.assertRaises(esprima.Error):
                    self.parse(source, source_type)

    def test_parenthesized_expressions_cannot_escape_as_arrow_placeholders(self):
        for expression in ('(a,)', '(a,b,)', '()', '(...args)', '(a,...args)'):
            for source in (f'@{expression} class C {{}}', f'class C {{ @{expression} method() {{}} }}'):
                with self.subTest(source=source), self.assertRaises(esprima.Error):
                    self.parse(source)
        for expression in ('(a,b)', '(() => dec)', '(function(){})', '((a,b))'):
            with self.subTest(expression=expression):
                self.parse(f'@{expression} class C {{}}')

    def test_private_chains_use_the_correct_private_environment(self):
        for source in (
            'class C { #x; @obj.#x method() {} }',
            'class C { #x; @obj.#x() method() {} }',
            'class C { @obj.#x method() {} #x; }',
            'class Outer { #x; method(){ @obj.#x class C {} } }',
            'class Outer { #x; method(){ class C { @obj.#x method() {} } } }',
        ):
            with self.subTest(source=source):
                self.parse(source)
        for source in (
            '@obj.#x class C { #x; }',
            'class C { @obj.#x method() {} }',
            'class Outer { #x; } @obj.#x class C {}',
        ):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                self.parse(source)

    def test_restricted_chains_and_parenthesized_alternatives(self):
        for expression in ('dec().member', 'dec()()', 'dec[member]', 'dec?.member', 'dec?.()'):
            with self.subTest(expression=expression), self.assertRaises(esprima.Error):
                self.parse(f'@{expression} class C {{}}')
            with self.subTest(parenthesized=expression):
                self.parse(f'@({expression}) class C {{}}')

    def test_export_and_class_positions_have_separate_starts(self):
        for source in (
            '@dec export class C {}', 'export @dec class C {}',
            '@dec export default class C {}', 'export default @dec class C {}',
            '@dec export default class {}', 'export default @dec class {}',
            '@dec @other export class C {}', 'export @dec @other class C {}',
            '/*😀*/\n@dec export default class {}',
        ):
            with self.subTest(source=source):
                offset = lambda index: len(source[:index].encode('utf-16-le')) // 2
                tree = self.parse(source, 'module', range=True, loc=True)
                export = tree.body[0]
                declaration = export.declaration
                self.assertEqual(export.range, [offset(source.index('export')), offset(len(source))])
                self.assertEqual(declaration.range, [offset(source.index('@')), offset(len(source))])
                self.assertEqual(declaration.decorators[0].range,
                                 [offset(source.index('@')), offset(source.index('@') + 4)])
                self.assertEqual(declaration.loc.start.line, 2 if '\n' in source else 1)

    def test_decorators_on_both_sides_of_export_are_rejected(self):
        for source in ('@dec export @other class C {}', '@dec export default @other class C {}'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                self.parse(source, 'module')

    def test_auto_accessor_keyword_disambiguation(self):
        for separator in (' ', '\t', '/*inline*/'):
            tree = self.parse(f'class C {{ @dec accessor{separator} field; }}')
            element = tree.body[0].body.body[0]
            self.assertEqual(element.type, 'AccessorProperty')
            self.assertEqual(element.key.name, 'field')
        for separator in ('\n', '\r\n', '\u2028', '\u2029', '/*\n*/', '//line\n'):
            tree = self.parse(f'class C {{ @dec accessor{separator} field; }}')
            elements = tree.body[0].body.body
            self.assertEqual([element.type for element in elements], ['PropertyDefinition', 'PropertyDefinition'])
            self.assertEqual(elements[0].key.name, 'accessor')
            self.assertEqual(elements[1].key.name, 'field')
            self.assertEqual(len(elements[0].decorators), 1)
        with self.assertRaises(esprima.Error):
            self.parse(r'class C { \u0061ccessor field; }')

    def test_await_and_yield_follow_the_enclosing_expression_context(self):
        self.parse('@(await dec) class C {}', 'module')
        self.parse('async function f(){ @(await dec) class C {} }')
        self.parse('function* f(){ @(yield dec) class C {} }')
        self.parse('async function* f(){ @(yield await dec) class C {} }')
        for source in ('@(await dec) class C {}', '@(yield dec) class C {}',
                       'function f(){ @(await dec) class C {} }'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                self.parse(source)


if __name__ == '__main__':
    unittest.main()
