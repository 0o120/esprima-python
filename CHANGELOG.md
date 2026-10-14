# Changelog

## Unreleased

- Use compact private identifier/punctuator tokens as read-only node-start
  markers in untouched facade parses. Reduce temporary marker allocations by
  90.7% and large-file parsing time by 4.0% in the recorded experiment; retain
  public AST/token layouts and customized parser/scanner allocation hooks.

- Resume serialization at custom values without redoing a completed acyclic
  prefix; reduce container-loop overhead while preserving dynamic visitor and
  field-map changes, exception order, recursion context and input lifetimes.
- Recognize inherited custom Array iteration before entering the fast path,
  avoiding duplicate iterator calls during fallback.

- Accelerate ordinary AST serialization with an iterative data converter and
  cheaper default scalar visits; preserve custom visitor/object fallbacks,
  complete metadata, nullable fields and deep-tree behavior.

- Add opt-in resource declarations, November 2023 decorators/auto-accessors,
  deferred/source import phases, and experimental default reexports, with
  explicit edition/grammar gates, read-only early-error validation and CLI flags.
- Preserve asynchronous disposal, module phases, nullable accessor values,
  decorator expressions and UTF-16 ranges through the coordinated toolchain.
- Reject accidental proposal syntax in the core export grammar, require reexport
  source clauses, and restore valid core `export default from;` expressions.
- Freeze 495 additional licensed Test262 import-phase sources and reject parser
  resource exhaustion as a substitute for an expected language syntax error.
- Freeze all 510 pinned resource/decorator Test262 sources with licensed,
  hash-verified offline syntax checks across their required execution goals.
- Record the 35th explicit failure-diagnostic migration without changing the
  original 1,604 fixture sources or snapshots.

## 5.0.0 — 2026-10-13

- Prepare stable distribution/runtime version metadata, PyPI documentation links,
  retained author and maintainer credits, and version-independent package checks.
  The import name remains `esprima`, and `__version__` remains a numeric tuple.

- Avoid native AST dictionary materialization during owned expression/scope
  validation and reuse proven BMP/UTF-16 identity positions. A separate large
  bundle parses in 30.818 seconds versus 36.539 seconds (15.7% less time), with
  default GC and all checks retained. Preserve direct Parser/Scanner hooks;
  see `docs/PERFORMANCE.md` for provenance and consumer-path limits.
- Accelerate identifier/digit runs, long comments and plain strings, decimal
  BigInt metadata, cover-grammar propagation and source-position conversion.
  Reduce validation dispatch/context/scope work for provably untouched parser
  trees and reuse bounded successful regex facts. Custom/standalone validation,
  diagnostics, edition checks and AST identity retain their complete behavior;
  see the current paired measurements in `docs/PERFORMANCE.md`.
- Require Python 3.11+ and fix the fork's wheel, entry point, README and version
  metadata. Retain `import esprima` and the historical version tuple.
- Restore every legacy fixture with unique discovery and explicit edition and
  schema/diagnostic migrations.
- Implement modern ECMAScript expressions, async iteration, class/private/static
  forms, module metadata, Unicode 17 lexing and ECMAScript regex validation.
- Add read-only early-error/scope validation and explicit edition gates.
- Preserve required nulls, JSON-safe literal descriptors, UTF-16 source positions,
  hashbangs and attached comments; fix Python CLI streams and error statuses.
- Repair JSX truncation, fragments/spread children and contextual grammar
  defects found by independent conformance checks.
- Add pinned Test262 corpora, reference tooling, coordinated CI and distribution
  checks. See the conformance and AST compatibility documents for migration and
  deliberately excluded browser/proposal behavior.
- Optimize ASCII scanning, punctuator dispatch, UTF-16 identity paths and static
  validation lookups/scope inventories and sparse supplementary-scalar position storage while retaining all correctness checks.
- Repair the initial module HTML-comment lexical goal; preserve reference bytes
  on Windows checkout and lock dev/build dependencies across platforms and Python floors.

## Upstream release history

The following entries preserve the historical Esprima/Esprima Python
release notes formerly stored in `ChangeLog`. They describe upstream
releases before this fork's 5.0 modernization.

### 4.0.1 — 2018-08-24

- Fix async/await, those are now reserved keywords in Python 3.7

### 4.0.0 — 2017-06-10

- Support ES2017 async function and await expression (issue 1079)
- Support ES2017 trailing commas in function parameters (issue 1550)
- Explicitly distinguish parsing a module vs a script (issue 1576)
- Fix JSX non-empty container (issue 1786)
- Allow JSX element in a yield expression (issue 1765)
- Allow `in` expression in a concise body with a function body (issue 1793)
- Setter function argument must not be a rest parameter (issue 1693)
- Limit strict mode directive to functions with a simple parameter list (issue 1677)
- Prohibit any escape sequence in a reserved word (issue 1612)
- Only permit hex digits in hex escape sequence (issue 1619)
- Prohibit labelled class/generator/function declaration (issue 1484)
- Limit function declaration as if statement clause only in non-strict mode (issue 1657)
- Tolerate missing ) in a with and do-while statement (issue 1481)

### 3.1.3 — 2016-12-22

- Support binding patterns as rest element (issue 1681)
- Account for different possible arguments of a yield expression (issue 1469)

### 3.1.2 — 2016-11-24

- Ensure that import specifier is more restrictive (issue 1615)
- Fix duplicated JSX tokens (issue 1613)
- Scan template literal in a JSX expression container (issue 1622)
- Improve XHTML entity scanning in JSX (issue 1629)

### 3.1.1 — 2016-10-31

- Fix assignment expression problem in an export declaration (issue 1596)
- Fix incorrect tokenization of hex digits (issue 1605)

### 3.1.0 — 2016-10-09

- Do not implicitly collect comments when comment attachment is specified (issue 1553)
- Fix incorrect handling of duplicated proto shorthand fields (issue 1485)
- Prohibit initialization in some variants of for statements (issue 1309, 1561)
- Fix incorrect parsing of export specifier (issue 1578)
- Fix ESTree compatibility for assignment pattern (issue 1575)

### 3.0.0 — 2016-09-03

- Support ES2016 exponentiation expression (issue 1490)
- Support JSX syntax (issue 1467)
- Use the latest Unicode 8.0 (issue 1475)
- Add the support for syntax node delegate (issue 1435)
- Fix ESTree compatibility on meta property (issue 1338)
- Fix ESTree compatibility on default parameter value (issue 1081)
- Fix ESTree compatibility on try handler (issue 1030)

### 2.7.3 — 2016-08-23

- Fix tokenizer confusion with a comment (issue 1493, 1516)

### 2.7.2 — 2016-02-02

- Fix out-of-bound error location in an invalid string literal (issue 1457)
- Fix shorthand object destructuring defaults in variable declarations (issue 1459)

### 2.7.1 — 2015-12-10

- Do not allow trailing comma in a variable declaration (issue 1360)
- Fix assignment to `let` in non-strict mode (issue 1376)
- Fix missing delegate property in YieldExpression (issue 1407)

### 2.7.0 — 2015-10-22

- Fix the handling of semicolon in a break statement (issue 1044)
- Run the test suite with major web browsers (issue 1259, 1317)
- Allow `let` as an identifier in non-strict mode (issue 1289)
- Attach orphaned comments as `innerComments` (issue 1328)
- Add the support for token delegator (issue 1332)

### 2.6.0 — 2015-09-01

- Properly allow or prohibit `let` in a binding identifier/pattern (issue 1048, 1098)
- Add sourceType field for Program node (issue 1159)
- Ensure that strict mode reserved word binding throw an error (issue 1171)
- Run the test suite with Node.js and IE 11 on Windows (issue 1294)
- Allow binding pattern with no initializer in a for statement (issue 1301)

### 2.5.0 — 2015-07-31

- Run the test suite in a browser environment (issue 1004)
- Ensure a comma between imported default binding and named imports (issue 1046)
- Distinguish `yield` as a keyword vs an identifier (issue 1186)
- Support ES6 meta property `new.target` (issue 1203)
- Fix the syntax node for yield with expression (issue 1223)
- Fix the check of duplicated proto in property names (issue 1225)
- Fix ES6 Unicode escape in identifier name (issue 1229)
- Support ES6 IdentifierStart and IdentifierPart (issue 1232)
- Treat await as a reserved word when parsing as a module (issue 1234)
- Recognize identifier characters from Unicode SMP (issue 1244)
- Ensure that export and import can be followed by a comma (issue 1250)
- Fix yield operator precedence (issue 1262)

### 2.4.1 — 2015-07-01

- Fix some cases of comment attachment (issue 1071, 1175)
- Fix the handling of destructuring in function arguments (issue 1193)
- Fix invalid ranges in assignment expression (issue 1201)

### 2.4.0 — 2015-06-26

- Support ES6 for-of iteration (issue 1047)
- Support ES6 spread arguments (issue 1169)
- Minimize npm payload (issue 1191)

### 2.3.0 — 2015-06-16

- Support ES6 generator (issue 1033)
- Improve parsing of regular expressions with `u` flag (issue 1179)

### 2.2.0 — 2015-04-17

- Support ES6 import and export declarations (issue 1000)
- Fix line terminator before arrow not recognized as error (issue 1009)
- Support ES6 destructuring (issue 1045)
- Support ES6 template literal (issue 1074)
- Fix the handling of invalid/incomplete string escape sequences (issue 1106)
- Fix ES3 static member access restriction (issue 1120)
- Support for `super` in ES6 class (issue 1147)

### 2.1.0 — 2015-03-09

- Support ES6 class (issue 1001)
- Support ES6 rest parameter (issue 1011)
- Expand the location of property getter, setter, and methods (issue 1029)
- Enable TryStatement transition to a single handler (issue 1031)
- Support ES6 computed property name (issue 1037)
- Tolerate unclosed block comment (issue 1041)
- Support ES6 lexical declaration (issue 1065)

### 2.0.0 — 2015-02-06

- Support ES6 arrow function (issue 517)
- Support ES6 Unicode code point escape (issue 521)
- Improve the speed and accuracy of comment attachment (issue 522)
- Support ES6 default parameter (issue 519)
- Support ES6 regular expression flags (issue 557)
- Fix scanning of implicit octal literals (issue 565)
- Fix the handling of automatic semicolon insertion (issue 574)
- Support ES6 method definition (issue 620)
- Support ES6 octal integer literal (issue 621)
- Support ES6 binary integer literal (issue 622)
- Support ES6 object literal property value shorthand (issue 624)

### 1.2.5 — 2015-03-03

- Fix scanning of implicit octal literals (issue 565)

### 1.2.4 — 2015-02-05

- Fix parsing of LeftHandSideExpression in ForInStatement (issue 560)
- Fix the handling of automatic semicolon insertion (issue 574)

### 1.2.3 — 2015-01-18

- Fix division by this (issue 616)

### 1.2.2 — 2014-05-18

- Fix duplicated tokens when collecting comments (issue 537)

### 1.2.1 — 2014-05-04

- Ensure that Program node may still have leading comments (issue 536)

### 1.2.0 — 2014-04-29

- Fix semicolon handling for expression statement (issue 462, 533)
- Disallow escaped characters in regular expression flags (issue 503)
- Performance improvement for location tracking (issue 520)
- Improve the speed of comment attachment (issue 522)

### 1.1.1 — 2014-03-26

- Fix token handling of forward slash after an array literal (issue 512)

### 1.1.0 — 2014-03-23

- Optionally attach comments to the owning syntax nodes (issue 197)
- Simplify binary parsing with stack-based shift reduce (issue 352)
- Always include the raw source of literals (issue 376)
- Add optional input source information (issue 386)
- Tokenizer API for pure lexical scanning (issue 398)
- Improve the web site and its online demos (issue 337, 400, 404)
- Performance improvement for location tracking (issue 417, 424)
- Support HTML comment syntax (issue 451)
- Drop support for legacy browsers (issue 474)

### 1.0.4 — 2013-08-27

- Minimize the payload for packages (issue 362)
- Fix missing cases on an empty switch statement (issue 436)
- Support escaped ] in regexp literal character classes (issue 442)
- Tolerate invalid left-hand side expression (issue 130)

### 1.0.3 — 2013-05-17

- Variable declaration needs at least one declarator (issue 391)
- Fix benchmark's variance unit conversion (issue 397)
- IE < 9: \v should be treated as vertical tab (issue 405)
- Unary expressions should always have prefix: true (issue 418)
- Catch clause should only accept an identifier (issue 423)
- Tolerate setters without parameter (issue 426)

### 1.0.2 — 2012-11-02

Improvement:
- Fix esvalidate JUnit output upon a syntax error (issue 374)

### 1.0.1 — 2012-10-28

Improvements:
- esvalidate understands shebang in a Unix shell script (issue 361)
- esvalidate treats fatal parsing failure as an error (issue 361)
- Reduce Node.js package via .npmignore (issue 362)

### 1.0.0 — 2012-10-22

Initial release.
