"""Edition boundaries for lexical tokens and grammar-driven regexp features."""
import unittest

import esprima
from esprima.regexp_validator import (
    RegExpEditionError, RegExpSyntaxError, normalize_ecma_version,
    regexp_features, validate_regexp,
)


class LexicalEditionTests(unittest.TestCase):
    def test_tokenizer_validates_explicit_editions(self):
        for edition in (5, *range(2015, 2027), 'latest'):
            with self.subTest(edition=edition):
                self.assertEqual(len(esprima.tokenize('x', {'ecmaVersion': edition})), 1)
        for edition in (None, True, False, 6, 2027, 2014, '2026', 'esnext', 2026.0, []):
            with self.subTest(edition=edition), self.assertRaises(ValueError):
                esprima.tokenize('x', {'ecmaVersion': edition})
        self.assertEqual(normalize_ecma_version('latest'), 2026)

    def test_tokenizer_lexical_feature_boundaries(self):
        cases = [
            ('0b101', 2015), ('0o77', 2015), ('`a`', 2015),
            (r'\u{61}', 2015), ('\U0001D49C', 2015),
            (r'"\u{1F600}"', 2015), ('a => a', 2015), ('...x', 2015),
            ('x ** y', 2016), ('x **= y', 2016),
            (r'tag`\xG1`', 2018), ('"a\u2028b"', 2019),
            ('42n', 2020), ('0xffn', 2020), ('x?.y', 2020), ('x ?? y', 2020),
            ('1_234', 2021), ('0xA_B', 2021), ('.1_2', 2021),
            ('x &&= y', 2021), ('x ||= y', 2021), ('x ??= y', 2021),
            ('#private', 2022), ('#!node\n42', 2023),
        ]
        for source, edition in cases:
            older = 5 if edition == 2015 else edition - 1
            with self.subTest(source=source, edition=edition):
                self.assertTrue(esprima.tokenize(source, {'ecmaVersion': edition}))
                with self.assertRaises(esprima.Error):
                    esprima.tokenize(source, {'ecmaVersion': older})
        # Ordinary escaped string characters and legacy numeric spellings remain ES5.
        for source in (r'"\u0061"', r'"\x61"', '0xff', '010', '08', r'"\8"'):
            esprima.tokenize(source, {'ecmaVersion': 5})
        esprima.tokenize('a?.3:0', {'ecmaVersion': 5})

    def test_tolerant_tokenizer_reports_edition_errors(self):
        tokens = esprima.tokenize('123n', {'ecmaVersion': 2019, 'tolerant': True})
        self.assertEqual(tokens[0].value, '123n')
        self.assertEqual(len(tokens.errors), 1)
        self.assertIn('requires ECMAScript 2020', tokens.errors[0]['message'])


class RegExpEditionTests(unittest.TestCase):
    def test_exact_regexp_feature_boundaries(self):
        cases = [
            ('a', 'u', 2015), ('a', 'y', 2015), ('a', 's', 2018),
            ('(?<=a)b', '', 2018), ('(?<!a)b', '', 2018),
            ('(?<name>a)', '', 2018), (r'(?<name>a)\k<name>', 'u', 2018),
            (r'\p{L}', 'u', 2018), (r'[\P{ASCII}]', 'u', 2018),
            ('a', 'd', 2022), ('[a&&b]', 'v', 2024),
            ('(?i:a)', '', 2025), ('(?i-:a)', '', 2025), ('(?im-s:a)', '', 2025),
            ('(?<name>a)|(?<name>b)', '', 2025),
        ]
        for pattern, flags, edition in cases:
            older = 5 if edition == 2015 else edition - 1
            with self.subTest(pattern=pattern, flags=flags, edition=edition):
                validate_regexp(pattern, flags, edition)
                with self.assertRaises(RegExpEditionError):
                    validate_regexp(pattern, flags, older)
                self.assertTrue(esprima.tokenize('/' + pattern + '/' + flags, {'ecmaVersion': edition}))
                with self.assertRaises(esprima.Error):
                    esprima.tokenize('/' + pattern + '/' + flags, {'ecmaVersion': older})

    def test_feature_tracking_uses_grammar_context(self):
        for pattern in (r'\(?<a>', '[(?<a>)]', r'\(?i:a\)', '[(?i:a)]', r'\p{ASCII}', r'[\p{ASCII}]'):
            with self.subTest(pattern=pattern):
                self.assertEqual(regexp_features(pattern), {})
                validate_regexp(pattern, '', 5)
                esprima.tokenize('/' + pattern + '/', {'ecmaVersion': 5})
        features = regexp_features(r'(?i:(?<a>\p{L}))|(?<a>x)', 'u')
        self.assertEqual(features['RegExp scoped modifiers'], 2025)
        self.assertEqual(features['RegExp disjoint duplicate capture names'], 2025)
        self.assertEqual(features['RegExp named capture groups'], 2018)
        self.assertEqual(features['RegExp Unicode property escapes'], 2018)
        with self.assertRaises(RegExpSyntaxError):
            validate_regexp('(?<a>x)(?<a>y)', '', 2026)

    def test_parser_and_tokenizer_agree_on_regex_editions(self):
        for source, edition in [('/(?i:a)/', 2025), ('/(?<a>x)|(?<a>y)/', 2025), ('/a/v', 2024)]:
            with self.subTest(source=source):
                esprima.parseScript(source, {'ecmaVersion': edition})
                with self.assertRaises(esprima.Error):
                    esprima.parseScript(source, {'ecmaVersion': edition - 1})
        for source in (r'/\(?<a>/', '/[(?<a>)]/', r'/\p{ASCII}/', r'/\(?i:a\)/'):
            esprima.parseScript(source, {'ecmaVersion': 5})


if __name__ == '__main__':
    unittest.main()
