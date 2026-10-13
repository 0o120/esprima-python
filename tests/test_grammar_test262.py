"""Frozen positive grammar regressions discovered by the full Test262 audit."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import esprima

CORPUS = Path(__file__).parent / 'fixtures' / 'test262-grammar'
REVISION = '2e0a56762801e275a9fdf96dc49d90ba0cddcf63'
CASE_COUNT = 283


class GrammarTest262Tests(unittest.TestCase):
    def test_frozen_positive_grammar_regressions(self):
        manifest = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['revision'], REVISION)
        self.assertEqual(manifest['caseCount'], CASE_COUNT)
        self.assertEqual(len(manifest['cases']), CASE_COUNT)
        paths = {case['path'] for case in manifest['cases']}
        self.assertEqual(len(paths), CASE_COUNT)
        actual_files = {path.relative_to(CORPUS).as_posix() for path in (CORPUS / 'test').rglob('*.js')}
        self.assertEqual(actual_files, paths)
        for case in manifest['cases']:
            with self.subTest(path=case['path'], mode=case['mode']):
                data = (CORPUS / case['path']).read_bytes()
                self.assertEqual(sha256(data).hexdigest(), case['sha256'])
                source = data.decode('utf-8')
                self.assertFalse(case['parseNegative'])
                self.assertIn(case['mode'], ('script', 'strict', 'module'))
                if case['mode'] == 'strict':
                    source = '"use strict";\n' + source
                parse = esprima.parseModule if case['mode'] == 'module' else esprima.parseScript
                recursion_limit = sys.getrecursionlimit()
                parse(source)
                self.assertEqual(sys.getrecursionlimit(), recursion_limit)


if __name__ == '__main__':
    unittest.main()
