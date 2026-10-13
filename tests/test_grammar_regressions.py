"""Reduced positive grammar repros from the pinned Test262 acceptance audit."""
import unittest
import esprima
from esprima.error_handler import Error


class GrammarRegressionTests(unittest.TestCase):
    def test_nested_pattern_default_assignments_reset_cover_flags(self):
        for source in [
            'class C {static {(function({x = y = arguments}){})()}}',
            'class C {static {new class {m({x = y = arguments}){}}}}',
            'function f({x = y = z}){}',
        ]:
            with self.subTest(source=source):
                esprima.parseScript(source)

    def test_async_identifier_iteration_heads_are_not_arrows(self):
        for source in [
            'for(async.x of xs);',
            'async function f(){for await(async of xs);}',
            r'for(\u0061sync of xs);',
        ]:
            with self.subTest(source=source):
                esprima.parseScript(source)
        with self.assertRaises(Error):
            esprima.parseScript('for(async of xs);')

    def test_super_and_new_target_are_available_in_method_parameters(self):
        for source in [
            'class C extends B {m(x=super.x){}}',
            'class C extends B {async m(x=super.m()){}}',
            '({m(x=super.x){}});',
            '({*m(x=super.x){}});',
            '({async m(x=super.m()){}});',
            'function f(x=new.target){}',
        ]:
            with self.subTest(source=source):
                esprima.parseScript(source)

    def test_parenthesized_unary_and_await_exponentiation(self):
        for source in ['(-1n)**-1n;', '(-x)**y;', 'async function f(){(await x)**y}']:
            with self.subTest(source=source):
                esprima.parseScript(source)
        for source in ['-x**y;', 'async function f(){await x**y}']:
            with self.subTest(source=source), self.assertRaises(Error):
                esprima.parseScript(source)

    def test_yield_import_and_template_middle(self):
        for source in ["async function* f(){yield import('x')}", 'function* f(){`a${yield}b`}']:
            with self.subTest(source=source):
                tree = esprima.parseScript(source)
                self.assertTrue(tree.body[0].generator)

    def test_import_meta_constructor_context(self):
        tree = esprima.parseModule('new import.meta();')
        self.assertEqual(tree.body[0].expression.type, 'NewExpression')
        with self.assertRaises(Error):
            esprima.parseModule("new import('x');")

    def test_optional_chain_after_completed_new_expression(self):
        tree = esprima.parseScript('new C()?.x;')
        self.assertEqual(tree.body[0].expression.type, 'ChainExpression')
        with self.assertRaises(Error):
            esprima.parseScript('new C?.x();')

    def test_sloppy_let_as_for_initializer(self):
        tree = esprima.parseScript('for(let;;);')
        self.assertEqual(tree.body[0].init.type, 'Identifier')
        self.assertEqual(tree.body[0].init.name, 'let')

    def test_iteration_assignment_patterns_clear_cover_initialized_name_errors(self):
        for source in [
            'f(function(){for({x=y}of xs);});',
            '(function*(){for({x=yield}of xs);})();',
            'f(function(){for([{x=y}]of xs);});',
            'f(function(){for({x=y}in xs);});',
        ]:
            with self.subTest(source=source):
                esprima.parseScript(source)


if __name__ == '__main__':
    unittest.main()
