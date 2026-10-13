"""Every frozen core parse-negative fixture must raise a JavaScript syntax error."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

import esprima

FIXTURES = Path(__file__).parent / "fixtures/test262-early-errors"


def strict_source(source):
    if source.startswith("#!"):
        end = next((index + 1 for index, character in enumerate(source) if character in "\r\n\u2028\u2029"), len(source))
        if source[end - 1:end] == "\r" and source[end:end + 1] == "\n":
            end += 1
        return source[:end] + '\n"use strict";\n' + source[end:]
    return '"use strict";\n' + source


class Test262EarlyErrorsTests(unittest.TestCase):
    def test_all_frozen_parse_negative_inputs(self):
        manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            self.assertEqual(sha256((FIXTURES / name).read_bytes()).hexdigest(), expected, name)
        cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), manifest["count"])
        self.assertEqual(len(cases), 4152)
        self.assertEqual(len({case["path"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(path=case["path"], mode=case["mode"]):
                source = case["source"]
                self.assertEqual(sha256(source.encode("utf-8")).hexdigest(), case["sha256"])
                text = strict_source(source) if case["mode"] == "strict" else source
                parse = esprima.parseModule if case["mode"] == "module" else esprima.parseScript
                # Resource limits and incidental Python exceptions must remain
                # distinct; only a parser Error satisfies the syntax gate.
                with self.assertRaises(esprima.Error):
                    parse(text)


if __name__ == "__main__":
    unittest.main()
