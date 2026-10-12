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

    def test_utf8_pipe_is_not_decoded_as_windows_ansi(self):
        result = subprocess.run([sys.executable, '-B', '-m', 'esprima'],
                                input="const text='😀，';", encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        literal = json.loads(result.stdout)['body'][0]['declarations'][0]['init']
        self.assertEqual(literal['value'], '😀，')

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

    def test_api_rejects_nontext_and_nonmapping_inputs(self):
        import esprima
        for operation in (esprima.parseScript, esprima.tokenize):
            with self.assertRaises(TypeError):
                operation(b'const x=1;')
            with self.assertRaises(TypeError):
                operation('x;', options=[])

    def test_custom_mapping_options_do_not_need_copy_method(self):
        from collections.abc import Mapping
        import esprima

        class Options(Mapping):
            def __iter__(self):
                return iter(('range',))

            def __len__(self):
                return 1

            def __getitem__(self, key):
                if key == 'range':
                    return True
                raise KeyError(key)

        self.assertEqual(esprima.parseScript('x;', Options()).range, [0, 2])
