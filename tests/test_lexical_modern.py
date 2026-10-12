"""Modern lexical grammar regressions, independent of parser grammar changes."""
import math
import unittest

import esprima
from esprima.character import Character, UNICODE_VERSION
from esprima.error_handler import Error, ErrorHandler
from esprima.regexp_validator import RegExpSyntaxError, validate_regexp
from esprima.scanner import Scanner


def scan(source):
    scanner = Scanner(source, ErrorHandler())
    scanner.scanComments()
    return scanner.lex()


class LexicalModernTests(unittest.TestCase):
    def test_pinned_identifiers(self):
        self.assertEqual(UNICODE_VERSION, '17.0.0')
        for name in ('\U0001D49C', '\U00010400', '\U0002EBF0', '\U00011F02', '$', '_'):
            with self.subTest(name=name):
                self.assertTrue(Character.isIdentifierStart(name))
                self.assertEqual(scan(name).value, name)
        self.assertTrue(Character.isIdentifierPart('\u200c'))
        self.assertFalse(Character.isIdentifierStart('\u200c'))
        self.assertFalse(Character.isWhiteSpace('\u180e'))
        for source in (r'\u{30}abc', r'a\u{2D}', '\u180e'):
            with self.subTest(source=source), self.assertRaises(Error):
                scan(source)

    def test_escaped_identifier_and_private_names(self):
        self.assertEqual(scan(r'\u{1D49C}x').value, '\U0001D49Cx')
        self.assertEqual(scan('#if').value, '#if')
        self.assertEqual(scan(r'#\u0069f').value, '#if')
        self.assertTrue(scan('#secret').private)
        for source in ('#', '#1', r'#\u{31}'):
            with self.subTest(source=source), self.assertRaises(Error):
                scan(source)

    def test_numeric_separators_and_binary64(self):
        cases = {
            '1_000': 1000, '.1_2': .12, '1.2_3e4_5': 1.23e45,
            '0b1010_0001': 161, '0o7_7': 63, '0xA_B': 171,
            '9007199254740993': 9007199254740992,
            '0x20000000000001': 9007199254740992,
            '0o400000000000000001': 9007199254740992,
            '0b100000000000000000000000000000000000000000000000000001': 9007199254740992,
            '1e9999': math.inf,
        }
        for source, value in cases.items():
            with self.subTest(source=source):
                self.assertEqual(scan(source).value, value)
        for source in ('1__0', '1_', '0_1', '01_2', '0x_1', '0b2', '0o8', '1._0', '1e_2', '1e+_2', '1e2_', '0x1g'):
            with self.subTest(source=source), self.assertRaises(Error):
                scan(source)

    def test_bigint_metadata_and_large_values(self):
        for source, value in [('12_345n', '12345'), ('0xffn', '255'), ('0b101n', '5'), ('0o77n', '63'), ('0n', '0')]:
            with self.subTest(source=source):
                token = scan(source)
                self.assertIsNone(token.value)
                self.assertEqual(token.bigint, value)
        self.assertEqual(scan('1' + '0' * 5000 + 'n').bigint, '1' + '0' * 5000)
        for source in ('01n', '00n', '08n', '1.0n', '1e2n', '1nfoo', '0xn'):
            with self.subTest(source=source), self.assertRaises(Error):
                scan(source)

    def test_json_superset_strings(self):
        for separator in ('\u2028', '\u2029'):
            source = '"a' + separator + 'b"'
            self.assertEqual(scan(source).value, 'a' + separator + 'b')
            scanner = Scanner(source, ErrorHandler())
            scanner.lex()
            self.assertEqual(scanner.lineNumber, 2)
        self.assertEqual(scan(r'"\8\9"').value, '89')
        self.assertTrue(scan(r'"\8\9"').octal)
        self.assertEqual(scan(r'"\08\09"').value, '\0' + '8' + '\0' + '9')
        for source in (r'"\08"', r'"\09"'):
            self.assertTrue(scan(source).octal)
            with self.assertRaises(Error):
                esprima.parseScript('"use strict"; ' + source)

    def test_template_invalid_escapes_are_deferred(self):
        for source in (r'`\8`', r'`\01`', r'`\xG1`', r'`\uQQQQ`', r'`\u{110000}`', r'`\u{}`'):
            with self.subTest(source=source):
                token = scan(source)
                self.assertIsNone(token.cooked)
                self.assertTrue(token.invalidEscape)
                self.assertTrue(token.tail)
        self.assertEqual(scan('`a\r\nb\rc`').value, 'a\nb\nc')
        self.assertEqual(scan('`a\r\nb\rc`').cooked, 'a\nb\nc')
        self.assertEqual(scan('`a\u2028b`').cooked, 'a\u2028b')
        scanner = Scanner('`a${{x:1}.x}b${2}c`', ErrorHandler())
        tokens = []
        while not scanner.eof():
            tokens.append(scanner.lex())
        templates = [token for token in tokens if token.head is not None]
        self.assertEqual([token.cooked for token in templates], ['a', 'b', 'c'])
        self.assertEqual([token.tail for token in templates], [False, False, True])

    def test_punctuators(self):
        source = 'a?.b ?? c; d &&= e; f ||= g; h ??= i; a?.3:0'
        values = [token.value for token in esprima.tokenize(source)]
        for value in ('?.', '??', '&&=', '||=', '??='):
            self.assertIn(value, values)
        self.assertEqual(values[-4:], ['?', '.3', ':', '0'])

    def test_hashbang_and_utf16_token_locations(self):
        scanner = Scanner('#!/usr/bin/env node\n42', ErrorHandler())
        scanner.scanComments()
        self.assertEqual(scanner.hashbang, '/usr/bin/env node')
        self.assertEqual(scanner.lex().value, 42)
        tokens = esprima.tokenize('#!node\n\U0001D49C /*\U0001F600*/ x', {'comment': True, 'range': True, 'loc': True})
        self.assertEqual(tokens[0].value, 'node')
        self.assertTrue(tokens[0].hashbang)
        self.assertEqual(tokens[1].range, [7, 9])
        self.assertEqual(tokens[1].loc.end.column, 2)
        self.assertEqual(tokens[2].range, [10, 16])
        self.assertEqual(tokens[2].loc.end.column, 9)
        self.assertEqual(tokens[3].loc.start.column, 10)
        for source in (' #!node', '\ufeff#!node', '\n#!node'):
            scanner = Scanner(source, ErrorHandler())
            scanner.scanComments()
            with self.subTest(source=source), self.assertRaises(Error):
                scanner.lex()


class RegExpModernTests(unittest.TestCase):
    def test_flags_and_no_python_patterns(self):
        scanner = Scanner('/x/dgimsy', ErrorHandler())
        token = scanner.scanRegExp()
        self.assertEqual((token.pattern, token.flags), ('x', 'dgimsy'))
        self.assertIsNone(token.regex)
        for flags in ('gg', 'ii', 'z', 'uv', 'ddu', 'G', '\\u0067'):
            with self.subTest(flags=flags), self.assertRaises(RegExpSyntaxError):
                validate_regexp('x', flags)

    def test_standard_positive_grammar(self):
        cases = [
            ('', ''), ('[]', ''), ('[^]', 'u'), ('a{2,4}?', ''),
            (r'(a)\1', 'u'), (r'\1(a)', 'u'), (r'\8', ''),
            (r'\k<not_a_capture>', ''), ('(?=a)*', ''),
            ('(?<=a)b', 'u'), ('(?<!a)b', 'u'),
            (r'(?<name>a)\k<name>', 'u'), (r'\k<name>(?<name>a)', ''),
            ('(?<a>x)|(?<a>y)', 'u'), ('(?:(?<a>x)|(?<a>y))', ''),
            ('(?i:a)(?m-s:^b$)', ''), ('(?i-:a)', ''), ('(?-ims:a)', 'v'),
            (r'\p{Script=Greek}\P{gc=Nd}', 'u'),
            (r'\p{scx=Hira}\p{L}\p{ASCII}\p{CWCF}', 'v'),
            (r'[\u{1F600}-\u{1F64F}]', 'u'),
            (r'[\uD83D\uDE00-\uD83D\uDE4F]', 'u'),
            (r'[\d-a]', ''), (r'\c_', ''), (r'[\c_]', ''),
            (r'[\p{ASCII}&&\p{Letter}]', 'v'),
            (r'[[a-z]--[aeiou]]', 'v'), (r'[[a-z]&&[^a-c]]', 'v'),
            (r'[\q{ab|cd}]', 'v'), (r'[\q{a|b}]', 'v'),
            (r'[^\q{a|b}]', 'v'), (r'\p{RGI_Emoji}', 'v'),
            (r'[^\p{RGI_Emoji}&&a]', 'v'),
            (r'[\!\#\%\&\-\,\:\;\<\=\>\@\`\~]', 'v'),
            ('a{foo}', ''), ('a{1,', ''), (']}', ''),
        ]
        for pattern, flags in cases:
            with self.subTest(pattern=pattern, flags=flags):
                validate_regexp(pattern, flags)

    def test_standard_negative_grammar(self):
        cases = [
            ('(', ''), (')', ''), ('[', ''), ('a{4,2}', ''), ('*a', ''),
            ('a++', ''), ('a{1}+', ''), ('(?P<a>x)', ''), ('(?i)x', ''),
            ('(?i-i:x)', ''), ('(?ii:x)', ''), ('(?g:x)', ''), ('(?-:x)', ''),
            ('(?<=a)*', ''), ('(?=a)*', 'u'), ('^*', ''),
            (r'\a', 'u'), (r'\xG0', 'u'), (r'\uQQQQ', 'u'),
            (r'\u{110000}', 'u'), (r'\u{}', 'u'), (r'\1', 'u'),
            (r'\0' + '1', 'u'), (r'\k<missing>', 'u'), (r'(?<a>x)\k<b>', ''),
            ('(?<a>x)(?<a>y)', ''), ('(?<a>(?<a>x))', 'u'),
            ('(?<a>(?<a>x)|y)', ''), ('(?<a>x|(?<a>y))', 'u'),
            ('(?<1>x)', 'u'), ('(?<>x)', ''),
            (r'[\d-a]', 'u'), ('[z-a]', ''),
            (r'[\u{1F64F}-\u{1F600}]', 'u'),
            (r'\p{script=Greek}', 'u'), (r'\p{Script=greek}', 'u'),
            (r'\p{Unknown}', 'u'), (r'\p{General_Category=latin}', 'u'),
            (r'\p{RGI_Emoji}', 'u'), (r'\P{RGI_Emoji}', 'v'),
            (r'[^\q{ab|cd}]', 'v'), (r'[^\p{RGI_Emoji}]', 'v'),
            ('[a&&b--c]', 'v'), ('[ab&&c]', 'v'), ('[a--bc]', 'v'),
            ('[a-]', 'v'), ('[a-b-c]', 'v'), ('[()]', 'v'), ('[!!]', 'v'),
            (r'[\q{\d}]', 'v'), (r'[\p{L}-a]', 'v'), ('[a&&]', 'v'),
            ('a{foo}', 'u'), ('a{1,', 'u'), (']}', 'u'),
        ]
        for pattern, flags in cases:
            with self.subTest(pattern=pattern, flags=flags), self.assertRaises(RegExpSyntaxError):
                validate_regexp(pattern, flags)


if __name__ == '__main__':
    unittest.main()
