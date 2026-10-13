import sys
import unittest

import esprima


class ResourceAndCommentTests(unittest.TestCase):
    def test_nested_functions_and_global_recursion_state(self):
        previous = sys.getrecursionlimit()
        esprima.parseScript('(function(){' * 32 + 'x();' + '})();' * 32)
        self.assertEqual(sys.getrecursionlimit(), previous)

    def test_excessive_nesting_has_structured_error(self):
        with self.assertRaisesRegex(esprima.Error, 'resource limit'):
            esprima.parseScript('(' * 2000 + 'x' + ')' * 2000)

    def test_empty_class_and_static_block_keep_inner_comments(self):
        tree = esprima.parseScript('class C{/*license*/static{/*inner*/}}', {'comment': True, 'attachComment': True})
        block = tree.body[0].body.body[0]
        self.assertEqual(block.innerComments[0].value, 'inner')
        empty = esprima.parseScript('class C{/*license*/}', {'comment': True, 'attachComment': True})
        self.assertEqual(empty.body[0].body.innerComments[0].value, 'license')
