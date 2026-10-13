# Changelog

## 5.0.0 — pending publication

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
