"""ASCII fast paths must preserve Unicode fallbacks, lexical goals and metadata."""
import unittest
from unittest.mock import patch

import esprima
from esprima.character import Character
from esprima.error_handler import ErrorHandler
from esprima.scanner import Scanner
from esprima.token import Token


def identifier(source, edition=2026):
    scanner = Scanner(source, ErrorHandler())
    scanner.ecmaVersion = edition
    return scanner.lex(), scanner


class ScannerPerformancePathTests(unittest.TestCase):
    def test_ascii_character_classification_matches_identifier_grammar(self):
        starts = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_\\')
        parts = starts | set('0123456789')
        for cp in range(128):
            with self.subTest(cp=cp):
                self.assertEqual(Character.isIdentifierStart(chr(cp)), chr(cp) in starts)
                self.assertEqual(Character.isIdentifierPart(chr(cp)), chr(cp) in parts)
        for source in ('', 'ab', '\U0001D49Cx'):
            self.assertFalse(Character.isIdentifierStart(source))
            self.assertFalse(Character.isIdentifierPart(source))

    def test_ascii_and_mixed_identifier_paths(self):
        cases = [
            ('simpleName123;', 'simpleName123', 13, False),
            ('_$9 +', '_$9', 3, False),
            ('ascii\u03b1x;', 'ascii\u03b1x', 7, False),
            ('ascii\U0001D49Cx;', 'ascii\U0001D49Cx', 7, False),
            ('\U0001D49Cascii;', '\U0001D49Cascii', 6, False),
            ('ascii\u200cx;', 'ascii\u200cx', 7, False),
            (r'ascii\u0062;', 'asciib', 11, True),
            (r'\u{1D49C}ascii;', '\U0001D49Cascii', 14, True),
            (r'\u0069f;', 'if', 7, True),
            (r'ascii\u{1D49C};', 'ascii\U0001D49C', 14, True),
            ('ascii\ud835\udc9cx;', 'ascii\U0001D49Cx', 8, False),
        ]
        for source, value, end, escaped in cases:
            with self.subTest(source=source):
                token, scanner = identifier(source)
                self.assertEqual((token.value, token.start, token.end, token.escaped), (value, 0, end, escaped))
                self.assertEqual(scanner.source[token.end], ';' if ';' in source else ' ')
        self.assertEqual(identifier(r'\u0069f;')[0].type, Token.Keyword)
        with self.assertRaises(esprima.Error):
            identifier('ascii\U0001D49C', 5)
        with self.assertRaises(esprima.Error):
            identifier(r'ascii\u{2D}')

    def test_plain_ascii_identifier_bypasses_complex_scan(self):
        scanner = Scanner('plainAscii123;', ErrorHandler())
        with patch.object(scanner, 'getComplexIdentifier', side_effect=AssertionError('slow path')):
            self.assertEqual(scanner.lex().value, 'plainAscii123')
        scanner = Scanner('plain\u03b1;', ErrorHandler())
        with patch.object(scanner, 'getComplexIdentifier', wraps=scanner.getComplexIdentifier) as fallback:
            self.assertEqual(scanner.lex().value, 'plain\u03b1')
            fallback.assert_called_once()

    def test_single_punctuator_bypasses_multichar_prefix_checks(self):
        class CountingSource(str):
            checks = 0

            def startswith(self, *args):
                self.checks += 1
                return super().startswith(*args)

        scanner = Scanner('(x', ErrorHandler())
        scanner.source = CountingSource(scanner.source)
        self.assertEqual(scanner.scanPunctuator().value, '(')
        self.assertEqual(scanner.source.checks, 0)

    def test_longest_punctuator_dispatch_and_decimal_exception(self):
        punctuators = ('>>>=', '===', '!==', '>>>', '<<=', '>>=', '**=', '&&=', '||=', '??=', '...',
                       '&&', '||', '??', '?.', '==', '!=', '+=', '-=', '*=', '/=', '++', '--',
                       '<<', '>>', '&=', '|=', '^=', '%=', '<=', '>=', '=>', '**')
        for punctuator in punctuators + tuple('(){};,[]:~<>=!+-*%&|^/.?'):
            scanner = Scanner(punctuator + ' x', ErrorHandler())
            with self.subTest(punctuator=punctuator):
                token = scanner.scanPunctuator()
                self.assertEqual((token.value, token.start, token.end), (punctuator, 0, len(punctuator)))
        self.assertEqual([token.value for token in esprima.tokenize('a?.3:0', {'ecmaVersion': 5})], ['a', '?', '.3', ':', '0'])
        scanner = Scanner('{}', ErrorHandler())
        scanner.scanPunctuator()
        self.assertEqual(scanner.curlyStack, ['{'])
        scanner.scanPunctuator()
        self.assertEqual(scanner.curlyStack, [])

    def test_utf16_ascii_identity_and_unicode_fallback(self):
        ascii_scanner = Scanner('abc\r\ndef', ErrorHandler())
        for index in range(-2, 11):
            self.assertEqual(ascii_scanner.utf16Offset(index), min(max(index, 0), 8))
        self.assertEqual(ascii_scanner.utf16Column(8, 5), 3)
        self.assertEqual(ascii_scanner.utf16Column(10, 5), 3)
        self.assertEqual(ascii_scanner.utf16Column(-2, -1), 0)
        self.assertIsNone(ascii_scanner._utf16Offsets)
        for source, expected in [('a\U0001F600b', [0, 1, 3, 4]), ('a\ud83d\ude00b', [0, 1, 2, 3, 4])]:
            scanner = Scanner(source, ErrorHandler())
            self.assertEqual([scanner.utf16Offset(index) for index in range(len(source) + 1)], expected)
        scanner = Scanner('a\U0001F600\nb', ErrorHandler())
        self.assertEqual(scanner.utf16Column(4, 3), 1)


if __name__ == '__main__':
    unittest.main()
