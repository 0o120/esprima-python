# Changelog

## 5.0.0 development

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
