# Esprima Python fork

A pure Python JavaScript parser and tokenizer targeting ECMAScript 2026 on
Python 3.11+. Modern expressions, classes, modules, Unicode and regex grammar
are supported with read-only scope and early-error validation. The development
release's tested coverage and deliberate limits are described in
[conformance notes](docs/CONFORMANCE.md).

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

```python
tree = esprima.parseModule('export const value = obj?.value ?? 123n;',
                          {'range': True, 'loc': True})
mapping = esprima.toDict(tree)
```

See [the AST compatibility contract](docs/AST_COMPATIBILITY.md) for the modern
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

The [performance report](docs/PERFORMANCE.md) records paired original/start/current
measurements. The latest pass reduces default ES2017 parsing time by 20–28%
relative to the preceding modern checkpoint and improves long comments, strings
and decimal BigInts substantially. General parsing remains 19–28% slower than
the original port on the paired fixtures, with scope checks enabled.
