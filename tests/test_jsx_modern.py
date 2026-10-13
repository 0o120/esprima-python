import unittest

import esprima


class JSXTests(unittest.TestCase):
    def parse(self, code, **options):
        return esprima.toDict(esprima.parseScript(code, {'jsx': True, **options}))

    def test_unclosed_elements_are_errors(self):
        for code in ('<A>', '<A><B></B>', '<A>text', '<A></B>', '<><A/></A>'):
            with self.subTest(code=code), self.assertRaises(esprima.Error):
                self.parse(code)

    def test_tolerant_truncation_has_errors_and_children(self):
        tree = self.parse('<A><B/>', tolerant=True)
        self.assertTrue(tree['errors'])
        self.assertEqual(len(tree['body'][0]['expression']['children']), 1)

    def test_fragments_and_spread_children(self):
        tree = self.parse('<>Hi<A {...props}>{...children}</A></>;')
        fragment = tree['body'][0]['expression']
        self.assertEqual(fragment['type'], 'JSXFragment')
        self.assertEqual(fragment['openingFragment']['type'], 'JSXOpeningFragment')
        child = fragment['children'][1]
        self.assertEqual(child['openingElement']['attributes'][0]['type'], 'JSXSpreadAttribute')
        self.assertEqual(child['children'][0]['type'], 'JSXSpreadChild')

    def test_nested_fragments_and_empty_container(self):
        tree = self.parse('<A><><B/>{/*comment*/}</></A>;')
        self.assertEqual(tree['body'][0]['expression']['children'][0]['type'], 'JSXFragment')

    def test_text_values_decode_entities_and_normalize_crlf(self):
        value = self.parse('<A>&amp;&#x1f600;a\r\nb</A>;')['body'][0]['expression']['children'][0]
        self.assertEqual(value['value'], '&😀a\nb')
        self.assertEqual(value['raw'], '&amp;&#x1f600;a\r\nb')
        self.assertEqual(self.parse('<A>&unknown<B/>{x}</A>;')['body'][0]['expression']['children'][0]['value'], '&unknown')

    def test_malformed_entity_and_text_eof_are_structured_errors(self):
        for source in ('<A>\r', '<A>></A>;', '<A>}</A>;'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                self.parse(source)

    def test_attribute_entities_and_positions(self):
        tree = self.parse('<A x="a\r\nb &amp; &#x1f600;"/>;', loc=True)
        attribute = tree['body'][0]['expression']['openingElement']['attributes'][0]
        self.assertEqual(attribute['value']['value'], 'a\r\nb & 😀')
        self.assertEqual(attribute['value']['loc']['end']['line'], 2)

    def test_invalid_reference_spelling_stays_literal(self):
        for reference in ('&#x110000;', '&#' + '9' * 5000 + ';', '&unknown;'):
            text = self.parse('<A>' + reference + '</A>;')['body'][0]['expression']['children'][0]
            self.assertEqual(text['value'], reference)
        self.assertEqual(self.parse('<A>&#xd800;</A>;')['body'][0]['expression']['children'][0]['value'], '\ud800')

    def test_reference_jsx_text_and_attributes(self):
        import json
        from pathlib import Path
        import shutil
        import subprocess
        root = Path(__file__).resolve().parents[1]
        if not shutil.which('node') or not (root / 'tools/reference/node_modules/@babel/parser').exists():
            self.skipTest('Pinned Babel JSX development reference required')
        sources = ['<A>&amp;&#x1f600;\r\nb</A>;', '<A x="a\r\nb &amp; &#x1f600;"/>;', '<A>&#xd800;&#x110000;</A>;', '<A>a\rb</A>;']
        script = "const p=require('./tools/reference/node_modules/@babel/parser');const s=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(s.map(x=>p.parse(x,{plugins:['estree','jsx']}).program.body[0].expression)));"
        result = subprocess.run(['node', '-e', script], cwd=root, input=json.dumps(sources),
                                encoding='utf-8', capture_output=True, check=True)
        expected = json.loads(result.stdout)
        for source, other in zip(sources, expected):
            actual = self.parse(source)['body'][0]['expression']
            if actual['children']:
                self.assertEqual(actual['children'][0]['value'], other['children'][0]['value'])
            else:
                self.assertEqual(actual['openingElement']['attributes'][0]['value']['value'], other['openingElement']['attributes'][0]['value']['value'])
