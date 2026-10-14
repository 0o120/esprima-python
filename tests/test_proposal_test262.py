"""Offline Test262 proposal syntax checks; fixture programs are never run."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import esprima
from tools.check_grammar_reference import strict_source

CORPUS = Path(__file__).parent / 'fixtures/proposals'
REVISION = '2e0a56762801e275a9fdf96dc49d90ba0cddcf63'


class ProposalTest262Tests(unittest.TestCase):
    def test_complete_frozen_resource_and_decorator_feature_inventory(self):
        manifest = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['revision'], REVISION)
        self.assertEqual(manifest['caseCount'], 995)
        self.assertEqual(manifest['sourceFileCount'], 510)
        self.assertEqual(manifest['parseNegativeChecks'], 117)
        self.assertEqual(manifest['omitted'], [])
        for name, expected in manifest['files'].items():
            self.assertEqual(sha256((CORPUS / name).read_bytes()).hexdigest(), expected, name)
        cases = json.loads((CORPUS / 'cases.json').read_text(encoding='utf-8'))['cases']
        self.assertEqual(len(cases), manifest['caseCount'])
        self.assertEqual(len({case['path'] for case in cases}), manifest['sourceFileCount'])
        self.assertEqual(len({(case['path'], case['mode']) for case in cases}), len(cases))
        self.assertEqual(dict(Counter(case['mode'] for case in cases)), manifest['modeCounts'])
        self.assertEqual(sum(case['parseNegative'] for case in cases), manifest['parseNegativeChecks'])
        for feature, count in manifest['featureModeCounts'].items():
            self.assertEqual(sum(feature in case['features'] for case in cases), count)
        for case in cases:
            with self.subTest(path=case['path'], mode=case['mode']):
                self.assertIn(case['mode'], ('script', 'strict', 'module'))
                self.assertTrue(set(case['features']) & set(manifest['selectionFeatures']))
                self.assertFalse(set(case['features']) & set(manifest['excludedFeatures']))
                self.assertFalse(set(case['features']) & set(manifest['phaseCorpusFeatures']))
                source = case['source']
                self.assertEqual(sha256(source.encode('utf-8')).hexdigest(), case['sha256'])
                text = strict_source(source) if case['mode'] == 'strict' else source
                parser = esprima.parseModule if case['mode'] == 'module' else esprima.parseScript
                previous_limit = sys.getrecursionlimit()
                if case['parseNegative']:
                    with self.assertRaises(esprima.Error) as rejected:
                        parser(text, manifest['options'])
                    self.assertNotIn('resource limit', str(rejected.exception).lower())
                else:
                    parser(text, manifest['options'])
                self.assertEqual(sys.getrecursionlimit(), previous_limit)


if __name__ == '__main__':
    unittest.main()
