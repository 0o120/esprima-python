# ECMAScript support and verification

The parser targets the dated ECMAScript 2026 grammar and current ESTree shapes.
It is a syntax and static-analysis tool, not a JavaScript runtime. The default
edition is 2026; `ecmaVersion` accepts 5 and 2015 through 2026. JSX is opt-in and
includes fragments and spread children. `esnext` remains a compatibility preset
for JSX and class fields, rather than a promise to implement draft proposals.

The verified grammar includes async generators/iteration, optional catch,
optional chains, nullish/logical assignment, BigInt and numeric separators,
modern regex syntax/flags, class fields/private names/static blocks, top-level
await, arbitrary module names, import attributes/options and hashbangs. Scope
validation checks bindings, parameters, exports, private environments, super,
new.target, strict rules, assignment targets and control-flow contexts.

The frozen CI corpus comprises 815 lexical/regex Test262 files, 4,152 selected
parse-negative cases and 283 positive grammar regressions, pinned to Test262
`2e0a56762801e275a9fdf96dc49d90ba0cddcf63`. It preserves licenses, feature
metadata, strict/module/raw modes, inventory and hashes. Original Esprima
sources remain intact: all 1,604 fixtures and two hardcoded tests run once.
The explicitly reviewed expectation migrations are documented separately.

A wider read-only audit accepted 19,683 core source files in 36,421
script/strict/module checks. Seven browser-only Annex B.3.9 cases remain
explicitly excluded: function calls as assignment/update/iteration targets are
rejected, matching the previous port and the pinned Acorn parser. The
[dated Annex B clause](https://tc39.es/ecma262/2026/multipage/additional-ecmascript-features-for-web-browsers.html#sec-web-compat-assignment-targets)
describes this optional browser behavior. Other documented sloppy Annex B
grammar, including HTML comments, string escapes and ordinary if-body function
declarations, is retained. Modules and strict code keep their required rules.

Independent Node/Acorn probes checked 51,762 regex patterns, 11,054 numeric
candidates and 25,000 malformed lexical sources. Four Node regex disagreements
were resolved against the dated specification's duplicate-name participation
rule. These checks establish substantial tested coverage, not certification as
a complete ECMAScript engine or a guarantee for every possible input.

Canonical positions use UTF-16 units. `positionEncoding='scalar'` is an explicit
legacy option. Native async aliases remain available; dictionaries use ESTree
keys. Regex values and BigInts serialize as null with descriptors. Overflowing
Number literals serialize as null plus `number='Infinity'` (or `-Infinity`/`NaN`
for supplied values); this JSON-safe interchange extension preserves the
distinction from actual null. NaN is not a JavaScript numeric literal and is
rejected by the generator's literal API. Required nullable AST fields survive.

Tolerant parsing retains syntax recovery diagnostics and avoids adding cascading
scope errors to an already invalid recovered tree. Fatal nesting exhaustion
raises a structured parser Error without modifying the process recursion limit;
32 nested functions are covered. Very deep input is bounded by the host Python
stack. Collection-only comments require `attachComment=True` for generation.

Resources, import defer, TypeScript, Flow and decorators are outside the core
scope. Future syntax must use a separately documented extension gate. JSON
serialization, transformation, native/mapping traversal, installed-package
checks, independent reparse and selected runtime comparisons are additional
cross-repository release gates.

The [grammar clause index](SPEC_COVERAGE.md) and its machine-readable manifest
map clauses 12–16, regex grammar and extension exclusions to checked-in tests
and exact fixture inventories. The [performance report](PERFORMANCE.md) records
latency and Python allocation measurements, including the parser budget exception.
