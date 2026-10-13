import unittest

import esprima


class ModernExpressionTests(unittest.TestCase):
    def expression(self, source):
        return esprima.toDict(esprima.parseScript(source))['body'][0]['expression']

    def test_optional_chain_boundaries(self):
        chain = self.expression('obj?.x?.(1);')
        self.assertEqual(chain['type'], 'ChainExpression')
        self.assertTrue(chain['expression']['optional'])
        outer = self.expression('(obj?.x).y;')
        self.assertEqual(outer['type'], 'MemberExpression')
        self.assertEqual(outer['object']['type'], 'ChainExpression')
        self.assertFalse(outer['optional'])

    def test_nullish_precedence_and_forbidden_mixing(self):
        self.assertEqual(self.expression('a ?? b + c;')['operator'], '??')
        for source in ('a ?? b || c;', 'a && b ?? c;', 'a?.b=1;', 'a?.b++;', 'a?.b`x`;', 'new a?.b();'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                self.expression(source)
        for source in ('(a ?? b) || c;', 'a ?? (b && c);', 'new (a?.b)();'):
            self.expression(source)

    def test_dynamic_import_arguments(self):
        expr = self.expression('import("x", {with:{type:"json"}});')
        self.assertEqual(expr['source']['value'], 'x')
        self.assertEqual(expr['options']['type'], 'ObjectExpression')
        self.expression('import("x")();')
        self.expression('import(("x", "y"),);')
        for source in ('import();', 'import(...x);', 'import("x", {}, 3);'):
            with self.assertRaises(esprima.Error):
                self.expression(source)

    def test_async_generator_and_iteration(self):
        tree = esprima.toDict(esprima.parseScript('async function* f(){for await (const x of xs){yield x;}}'))
        function = tree['body'][0]
        self.assertTrue(function['async'])
        self.assertTrue(function['generator'])
        self.assertTrue(function['body']['body'][0]['await'])

    def test_import_meta_top_level_await_and_optional_catch(self):
        tree = esprima.toDict(esprima.parseModule('await f(import.meta.url);'))
        self.assertEqual(tree['body'][0]['expression']['type'], 'AwaitExpression')
        with self.assertRaises(esprima.Error):
            esprima.parseScript('import.meta;')
        self.assertIsNone(esprima.toDict(esprima.parseScript('try{}catch{}'))['body'][0]['handler']['param'])

    def test_bigint_and_logical_assignment(self):
        self.assertEqual(self.expression('123n;')['bigint'], '123')
        for operator in ('&&=', '||=', '??='):
            self.assertEqual(self.expression('x '+operator+' y;')['operator'], operator)

    def test_tagged_invalid_escape(self):
        expr = self.expression(r'tag`\unicode`;')
        self.assertIsNone(expr['quasi']['quasis'][0]['value']['cooked'])
        with self.assertRaises(esprima.Error):
            self.expression(r'`\unicode`;')
