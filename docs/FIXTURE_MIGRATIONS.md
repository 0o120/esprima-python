# Legacy fixture migrations

The 1,604 original fixture sources and snapshots remain intact. The test harness
now assigns every source a unique relative-path test ID and checks the inventory.
ES6 and ES2017 fixture groups explicitly use their edition, so a newer default
cannot turn an older-edition negative into an unnoticed passing case.

`test/fixture-migrations.json` lists thirty-three intentional expectation changes,
each with a reason, a replacement snapshot and independent Acorn 8.19.0 syntax
acceptance. These cover current dynamic-import AST/options, Annex B string
escapes, the corrected computed-method flag and improved malformed-template,
private-token and unclosed-JSX diagnostics. Ten additional cases restore missing
early-error checks for undeclared local module exports and async function
declarations used directly as if-statement bodies. Both successful and failed parses
are asserted; the harness does not skip any source.

Eight later context repairs correctly accept ordinary nested await IdentifierName
uses and reject generator parameter initializers and escaped reserved words with
precise grammar diagnostics. These changes are independently syntax-checked too.
The final binding diagnostic rejects a reserved generator parameter at its own
token instead of the later closing brace.

`esprima.schema.migrate_legacy_fixture` performs only documented schema changes:
required nullable fields, false optional/await flags, empty module attributes,
current class-field nodes, old import-call representation, JSON-safe regex
values and specification-required template raw line-ending normalization.
Semantic operators, values, keys, names and other fields remain compared.

The formerly expected-failing Unicode-regex fixture now passes normally. The
fixture inventory guard and migration manifest make future changes reviewable.
