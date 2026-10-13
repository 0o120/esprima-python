"""Var-scan elision keeps declaration boundaries and source contracts intact."""
import unittest

import esprima
from esprima import nodes
from esprima.validation import validate_program


class VarSourceValidationTests(unittest.TestCase):
    def test_no_var_source_retains_direct_and_labeled_function_bindings(self):
        cases = [
            'let conflict; function conflict() {}',
            'let conflict; label: function conflict() {}',
            'function outer(conflict) { let conflict; }',
            'class C { static { function conflict() {} let conflict; } }',
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaisesRegex(esprima.Error, 'already been declared'):
                esprima.parseScript(source)
        esprima.parseModule('function declared() {} export {declared};')

    def test_vars_nested_in_statement_boundaries_keep_conflict_errors(self):
        cases = [
            '{ let conflict; if (condition) { var conflict; } }',
            '{ let conflict; for (var conflict = 0; condition; ) {} }',
            '{ let conflict; for (var conflict in collection) {} }',
            '{ let conflict; for (var conflict of collection) {} }',
            'switch (value) { case 0: let conflict; case 1: var conflict; }',
            'class C { static { let conflict; if (condition) { var conflict; } } }',
            'try {} catch ({conflict}) { var conflict; }',
            'try {} catch (error) { let conflict; if (condition) { var conflict; } }',
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaisesRegex(esprima.Error, 'already been declared'):
                esprima.parseScript(source)

    def test_comments_strings_and_identifier_substrings_are_conservative(self):
        cases = [
            '/* var */ const value = 1;',
            '// variables\nconst value = 1;',
            'const value = "var";',
            'const invariant = 1;',
            'const object = {v\\u0061r: 1}; object.v\\u0061r;',
            'for (let value of collection) { let value; }',
            'label: function declared() {}',
            'try {} catch (error) { var error; }',
        ]
        for source in cases:
            with self.subTest(source=source):
                ordinary = esprima.parseScript(source).toDict()
                complete = esprima.parseScript(source, delegate=lambda *args: None).toDict()
                self.assertEqual(ordinary, complete)

    def test_escaped_var_declaration_keyword_remains_a_parse_error(self):
        for source in ('\\u0076ar value;', 'v\\u0061r value;', 'va\\u0072 value;'):
            with self.subTest(source=source), self.assertRaisesRegex(esprima.Error, 'Keyword must not contain escaped characters'):
                esprima.parseScript(source)

    def test_str_subclass_false_containment_cannot_hide_var_conflicts(self):
        class FalseContains(str):
            def __contains__(self, value):
                return False
        source = FalseContains('let conflict; if (condition) { var conflict; }')
        with self.assertRaisesRegex(esprima.Error, 'already been declared'):
            esprima.parseScript(source)

    def test_user_options_cannot_assert_a_var_absence_proof(self):
        with self.assertRaisesRegex(esprima.Error, 'already been declared'):
            esprima.parseScript('let conflict; var conflict;', {'no_var': True, '_no_var': True})

    def test_delegate_inserted_var_is_checked_with_original_binding(self):
        inserted = nodes.Identifier('conflict')
        def delegate(node, metadata):
            if node.type == 'Program':
                node.body.append(nodes.VariableDeclaration([nodes.VariableDeclarator(inserted, None)], 'var'))
        with self.assertRaisesRegex(esprima.Error, 'already been declared'):
            esprima.parseScript('let conflict;', delegate=delegate)

    def test_standalone_modified_tree_still_collects_var_declarations(self):
        program = esprima.parseScript('let conflict;')
        inserted = nodes.Identifier('conflict')
        program.body.append(nodes.VariableDeclaration([nodes.VariableDeclarator(inserted, None)], 'var'))
        before = program.toDict()
        errors = []
        validate_program(program, lambda message, original: errors.append((message, original)))
        self.assertTrue(any('already been declared' in message and original is inserted for message, original in errors))
        self.assertEqual(program.toDict(), before)


if __name__ == '__main__':
    unittest.main()
