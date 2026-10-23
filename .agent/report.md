# job job-perf3-10240012  started 2026-10-23T15:14:35Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. The change is committed on `job-perf3-10240012`.

**Change**
- `AIL_CURRENT/python/pkg-v12/cruntime.py`: marked `ail_exception_uncaught` and `ail_raise_named` `__attribute__((noreturn))`.
- GCC can now prove `0 <= position <= len(data)` after `remaining()`’s guard and fold the `ck_sub` overflow check. No app source changed.

**Profile / ceiling**
- rdtsc on generated C: per-record loop `709,541,927 / 1,193,992,702` cycles = **59.5%** of the function.
- Hand-edited C showed `ck_sub` alone worth ~8% overall, all unchecked reads ~16%.

**Measurement** (`python3 bench/compare.py --base b6e5a2f --app binary_cursor_records`)
- AIL/C: `5.091` → **`4.630`** = **9.1% improvement**
- AIL ms: `50.8` → `46.0`; C: `10.0` → `9.9`
- RSS MiB: `1.7/1.7/2.5/2.7` unchanged
- Binary KiB: AIL `39` → `35`
- Every timed run checked byte-for-byte against the Python oracle.

**Tests on final commit** (`5ecee31`, `-j 2`): 9 modules, 0 failed — `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_exception_values_core`, `test_ail_exception_values_app`, `test_ail_excfix`, `test_c_api_bridge`, `test_ail_parallel_for`, `test_ail_short_style_traps`.

**Probes** (`/tmp/probes/perf3_*.py`, both general and default builds): `no_trap`, `traps_catch`, `traps_nested`, `traps_sources`, `traps_uncaught` — all match CPython stdout/exit.

Commits: `b6fce7f` code + `5ecee31` DEVLOG numbers; `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 9257921, "input": 679580, "output": 25797, "reasoning": 31456, "cache.write": 0, "cache.read": 8521088}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review**

**Diff.** Only functional change is two `__attribute__((noreturn))` declarations in `AIL_CURRENT/python/pkg-v12/cruntime.py` (for `ail_exception_uncaught`, `ail_raise_named`). Both are genuinely non-returning (`_Exit(1)` / `ail_exc_throw` longjmp), so the attribute is sound. The rest of the diff is DEVLOG, MANIFEST and captured bench JSON.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`, general + default builds, HEAD and `/tmp/base`):
- own: `p_uncaught`, `p_caught`, `p_nested`, `p_traps`, `p_noexc`, `p_loopexc`, `p_finally_raise`, `p_uncaught_after_print`, `p_mutate_iter` — all stdout/exit match CPython on both builds; identical results on base.
- worker's `/tmp/probes/perf3_*` (5) rerun — all match on both builds.
No crash, wrong status, or output difference found. No pre-existing differences surfaced.

**C invariance.** For non-trap programs (`p_noexc`, gdev `g00_000`) the `--debug-dir` generated C differs from base only by the two intended declaration lines; the general-path runtime (`g01_008`) is byte-identical.

**Tests** on HEAD, `-j 2`: the worker's 9 modules + `test_ail_exception_aggregate_objects`, `test_ail_exception_context`, `test_ail_exception_resources` — 12/12 ok, 0 failed. `update_manifest.py --check` exits 0.

**Speed.** `python3 bench/compare.py --base b6e5a2f --app binary_cursor_records`: AIL/base `0.904 [0.902,0.907]`, AIL/C `4.707 [4.654,4.754]`, AIL 46.1 ms vs base 50.9 ms (~9.6% faster), C 9.8 ms; RSS 1.7/1.7, binary 35 vs 39 KiB. Above the 5% bar, while still far from C. `perf_event_open` is denied on this runner, so the instruction-count check could not run.

**Claim check.** Change/noreturn (verified); ~9.1% gain (verified, I measured 9.6%); RSS/binary (verified); oracle-checked runs (verified by successful compare); tests/probes/manifest (verified). Exact rdtsc 59.5% and hand-edited 8%/16% figures, and the specific `ck_sub` folding mechanism, are unverified (the measured speedup is consistent with them).

**Note.** HEAD is `36c4c0b` ("worker: uncommitted edits"), which only adds three bench-result JSONs (one `-dirty`); the report names `5ecee31` as final. Record-keeping nit, not a defect.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1282970, "input": 46277, "output": 6441, "reasoning": 9004, "cache.write": 0, "cache.read": 1221248}]

FINAL VERDICT: ACCEPT  2026-10-23T16:09:14Z
