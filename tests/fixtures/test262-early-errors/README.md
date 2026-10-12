# Frozen parse-negative grammar corpus

This is the complete selected **core-language parse-phase SyntaxError** set from
Test262 revision recorded in `manifest.json`. Original headers and source paths
are retained in `cases.json`; the upstream BSD license is included. No fixture
program is executed. Runtime and resolution negatives are excluded.

Modes honor `module`, `onlyStrict`, `noStrict` and raw source: modules use
parseModule, onlyStrict receives an unescaped directive (after a hashbang if
present), and other inputs retain their original non-strict/raw source. The
same explicit proposal omission policy as the positive grammar audit is pinned
in the manifest. Explicit resource management is excluded from the published
2026 acceptance gate.

`tests/test_early_errors_test262.py` verifies source/file hashes, fixture count
and unique paths, then requires `esprima.Error` for every case. Resource limits,
RecursionError and incidental Python exceptions never count as successful syntax
rejection. Regenerate deliberately with `python tools/freeze_early_errors.py
PATH_TO_TEST262`; the script verifies the pinned checkout revision.
