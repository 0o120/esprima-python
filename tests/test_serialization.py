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
