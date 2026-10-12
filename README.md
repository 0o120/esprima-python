# Esprima Python fork

A pure Python JavaScript parser and tokenizer. The modernization branch targets
ECMAScript 2026 on Python 3.11+. New syntax and conformance work are tracked by
regression tests; the development version is not a completed conformance claim.

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

See [the AST compatibility contract](docs/AST_COMPATIBILITY.md) for the modern
node format, source-position units and extension policy. JSX is opt-in.

## Development

```sh
python -m unittest discover -v
python -m pytest
python -m build
```

The legacy corpus contains 1,604 JavaScript fixtures plus two API tests.
The discovery guard verifies that every fixture runs once. Install the `dev`
extra in a virtual environment for the additional checks.
