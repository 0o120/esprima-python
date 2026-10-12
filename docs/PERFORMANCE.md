# Performance evidence

Measurements use CPython 3.12.0 on Windows x64, exact source imports and identical trusted ES2017 scripts. Source programs are parsed/tokenized, never executed. Timings exclude serialization and fixture preparation. Allocation measurements use `tracemalloc` separately from timing; they describe Python allocations, not total process RSS or native allocations. Cold import results can include warm filesystem caches.

The plan used an initial roughly 10% regression budget and required investigating exceptions. **Parsing exceeds that budget**: the new parser is 63–73% slower than the original port on these two fixtures after optimization. The added static/early-error pass, correct UTF-16 metadata and broader grammar are material costs. These measurements do not establish that every workload has the same ratio. The budget exception remains explicit for release review; no correctness check is disabled to improve the result.

| Fixture | Ranges | Old parser ms | New parser ms | Change |
| --- | --- | ---: | ---: | ---: |
| small-es2017.js (472 bytes) | False | 0.901 | 1.557 | +72.8% |
| small-es2017.js (472 bytes) | True | 0.932 | 1.600 | +71.7% |
| medium-es2017.js (34412 bytes) | False | 61.289 | 100.193 | +63.5% |
| medium-es2017.js (34412 bytes) | True | 64.981 | 111.097 | +71.0% |

Cold import in the paired parser measurement increased 8.7%. An independent tokenizer run measured a 10.7% increase. Small absolute differences and filesystem/process variability warrant repeated measurements on deployment hosts.

Compared with the first modern implementation, final parsing is about 40–46% faster on these fixtures. ASCII identifier classification and scanning avoid unnecessary Unicode searches; punctuator lookup dispatches by its initial character; ASCII UTF-16 conversion uses identity with boundary clamping. Static validation uses specialized node access and per-pass scope inventory caches while preserving custom mappings, subclass behavior, diagnostic identity and cache lifetime.

Standalone validation on identical preparsed native ASTs improved 44% for the small script and 53% for the medium script. The original profile attributed about 40% of parse time to validation; it also identified scanning and repeated position conversion as substantial costs.

Tokenizer latency rose about 5–6% without ranges and 11–16% with ranges. Tokenizer peak Python allocations were essentially unchanged (0.99–1.01x). Parser peak allocations were 1.48–1.68x for the small source and 1.50–2.22x for the medium source, depending on range tracking. Modern parsing retains diagnostic metadata and validates scopes. Fresh-import peak allocation fell about 40%, and retained import allocation about 77%, with compact Unicode tables replacing the old enormous character-set construction.

Reproducible raw measurements (fixture hashes, revisions, options and individual samples):

- [Final parser latency](benchmarks/parser.json)
- [First modern implementation latency](benchmarks/parser-before-optimization.json)
- [Standalone validator comparison](benchmarks/validator.json)
- [Tokenizer, startup and allocation measurements](benchmarks/tokenizer-memory.json)

The workspace implementation evidence also includes scripts and extracted baseline revisions. Treat these results as a measured release-review exception and a future profiling baseline, rather than a portable hardware performance guarantee.
