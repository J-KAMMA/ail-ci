# DEVLOG

## 2026-10-26 - suite fix: refresh C pins for noreturn traps (job-perf3-10270015)

The accepted perf3 change adds two `__attribute__((noreturn))` forward declarations to the
emitted runtime, so the full generated C for every program now differs from the old baseline.
`test_ail_numeric_bindings` and `test_ail_record_initializers` pinned the pre-change bytes and
failed even though the programs' behaviour is unchanged. Refreshed their five scalar hashes; the
only C difference from the old pins is the two intended declarations. Also carried the upstream
`bench/compare.py` `fmt` fix (already on integration, this branch predated it) so
`test_ail_pre110` passes. Probes `/tmp/probes/p_*.py` (no trap, sources, nested, return, uncaught)
match CPython in both builds.

## 2026-10-23 - binary_cursor_records: runtime traps are noreturn (job-perf3-10240012)

`BinaryCursor__remaining` checks `0 <= position <= len(data)` and then calls `ail_raise_named`, but the
runtime declared that trap as an ordinary `void` function. GCC therefore had to keep the fall-through
path alive and could not use the test to prove the subtraction cannot overflow, so `ck_sub` stayed in
the accessor. `ail_exception_uncaught` has the same property (it ends in `_Exit(1)`), so both now have
an explicit `__attribute__((noreturn))` declaration in `cruntime.py`. No app source changed.

Profiling: rdtsc instrumentation of the generated C (40M records, 496 MiB) put the per-record loop at
709,541,927 of 1,193,992,702 cycles (59.5% of the function). The accessor checks are inside that loop;
hand-edited generated C put the `ck_sub` in `remaining()` alone at ~8% overall and all unchecked reads
at ~16%, so the 9.1% below is in line with that ceiling.

`python3 bench/compare.py --app binary_cursor_records`:

| | AIL/C | AIL new/base/C/Rust ms | RSS MiB new/base/C/Rust | binary KiB new/base/C/Rust |
| --- | ---: | ---: | ---: | ---: |
| before | 5.091 [5.041, 5.253] | 50.8/50.8/10.0/9.6 | 1.7/1.7/2.5/2.7 | 39/39/15/1912 |
| after | 4.630 [4.607, 4.674] | 46.0/51.0/9.9/9.6 | 1.7/1.7/2.5/2.7 | 35/39/15/1912 |

Ratio improved 9.1%; `compare.py` checked every timed run byte-for-byte against its Python oracle.
Tests: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`,
`test_ail_exception_values_core`, `test_ail_exception_values_app`, `test_ail_excfix`,
`test_c_api_bridge`, `test_ail_parallel_for`, `test_ail_short_style_traps` all pass. Probes
`/tmp/probes/perf3_*.py` match CPython on both the general and default builds.

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
