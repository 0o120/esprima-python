# ECMAScript toolchain compatibility contract

The modernization targets the published ECMAScript 2026 grammar on Python 3.11+.
Syntax support is tracked by tests and the feature matrix; an AST node name by
itself is not a conformance claim. JSX is an explicit extension. Resource
management declarations and other proposals are outside the core edition gate.

The interchange format is ESTree. Native Python objects retain safe aliases
`isAsync` and `allowAwait`, while JSON uses `async` and `await`. Consumers accept
native nodes and mappings without copying away node identity. Class fields use
`PropertyDefinition`; chains, private names, static blocks, import attributes and
dynamic import options use their current ESTree shapes.

Required nullable fields are preserved. Missing optional metadata is distinct
from a required null. Regular expression literals have `value: null` and
`regex: {pattern, flags}`; parsing does not compile a Python regular expression.
BigInt literals have `value: null` and a decimal `bigint` string. Ordinary Number
literals follow JavaScript binary64 semantics rather than arbitrary Python ints.

Canonical `range`, `start`/`end`, location columns and delegate offsets use UTF-16
code units. The scanner retains Python scalar indices for slicing internally.
Searches accept `range` or `start`/`end` and reject missing positions clearly.
Modern identifier rules use pinned Unicode 17 data, not the host Python Unicode
database. Historical utility functions remain explicitly versioned.

Walking is semantic: noncomputed property keys and labels are not automatically
references. Custom visitor overlays do not modify the base visitor. Generation
does not modify caller nodes or option mappings and isolates state per call.

Each feature is checked in native and serialized form through parse, walk,
generate and independent reparse. Semantic regressions also compare trusted
JavaScript execution results. Formatting, raw spelling and comments may change;
strict directives, evaluation order, literal values and module metadata may not.
