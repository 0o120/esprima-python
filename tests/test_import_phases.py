"""Explicit import-phase extensions preserve their syntax and ESTree meaning."""
from hashlib import sha256
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import esprima
from esprima.validation import validate_program


OPTIONS = {'deferredImportEvaluation': True, 'sourcePhaseImports': True}
REFERENCE = Path(os.environ.get('ESCODEGEN_REFERENCE_NODE_MODULES',
    str(Path(__file__).resolve().parents[1] / 'tools/reference/node_modules')))
CORPUS = Path(__file__).parent / 'fixtures/import-phases'


def normalized(value):
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()
                if key not in {'identifierName', 'extra'}
                and not (key in {'start', 'end'} and isinstance(item, int))
                and not (key == 'phase' and item is None)}
    return value


class ImportPhaseTests(unittest.TestCase):
    def test_extensions_are_independent_explicit_current_edition_gates(self):
        for phase, option, static in (
            ('defer', 'deferredImportEvaluation', 'import defer * as ns from "m";'),
            ('source', 'sourcePhaseImports', 'import source mod from "m";'),
        ):
            for source in (static, 'import.' + phase + '("m");'):
                with self.subTest(source=source):
                    with self.assertRaisesRegex(esprima.Error, option):
                        esprima.parseModule(source)
                    wrong = 'sourcePhaseImports' if phase == 'defer' else 'deferredImportEvaluation'
                    with self.assertRaisesRegex(esprima.Error, option):
                        esprima.parseModule(source, {wrong: True})
                    with self.assertRaisesRegex(esprima.Error, 'requires ECMAScript 2026'):
                        esprima.parseModule(source, {option: True, 'ecmaVersion': 2025})
                    esprima.parseModule(source, {option: True})

    def test_static_specifiers_attributes_binding_names_and_json(self):
        for source, phase, specifier, name in (
            ('import defer * as ns from "m" with {type:"json"};', 'defer', 'ImportNamespaceSpecifier', 'ns'),
            ('import source mod from "m" with {type:"json"};', 'source', 'ImportDefaultSpecifier', 'mod'),
            ('import source source from "m";', 'source', 'ImportDefaultSpecifier', 'source'),
            ('import source from from "m";', 'source', 'ImportDefaultSpecifier', 'from'),
            ('import defer * as defer from "m";', 'defer', 'ImportNamespaceSpecifier', 'defer'),
            ('import\nsource/* gap */\nmod from "m";', 'source', 'ImportDefaultSpecifier', 'mod'),
            ('import\ndefer\n* as ns from "m";', 'defer', 'ImportNamespaceSpecifier', 'ns'),
        ):
            with self.subTest(source=source):
                node = esprima.parseModule(source, OPTIONS).body[0]
                self.assertEqual(node.phase, phase)
                self.assertEqual(len(node.specifiers), 1)
                self.assertEqual(node.specifiers[0].type, specifier)
                self.assertEqual(node.specifiers[0].local.name, name)
                self.assertEqual(json.loads(json.dumps(node.toDict()))['phase'], phase)
                if 'with' in source:
                    self.assertEqual(node.attributes[0].value.value, 'json')

    def test_contextual_default_bindings_and_normal_import_shapes_are_preserved(self):
        for option in ({}, OPTIONS):
            for name in ('defer', 'source'):
                for source in ('import ' + name + ' from "m";',
                               'import ' + name + ', {x} from "m";',
                               'import ' + name + ', * as ns from "m";'):
                    with self.subTest(source=source, options=option):
                        node = esprima.parseModule(source, option).body[0]
                        self.assertEqual(node.specifiers[0].local.name, name)
                        self.assertNotIn('phase', node.toDict())
            node = esprima.parseScript('import("m");', option).body[0].expression
            self.assertNotIn('phase', node.toDict())
            self.assertIsNone(node.options)
        node = esprima.parseModule('new import.meta.C();', OPTIONS).body[0].expression
        self.assertEqual(node.callee.object.type, 'MetaProperty')
        self.assertEqual(node.callee.object.property.name, 'meta')

    def test_dynamic_phases_options_trailing_commas_and_chains(self):
        for phase in ('defer', 'source'):
            for arguments in ('"m"', '"m",', '"m",{}', '"m",{},'):
                for parser in (esprima.parseScript, esprima.parseModule):
                    source = 'import.' + phase + '(' + arguments + ');'
                    with self.subTest(source=source, parser=parser.__name__):
                        node = parser(source, OPTIONS).body[0].expression
                        self.assertEqual(node.type, 'ImportExpression')
                        self.assertEqual(node.phase, phase)
                        self.assertEqual(node.source.value, 'm')
                        self.assertEqual(node.options is None, '{}' not in arguments)
            source = 'import\n./* gap */\n' + phase + '\n("m").then(f);'
            node = esprima.parseScript(source, OPTIONS).body[0].expression
            self.assertEqual(node.callee.object.phase, phase)

    def test_invalid_specifiers_contexts_and_dynamic_forms_are_rejected(self):
        sources = [
            'import defer defaultBinding from "m";', 'import defer {x} from "m";',
            'import defer "m";', 'import defer * as ns, {x} from "m";',
            'import source * as ns from "m";', 'import source {x} from "m";',
            'import source "m";', 'import source mod, {x} from "m";',
            'import source mod, * as ns from "m";',
            'import source await from "m";', 'import defer * as await from "m";',
            'export defer * from "m";', 'export source mod from "m";',
            'import source mod from "m"; let mod;',
            'import defer * as ns from "m"; var ns;',
            'import source mod from "m" with {type:"json", type:"json"};',
            'import defer * as ns from "m" with {type:1};',
            r'import \u0064efer * as ns from "m";',
            r'import \u0073ource mod from "m";',
            '{ import defer * as ns from "m"; }',
            'function f(){ import source mod from "m"; }',
        ]
        for phase in ('defer', 'source'):
            sources.extend('import.' + phase + arguments + ';' for arguments in
                           ('()', '("m",{},0)', '(...x)', '("m",...x)',
                            '("m",,)', '', '?.("m")', '["m"]'))
            sources += ['new import.' + phase + '("m");',
                        'import.' + phase + '("m") = 1;',
                        r'import.\u00' + ('64efer' if phase == 'defer' else '73ource') + '("m");']
        for source in sources:
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseModule(source, OPTIONS)
        for source in ('import defer * as ns from "m";', 'import source mod from "m";'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source, OPTIONS)

    def test_utf16_positions_and_tokens(self):
        source = '/*😀*/ import.source("m", {with:{type:"json"}});'
        tree = esprima.parseScript(source, dict(OPTIONS, range=True, loc=True, tokens=True))
        expression = tree.body[0].expression
        self.assertEqual(expression.range[0], 7)
        self.assertEqual(expression.loc.start.column, 7)
        self.assertEqual(tree.tokens[0].range, [7, 13])
        self.assertEqual(tree.tokens[2].value, 'source')
        self.assertEqual(tree.tokens[2].type, 'Identifier')
        tokens = esprima.tokenize(source, {'range': True, 'loc': True})
        self.assertEqual([token.toDict() for token in tree.tokens], [token.toDict() for token in tokens])

    def test_supplied_native_and_mapping_phase_asts_are_validated_without_mutation(self):
        def errors(tree, edition=2026):
            result = []
            validate_program(tree, lambda message, node: result.append((message, node)), edition)
            return result
        for phase, source in (
            ('defer', 'import defer * as ns from "m";'),
            ('source', 'import source mod from "m";'),
        ):
            native = esprima.parseModule(source, OPTIONS)
            self.assertEqual(errors(native), [])
            mapping = native.toDict()
            original = copy.deepcopy(mapping)
            self.assertEqual(errors(mapping), [])
            self.assertEqual(mapping, original)
            self.assertTrue(errors(mapping, 2025))
            for invalid in ('evil', '', False, 1, [], {}):
                with self.subTest(phase=phase, invalid=invalid):
                    tree = copy.deepcopy(mapping)
                    tree['body'][0]['phase'] = invalid
                    before = copy.deepcopy(tree)
                    result = errors(tree)
                    self.assertTrue(result)
                    self.assertEqual(tree, before)
                    self.assertIs(result[0][1], tree['body'][0])
            for invalid_type in ('ImportSpecifier', 'ImportDefaultSpecifier' if phase == 'defer' else 'ImportNamespaceSpecifier'):
                tree = copy.deepcopy(mapping)
                tree['body'][0]['specifiers'][0]['type'] = invalid_type
                with self.subTest(phase=phase, invalid_type=invalid_type):
                    self.assertTrue(errors(tree))
            for count in (0, 2):
                tree = copy.deepcopy(mapping)
                tree['body'][0]['specifiers'] *= count
                with self.subTest(phase=phase, specifier_count=count):
                    self.assertTrue(errors(tree))
            tree = copy.deepcopy(mapping)
            tree['sourceType'] = 'script'
            self.assertTrue(errors(tree))
            tree = copy.deepcopy(mapping)
            tree['body'] = [{'type': 'BlockStatement', 'body': tree['body']}]
            self.assertTrue(errors(tree))
            for parser in (esprima.parseScript, esprima.parseModule):
                native = parser('import.' + phase + '("m");', OPTIONS)
                self.assertEqual(errors(native), [])
                tree = native.toDict()
                self.assertTrue(errors(tree, 2025))
                tree['body'][0]['expression']['phase'] = 'evil'
                self.assertTrue(errors(tree))
                tree['body'][0]['expression']['phase'] = phase
                tree['body'][0]['expression']['source'] = None
                self.assertTrue(errors(tree))
        tree = esprima.parseModule('export * from "m";').toDict()
        tree['body'][0]['phase'] = 'defer'
        self.assertTrue(errors(tree))
        def invalid_delegate(node, metadata):
            if node.type == 'ImportExpression':
                node.phase = 'evil'
            return node
        with self.assertRaisesRegex(esprima.Error, 'Import phase'):
            esprima.parseScript('import("m");', delegate=invalid_delegate)

    @unittest.skipUnless(shutil.which('node') and (REFERENCE / '@babel/parser').exists(), 'pinned Babel AST oracle required')
    def test_independent_babel_estree_values_and_positions(self):
        jobs = []
        for phase, static in (
            ('defer', 'import defer * as ns from "m" with {type:"json"};'),
            ('source', 'import source mod from "m" with {type:"json"};'),
        ):
            jobs += [{'source': static, 'module': True},
                     {'source': '/*😀*/ import\n.' + phase + '("m", {with:{type:"json"}},);', 'module': False},
                     {'source': 'const p=import.' + phase + '("m",).then(f);', 'module': False}]
        script = '''
const fs=require('node:fs'), babel=require(process.argv[1]);
if(require(process.argv[1]+'/package.json').version!=='8.0.7') throw Error('Expected Babel 8.0.7');
const jobs=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(jobs.map(job=>babel.parse(job.source,{
  sourceType:job.module?'module':'script',ranges:true,
  plugins:['estree','sourcePhaseImports','deferredImportEvaluation']}).program)));
'''
        process = subprocess.run(['node', '-e', script, str(REFERENCE / '@babel/parser')],
            input=json.dumps(jobs), encoding='utf-8', text=True, capture_output=True, check=True)
        references = json.loads(process.stdout)
        for job, reference in zip(jobs, references):
            parser = esprima.parseModule if job['module'] else esprima.parseScript
            actual = parser(job['source'], dict(OPTIONS, range=True, loc=True)).toDict()
            # Comments are collected separately by Babel and esprima. Compare
            # statement trees including range/loc without attachment metadata.
            def clean(value):
                if isinstance(value, list):
                    return [clean(item) for item in value]
                if isinstance(value, dict):
                    return {key: clean(item) for key, item in value.items()
                            if key not in {'comments', 'leadingComments', 'trailingComments', 'innerComments'}}
                return value
            with self.subTest(source=job['source']):
                self.assertEqual(normalized(clean(actual['body'])), normalized(clean(reference['body'])))

    def test_frozen_test262_phase_syntax_corpus(self):
        manifest = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
        for name, expected in manifest['files'].items():
            self.assertEqual(sha256((CORPUS / name).read_bytes()).hexdigest(), expected, name)
        cases = json.loads((CORPUS / 'cases.json').read_text(encoding='utf-8'))['cases']
        self.assertEqual(len(cases), manifest['caseCount'])
        for case in cases:
            with self.subTest(path=case['path'], mode=case['mode']):
                source = case['source']
                self.assertEqual(sha256(source.encode('utf-8')).hexdigest(), case['sha256'])
                if case['mode'] == 'strict':
                    source = '"use strict";\n' + source
                parser = esprima.parseModule if case['mode'] == 'module' else esprima.parseScript
                if case['parseNegative']:
                    with self.assertRaises(esprima.Error) as rejected:
                        parser(source, OPTIONS)
                    self.assertNotIn('resource limit', str(rejected.exception).lower())
                else:
                    parser(source, OPTIONS)


if __name__ == '__main__':
    unittest.main()
