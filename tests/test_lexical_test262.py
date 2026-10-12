"""Frozen Test262 lexical syntax gate, honoring strict/raw/module flags."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

import esprima

CORPUS = Path(__file__).parent / 'fixtures' / 'test262-lexical'
REVISION = '2e0a56762801e275a9fdf96dc49d90ba0cddcf63'
CASE_COUNT = 815


def strict_source(source):
    """Inject strict mode without moving an initial hashbang from source index 0."""
    if source.startswith('#!'):
        for i, ch in enumerate(source):
            if ch in '\r\n\u2028\u2029':
                end = i + 1
                if ch == '\r' and source[end:end + 1] == '\n':
                    end += 1
                return source[:end] + '"use strict";\n' + source[end:]
        return source + '\n"use strict";\n'
    return '"use strict";\n' + source


class LexicalTest262Tests(unittest.TestCase):
    def test_frozen_lexical_syntax_corpus(self):
        manifest = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['revision'], REVISION)
        self.assertEqual(manifest['caseCount'], CASE_COUNT)
        self.assertEqual(len(manifest['cases']), CASE_COUNT)
        self.assertEqual(len({case['path'] for case in manifest['cases']}), CASE_COUNT)
        actual_files = {path.relative_to(CORPUS).as_posix() for path in (CORPUS / 'test').rglob('*.js')}
        self.assertEqual(actual_files, {case['path'] for case in manifest['cases']})
        for case in manifest['cases']:
            data = (CORPUS / case['path']).read_bytes()
            self.assertEqual(sha256(data).hexdigest(), case['sha256'], case['path'])
            source = data.decode('utf-8')
            flags = case['flags']
            if 'module' in flags:
                modes = ['module']
            elif 'raw' in flags or 'noStrict' in flags:
                modes = ['script']
            elif 'onlyStrict' in flags:
                modes = ['strict']
            else:
                modes = ['script', 'strict']
            for mode in modes:
                with self.subTest(path=case['path'], mode=mode):
                    parse = esprima.parseModule if mode == 'module' else esprima.parseScript
                    text = strict_source(source) if mode == 'strict' else source
                    if case['parseNegative']:
                        with self.assertRaises(esprima.Error):
                            parse(text)
                    else:
                        parse(text)


if __name__ == '__main__':
    unittest.main()
