"""Fast ASCII scanning still follows the complete lexical goals and locations."""
import unittest
import esprima
from esprima.error_handler import ErrorHandler
from esprima.scanner import Scanner


class ScanningBoundaryTests(unittest.TestCase):
    def test_ascii_run_escape_unicode_and_private_boundaries(self):
        cases = [('x;', 'x', False), ('longName9;', 'longName9', False),
                 (r'long\u004eame;', 'longName', True), ('long\u03b1;', 'long\u03b1', False),
                 (r'#long\u004eame;', '#longName', True), ('#longName;', '#longName', False)]
        for source, name, escaped in cases:
            with self.subTest(source=source):
                scanner = Scanner(source, ErrorHandler())
                token = scanner.lex()
                self.assertEqual(token.value, name)
                self.assertIs(token.escaped, escaped)
                self.assertEqual(scanner.source[token.end], ';')
        for source in (r'long\x41', r'long\u002d', r'\u0069f=1'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)

    def test_horizontal_runs_and_all_line_terminators_keep_metadata(self):
        for horizontal in (' ', '    ', '\t\v\f', '\u00a0\u1680\u2000\u200a\ufeff'):
            for newline in ('\n', '\r', '\r\n', '\u2028', '\u2029'):
                source = horizontal + '// note' + newline + horizontal + 'x;'
                with self.subTest(horizontal=horizontal, newline=newline):
                    tree = esprima.parseScript(source, comment=True, tokens=True, range=True, loc=True)
                    node = tree.body[0].expression
                    self.assertEqual(node.loc.start.line, 2)
                    self.assertEqual(node.loc.start.column, len(horizontal))
                    self.assertEqual(node.range, [len(source)-2, len(source)-1])
                    self.assertEqual(tree.comments[0].value, ' note')
                    self.assertEqual(tree.tokens[0].loc.start.line, 2)
        for source in ('\u0085x', '\u180ex'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)

    def test_comment_and_html_goals_after_horizontal_runs(self):
        source = 'x;/* block\r\n */ \t --> ignored\n y;'
        tree = esprima.parseScript(source, comment=True)
        self.assertEqual([statement.expression.name for statement in tree.body], ['x', 'y'])
        self.assertEqual(len(tree.comments), 2)
        with self.assertRaises(esprima.Error):
            esprima.parseModule(source)
        for source in ('', '    ', '\t\v\f'):
            self.assertEqual(esprima.parseScript(source).body, [])


if __name__ == '__main__':
    unittest.main()
