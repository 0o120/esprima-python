"""Restricted productions inspect trivia gaps, not lines within tokens."""
import importlib
import unittest
from unittest.mock import patch

import esprima
from esprima.parser import Marker, Parser


BREAKS = ('\n', '\r', '\r\n', '\u2028', '\u2029')
GAPS = BREAKS + ('/*\n*/', '// comment\n')


class LineTerminatorBoundaryTests(unittest.TestCase):
    def test_next_token_gap_does_not_change_raw_token_ending_lines(self):
        for gap, expected in ((' ', False), ('/* same line */', False),
                              ('\n', True), ('/*\n*/', True)):
            parser = Parser('a' + gap + '"x\\\ny"')
            parser.nextToken()
            with self.subTest(gap=gap):
                self.assertIs(parser.hasLineTerminator, expected)
                self.assertEqual(parser.lookahead.value, 'xy')
                self.assertEqual(parser.lookahead.lineNumber, 3 if expected else 2)

    def test_custom_position_markers_do_not_change_statement_grammar(self):
        class OffsetMarker(Marker):
            def __getattribute__(self, name):
                value = super().__getattribute__(name)
                return value + 100 if name == 'line' else value

        module = importlib.import_module('esprima.parser')
        with patch.object(module, 'Marker', OffsetMarker):
            body = esprima.parseScript('function f(){return "value";}').body[0].body.body
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0].argument.value, 'value')

    def test_return_inserts_semicolon_before_strings_and_templates(self):
        for gap in GAPS:
            for expression in ('"value"', '"x\\\ny"', '`value`', '`x\ny`', '"x\u2028y"', '"x\u2029y"'):
                with self.subTest(gap=gap, expression=expression):
                    body = esprima.parseScript('function f(){return' + gap + expression + ';}').body[0].body.body
                    self.assertEqual(len(body), 2)
                    self.assertEqual(body[0].type, 'ReturnStatement')
                    self.assertIsNone(body[0].argument)
                    self.assertEqual(body[1].type, 'ExpressionStatement')

    def test_return_and_throw_allow_multiline_tokens_without_a_gap_break(self):
        for separator in BREAKS:
            for keyword in ('return', 'throw'):
                for expression, expected in (('"x\\' + separator + 'y"', 'Literal'),
                                              ('`x' + separator + 'y`', 'TemplateLiteral')):
                    with self.subTest(separator=separator, keyword=keyword, expression=expression):
                        body = esprima.parseScript('function f(){' + keyword + ' ' + expression + ';}').body[0].body.body
                        self.assertEqual(len(body), 1)
                        self.assertEqual(body[0].argument.type, expected)
        for separator in ('\u2028', '\u2029'):
            for keyword in ('return', 'throw'):
                source = 'function f(){' + keyword + ' "x' + separator + 'y";}'
                with self.subTest(separator=separator, keyword=keyword):
                    argument = esprima.parseScript(source).body[0].body.body[0].argument
                    self.assertEqual(argument.value, 'x' + separator + 'y')

    def test_throw_rejects_real_gap_line_terminators(self):
        for gap in GAPS:
            for expression in ('"value"', '"x\\\ny"', '`x\ny`'):
                with self.subTest(gap=gap, expression=expression), self.assertRaisesRegex(esprima.Error, 'newline after throw'):
                    esprima.parseScript('function f(){throw' + gap + expression + ';}')

    def test_yield_retains_multiline_arguments_and_respects_real_breaks(self):
        for expression in ('"x\\\ny"', '`x\ny`'):
            for gap in (' ', '\n', '/*\n*/'):
                body = esprima.parseScript('function* f(){yield' + gap + expression + ';}').body[0].body.body
                with self.subTest(expression=expression, gap=gap):
                    self.assertEqual(body[0].expression.type, 'YieldExpression')
                    if gap == ' ':
                        self.assertIsNotNone(body[0].expression.argument)
                        self.assertEqual(len(body), 1)
                    else:
                        self.assertIsNone(body[0].expression.argument)
                        self.assertEqual(len(body), 2)

    def test_internal_newline_cannot_insert_a_missing_statement_separator(self):
        for source in ('a "x\\\ny";', '1 "x\\\ny";', '"a" "x\\\ny";',
                       'var x=1 "x\\\ny";'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)

    def test_class_getters_and_setters_can_cross_line_breaks(self):
        for gap in (' ',) + GAPS:
            for prefix in ('', 'static '):
                source = 'class C{' + prefix + 'get' + gap + 'x(){return 1;} ' + prefix + 'set' + gap + 'x(v){}}'
                with self.subTest(gap=gap, prefix=prefix):
                    elements = esprima.parseScript(source).body[0].body.body
                    self.assertEqual([node.type for node in elements], ['MethodDefinition'] * 2)
                    self.assertEqual([node.kind for node in elements], ['get', 'set'])
                    self.assertEqual([node.key.name for node in elements], ['x', 'x'])
                    self.assertEqual([node.static for node in elements], [bool(prefix)] * 2)

    def test_class_modifiers_use_start_of_multiline_property_names(self):
        for separator in BREAKS:
            for prefix in ('', 'static '):
                for modifier, params in (('get', ''), ('set', 'v'), ('async', '')):
                    source = 'class C{' + prefix + modifier + ' "x\\' + separator + 'y"(' + params + '){}}'
                    with self.subTest(separator=separator, prefix=prefix, modifier=modifier):
                        elements = esprima.parseScript(source).body[0].body.body
                        self.assertEqual(len(elements), 1)
                        method = elements[0]
                        self.assertEqual(method.key.value, 'xy')
                        self.assertEqual(method.kind, modifier if modifier != 'async' else 'method')
                        self.assertIs(method.value.isAsync, modifier == 'async')

    def test_async_modifier_still_disallows_a_line_break_before_the_name(self):
        for gap in GAPS:
            elements = esprima.parseScript('class C{async' + gap + '"x\\\ny"(){}}').body[0].body.body
            with self.subTest(gap=gap):
                self.assertEqual([node.type for node in elements], ['PropertyDefinition', 'MethodDefinition'])
                self.assertEqual(elements[0].key.name, 'async')
                self.assertFalse(elements[1].value.isAsync)

    def test_modifier_lookahead_distinguishes_quoted_punctuation_from_tokens(self):
        for name in ('(', ')', '{', '}', '=', ';', '*', '[', ']', ',', '?.'):
            for modifier in ('static', 'async', 'accessor'):
                suffix = '=1;' if modifier == 'accessor' else '(){}'
                source = 'class C{' + modifier + ' "' + name + '"' + suffix + '}'
                with self.subTest(source=source):
                    elements = esprima.parseScript(source, decorators=modifier == 'accessor').body[0].body.body
                    self.assertEqual(len(elements), 1)
                    member = elements[0]
                    self.assertEqual(member.key.value, name)
                    if modifier == 'accessor':
                        self.assertEqual(member.type, 'AccessorProperty')
                    else:
                        self.assertEqual(member.type, 'MethodDefinition')
                        self.assertIs(member.static, modifier == 'static')
                        self.assertIs(member.value.isAsync, modifier == 'async')

    def test_auto_accessor_modifier_uses_start_of_multiline_name(self):
        for gap in (' ', '\n', '/*\n*/'):
            elements = esprima.parseScript('class C{accessor' + gap + '"x\\\ny"=1;}', decorators=True).body[0].body.body
            with self.subTest(gap=gap):
                if gap == ' ':
                    self.assertEqual(len(elements), 1)
                    self.assertEqual(elements[0].type, 'AccessorProperty')
                    self.assertEqual(elements[0].key.value, 'xy')
                else:
                    self.assertEqual([node.type for node in elements], ['PropertyDefinition'] * 2)

    def test_get_and_set_field_and_method_names_remain_available(self):
        elements = esprima.parseScript('class C{get;set=1;get(){}set(v){}}').body[0].body.body
        self.assertEqual([node.type for node in elements], ['PropertyDefinition'] * 2 + ['MethodDefinition'] * 2)
        for keyword in ('get', 'set'):
            with self.subTest(keyword=keyword), self.assertRaises(esprima.Error):
                esprima.parseScript('class C{' + keyword + '\nx;}')
            for prefix in ('', 'static '):
                for gap in GAPS:
                    source = 'class C{' + prefix + keyword + gap + '*method(){}}'
                    with self.subTest(source=source):
                        field, method = esprima.parseScript(source).body[0].body.body
                        self.assertEqual(field.type, 'PropertyDefinition')
                        self.assertEqual(field.key.name, keyword)
                        self.assertIs(field.static, bool(prefix))
                        self.assertEqual(method.type, 'MethodDefinition')
                        self.assertTrue(method.value.generator)
                        self.assertFalse(method.static)

    def test_historical_editions_keep_the_same_line_terminator_rules(self):
        for edition in (2015, 2016, 2017, 2020, 2022, 2026):
            with self.subTest(edition=edition):
                tree = esprima.parseScript('class C{get\nx(){return "x\\\ny";}}', ecmaVersion=edition)
                self.assertEqual(tree.body[0].body.body[0].kind, 'get')
                body = esprima.parseScript('function f(){return\n"x";}', ecmaVersion=edition).body[0].body.body
                self.assertIsNone(body[0].argument)
                self.assertEqual(len(body), 2)


if __name__ == '__main__':
    unittest.main()
