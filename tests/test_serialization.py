import json
import unittest

import esprima


class SerializationTests(unittest.TestCase):
    def test_required_null_fields_survive(self):
        tree = esprima.toDict(esprima.parseScript('var x; if (x) f(); function f(){ return; }'))
        self.assertIsNone(tree['body'][0]['declarations'][0]['init'])
        self.assertIsNone(tree['body'][1]['alternate'])
        self.assertIsNone(tree['body'][2]['body']['body'][0]['argument'])

    def test_regex_null_mapping_is_serializable(self):
        literal = {'type': 'Literal', 'raw': '/a/', 'value': None,
                   'regex': {'pattern': 'a', 'flags': ''}}
        self.assertEqual(json.loads(json.dumps(esprima.toDict(literal))), literal)

    def test_no_unrequested_locations(self):
        tree = esprima.toDict(esprima.parseScript('x;'))
        self.assertNotIn('loc', tree)
        self.assertNotIn('range', tree)

    def test_nonfinite_numbers_are_json_safe_and_distinct_from_null(self):
        tree = esprima.toDict(esprima.parseScript('const x=1e400;'))
        literal = tree['body'][0]['declarations'][0]['init']
        self.assertIsNone(literal['value'])
        self.assertEqual(literal['number'], 'Infinity')
        json.dumps(tree, allow_nan=False)

    def test_utf16_pair_and_scalar_literals_agree(self):
        escaped = esprima.parseScript(r'"\ud83d\ude00";').body[0].expression.value
        scalar = esprima.parseScript('"😀";').body[0].expression.value
        self.assertEqual(escaped, scalar)
        self.assertEqual(escaped, '😀')
        self.assertEqual(esprima.parseScript(r'"\ud800";').body[0].expression.value, '\ud800')
