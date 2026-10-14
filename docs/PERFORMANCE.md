# Performance evidence

## Post-gap performance audit — October 2026

An iterative serializer converts ordinary native ASTs and built-in containers
without allocating a visitor generator and wrapper for every value. It retains
nullable fields, async/await aliases, regex/nonfinite metadata, field order,
shared-child copying and Object cycle diagnostics. Custom keys, descriptors,
objects and modified/subclassed visitors retain the general visitor protocol;
a late fallback can add work. No cross-call AST cache is retained.

| Operation | Before | After | Less time |
| --- | ---: | ---: | ---: |
| Medium `toDict`, milliseconds | 76.225 | 26.875 | 64.7% |
| Metadata `toDict`, milliseconds | 743.087 | 218.966 | 70.5% |
| YouTube first `toDict`, seconds | 41.755 | 18.479 | 55.7% |
| YouTube parse + `toDict`, seconds | 72.934 | 49.375 | 32.3% |

The native tree is retained in the large-file pipeline. Component trees have
already been converted once; the YouTube conversion is the first conversion.
Parser/scanner grammar code is unchanged, and standalone parsing remains about
31 seconds on the 10.9 MB file. Its full public and semantic AST digests match
the baseline. Generated JavaScript is byte-identical and reparses correctly.

All 1,837 parser CI methods pass on CPython 3.11-3.15. The coordinated audit
also passes 9,828 generation checks and 4,914 independent Babel round trips.
Focused regressions cover deep mappings, shared nodes, custom keys/metaclasses,
descriptors, visitors, aliases and nonfinite values.

Measurements use CPython 3.12.0 on Windows, default garbage collection and
sequential alternating before/after processes. Large-file figures are medians
of three fresh processes per version. Component figures use three fresh
processes per version, seven warmed calls per process and the median of process
medians. All raw samples, including outliers and small regressions, are retained.
Imports, input reading and correctness comparisons are outside timing windows.

Reproduction scripts, exact Python source hashes, profiles, logs, environments,
and distributions are outside the repositories in
`C:/Users/Ryzen/Benchmarks/toolchain-performance-2026-10-13/`.
The report covers first-call/allocation costs, compatibility fallbacks and
Python 3.11/3.15 boundary timings as well as the main comparisons. These are
workload-specific results, not a universal speed guarantee.

## Earlier performance work

The third October 2026 pass reduces a separate 10.9 MB production bundle's default
parse median from 36.539 to 30.818 seconds: 15.7% less time, or 1.186x throughput.
It avoids unnecessary native AST dictionary allocation during private validation
and reuses lazily proven BMP/UTF-16 identity positions. Syntax, scope, edition
and regex checks remain enabled, with default garbage collection.

## Earlier large-file comparison

CPython 3.12.0 on Windows x64; three fresh isolated processes per version,
run sequentially. The baseline is `6652012`; the measured current Python sources
match `865188a`. Imports, source reading and semantic hashing are outside the
public `parseScript` timer. Earlier experimental trials remain separate.

| Measurement | Baseline | Current | Less time |
| --- | ---: | ---: | ---: |
| Default parse median | 36.539 s | 30.818 s | 15.7% |
| Static validation median | 7.810 s | 3.874 s | 50.4% |
| GC time median, within parse | 7.517 s | 5.304 s | 29.4% |
| Individual parse trials | 36.492 / 36.539 / 38.311 s | 31.426 / 30.818 / 30.492 s | |

GC time is already included in parsing and validation; do not add these rows.
The historical original-port median is 29.840 seconds on this host/interpreter,
so the latest median is about 3.3% slower. The earlier old-port measurement uses
two trials; that parser predates the separate modern static checks.

The complete semantic AST matches the independently established Acorn/Babel
digest. Both Python floors pass all 1,759 parser methods with warnings treated
as errors and zero skips. Each native-reader group also passes 36,690 paired
checks covering 63,833 ordered diagnostics and original node identities.
Direct/custom parsers retain their overridable scanner position hooks; the new
BMP shortcut is limited to facade-owned instances. Public standalone validation,
custom mappings/delegates, subclasses, JSX and historical editions retain their
complete paths. AST dictionaries remain available when callers request them.

Isolated validation-only allocation studies reduce peak process private bytes
from approximately 786 MB to 631 MB. The second scope/binding reader group alone
consistently reduces validation time by 11.5% and peak private bytes by about
46 MB, but its whole-parse timing gain is small and noisy. Some dictionary work
is deferred to consumers, so parse-only gains must not be applied unchanged to
serialization or a full toolchain. The workspace report measures those paths
separately. Private bytes are a process-memory metric, not `tracemalloc` peaks.

In a separate fresh public `parseScript(source).toDict()` pair, total time falls
from 76.981 to 75.191 seconds (2.3%). Parsing falls from 36.336 to 31.037 seconds,
but serialization rises from 40.317 to 43.779 seconds (8.6%); temporary native
tree release is included. Both full mapping digests match the reference.
Parse-stage peak private bytes fall from 786.8 to 630.5 decimal MB (20%), while
full consumer peak private bytes stay approximately 1,252 MB. This is one pair,
not a multi-trial consumer median.

All 15 general fixture AST/metadata comparisons match the frozen baseline.
Thirteen timing rows improve; JSX is 0.41% slower (0.079 ms) and the decimal
BigInt fixture is 9.17% slower (0.046 ms). These results do not establish a
universal speedup.

The supplied source stays in the workspace root, outside every repository.
Supplemental tests, runners, snapshots and raw results also stay outside the
repositories, under `implementation-artifacts/performance-youtube-round3`.
That artifact directory contains
`final-latency-summary.json`, per-trial source hashes and the compatibility and
allocation evidence. No production-bundle fixture is part of this distribution.

## Earlier paired measurements

The preceding October 2026 follow-up reduces default parsing time by 20–28% on the paired
ES2017 scripts relative to the preceding modern checkpoint. Comment/string-heavy
parsing is 2.5x as fast as the original port; the 30,000-digit decimal BigInt case
is about 178x as fast as the preceding modern version. Scope validation, edition
gates, regex grammar and UTF-16 metadata remain enabled.

At that checkpoint general parsing exceeded the original roughly 10% regression budget:
default parsing is 19–28% slower than the original on the two ES2017 fixtures.
The original parser does less static validation. This release-review exception
does not imply every workload has the same ratio.

CPython 3.12.0 on Windows x64; exact source imports in isolated processes.
`old` means original master `e3b8965`; `start` means modern checkpoint `618be2b`;
the table's current sources match commit `78a3bfc`. Timing excludes input
reading, AST serialization and imports. Four warmups precede nine timing
samples; GC is enabled, with collection outside each sample. Trusted programs
are never executed. All 15 start/current AST and metadata comparisons match.

| Source/options | Old ms | Start ms | Current ms | Less time than start |
| --- | ---: | ---: | ---: | ---: |
| Small ES2017 | 0.941 | 1.531 | 1.204 | 21.3% |
| Small ES2017, metadata | 1.632 | 2.576 | 2.068 | 19.7% |
| Medium ES2017 | 63.708 | 103.233 | 75.480 | 26.9% |
| Medium ES2017, metadata | 110.819 | 174.560 | 146.123 | 16.3% |
| Minified functions | 15.331 | 25.128 | 18.832 | 25.1% |
| Comments/plain strings | 15.478 | 18.483 | 6.162 | 66.7% |
| Comments/plain strings, metadata | 20.342 | 25.340 | 12.861 | 49.2% |
| Arithmetic/arrays | 33.380 | 49.197 | 35.339 | 28.2% |
| Numbers | 10.790* | 16.996 | 11.236 | 33.9% |
| Modern classes/modules | unsupported | 28.021 | 21.760 | 22.3% |
| Repeated modern regexes | unsupported | 13.253 | 6.425 | 51.5% |
| Decimal BigInt, 30,000 digits | unsupported | 91.756 | 0.517 | 99.4% |
| Literal Unicode | 5.665 | 9.345 | 7.444 | 20.3% |
| Literal Unicode, metadata | 11.255* | 20.422 | 17.455 | 14.5% |
| JSX | unsupported | 22.300 | 19.545 | 12.4% |

Metadata means `range`, `loc`, `tokens` and `comment` together, rather than just
ranges. *The original number case produces wrong binary64 values, and its
Unicode metadata uses scalar positions rather than required UTF-16 units.
Those old timings do not represent equal correctness. Warm repeated-regex
results benefit from the bounded cache. A separate fresh-process first parse,
including deferred first-parse imports, takes 17.3 ms versus 90.2 ms at start.

Tokenizer time falls 8–12% on the small fixture and 8–10% on the medium fixture
relative to start. Against the original, the medium tokenizer is 5.4% faster
without ranges and within 1.1% with ranges. The comment/string case is about
4x as fast as the original. Literal Unicode with ranges remains 8.6% slower
than the original, which reports different position units.

Source-only cold import is 89.0 ms versus 85.5 ms at start and 79.4 ms originally.
These are fresh processes with an empty bytecode-cache prefix; filesystem caches
can be warm. A warm interpreter's import is a different workload.

## Changes and retained contracts

ASCII identifier/digit runs and long comment/plain-string spans use compiled
C-backed searches with complete Unicode, escape, separator, line-terminator and
error fallbacks. Decimal BigInt metadata avoids an integer/decimal roundtrip.
Cover-grammar identity propagation, early member-loop exits, compact internal
markers and fewer position conversion calls reduce repeated Python work.

Validation uses cheaper immutable contexts and exact native/dict readers.
A private route for untouched current-edition parser trees dispatches known
expression children directly. A source proof can omit recursive `var` inventory
when exact builtin source text contains no `var`; direct function bindings and
all lexical conflicts remain checked. Custom delegates, parser subclasses,
JSX, historical editions and standalone validation retain the complete path.
Validation never stores results on or mutates the caller's AST.

Successful regex facts use an LRU of at most 128 exact immutable inputs, with
pattern/flag length limits. Failures are not cached; returned feature mappings
are fresh, and edition keys remain distinct. Unicode/scalar conversion,
diagnostic ordering and diagnostic node identity are preserved.

Both Python floors pass 1,759 unittest methods, including all 1,606 original
fixture/API methods and frozen lexical, parse-negative and grammar corpora.
An additional 36,690 paired validation checks preserve 63,833 diagnostics, and
1,200 scanner/AST/token/comment/error/location comparisons match start exactly.

## Allocation and remaining costs

Separately instrumented single-operation Python peak allocation is 2,221,766
bytes for the medium parse versus 2,231,429 at start and 1,005,622 originally.
The new AST and diagnostic metadata remain a substantial cost. Comment/string
peak falls 4.4%; the huge decimal BigInt peak falls 68.3%, from 312,672 to 99,074
bytes. These are `tracemalloc` results, not process RSS or native allocations.

The earlier sparse UTF-16 index continues to avoid a full source-length prefix
array. Its original Unicode experiment reduced peak allocation 21–37% relative
to the preceding implementation, with identical positions.

## Reproducible evidence and history

Published benchmark JSON uses `<workspace>` and `<python>` labels for local
filesystem prefixes; numerical results, file hashes and revisions are
unchanged. The Python version and platform remain recorded explicitly.

- [Current 15-case parser samples and source hashes](benchmarks/round2-parser.json)
- [Current tokens, cold imports and first-parse samples](benchmarks/round2-secondary.json)
- [Previous modern checkpoint](benchmarks/parser.json)
- [First modern implementation](benchmarks/parser-before-optimization.json)
- [Previous validator comparison](benchmarks/validator.json)
- [Previous tokenizer/startup/allocation checkpoint](benchmarks/tokenizer-memory.json)
- [Sparse UTF-16 experiment](benchmarks/sparse-utf16.json)

The workspace `implementation-artifacts/performance-round2/parser` directory
contains runners, trusted input files, exact starting source snapshots and
semantic comparison evidence. Measured file hashes were stable during timing
and verified against the recorded committed revision. Previous samples are
preserved: the former 57–72% default parser regression describes that earlier
checkpoint. Measure deployment workloads before treating these host-specific
medians as a performance guarantee.
