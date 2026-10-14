"""Public serialization must retain visitor protocols and complete metadata."""
import json
import unittest
from unittest.mock import patch

import esprima
from esprima.objects import Array, Object
from esprima.visitor import ToDictVisitor, Visited, Visitor


class GenericSerializer(ToDictVisitor):
    """Use the general visitor protocol as an independent conversion route."""


class SerializationFastPathTests(unittest.TestCase):
    def test_native_mapping_and_tokens_match_general_visitor(self):
        cases = [
            ('/* lead */ const 名="😀"; const r=/a+/gi; var x; f?.(x);', {}),
            ('async function f(){for await (const x of y) yieldValue(x);}', {}),
            ('const x=<A key={1}>hello<B />{value}</A>;', {'jsx': True}),
            ('@dec export class C { @member accessor x=1; }', {'sourceType': 'module', 'decorators': True}),
            ('await using r=open(); import defer * as d from "m";',
             {'sourceType': 'module', 'explicitResourceManagement': True, 'deferredImportEvaluation': True}),
            ('function f(){return;} try{}catch{} for(;;)break;', {}),
        ]
        for source, options in cases:
            with self.subTest(source=source):
                tree = esprima.parse(source, dict(options, range=True, loc=True, tokens=True,
                                                 comment=True, attachComment=True))
                expected = GenericSerializer().visit(tree)
                actual = esprima.toDict(tree)
                self.assertEqual(actual, expected)
                self.assertEqual(json.dumps(actual), json.dumps(expected))
                self.assertEqual(esprima.toDict(actual), GenericSerializer().visit(expected))
                self.assertEqual(esprima.toDict(esprima.tokenize(source, options, tolerant=True)),
                                 GenericSerializer().visit(esprima.tokenize(source, options, tolerant=True)))

    def test_nullable_nonfinite_and_alias_collision_order(self):
        values = [float('inf'), float('-inf'), float('nan'), -0.0, None]
        for value in values:
            obj = {'type': 'Literal', 'value': value, 'raw': 'null',
                   'isAsync': True, 'async': False, 'cooked': None, '_hidden': 1}
            self.assertEqual(json.dumps(esprima.toDict(obj), allow_nan=False),
                             json.dumps(GenericSerializer().visit(obj), allow_nan=False))
        regex = {'type': 'Literal', 'regex': {}, 'value': object()}
        self.assertEqual(esprima.toDict(regex), GenericSerializer().visit(regex))

    def test_shared_nodes_are_copied_and_object_cycles_are_reported(self):
        obj = Object()
        obj.child = {'type': 'Identifier', 'name': 'x'}
        original = [obj, obj]
        result = esprima.toDict(original)
        self.assertEqual(result, GenericSerializer().visit(original))
        self.assertIsNot(result[0], result[1])
        self.assertIsNot(result[0]['child'], result[1]['child'])
        obj.child = obj
        self.assertEqual(esprima.toDict(obj), {'child': {'error': 'Infinite recursion detected...'}})

    def test_deep_mappings_do_not_use_python_recursion(self):
        node = {'type': 'Identifier', 'name': 'bottom'}
        for _ in range(3000):
            node = {'type': 'UnaryExpression', 'operator': '!', 'argument': node}
        result = esprima.toDict(node)
        for _ in range(3000):
            result = result['argument']
        self.assertEqual(result, {'type': 'Identifier', 'name': 'bottom'})

    def test_custom_dictionary_property_is_read_once(self):
        reads = []
        class Custom(Object):
            @property
            def __dict__(self):
                reads.append('dictionary')
                return {'value': len(reads)}
        self.assertEqual(esprima.toDict({'prefix': [1, 2], 'custom': Custom()}),
                         {'prefix': [1, 2], 'custom': {'value': 1}})
        self.assertEqual(reads, ['dictionary'])

    def test_custom_key_is_not_compared_before_fallback(self):
        calls = []
        class Key(str):
            def startswith(self, prefix):
                calls.append('startswith')
                return super().startswith(prefix)
            def __eq__(self, other):
                calls.append('eq')
                return super().__eq__(other)
            __hash__ = str.__hash__
        value = {Key('type'): 'Literal', 'value': 3}
        calls.clear()
        expected = GenericSerializer().visit(value)
        expected_calls = calls[:]
        calls.clear()
        self.assertEqual(esprima.toDict(value), expected)
        self.assertEqual(calls, expected_calls)

    def test_custom_metaclass_hash_is_not_called_before_fallback(self):
        calls = []
        class Meta(type):
            def __hash__(self):
                calls.append('hash')
                return type.__hash__(self)
        class Value(metaclass=Meta):
            pass
        obj = Value()
        result = esprima.toDict({'opaque': obj})
        self.assertIs(result['opaque'], obj)
        self.assertEqual(calls, [])

    def test_class_descriptor_is_not_invoked_by_eligibility_checks(self):
        calls = []
        class Equality:
            def __get__(self, instance, owner):
                calls.append('descriptor')
                return object.__eq__
        class Custom(Object):
            __eq__ = Equality()
            __hash__ = object.__hash__
        obj = Custom()
        obj.value = 1
        expected = GenericSerializer().visit(obj)
        expected_calls = calls[:]
        calls.clear()
        self.assertEqual(esprima.toDict(obj), expected)
        self.assertEqual(calls, expected_calls)

    def test_subclasses_monkeypatches_and_instance_handlers_remain_dynamic(self):
        class Custom(ToDictVisitor):
            def visit_str(self, value):
                yield Visited(value.upper())
        self.assertEqual(Custom().visit({'value': 'x'}), {'value': 'X'})
        with patch.object(ToDictVisitor, 'visit_str', Custom.visit_str, create=True):
            self.assertEqual(esprima.toDict({'value': 'x'}), {'value': 'X'})
        visitor = ToDictVisitor()
        def changed(value):
            yield Visited(value + '!')
        visitor.visit_str = changed
        self.assertEqual(visitor.visit({'value': 'x'}), {'value': 'x!'})
        self.assertEqual(visitor.visit({'value': 'y'}), {'value': 'y!'})
        with patch.dict(ToDictVisitor.map, {'value': 'renamed'}):
            self.assertEqual(esprima.toDict({'value': 'x'}), {'renamed': 'x'})

    def test_custom_array_iteration_occurs_once(self):
        calls = []
        def changed(array):
            calls.append('iterate')
            yield {'custom': object()}
        with patch.object(Array, '__iter__', changed, create=True):
            result = esprima.toDict(Array([1]))
        self.assertEqual(len(result), 1)
        self.assertEqual(calls, ['iterate'])

    def test_object_truthiness_hooks_and_generic_visitor_overrides(self):
        calls = []
        class Truthy(Object):
            def __bool__(self):
                calls.append('bool')
                return True
        obj = Truthy()
        obj.value = 1
        expected = GenericSerializer().visit(obj)
        expected_calls = calls[:]
        calls.clear()
        self.assertEqual(esprima.toDict(obj), expected)
        self.assertEqual(calls, expected_calls)
        class Custom(Visitor):
            def visit_Generic(self, obj):
                yield Visited('custom')
        self.assertEqual(Custom().visit(1), 'custom')


if __name__ == '__main__':
    unittest.main()
