"""Explicit resource-management grammar and static-semantics regressions.

Source cases are parsed as data. Independent Acorn/Babel acceptance and ESTree
checks are recorded by the external differential runner, never executed here.
"""
import unittest

import esprima
from esprima.validation import validate_program


VALID_CASES = (
    ('module', 'using resource = acquire();'),
    ('module', 'await using resource = acquire();'),
    ('module', 'await using resource = await acquire();'),
    ('module', 'using resource = acquire(), second = acquire(); export {resource};'),
    ('script', '{ using resource = acquire(); }'),
    ('script', '{ using await = acquire(); }'),
    ('script', '{ using yield = acquire(); }'),
    ('script', '{ using using = acquire(); }'),
    ('script', '{ using of = acquire(); }'),
    ('script', '{ using \\u0072esource = acquire(); }'),
    ('script', '{ using /* comment */ resource = acquire(); }'),
    ('module', 'await /* comment */ using /* comment */ resource = acquire();'),
    ('script', '{ using resource = (value in object); }'),
    ('script', '{ using resource = acquire()\n next(); }'),
    ('script', 'function f(){ using resource = acquire(); }'),
    ('script', 'function* f(){ using resource = yield acquire(); }'),
    ('script', 'async function f(){ await using resource = acquire(); }'),
    ('script', 'async function* f(){ await using resource = yield acquire(); }'),
    ('script', 'const f = async () => { await using resource = acquire(); };'),
    ('script', 'class C { static { using resource = acquire(); } method(){ using resource = acquire(); } }'),
    ('script', 'class C { async method(){ await using resource = acquire(); } }'),
    ('script', 'switch (n) { case 1: { using resource = acquire(); break; } default: { using resource = acquire(); } }'),
    ('script', 'try { using resource = acquire(); } catch (e) { using other = acquire(); } finally { using last = acquire(); }'),
    ('script', 'for (using resource = acquire(); test; update) {}'),
    ('script', 'for (using a = acquire(), b = acquire(); test; update) {}'),
    ('script', 'for (using of = acquire(); test; update) {}'),
    ('script', 'for (using resource of resources) {}'),
    ('script', 'for (using resource\n of resources) {}'),
    ('script', 'for (using resource of resources) { let resource; }'),
    ('module', 'for (await using resource of resources) {}'),
    ('module', 'for (await using of of resources) {}'),
    ('module', 'for await (using resource of resources) {}'),
    ('module', 'for await (await using resource of resources) {}'),
    ('module', 'for (await using resource = acquire(); test; update) {}'),
    ('script', 'async function f(){ for (await using resource of resources) {} }'),
    ('script', 'async function f(){ for await (using resource of resources) {} }'),
    ('script', 'async function f(){ for await (await using resource of resources) {} }'),
    ('script', '{ using resource = acquire(); { using resource = acquire(); } }'),
    ('script', 'function f(resource){ { using resource = acquire(); } }'),
    ('script', 'using = acquire(); using.resource; using(resource); using: while(test) break using;'),
    ('script', 'using\nresource = acquire();'),
    ('script', 'using /*\n*/ resource = acquire();'),
    ('script', 'using instanceof Resource; using in object;'),
    ('script', 'for (using of resources) {}'),
    ('script', 'for (using in object) {}'),
    ('script', 'for (using\n of resources) {}'),
    ('script', 'for (using.of of resources) {}'),
    ('script', 'for (using[of] of resources) {}'),
    ('script', 'for (using [resource] of resources) {}'),
    ('script', 'for (using of of) {}'),
    ('module', 'await\nusing(resource);'),
    ('module', 'await using\n(resource);'),
    ('module', 'await using instanceof Resource;'),
    ('module', 'using [resource] = acquire();'),
    ('module', 'await using\nresource = acquire();'),
    ('module', 'await using /*\n*/ resource = acquire();'),
)

INVALID_CASES = (
    ('script', 'using resource = acquire();'),
    ('script', 'await using resource = acquire();'),
    ('module', 'using resource;'),
    ('module', 'await using resource;'),
    ('module', 'using resource = acquire(), second;'),
    ('module', 'await using resource = acquire(), second;'),
    ('module', 'using {resource} = acquire();'),
    ('module', 'await using {resource} = acquire();'),
    ('module', 'await using [resource] = acquire();'),
    ('module', 'using let = acquire();'),
    ('module', 'using await = acquire();'),
    ('module', 'using yield = acquire();'),
    ('module', 'using eval = acquire();'),
    ('script', '{ using let = acquire(); }'),
    ('script', '{ using \\u006cet = acquire(); }'),
    ('script', '"use strict"; { using eval = acquire(); }'),
    ('script', '{ using resource = acquire(), resource = acquire(); }'),
    ('script', '{ using resource = acquire(); let resource; }'),
    ('script', '{ const resource = 1; using resource = acquire(); }'),
    ('script', '{ using resource = acquire(); var resource; }'),
    ('script', '{ using resource = acquire(); { var resource; } }'),
    ('script', '{ using resource = acquire(); function resource() {} }'),
    ('script', '{ using resource = acquire(); class resource {} }'),
    ('script', 'function f(resource){ using resource = acquire(); }'),
    ('script', 'try {} catch(resource){ using resource = acquire(); }'),
    ('module', 'import resource from "m"; using resource = acquire();'),
    ('script', 'function f(){ await using resource = acquire(); }'),
    ('script', 'async function f(){ function g(){ await using resource = acquire(); } }'),
    ('script', 'async function f(){ (() => { await using resource = acquire(); })(); }'),
    ('module', 'function f(){ await using resource = acquire(); }'),
    ('module', 'class C { static { await using resource = acquire(); } }'),
    ('script', 'function* f(){ using yield = acquire(); }'),
    ('script', 'async function f(){ using await = acquire(); }'),
    ('script', 'for (using resource;;) {}'),
    ('script', 'for (using resource in resources) {}'),
    ('script', 'for (using resource = acquire() in resources) {}'),
    ('script', 'for (using resource = acquire() of resources) {}'),
    ('script', 'for (using a, b of resources) {}'),
    ('script', 'for (using a = acquire(), b of resources) {}'),
    ('script', 'for (using {resource} of resources) {}'),
    ('script', 'for (using of of resources) {}'),
    ('script', 'for (using resource of resources) { var resource; }'),
    ('script', 'for (using resource = acquire(); test; update) { var resource; }'),
    ('script', 'for (await using resource of resources) {}'),
    ('module', 'for (await using resource in resources) {}'),
    ('module', 'for (await using resource = acquire() of resources) {}'),
    ('module', 'for await (using resource = acquire();; ) {}'),
    ('module', 'for await (await using resource = acquire();; ) {}'),
    ('module', 'for await (using resource in resources) {}'),
    ('module', 'for await (await using resource in resources) {}'),
    ('module', 'for (await using await of resources) {}'),
    ('script', 'if (test) using resource = acquire();'),
    ('script', 'while (test) using resource = acquire();'),
    ('script', 'for (;;) using resource = acquire();'),
    ('script', 'label: using resource = acquire();'),
    ('module', 'if (test) await using resource = acquire();'),
    ('script', 'switch (n) { case 1: using resource = acquire(); }'),
    ('module', 'switch (n) { default: await using resource = acquire(); }'),
    ('module', 'export using resource = acquire();'),
    ('module', 'export await using resource = acquire();'),
    ('module', 'await\nusing resource = acquire();'),
    ('module', 'await /*\n*/ using resource = acquire();'),
    ('script', 'await using\n resource = acquire();'),
    ('module', '\\u0075sing resource = acquire();'),
    ('module', 'await \\u0075sing resource = acquire();'),
)


class ResourceDeclarationTests(unittest.TestCase):
    def parse(self, source, source_type='script', **options):
        return esprima.parse(source, sourceType=source_type, explicitResourceManagement=True, **options)

    def test_positive_grammar_and_contexts(self):
        for source_type, source in VALID_CASES:
            with self.subTest(source_type=source_type, source=source):
                self.parse(source, source_type)

    def test_negative_grammar_and_early_errors(self):
        for source_type, source in INVALID_CASES:
            with self.subTest(source_type=source_type, source=source), self.assertRaises(esprima.Error):
                self.parse(source, source_type)

    def test_feature_is_explicit_and_edition_gated(self):
        for source in ('using resource = acquire();', 'await using resource = acquire();',
                       'for(using resource of resources){}'):
            with self.subTest(source=source):
                with self.assertRaises(esprima.Error):
                    esprima.parseModule(source)
                with self.assertRaises(esprima.Error):
                    esprima.parseModule(source, explicitResourceManagement=False)
                with self.assertRaisesRegex(esprima.Error, 'requires ECMAScript 2026'):
                    self.parse(source, 'module', ecmaVersion=2025)
                self.parse(source, 'module', ecmaVersion='latest')
        esprima.parseScript('using(resource);', ecmaVersion=5)

    def test_await_disposal_and_iteration_are_independent(self):
        for loop_await in (False, True):
            for disposal_await in (False, True):
                keyword = 'await using' if disposal_await else 'using'
                loop = 'for await' if loop_await else 'for'
                tree = self.parse(f'{loop} ({keyword} resource of resources) {{}}', 'module')
                result = tree.toDict()['body'][0]
                self.assertEqual(result['await'], loop_await)
                self.assertEqual(result['left']['kind'], keyword)
                self.assertIsNone(result['left']['declarations'][0]['init'])

    def test_contextual_keywords_preserve_expression_interpretations(self):
        for source in ('using\nresource = acquire();', 'using /*\n*/ resource = acquire();'):
            tree = self.parse(source)
            self.assertEqual([node.type for node in tree.body], ['ExpressionStatement', 'ExpressionStatement'])
            self.assertEqual(tree.body[0].expression.name, 'using')
        for source in ('await using\nresource = acquire();', 'await using /*\n*/ resource = acquire();'):
            tree = self.parse(source, 'module')
            self.assertEqual([node.type for node in tree.body], ['ExpressionStatement', 'ExpressionStatement'])
            self.assertEqual(tree.body[0].expression.type, 'AwaitExpression')
            self.assertEqual(tree.body[0].expression.argument.name, 'using')
        self.assertEqual(self.parse('using [resource] = acquire();', 'module').body[0].expression.left.type,
                         'MemberExpression')
        self.assertEqual(self.parse('for(using of resources){}').body[0].left.type, 'Identifier')
        self.assertEqual(self.parse(r'for(using \u006ff of resources){}').body[0].left.kind, 'using')

    def test_declaration_and_identifier_positions(self):
        source = '/*😀*/\nawait /*same*/ using resource = acquire();'
        tree = self.parse(source, 'module', range=True, loc=True, tokens=True, comment=True)
        declaration = tree.body[0]
        identifier = declaration.declarations[0].id
        offset = lambda index: len(source[:index].encode('utf-16-le')) // 2
        self.assertEqual(declaration.range, [offset(source.index('await')), offset(len(source))])
        self.assertEqual(identifier.range, [offset(source.index('resource')), offset(source.index('resource') + 8)])
        self.assertEqual(declaration.loc.start.line, 2)
        self.assertEqual(declaration.loc.start.column, 0)
        self.assertEqual([token.value for token in tree.tokens[:3]], ['await', 'using', 'resource'])
        self.assertEqual(len(tree.comments), 2)
        scalar = self.parse(source, 'module', range=True, positionEncoding='scalar')
        self.assertEqual(scalar.body[0].range, [source.index('await'), len(source)])

    def test_tolerant_scope_and_context_errors(self):
        for source_type, source, expected in (
            ('script', 'using resource = acquire();', 'script top level'),
            ('script', '{ using resource = acquire(); let resource; }', 'already been declared'),
            ('script', 'function f(){ await using resource = acquire(); }', 'async functions or modules'),
            ('script', 'switch(n){default: using resource = acquire();}', 'switch cases require a block'),
        ):
            with self.subTest(source=source):
                tree = self.parse(source, source_type, tolerant=True, range=True, loc=True)
                self.assertTrue(tree.errors)
                self.assertTrue(any(expected in error['message'] for error in tree.errors))
                self.assertTrue(all(isinstance(error['index'], int) for error in tree.errors))

    def test_public_validator_checks_resource_ast(self):
        tree = self.parse('using resource = acquire();', 'module').toDict()
        report = lambda ast: self.validate(ast)
        self.assertEqual(report(tree), [])
        tree['sourceType'] = 'script'
        self.assertTrue(any('script top level' in message for message in report(tree)))
        tree['sourceType'] = 'module'
        declaration = tree['body'][0]
        declaration['declarations'][0]['init'] = None
        self.assertTrue(any('Missing initializer' in message for message in report(tree)))
        declaration['declarations'][0]['id'] = {'type': 'ObjectPattern', 'properties': []}
        self.assertTrue(any('binding identifier' in message for message in report(tree)))

    @staticmethod
    def validate(tree):
        result = []
        validate_program(tree, lambda message, node: result.append(message))
        return result


if __name__ == '__main__':
    unittest.main()
