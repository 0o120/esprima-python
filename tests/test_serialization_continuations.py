"""A late custom value must preserve the original visitor's suspended state."""
import gc
import json
import unittest
import weakref
from unittest.mock import patch

import esprima
from esprima.objects import Array, Object
from esprima.visitor import ToDictVisitor, Visited


class GeneralVisitor(ToDictVisitor):
    pass


class Custom(Object):
    def __init__(self, read):
        self.read = read

    @property
    def __dict__(self):
        return self.read()


class ContinuationTests(unittest.TestCase):
    def compare(self, build, expected_error=None):
        results = []
        for cls in (GeneralVisitor, ToDictVisitor):
            with patch.dict(ToDictVisitor.map, ToDictVisitor.map.copy(), clear=True):
                visitor = cls()
                source, calls = build(visitor)
                try:
                    result = ('value', json.dumps(visitor.visit(source), allow_nan=False))
                except (TypeError, ValueError, RuntimeError) as error:
                    if expected_error is None:
                        raise
                    self.assertIsInstance(error, expected_error)
                    result = ('error', type(error).__name__, str(error))
                self.assertEqual(visitor._visit_count, 0)
                self.assertEqual(visitor._visit_context, {})
                results.append((result, calls))
        self.assertEqual(results[0], results[1])
        return results[1]

    def test_nested_lists_and_native_ancestors_keep_context(self):
        def build(visitor):
            calls = []
            root, inner = Object(), Object()
            root.label, inner.label = 'root', 'inner'
            def read():
                calls.append(sorted(getattr(node, 'label', None) or 'custom'
                                    for node in visitor._visit_context))
                return {'value': 7}
            inner.values = [1, {'nested': [2, Custom(read)]}, 3]
            root.body = [Object(), inner]
            return root, calls
        result, calls = self.compare(build)
        self.assertEqual(result[0], 'value')
        self.assertEqual(calls, [['custom', 'inner', 'root']])

    def test_parent_keys_are_mapped_after_children_complete(self):
        def build(visitor):
            calls = []
            def read():
                calls.append('map changed')
                ToDictVisitor.map.update({'branch': 'changed', 'list': 'renamed'})
                return {'value': 1}
            return {'branch': {'list': [0, Custom(read)]}, 'after': 2}, calls
        result, _ = self.compare(build)
        self.assertEqual(json.loads(result[1]), {'changed': {'renamed': [0, {'value': 1}]}, 'after': 2})

    def test_earlier_values_are_not_read_again_after_a_hook(self):
        def build(visitor):
            calls = []
            source = {'prefix': {'value': 1}, 'custom': None, 'after': 3}
            def read():
                calls.append('read')
                source['prefix']['value'] = 99
                source['after'] = 4
                return {'value': 2}
            source['custom'] = Custom(read)
            return source, calls
        result, calls = self.compare(build)
        self.assertEqual(json.loads(result[1]), {'prefix': {'value': 1}, 'custom': {'value': 2}, 'after': 4})
        self.assertEqual(calls, ['read'])

    def test_live_source_fields_control_nonfinite_finalization(self):
        def build(visitor):
            calls = []
            source = {'type': 'Other', 'value': 7, 'custom': None}
            def read():
                source['type'], source['value'] = 'Literal', float('inf')
                calls.append('mutated')
                return {'ok': True}
            source['custom'] = Custom(read)
            return source, calls
        result, _ = self.compare(build)
        self.assertEqual(json.loads(result[1])['number'], 'Infinity')

    def test_new_visitor_methods_apply_to_remaining_nodes(self):
        def run(cls):
            calls = []
            def identifier(self, node):
                calls.append(node.name)
                yield Visited('custom:' + node.name)
            def read():
                ToDictVisitor.visit_Identifier = identifier
                return {'ok': True}
            try:
                return cls().visit([esprima.nodes.Identifier('first'), Custom(read),
                                    esprima.nodes.Identifier('last')]), calls
            finally:
                del ToDictVisitor.visit_Identifier
        self.assertEqual(run(ToDictVisitor), run(GeneralVisitor))

    def test_backreference_to_active_native_ancestor(self):
        def build(visitor):
            root = Object()
            root.prefix = [1, 2, 3]
            calls = []
            def read():
                calls.append('read')
                return {'ancestor': root}
            root.custom = Custom(read)
            return root, calls
        result, _ = self.compare(build)
        self.assertIn('Infinite recursion detected', result[1])

    def test_changed_map_hashes_keys_only_after_visiting_later_values(self):
        def build(visitor):
            calls = []
            def change():
                calls.append('change')
                ToDictVisitor.map['custom'] = []
                return {'ok': 1}
            def later():
                calls.append('later')
                return {'ok': 2}
            return {'prefix': 1, 'custom': Custom(change), 'later': Custom(later)}, calls
        result, calls = self.compare(build, TypeError)
        self.assertEqual(result[0:2], ('error', 'TypeError'))
        self.assertEqual(calls, ['change', 'later'])

    def test_input_dictionary_size_errors_and_hook_exceptions(self):
        for mutate in (True, False):
            def build(visitor, mutate=mutate):
                calls = []
                source = {'prefix': [1, 2], 'custom': None, 'last': 3}
                def read():
                    calls.append('read')
                    if mutate:
                        source['added'] = 4
                        return {}
                    raise ValueError('hook failure')
                source['custom'] = Custom(read)
                return source, calls
            result, calls = self.compare(build, RuntimeError if mutate else ValueError)
            self.assertEqual(result[0], 'error')
            self.assertEqual(calls, ['read'])

    def test_cyclic_prefix_retains_full_fallback(self):
        def build(visitor):
            root = Object()
            calls = []
            root.cycle = root
            def read():
                calls.append('read')
                return {'ok': 1}
            root.custom = Custom(read)
            return root, calls
        self.compare(build)

    def test_alias_collision_before_a_late_map_change(self):
        def build(visitor):
            calls = []
            def read():
                ToDictVisitor.map['async'] = 'changed'
                calls.append('read')
                return {'value': 1}
            return {'isAsync': False, 'async': [Custom(read)]}, calls
        result, _ = self.compare(build)
        self.assertEqual(json.loads(result[1]), {'async': False, 'changed': [{'value': 1}]})

    def test_literal_finalization_after_custom_metadata(self):
        for number in (float('inf'), float('-inf'), float('nan')):
            def build(visitor, number=number):
                return {'type': 'Literal', 'value': number, 'raw': 'null',
                        'metadata': Custom(lambda: {'ok': True})}, []
            result, _ = self.compare(build)
            self.assertIsNone(json.loads(result[1])['value'])

    def test_generator_and_visited_transport_values(self):
        def build(visitor):
            calls = []
            def values():
                first = yield {'value': 1, 'omitted': None}
                calls.append(first)
                yield Visited({'retained': None})
            return {'prefix': [0, 1], 'generator': values()}, calls
        result, calls = self.compare(build)
        self.assertEqual(calls, [{'value': 1}])
        self.assertEqual(json.loads(result[1])['generator'], {'retained': None})

    def test_deep_continuation_is_iterative(self):
        for cls in (GeneralVisitor, ToDictVisitor):
            calls = []
            def read(calls=calls):
                calls.append('read')
                return {'ok': True}
            source = Custom(read)
            for _ in range(3000):
                source = {'child': source}
            converted = cls().visit(source)
            for _ in range(3000):
                converted = converted['child']
            self.assertEqual(converted, {'ok': True})
            self.assertEqual(calls, ['read'])

    def test_completed_continuation_does_not_retain_input_without_gc(self):
        root = Object()
        root.prefix = [esprima.nodes.Identifier('x') for _ in range(50)]
        root.custom = Custom(lambda: {'ok': True})
        reference = weakref.ref(root)
        enabled = gc.isenabled()
        gc.disable()
        try:
            result = esprima.toDict(root)
            del root
            self.assertIsNone(reference())
            self.assertEqual(result['custom'], {'ok': True})
        finally:
            if enabled:
                gc.enable()

    def test_visitor_reuse_after_continuation(self):
        visitor = ToDictVisitor()
        for _ in range(3):
            value = {'prefix': [1, 2], 'custom': Custom(lambda: {'ok': True})}
            self.assertEqual(visitor.visit(value), {'prefix': [1, 2], 'custom': {'ok': True}})
            self.assertEqual(visitor._visit_context, {})
            self.assertEqual(visitor._visit_count, 0)

    def test_inherited_array_iterator_remains_a_custom_protocol(self):
        calls = []
        class CustomList(list):
            __slots__ = ()
            def __iter__(self):
                calls.append('iterate')
                yield Custom(lambda: {'ok': True})
        original = Array.__bases__
        try:
            Array.__bases__ = (CustomList,)
            self.assertEqual(esprima.toDict(Array([1])), [{'ok': True}])
        finally:
            Array.__bases__ = original
        self.assertEqual(calls, ['iterate'])


if __name__ == '__main__':
    unittest.main()
