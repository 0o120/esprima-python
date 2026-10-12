import json
import subprocess
import sys
import unittest


class CLITests(unittest.TestCase):
    def run_cli(self, code, *args):
        return subprocess.run([sys.executable, '-B', '-m', 'esprima', *args],
                              input=code, text=True, capture_output=True)

    def test_stdin_is_json(self):
        result = self.run_cli('const x=1;')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['type'], 'Program')
        self.assertEqual(result.stderr, '')

    def test_error_is_nonzero_and_on_stderr(self):
        result = self.run_cli('const =;')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('Unexpected token', json.loads(result.stderr)['message'])

    def test_module_and_timing(self):
        result = self.run_cli('export const x=1;', '--module', '--timing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['sourceType'], 'module')
        self.assertIn('Parsed in', result.stderr)
