"""Iterative serialization of ordinary data; custom protocols use the visitor."""

import math
from types import GetSetDescriptorType

from .objects import Array, Object
from .schema import NULLABLE_FIELDS


class _UseVisitor(Exception):
    pass


_SCALARS = frozenset((str, int, float, bool, bytes, complex, type(None)))
_ARRAY_HOOKS = frozenset(('__iter__', '__getitem__', '__len__', '__getattribute__', '__class__'))


def _plain_object(cls):
    # No descriptors, proxies, equality hooks, or custom dictionaries may run
    # before a fallback: replaying those hooks could change caller behavior.
    if type(cls) is not type or not issubclass(cls, Object):
        return False
    dictionary = None
    methods = {}
    for base in cls.__mro__:
        fields = vars(base)
        if base is not object and '__class__' in fields:
            return False
        if '__bool__' in fields or '__len__' in fields:
            return False
        if dictionary is None and '__dict__' in fields:
            dictionary = fields['__dict__']
        for name in ('__getattribute__', '__eq__', '__hash__'):
            if name not in methods and name in fields:
                methods[name] = fields[name]
    return (type(dictionary) is GetSetDescriptorType
            and methods.get('__getattribute__') is object.__getattribute__
            and methods.get('__eq__') is object.__eq__
            and methods.get('__hash__') is object.__hash__)


def to_dict(value, visitor):
    """Convert a pure graph, or request the original visitor without side effects.

    There is no retained graph/type cache. Shared children are copied per
    occurrence, Object cycles retain the historical error mapping, and depth
    is limited by memory rather than Python's recursion limit.
    """
    classes = {}
    active = set()
    stack = []
    field_map = visitor.map

    def enter(value):
        cls = type(value)
        if type(cls) is not type:
            raise _UseVisitor
        if cls in _SCALARS:
            return value
        identity = id(value)
        object_identity = None
        if cls is list or cls is Array:
            if cls is Array and _ARRAY_HOOKS.intersection(vars(Array)):
                raise _UseVisitor
            if identity in active:
                raise _UseVisitor
            result = []
            active.add(identity)
            stack.append((result, enumerate(value), None, identity, None))
            return result
        if cls is not dict:
            plain = classes.get(cls)
            if plain is None:
                plain = (_plain_object(cls) and
                         getattr(visitor, 'visit_' + cls.__name__, visitor.visit_Object)
                         == visitor.visit_Object)
                classes[cls] = plain
            if not plain:
                raise _UseVisitor
            if identity in active:
                return {'error': 'Infinite recursion detected...'}
            object_identity = identity
            value = value.__dict__
            if type(value) is not dict:
                raise _UseVisitor
        # Restrict checks to built-in strings before hash/equality operations.
        if any(type(key) is not str for key in value):
            raise _UseVisitor
        kind = value.get('type')
        if kind is not None and type(kind) is not str:
            raise _UseVisitor
        if kind == 'Literal':
            raw_cls, value_cls = type(value.get('raw')), type(value.get('value'))
            if (type(raw_cls) is not type or type(value_cls) is not type
                    or raw_cls not in _SCALARS or value_cls not in _SCALARS):
                raise _UseVisitor
        identity = object_identity if object_identity is not None else id(value)
        if identity in active:
            raise _UseVisitor
        result = {}
        active.add(identity)
        stack.append((result, iter(value.items()), value, identity, NULLABLE_FIELDS.get(kind, ())))
        return result

    result = enter(value)
    while stack:
        output, entries, source, identity, nullable = stack[-1]
        try:
            key, item = next(entries)
        except StopIteration:
            if source is not None and source.get('type') == 'Literal':
                if 'regex' in output or output.get('raw') == 'null':
                    output['value'] = None
                number = source.get('value')
                if type(number) is float and not math.isfinite(number):
                    output['value'] = None
                    output['number'] = 'NaN' if math.isnan(number) else ('Infinity' if number > 0 else '-Infinity')
            active.remove(identity)
            stack.pop()
            continue
        if source is None:
            cls = type(item)
            output.append(item if type(cls) is type and cls in _SCALARS else enter(item))
        elif not key.startswith('_') and (item is not None or key in nullable or key == 'cooked'):
            if source.get('type') == 'Literal' and key == 'value' and 'regex' in source:
                converted = None
            else:
                cls = type(item)
                converted = item if type(cls) is type and cls in _SCALARS else enter(item)
            output[field_map.get(key, key)] = converted
    return result
