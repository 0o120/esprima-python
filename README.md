# Esprima Python fork

A pure Python JavaScript parser and tokenizer targeting ECMAScript 2026 on
Python 3.11+. Modern expressions, classes, modules, Unicode and regex grammar
are supported with read-only scope and early-error validation. The 5.0 release
series' tested coverage and deliberate limits are described in
[conformance notes](https://github.com/0o120/esprima-python/blob/master/docs/CONFORMANCE.md).

```sh
pip install esprima-fork
```

```python
import esprima

tree = esprima.parseScript("const answer = 42", {"range": True, "loc": True})
print(esprima.toDict(tree))
```

This distribution imports as `esprima`. Do not install the separate upstream
`esprima` distribution in the same environment: both own that import directory.
This fork is based on German M. Bravo's port and Ariya Hidayat's Esprima;
upstream author credits and BSD notices are retained.

## Upgrading from 4.x

Version 5.0 requires Python 3.11 or newer. Parsing defaults to ECMAScript 2026;
select `ecmaVersion=2017` when an older grammar is required. Source ranges and
columns now use JavaScript UTF-16 units; `positionEncoding='scalar'` restores
Python character offsets. Scope and early-error checks reject invalid programs
that older releases sometimes accepted. JSON output retains required null fields
and safe BigInt, regex and non-finite Number descriptors. Check consumers of the
old AST format against the
[migration contract](https://github.com/0o120/esprima-python/blob/master/docs/AST_COMPATIBILITY.md).
The import name remains `esprima`; `esprima.version` is the distribution version
string and `esprima.__version__` remains the historical `(major, minor, patch)`
tuple. See the [changelog](https://github.com/0o120/esprima-python/blob/master/CHANGELOG.md)
for the complete changes.

```python
tree = esprima.parseModule('export const value = obj?.value ?? 123n;',
                          {'range': True, 'loc': True})
mapping = esprima.toDict(tree)
```

See [the AST compatibility contract](https://github.com/0o120/esprima-python/blob/master/docs/AST_COMPATIBILITY.md) for the modern
node format and UTF-16 position units. Use `positionEncoding='scalar'` for legacy
Python-index behavior, `ecmaVersion=2017` for an older grammar, and `jsx=True`
for JSX fragments/elements/spread children. `comment=True` collects comments;
`attachComment=True` also attaches them for generation. Required null fields
and BigInt/regex/overflow-Number descriptors survive JSON serialization.

The CLI accepts UTF-8 files or stdin. JSON goes to stdout; parse diagnostics and
optional `--timing` go to stderr, and errors return a nonzero status.

```sh
esprima --module --range example.js
esprima --jsx --tokens example.jsx
```

## Opt-in syntax extensions

The dated ECMAScript 2026 grammar remains the default. The following extensions
require `ecmaVersion=2026` and their own explicit option; `esnext` does not enable
them implicitly:

| Parser option | Syntax and AST contract |
| --- | --- |
| `explicitResourceManagement=True` | `using` and `await using`, including loop declarations; `VariableDeclaration.kind` preserves the distinction |
| `decorators=True` | November 2023 decorators and auto-accessors; `Decorator.expression`, optional `decorators` arrays, and `AccessorProperty` |
| `deferredImportEvaluation=True` | Static namespace imports and dynamic `import.defer(...)`, retaining `phase="defer"` |
| `sourcePhaseImports=True` | Static source bindings and dynamic `import.source(...)`, retaining `phase="source"` |
| `exportDefaultFrom=True` | Experimental default reexports with a required `from` clause and canonical `ExportDefaultSpecifier.exported` |

```python
tree = esprima.parseModule('await using resource = acquire();',
                          {'explicitResourceManagement': True})
assert tree.toDict()['body'][0]['kind'] == 'await using'

tree = esprima.parseScript('@logged class C { accessor value; }',
                          {'decorators': True, 'range': True})
```

The CLI exposes `--explicit-resource-management`, `--decorators`,
`--deferred-import-evaluation`, `--source-phase-imports`, and
`--export-default-from`. Invalid contexts remain errors, including top-level
script resource declarations, decorated constructors, and bare `export value;`.

For generation, enable the corresponding generator `extensions` options
(`resourceManagement`, `decorators`, `deferredImportEvaluation`,
`sourcePhaseImports`, `exportDefaultFrom`). The coordinated walker traverses the
new shapes without modifying nodes. These tools preserve syntax; they do not
execute, transpile, or implement disposal/decorator/module-loading runtime APIs.

## Development

```sh
python -m unittest discover -v
python -m pytest
python -m build
```

The legacy corpus contains 1,604 JavaScript fixtures plus two API tests.
The discovery guard verifies that every fixture runs once. Install the `dev`
extra in a virtual environment for the additional checks.

Install the coordinated walker/utility/generator candidates to run all pipeline
tests. Reference parsers are development-only: `npm ci --prefix tools/reference`.
Frozen Test262 corpora run without a network or a JavaScript runtime; Node is
used for independent pipeline/source-map comparisons. Build wheels from source
archives and run `python tools/check_distribution.py` before release.
Maintainers can follow the
[release instructions](https://github.com/0o120/esprima-python/blob/master/RELEASING.md).

The [performance report](https://github.com/0o120/esprima-python/blob/master/docs/PERFORMANCE.md)
records paired measurements and their limits. The latest parser pass reduced
default parsing time for a separate large bundle by 15.7%, with default garbage
collection and full validation retained. Serialization has a smaller improvement;
see the report for exact baselines and consumer costs.
