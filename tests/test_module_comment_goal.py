"""The initial token must use the module comment grammar."""
import unittest
import esprima


class ModuleCommentGoalTests(unittest.TestCase):
    def test_html_comment_open_and_close_are_rejected_in_modules(self):
        for prefix in ('<!-- comment', '--> comment'):
            for padding in ('', ' ', '\n', '\r\n'):
                source = padding + prefix + '\n1;'
                with self.subTest(source=source):
                    with self.assertRaises(esprima.Error):
                        esprima.parseModule(source)
                    with self.assertRaises(esprima.Error):
                        esprima.parse(source, sourceType='module', jsx=True)
                    tokens = esprima.tokenize(source, sourceType='module', comment=True)
                    self.assertTrue(tokens)
                    self.assertFalse(any(token.type == 'LineComment' for token in tokens))
                    self.assertEqual(tokens[0].value, '<' if prefix.startswith('<') else '--')

    def test_legacy_script_comments_remain_supported(self):
        for prefix in ('<!-- comment', '--> comment'):
            tree = esprima.parseScript(prefix + '\n1;', comment=True)
            self.assertEqual(tree.body[0].expression.value, 1)
            self.assertEqual(tree.comments[0].type, 'Line')


if __name__ == '__main__':
    unittest.main()
