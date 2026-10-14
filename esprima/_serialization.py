"""Iterative serialization of ordinary data; custom protocols use the visitor."""

import math
from collections import deque

from .objects import Array, Object
from .schema import NULLABLE_FIELDS


class _UseVisitor(Exception):
    def __init__(self, continuation=None):
        self.continuation = continuation


_SCALARS = frozenset((str, int, float, bool, bytes, complex, type(None)))
_ARRAY_HOOKS = frozenset(('__iter__', '__getitem__', '__len__', '__getattribute__', '__class__'))
_OBJECT_DICTIONARY = vars(Object)['__dict__']


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
    return (dictionary is _OBJECT_DICTIONARY
            and methods.get('__getattribute__') is object.__getattribute__
            and methods.get('__eq__') is object.__eq__
            and methods.get('__hash__') is object.__hash__)


def _resume_list(output, entries):
    from . import visitor as protocol
    output.append((yield None))
    for _, item in entries:
        output.append((yield item))
    yield protocol.Visited(output)


def _resume_dict(visitor, source, entries, output, nullable, key):
    """Continue the suspended visit_dict protocol, including late map changes."""
    from . import visitor as protocol
    # The original protocol hashes mapped keys only after every value has
    # been visited. Keep that ordering if a custom hook changes the map.
    items = list(output.items())
    value = yield None
    key = protocol.unicode(key)
    items.append((visitor.map.get(key, key), value))
    for key, item in entries:
        if not key.startswith('_') and (item is not None or key in nullable or key == 'cooked'):
            if source.get('type') == 'Literal' and key == 'value' and 'regex' in source:
                value = None
            else:
                value = yield item
            key = protocol.unicode(key)
            items.append((visitor.map.get(key, key), value))
    items = dict(items)
    if items.get('type') == 'Literal' and ('regex' in items or items.get('raw') == 'null'):
        items['value'] = None
    numeric = source.get('value')
    if source.get('type') == 'Literal' and isinstance(numeric, float) and not math.isfinite(numeric):
        items['value'] = None
        items['number'] = 'NaN' if math.isnan(numeric) else ('Infinity' if numeric > 0 else '-Infinity')
    yield protocol.Visited(items)


def _continuation(visitor, frames, item):
    stack = deque()
    context = {}
    for frame in frames:
        output, entries, source, _, nullable, native, _, _, _, key = frame
        if native is not None:
            handler = visitor.visit_Object
            wrapper = handler(native)
            next(wrapper)  # Its ordinary dictionary was already read safely.
            context[native] = handler
            stack.append((wrapper, native))
        resume = (_resume_list(output, entries) if source is None else
                  _resume_dict(visitor, source, entries, output, nullable, key))
        next(resume)  # Suspend at the child already selected by the fast path.
        stack.append((resume, None))
    stack.append((item, None))
    return stack, context


def to_dict(value, visitor):
    """Convert pure data and resume the general visitor at custom behavior.

    There is no retained graph/type cache. Shared children are copied per
    occurrence, Object cycles retain the historical error mapping, and depth
    is limited by memory rather than Python's recursion limit.
    """
    classes = {}
    active = set()
    stack = []
    field_map = visitor.map
    cycle_seen = False

    def enter(value, parent=None, key=None):
        nonlocal cycle_seen
        cls = type(value)
        if type(cls) is not type:
            raise _UseVisitor
        if cls in _SCALARS:
            return value
        identity = id(value)
        object_identity = None
        native = None
        if cls is list or cls is Array:
            if cls is Array:
                bases = Array.__bases__
                if (len(bases) != 1 or bases[0] is not list
                        or _ARRAY_HOOKS.intersection(vars(Array))):
                    raise _UseVisitor
            if identity in active:
                cycle_seen = True
                raise _UseVisitor
            result = []
            active.add(identity)
            stack.append([result, enumerate(value), None, identity, None, None, parent, key, False, None])
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
                cycle_seen = True
                return {'error': 'Infinite recursion detected...'}
            object_identity = identity
            native = value
            value = value.__dict__
            if type(value) is not dict:
                raise _UseVisitor
        # Restrict checks to built-in strings before hash/equality operations.
        for field in value:
            if type(field) is not str:
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
            cycle_seen = True
            raise _UseVisitor
        result = {}
        active.add(identity)
        stack.append([result, iter(value.items()), value, identity,
                      NULLABLE_FIELDS.get(kind, ()), native, parent, key, kind == 'Literal', None])
        return result

    result = enter(value)
    while stack:
        frame = stack[-1]
        output, entries, source, identity, nullable, _, parent, parent_key, literal, _ = frame
        for key, item in entries:
            if source is not None:
                if key.startswith('_') or item is None and key not in nullable and key != 'cooked':
                    continue
                if literal and key == 'value' and 'regex' in source:
                    output[field_map.get(key, key)] = None
                    continue
            cls = type(item)
            if type(cls) is type and cls in _SCALARS:
                converted = item
            else:
                frame[9] = key
                depth = len(stack)
                try:
                    converted = enter(item, output, key)
                except _UseVisitor:
                    # Cyclic prefixes can affect the legacy recursion context;
                    # keep their historical complete fallback behavior.
                    if cycle_seen:
                        raise
                    raise _UseVisitor(_continuation(visitor, stack, item)) from None
                if len(stack) != depth:
                    break
            if source is None:
                output.append(converted)
            else:
                output[field_map.get(key, key)] = converted
        else:
            if literal:
                if 'regex' in output or output.get('raw') == 'null':
                    output['value'] = None
                number = source.get('value')
                if type(number) is float and not math.isfinite(number):
                    output['value'] = None
                    output['number'] = 'NaN' if math.isnan(number) else ('Infinity' if number > 0 else '-Infinity')
            active.remove(identity)
            stack.pop()
            if type(parent) is list:
                parent.append(output)
            elif parent is not None:
                parent[field_map.get(parent_key, parent_key)] = output
    return result
