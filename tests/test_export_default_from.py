"""Default-from proposal syntax cannot leak into the standard module grammar."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import esprima
from esprima.schema import migrate_legacy_fixture
from esprima.validation import validate_program

REFERENCE = Path(os.environ.get('ESCODEGEN_REFERENCE_NODE_MODULES',
    str(Path(__file__).resolve().parents[1] / 'tools/reference/node_modules')))
OPTIONS = {'exportDefaultFrom': True}


def errors(tree, edition=2026):
    result = []
    validate_program(tree, lambda message, node: result.append((message, node)), edition)
    return result


class ExportDefaultFromTests(unittest.TestCase):
    def test_proposal_requires_independent_explicit_current_edition_gate(self):
        sources = ['export value from "m";', 'export value, {other} from "m";',
                   'export default from "m";', 'export value, * as ns from "m";']
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(esprima.Error, 'exportDefaultFrom=True'):
                    esprima.parseModule(source)
                with self.assertRaisesRegex(esprima.Error, 'exportDefaultFrom=True'):
                    esprima.parseModule(source, {'sourcePhaseImports': True, 'deferredImportEvaluation': True})
                with self.assertRaisesRegex(esprima.Error, 'requires ECMAScript 2026'):
                    esprima.parseModule(source, dict(OPTIONS, ecmaVersion=2025))
                node = esprima.parseModule(source, OPTIONS).body[0]
                self.assertEqual(node.type, 'ExportNamedDeclaration')
                self.assertEqual(node.specifiers[0].type, 'ExportDefaultSpecifier')
                self.assertIsNone(node.declaration)
                self.assertEqual(node.source.value, 'm')

    def test_canonical_exported_field_and_native_local_alias(self):
        node = esprima.parseModule('export value from "m";', OPTIONS).body[0].specifiers[0]
        self.assertEqual(node.exported.name, 'value')
        self.assertIs(node.local, node.exported)
        self.assertNotIn('local', node.toDict())
        replacement = esprima.nodes.Identifier('replacement')
        node.local = replacement
        self.assertIs(node.exported, replacement)
        self.assertEqual(node.toDict()['exported']['name'], 'replacement')

    def test_named_namespace_attributes_and_identifier_names(self):
        named = esprima.parseModule('export value, {other as renamed,} from "m";', OPTIONS).body[0]
        self.assertEqual([specifier.type for specifier in named.specifiers], ['ExportDefaultSpecifier', 'ExportSpecifier'])
        self.assertEqual(named.specifiers[1].exported.name, 'renamed')
        namespace = esprima.parseModule('export value, * as "a b" from "m" with {type:"json"};', OPTIONS).body[0]
        self.assertEqual(namespace.specifiers[1].type, 'ExportNamespaceSpecifier')
        self.assertEqual(namespace.specifiers[1].exported.value, 'a b')
        self.assertEqual(namespace.attributes[0].value.value, 'json')
        # The proposal grammar uses IdentifierName, not a local binding. These
        # names therefore retain their spelling without strict-binding rules.
        for name in ('default', 'await', 'yield', 'static', 'enum', 'async', 'if'):
            with self.subTest(name=name):
                node = esprima.parseModule('export ' + name + ' from "m";', OPTIONS).body[0]
                self.assertEqual(node.specifiers[0].exported.name, name)
        node = esprima.parseModule('export\nvalue,\n* as ns\nfrom "m";', OPTIONS).body[0]
        self.assertEqual(node.specifiers[1].exported.name, 'ns')
        esprima.parseModule(r'export \u0076alue from "m";', OPTIONS)

    def test_bare_exports_bad_clauses_and_duplicate_export_names_always_reject(self):
        sources = [
            'const value=1; export value;', 'const value=1; export value, {value as other};',
            'export value, {};', 'export value, * as ns;', 'export value, * from "m";',
            'export value, other from "m";', 'export value, {other}, * as ns from "m";',
            'export value, * as ns, {other} from "m";', 'export value from 1;',
            'export value, {other as value} from "m";', 'export value, * as value from "m";',
            'export value from "m"; export value from "n";',
            'export default from "m"; export default 1;',
            'export value from "m" with {type:1};',
            'export value from "m" with {type:"json",type:"json"};',
            '{export value from "m";}', 'function f(){export value from "m";}',
        ]
        for source in sources:
            for options in ({}, OPTIONS):
                with self.subTest(source=source, options=options), self.assertRaises(esprima.Error):
                    esprima.parseModule(source, options)
        with self.assertRaises(esprima.Error):
            esprima.parseScript('export value from "m";', OPTIONS)

    def test_standard_default_expressions_and_declarations_remain_valid(self):
        sources = [
            'const from=1; export default from;', 'const from=1; export default from + 1;',
            'const from=()=>1; export default from();', 'export default 1;',
            'export default function(){}', 'export default async function(){}',
            'export default class {}', 'export async function f(){}',
            'export const value=1;', 'const value=1; export {value};',
            'export {default as value} from "m";', 'export * as ns from "m";',
        ]
        for source in sources:
            for options in ({}, OPTIONS):
                with self.subTest(source=source, options=options):
                    esprima.parseModule(source, options)

    def test_supplied_native_and_mapping_ast_shape_is_checked_read_only(self):
        native = esprima.parseModule('export value, {other} from "m";', OPTIONS)
        self.assertEqual(errors(native), [])
        mapping = native.toDict()
        self.assertEqual(errors(mapping), [])
        self.assertTrue(errors(mapping, 2025))
        variants = []
        tree = copy.deepcopy(mapping)
        tree['body'][0]['source'] = None
        variants.append(tree)
        tree = copy.deepcopy(mapping)
        tree['body'][0]['declaration'] = {'type': 'VariableDeclaration', 'kind': 'var', 'declarations': []}
        variants.append(tree)
        tree = copy.deepcopy(mapping)
        tree['body'][0]['specifiers'].reverse()
        variants.append(tree)
        tree = copy.deepcopy(mapping)
        tree['body'][0]['specifiers'].append(copy.deepcopy(tree['body'][0]['specifiers'][0]))
        variants.append(tree)
        tree = copy.deepcopy(mapping)
        tree['body'][0]['specifiers'][0]['exported'] = {'type': 'Literal', 'value': 'value'}
        variants.append(tree)
        tree = copy.deepcopy(mapping)
        tree['body'][0]['specifiers'][0]['local'] = {'type': 'Identifier', 'name': 'conflict'}
        variants.append(tree)
        for name in (False, None, [], {}, ''):
            tree = copy.deepcopy(mapping)
            tree['body'][0]['specifiers'][0]['exported'] = {'type': 'Identifier', 'name': name}
            variants.append(tree)
        tree = copy.deepcopy(mapping)
        tree['body'][0]['specifiers'].append({'type': 'ExportNamespaceSpecifier', 'exported': {'type': 'Identifier', 'name': 'ns'}})
        variants.append(tree)
        for tree in variants:
            with self.subTest(tree=tree):
                before = copy.deepcopy(tree)
                self.assertTrue(errors(tree))
                self.assertEqual(tree, before)
        legacy = copy.deepcopy(mapping)
        specifier = legacy['body'][0]['specifiers'][0]
        specifier['local'] = specifier.pop('exported')
        self.assertEqual(errors(legacy), [])

    @unittest.skipUnless(shutil.which('node') and (REFERENCE / '@babel/parser').exists(), 'pinned Babel proposal oracle required')
    def test_independent_babel_proposal_ast_and_standard_rejection(self):
        sources = ['export value from "m";', 'export default from "m";',
                   'export await from "m";', 'export value, {other as x} from "m";',
                   '/*😀*/ export value, * as ns from "m" with {type:"json"};']
        script = '''
const fs=require('node:fs'), babel=require(process.argv[1]);
if(require(process.argv[1]+'/package.json').version!=='8.0.7') throw Error('Expected Babel 8.0.7');
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(source=>{
  let standardAccepted=true;try{babel.parse(source,{sourceType:'module',plugins:['estree']});}catch(e){standardAccepted=false;}
  const program=babel.parse(source,{sourceType:'module',ranges:true,plugins:['estree','exportDefaultFrom']}).program;
  return {standardAccepted,program};
})));
'''
        process = subprocess.run(['node', '-e', script, str(REFERENCE / '@babel/parser')],
            input=json.dumps(sources), text=True, encoding='utf-8', capture_output=True, check=True)
        def normalized(value):
            if isinstance(value, list):
                return [normalized(item) for item in value]
            if isinstance(value, dict):
                return {key: normalized(item) for key, item in value.items()
                        if key not in {'identifierName', 'extra', 'leadingComments', 'trailingComments', 'innerComments'}
                        and not (key in {'start', 'end'} and isinstance(item, int))}
            return value
        for source, reference in zip(sources, json.loads(process.stdout)):
            with self.subTest(source=source):
                self.assertFalse(reference['standardAccepted'])
                actual = esprima.parseModule(source, dict(OPTIONS, loc=True, range=True)).toDict()['body']
                expected = migrate_legacy_fixture(reference['program']['body'])
                self.assertEqual(normalized(actual), normalized(expected))


if __name__ == '__main__':
    unittest.main()
