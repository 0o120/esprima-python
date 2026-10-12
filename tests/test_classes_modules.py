import unittest

import esprima


class ClassModuleTests(unittest.TestCase):
    def test_current_class_elements(self):
        tree = esprima.toDict(esprima.parseScript('class A extends B { #x=1; static #y; [key]=2; "q"=3; 0; async=1; static=2; static { f(); } get #p(){return this.#x;} set #p(v){this.#x=v;} async *m(){yield await f();} constructor(){super();} }'))
        body = tree['body'][0]['body']['body']
        self.assertEqual(body[0]['type'], 'PropertyDefinition')
        self.assertEqual(body[0]['key']['type'], 'PrivateIdentifier')
        self.assertIsNone(body[1]['value'])
        self.assertEqual(body[7]['type'], 'StaticBlock')
        self.assertTrue(body[-2]['value']['generator'])
        self.assertTrue(body[-2]['value']['async'])
        self.assertEqual(body[-1]['kind'], 'constructor')

    def test_class_field_separators_and_illegal_keys(self):
        for source in ('class A { x y }', 'class A { constructor; }', 'class A { static prototype; }', 'class A { async constructor(){} }'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseScript(source)
        esprima.parseScript('class A { x\ny\nstatic\nz }')

    def test_private_brand_and_object_async_generator(self):
        tree = esprima.toDict(esprima.parseScript('class A { #x; m(o){ return #x in o; } }'))
        self.assertEqual(tree['body'][0]['body']['body'][1]['value']['body']['body'][0]['argument']['left']['type'], 'PrivateIdentifier')
        obj = esprima.toDict(esprima.parseScript('({async *m(){yield await f();}});'))
        method = obj['body'][0]['expression']['properties'][0]['value']
        self.assertTrue(method['async'])
        self.assertTrue(method['generator'])

    def test_module_names_and_attributes(self):
        tree = esprima.toDict(esprima.parseModule('import {"a-b" as x} from "m" with {type:"json"}; export * as "n-s" from "n" with {"type":"json"}; export {x as "x-y"};'))
        self.assertEqual(tree['body'][0]['specifiers'][0]['imported']['value'], 'a-b')
        self.assertEqual(tree['body'][0]['attributes'][0]['type'], 'ImportAttribute')
        self.assertEqual(tree['body'][1]['exported']['value'], 'n-s')
        self.assertEqual(tree['body'][2]['specifiers'][0]['exported']['value'], 'x-y')

    def test_import_attribute_negative_cases(self):
        for source in ('import x from "m" with {type:1};', 'import x from "m" with {type:"json",type:"json"};', 'import {"x"} from "m";', 'import await from "m";'):
            with self.subTest(source=source), self.assertRaises(esprima.Error):
                esprima.parseModule(source)
