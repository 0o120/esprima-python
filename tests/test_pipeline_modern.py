"""Optional coordinated parser/generator integration and JSON interchange gates."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import esprima

WORKSPACE = Path(__file__).resolve().parents[2]
for dependency in ('esutils-python', 'escodegen-python'):
    if (WORKSPACE / dependency).is_dir():
        sys.path.insert(0, str(WORKSPACE / dependency))
try:
    import escodegen
except ImportError:
    escodegen = None

REFERENCE = Path(os.environ.get('ESCODEGEN_REFERENCE_NODE_MODULES',
    str(Path(__file__).resolve().parents[1] / 'tools' / 'reference' / 'node_modules')))
BRIDGE = Path(__file__).resolve().parents[1] / 'tools' / 'reference' / 'parse.cjs'


@unittest.skipUnless(escodegen is not None, 'optional coordinated generator required')
class ModernPipelineTests(unittest.TestCase):
    def test_bigint_property_keys_and_exact_json_interchange(self):
        for source in ['({123n:1});', '({0x20000000000001n:1});', 'class C{123n=1;0x20000000000001n(){}}',
                       'const {123n:x}=obj;']:
            with self.subTest(source=source):
                tree = esprima.parseScript(source)
                mapping = json.loads(json.dumps(tree.toDict(), allow_nan=False))
                native = escodegen.generate(tree)
                self.assertEqual(native, escodegen.generate(mapping))
                self.assertIn('n', native)
                reparsed = esprima.parseScript(native).toDict()
                # Reparse must retain BigInt descriptors rather than null keys.
                self.assertIn('bigint', json.dumps(reparsed))
                if '20000000000001' in source:
                    self.assertIn('9007199254740993n', native)

    def test_nonfinite_number_interchange_is_json_safe_and_preserves_number(self):
        for source in ['1e400;', '-1e400;', '({1e400:1});']:
            with self.subTest(source=source):
                tree = esprima.parseScript(source)
                mapping = json.loads(json.dumps(tree.toDict(), allow_nan=False))
                code = escodegen.generate(mapping)
                self.assertEqual(code, escodegen.generate(tree))
                self.assertIn('1e400', code)
                self.assertNotIn('null', code)

    def test_attached_inner_comments_survive_empty_containers(self):
        sources = ['function f(){/*license*/}', 'class C{/*license*/}', 'class C{static{/*license*/}}',
                   'const x={/*license*/};', 'const x=[/*license*/];',
                   'class C{static/*prefix*/{\n/*license*/\n}}']
        for source in sources:
            tree = esprima.parseScript(source, {'comment': True, 'attachComment': True, 'range': True, 'loc': True})
            for preserve in [False, True]:
                with self.subTest(source=source, preserve=preserve):
                    code = escodegen.generate(tree, {'comment': True, 'sourceCode': source,
                        'format': {'preserveBlankLines': preserve}})
                    self.assertEqual(code.count('license'), 1)
                    if 'prefix' in source:
                        self.assertEqual(code.count('prefix'), 1)
                    esprima.parseScript(code)

    @unittest.skipUnless(shutil.which('node') and (REFERENCE / 'acorn').exists(), 'pinned AST oracle required')
    def test_modern_native_and_mapping_semantics_match_independent_parser(self):
        jobs = [
            {'source': 'function f(){"use\\u0020strict";return this;}'},
            {'source': 'const x=(a?.b).c; (a?.b)?.c; new C()?.a;'},
            {'source': '({get [x](){return 1},set [x](value){}}); function f({x=y=z}){}'},
            {'source': 'class C {123n=1;#x; static {this.value=1} get #v(){return this.#x} set #v(v){this.#x=v}}'},
            {'source': 'const el=<><A title="&quot;&amp;" {...props}>{/*comment*/}{value}</A></>;','jsx': True},
            {'source': 'import x from "m" with {type:"json"}; export {x as "a b"};','module': True},
            {'source': 'export * as "a b" from "m"; await import("m",{with:{type:"json"}});','module': True},
        ]
        generated = []
        for job in jobs:
            parser = esprima.parseModule if job.get('module') else esprima.parseScript
            tree = parser(job['source'], {'jsx': job.get('jsx', False)})
            code = escodegen.generate(tree)
            self.assertEqual(code, escodegen.generate(json.loads(json.dumps(tree.toDict(), allow_nan=False))))
            generated.append(dict(job, source=code, normalized=True))
        env = dict(os.environ, ESCODEGEN_REFERENCE_NODE_MODULES=str(REFERENCE))
        def normalize(batch):
            result = subprocess.run(['node', str(BRIDGE)], input=json.dumps(batch),
                                    text=True, encoding='utf-8', capture_output=True, env=env, check=True)
            return json.loads(result.stdout)
        self.assertEqual(normalize([dict(job, normalized=True) for job in jobs]), normalize(generated))

    @unittest.skipUnless(shutil.which('node') and (REFERENCE / 'source-map').exists(), 'pinned source-map consumer required')
    def test_astral_locations_map_back_through_an_independent_consumer(self):
        source = '//\U0001f600\r\nconst \U00010400="\U0001f600";\r\n\U00010400;'
        tree = esprima.parseScript(source, {'loc': True, 'range': True})
        result = escodegen.generate(tree, {'sourceMap': 'input.js', 'sourceMapWithCode': True,
                                          'sourceContent': source})
        index = result.code.rfind('\U00010400')
        prefix = result.code[:index]
        payload = {'map': result.map.toJSON(), 'position': {'line': prefix.count('\n') + 1,
                   'column': len(prefix.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}}
        script = 'const {SourceMapConsumer}=require(' + json.dumps(str(REFERENCE / 'source-map')) + ');' + (
            'let s="";process.stdin.on("data",d=>s+=d);process.stdin.on("end",async()=>{'
            'const d=JSON.parse(s);await SourceMapConsumer.with(d.map,null,c=>'
            'console.log(JSON.stringify(c.originalPositionFor(d.position))))});')
        process = subprocess.run(['node', '-e', script], input=json.dumps(payload), text=True,
                                 encoding='utf-8', capture_output=True, check=True)
        position = json.loads(process.stdout)
        self.assertEqual((position['line'], position['column']), (3, 0))
        self.assertEqual(position['name'], '\U00010400')


if __name__ == '__main__':
    unittest.main()
