# DEVLOG

## 2026-10-23 - method bounds with annotated returns (job-perf3b-10240813)

The earlier method-field analysis did not fire on the real accessors: the AIL front end writes
`-> int` as the bare name `__ail_checked_int__`, and `inline_candidate` walked the `FunctionDef`
including its return and argument annotations, so that load made every annotated zero-argument
method look impure and `remaining()` was never analysed in place. Annotations are not runtime body
expressions; `rangecheck.py` now collects the id of every annotation node and skips those nodes in
the candidate walk. Nothing else changes: a method with an assignment, loop, try or non-builtin
call is still rejected, and a field store, unknown call or alias still forgets its facts.

`python3 bench/compare.py --app binary_cursor_records`, median of nine windows on this runner:

| app | ms ail/base/c/rust | ail/base | ail/c |
| --- | --- | --- | --- |
| binary_cursor_records | 40.8/47.2/9.8/9.5 | 0.866 [0.863, 0.871] faster | 4.145 [4.119, 4.170] slower |

Before (HEAD 4ffe276) the AIL/C ratio was `4.728 [4.701, 4.824] slower`; the ranges do not overlap
(13.4% less AIL time, above the 3% keep threshold). Result:
`bench/results/2026-10-23-12f2492.json`. The new test checks that generated
`Cursor__read_u8`/`read_u32_le` contain no `ail_bytes_get`, while the unguarded method keeps its
check.

Probes (`bash ~/tools/cmp.sh /tmp/probes/<name>.py $PWD`, CPython and both compiler paths agree):
`cursor_fields.py` and `bcursor_fields.py` (annotated `remaining`/`read_*` analysed in place,
u8/u16/u32 widths, empty, exact short and long boundaries, negative position, aliasing, values
through an argument, a list item, an attribute and a dict value), `method_side_effects.py`
(annotated methods with a store, a loop and a try are not inlined; out-of-range reads still raise),
`range_guards.py` (plain guarded reads on bytes/list plus unguarded bytes indexing). Tests:
`test_ail_range_checks.py`, `test_ail_binary_cursor_cli.py`, `test_ail_safetynet.py`,
`test_ail_files.py`, `test_ail_corpus_findings3.py` all pass.

## 2026-10-23 - range proofs through struct fields and safe method inlining (job-perf3b-10240127)

`binary_cursor_records` was 4.99x slower than C because every `read_*` method rechecked the same
cursor invariants: `remaining()` validated `position`, each byte read paid `ail_bytes_get`'s bounds
check, and the index arithmetic paid `ck_add`. The value-range analysis only reasoned about plain
locals, so it could not connect a guard on a method result to the receiver's fields.

`rangecheck.py` now tracks fields of a single unaliased object parameter (`#fld:o.f`, plus
`#len:#fld:o.f` for bytes/list fields), and records the identity of a subtraction between two exact
symbols. A guard on the difference (`available < 4`) therefore refines its operands
(`position <= len - 4`). Zero-argument methods whose bodies are only guards and a return, with no
assignment, loop, try or non-builtin call, are analysed in place against the caller's field facts,
so `remaining()`'s guard proves `position <= len` inside each `read_*`; `prove_le` now follows a
chain such as `start -> position -> len` that was previously stopped at an already-seen symbol.
Field facts are forgotten on a field store, an unknown method call, an unanalysed construct, or a
field passed to other code, and a function with any parameter besides the receiver is not tracked,
so an aliased argument cannot leave stale facts. `pyfunc.py` wires the class field/method lookups
into `rangecheck.Info` and marks bytes-field subscripts for the same resolver.

`python3 bench/compare.py --app binary_cursor_records`, median of nine windows on this runner:

| app | ms ail/base/c/rust | ail/base | ail/c |
| --- | --- | --- | --- |
| binary_cursor_records | 41.4/51.3/10.5/10.0 | 0.803 [0.801, 0.806] faster | 3.975 [3.943, 4.031] slower |

The base ratio was `4.986 [4.904, 4.997] slower`; the ranges do not overlap (19.3% less AIL time).
Result: `bench/results/2026-10-23-3b21283-dirty.json`. The generated C for `read_u8`, `read_u16_*`
and `read_u32_*` has no `ail_bytes_get`/`ck_add`/`ck_sub` left, and every timed run matched the
Python oracle byte-for-byte.

Probes (`bash ~/tools/cmp.sh /tmp/probes/<name>.py $PWD`, CPython and both compiler paths agree):
`field_remaining_reads.py` (inlined `remaining`, u8/u16/u32, exact boundary, invalid position),
`field_mutation_soundness.py` (field store, bytes-field reassignment, unknown method call, aliased
object argument all keep the out-of-range read checked), `field_guard_bounds.py` (direct
`len(field) - 1` guard and negative index). Tests: `test_ail_range_checks.py`,
`test_ail_binary_cursor_cli.py`, `test_ail_safetynet.py`, `test_ail_files.py`,
`test_ail_corpus_findings3.py` all pass.

## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
