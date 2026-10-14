"""Owned parsing must preserve positions and low-level allocation hooks."""
import importlib
import unittest
from unittest.mock import patch

import esprima
from esprima.error_handler import ErrorHandler
from esprima.objects import Object
from esprima.parser import Marker, Parser
from esprima.scanner import RawToken, Scanner


parser_module = importlib.import_module('esprima.parser')
scanner_module = importlib.import_module('esprima.scanner')
facade = importlib.import_module('esprima.esprima')


def positions(root):
    result = []
    pending = [root]
    while pending:
        value = pending.pop()
        if isinstance(value, Object):
            fields = vars(value)
            if '_start' in fields:
                result.append(tuple(fields.get(key) for key in
                                    ('type', '_start', '_end', '_line', '_column')))
            pending.extend(fields.values())
        elif isinstance(value, (list, tuple)):
            pending.extend(value)
    return result


class TokenMarkerCompatibilityTests(unittest.TestCase):
    def test_positions_and_public_metadata_match_delegate_path(self):
        cases = [
            ('', {}),
            ('/* first */ x.y(z)[q]?.r?.(s);', {}),
            ('\r\nconst \U0001d49c="\U0001f600";\u2028\U0001d49c?.x;\rlet \u03c0=1;\u2029\u03c0++;', {}),
            ('const s="a\\\r\nb"; s.length; `first\n${s.x} last`.length;', {}),
            ('const \ud835\udc9c=1; \ud835\udc9c.x;', {}),
            (r'const \u0061=1; a.\u0069f; ({\u0069f:a});', {}),
            ('function f(a){return a+b*c-d/e**2;} const q=(x)=>({x});', {}),
            ('class A { #x=1; static { this.x=2; } f(o){return #x in o;} }', {}),
            ('const r=/a+/giu; r.test("a"); const b=0xffn;', {}),
            ('@dec class C { @field accessor x=1; }', {'decorators': True}),
            ('async function f(){await using x=open(); return x?.value;}',
             {'explicitResourceManagement': True}),
            ('import source x from "x"; export {x};',
             {'sourcePhaseImports': True, 'sourceType': 'module'}),
        ]
        for source, extra in cases:
            for encoding in ('utf16', 'scalar'):
                for metadata in (False, True):
                    options = dict(extra, positionEncoding=encoding, range=metadata,
                                   loc=metadata, tokens=metadata, source='source.js')
                    with self.subTest(source=source, options=options):
                        expected = esprima.parse(source, options, delegate=lambda node, meta: None)
                        actual = esprima.parse(source, options)
                        self.assertEqual(actual.toDict(), expected.toDict())
                        self.assertEqual(positions(actual), positions(expected))

    def test_invalid_input_diagnostics_match_delegate_path(self):
        for source in ('let a=;','"use strict"; let yield=1;', r'var \u0069f=1;',
                       'const x=1; const x=2;', 'a?.b=1;', 'a ?? b || c;',
                       '\n"\U0001f600"; let x = ;', 'throw\n1;'):
            for tolerant in (False, True):
                outcomes = []
                for delegate in (None, lambda node, meta: None):
                    try:
                        tree = esprima.parseScript(source, tolerant=tolerant, delegate=delegate)
                        outcomes.append(('ast', tree.toDict()))
                    except esprima.Error as error:
                        outcomes.append(('error', error.toDict()))
                with self.subTest(source=source, tolerant=tolerant):
                    self.assertEqual(*outcomes)

    def test_public_tokens_remain_dynamic_objects(self):
        scanner = Scanner('a + 1', ErrorHandler())
        token = scanner.lex()
        self.assertIs(type(token), RawToken)
        self.assertEqual(set(vars(token)), {
            'bigint', 'private', 'invalidEscape', 'escaped', 'type', 'value',
            'pattern', 'flags', 'regex', 'octal', 'cooked', 'head', 'tail',
            'lineNumber', 'lineStart', 'start', 'end'})
        self.assertIsNone(token.unrecognized)
        token.extension = 42
        self.assertEqual(token.toDict()['extension'], 42)
        del token.extension
        self.assertIsNone(token.extension)

    def test_direct_parser_keeps_independent_mutable_markers(self):
        parser = Parser('a.b+c;')
        parser.nextToken()
        token = parser.lookahead
        first = parser.createNode()
        second = parser.startNode(token)
        self.assertIs(type(token), RawToken)
        self.assertIs(type(first), Marker)
        self.assertIs(type(second), Marker)
        self.assertIsNot(first, second)
        first.index = 100
        self.assertEqual(token.start, 1)
        self.assertEqual(second.index, 1)

    def test_scanner_method_override_observes_ordinary_tokens(self):
        observed = []
        original = Scanner.lex
        def lex(scanner):
            token = original(scanner)
            observed.append(type(token))
            token.extension = True
            return token
        with patch.object(Scanner, 'lex', lex):
            esprima.parseScript('a.b+c(d);')
        self.assertTrue(observed)
        self.assertEqual(set(observed), {RawToken})

    def test_parser_method_override_observes_ordinary_markers(self):
        observed = []
        original = Parser.finalize
        def finalize(parser, marker, node):
            observed.append(type(marker))
            return original(parser, marker, node)
        with patch.object(Parser, 'finalize', finalize):
            esprima.parseScript('a.b+c(d);')
        self.assertTrue(observed)
        self.assertEqual(set(observed), {Marker})

    def test_replaced_raw_token_constructor_is_not_bypassed(self):
        seen = []
        class CustomToken(RawToken):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(self.value)
        with patch.object(scanner_module, 'RawToken', CustomToken):
            esprima.parseScript('a.b+c;')
        self.assertEqual(seen, ['a', '.', 'b', '+', 'c', ';', ''])

    def test_raw_token_initializer_mutation_is_not_bypassed(self):
        seen = []
        original = RawToken.__init__
        def initialize(token, *args, **kwargs):
            original(token, *args, **kwargs)
            seen.append(token.value)
        with patch.object(RawToken, '__init__', initialize):
            esprima.parseScript('a.b+c;')
        self.assertEqual(seen, ['', 'a', '.', 'b', '+', 'c', ';', ''])

    def test_replaced_marker_constructor_is_not_bypassed(self):
        seen = []
        class CustomMarker(Marker):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(self.index)
        with patch.object(parser_module, 'Marker', CustomMarker):
            esprima.parseScript('a.b+c;')
        self.assertGreater(len(seen), 7)

    def test_marker_initializer_mutation_is_not_bypassed(self):
        seen = []
        original = Marker.__init__
        def initialize(marker, *args, **kwargs):
            original(marker, *args, **kwargs)
            seen.append(marker.index)
        with patch.object(Marker, '__init__', initialize):
            esprima.parseScript('a.b+c;')
        self.assertGreater(len(seen), 7)

    def test_parser_subclass_keeps_token_and_marker_protocols(self):
        observed = []
        class CustomParser(Parser):
            def finalize(self, marker, node):
                observed.append((type(self.lookahead), type(marker)))
                return super().finalize(marker, node)
        with patch.object(facade, 'Parser', CustomParser):
            esprima.parseScript('a.b+c;')
        self.assertEqual(set(observed), {(RawToken, Marker)})

    def test_scanner_subclass_keeps_token_protocol(self):
        observed = []
        class CustomScanner(Scanner):
            def lex(self):
                token = super().lex()
                observed.append(type(token))
                return token
        with patch.object(parser_module, 'Scanner', CustomScanner):
            esprima.parseScript('a.b+c;')
        self.assertEqual(set(observed), {RawToken})

    def test_public_ast_nodes_retain_dynamic_fields_and_classes(self):
        tree = esprima.parseScript('x.y(x);')
        expr = tree.body[0].expression
        self.assertIs(type(expr), esprima.nodes.CallExpression)
        self.assertIs(type(expr.arguments[0]), esprima.nodes.Identifier)
        self.assertIsNot(expr.callee.object, expr.arguments[0])
        expr.arguments[0].name = 'changed'
        self.assertEqual(expr.callee.object.name, 'x')
        expr.custom = {'value': 1}
        self.assertEqual(tree.toDict()['body'][0]['expression']['custom'], {'value': 1})


if __name__ == '__main__':
    unittest.main()
