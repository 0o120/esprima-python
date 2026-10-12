import unittest

import esprima


class JSXTests(unittest.TestCase):
    def parse(self, code, **options):
        return esprima.toDict(esprima.parseScript(code, {'jsx': True, **options}))

    def test_unclosed_elements_are_errors(self):
        for code in ('<A>', '<A><B></B>', '<A>text', '<A></B>', '<><A/></A>'):
            with self.subTest(code=code), self.assertRaises(esprima.Error):
                self.parse(code)

    def test_tolerant_truncation_has_errors_and_children(self):
        tree = self.parse('<A><B/>', tolerant=True)
        self.assertTrue(tree['errors'])
        self.assertEqual(len(tree['body'][0]['expression']['children']), 1)

    def test_fragments_and_spread_children(self):
        tree = self.parse('<>Hi<A {...props}>{...children}</A></>;')
        fragment = tree['body'][0]['expression']
        self.assertEqual(fragment['type'], 'JSXFragment')
        self.assertEqual(fragment['openingFragment']['type'], 'JSXOpeningFragment')
        child = fragment['children'][1]
        self.assertEqual(child['openingElement']['attributes'][0]['type'], 'JSXSpreadAttribute')
        self.assertEqual(child['children'][0]['type'], 'JSXSpreadChild')

    def test_nested_fragments_and_empty_container(self):
        tree = self.parse('<A><><B/>{/*comment*/}</></A>;')
        self.assertEqual(tree['body'][0]['expression']['children'][0]['type'], 'JSXFragment')
