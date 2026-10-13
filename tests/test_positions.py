import unittest

import esprima


class PositionTests(unittest.TestCase):
    def test_astral_ranges_columns_comments_tokens_delegate(self):
        seen = []
        code = "/*😀*/ var 𐐀='😀';"
        tree = esprima.parseScript(code, {'range': True, 'loc': True, 'tokens': True, 'comment': True},
                                   delegate=lambda node, meta: seen.append((node.type, meta.start.offset, meta.end.offset)))
        identifier = tree.body[0].declarations[0].id
        self.assertEqual(identifier.range, [11, 13])
        self.assertEqual(identifier.loc.end.column, 13)
        self.assertEqual(tree.comments[0].range, [0, 6])
        self.assertEqual(tree.tokens[1].range, [11, 13])
        self.assertIn(('Identifier', 11, 13), seen)

    def test_scalar_compatibility_is_explicit(self):
        node = esprima.parseScript('var 𐐀=1;', {'range': True, 'positionEncoding': 'scalar'}).body[0].declarations[0].id
        self.assertEqual(node.range, [4, 5])

    def test_multiline_string_start(self):
        tree = esprima.parseScript("'\\\n' + bar", {'loc': True})
        self.assertEqual(tree.body[0].expression.loc.start.column, 0)
        self.assertEqual(tree.body[0].expression.loc.start.line, 1)

    def test_hashbang_metadata(self):
        tree = esprima.parseScript('#!/usr/bin/env node\nconst x=1;', {'comment': True})
        self.assertEqual(tree.hashbang, '/usr/bin/env node')
        self.assertTrue(tree.comments[0].hashbang)
