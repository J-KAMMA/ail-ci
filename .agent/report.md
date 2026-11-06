# job job-fbpmap2-11070025  started 2026-11-06T15:37:47Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**What landed** (`2da03b6`, on `job-fbpmap2-11070025`; not pushed — this runner's brief says commit only):
- `AIL_CURRENT/python/pkg-v12/cruntime.py`: `AIL_PAR_SCHED=guided` selects a guided worker (`ail_par_work_guided`) that claims `max(min_block, remaining/(2*threads))` iterations with one CAS on the start index; blocks contiguous and in index order; `min_block = 20 us / (probe-rate ns/iter)` from the probe prefix, stored per call site. Failures compare by block start offset, so the sequential-first exception wins. `PARRED` forces `min_block = 0`, keeping its own chunk layout. Unset → the untouched fixed-block loop (all `_PAR_CAPPED_EDITS` strings still unique; `lab/race/pmap/run.py` instrumentation markers still unique).
- New `test_ail_par_sched.py` + `tests.d` registration (4 tests: guided vs sequential at 1/2/4/16, first-failing-block at 16 threads both ways round, 1 iteration / more threads than iterations, reduction exact under both schedules).
- `lab/race/PMAP.md` "After" section; manifest updated and `--check` clean.

**Numbers, 4 threads, median of 9 alternating wall times**: uniform 1.01x, tiny 1.00x (targets met), heavy **1.89x** (met), par_collatz 1.07x (not slower, met), **ramp 1.05x — missed 1.15x**, named with numbers in PMAP.md. Instruction counts unavailable here (`perf_event_open` denied, no valgrind).

**Verified**: the five loads print identical bytes at threads 1/2/4/16, variable set and unset; `lab/race/run.py --quick` → 0 silent races, 16/17 safe matched, 16/17 GIL-free (only `safe/int_beyond_int64.py`, the expected loud stop). TSan clean on a map and a `parallel for` program under both schedules; ASan/UBSan clean at 4 and 16 threads with guided. `test_ail_par_sched`, `test_ail_parallel_for`, `test_ail_par_reduce_rt`, `test_ail_typed_parallel` (incl. its TSan/ASan cases), `test_ail_files`, `test_ail_corpus_findings3` pass; `test_ail_safetynet` passes without the 1.5 GB cap (its generators/GC case OOMs under the cap, unrelated to this change).

**Probes** (all matched CPython, default and forced builds): `p_ramp_map.py`, `p_small_map.py` via `~/tools/cmp.sh` at 1 and 16 threads with the variable set and unset; AIL-syntax `trap1`/`trap2` (early-small vs late-large exception at 16 threads), `small` (1/2/3 iterations, 16 threads), `g1` compared against the sequential AIL build under both schedules.
[commandcode stop=end_turn turns=75 out_tokens=56328]

## review 0
[model commandcode/deepseek-v4.1-flash]
**Review: fbpmap2 guided chunk sizes**

**What the change really does** — one line: `cruntime.py`'s `PAR` gains an env-selected worker `ail_par_work_guided` (`AIL_PAR_SCHED=guided`) that claims `max(min_block, rem/(2*threads))` with one CAS on the start offset, derives `min_block` from the probe-prefix rate stored in a new `ail_par_site.ns_per_iter`, records failures by start offset, and forces `min_block=0` for `PARRED`; the unset path is the old loop plus one branch. That matches the report.

**Probes** (all in `/tmp/rprobes`; AIL probes run at T=1/2/4/16 × unset/guided vs the sequential build, `.py` probes via `cmp.sh` vs CPython, general and default path):

| probe | covers | result |
|---|---|---|
| p1_edges.ail | n=0,1,2,3,7,64,65,66,127,129,1000,20000; negative lo; two output lists; bytearray | match |
| p2_exc.ail | first-failing-iteration vs block order, 4 modes, 16 threads, repeated sites | match |
| p3_reuse.ail | same site at 30000/30000/50/40000/30000; two loops in sequence | match |
| p4_types.ail | float lists, list-item dtypes, int64 boundary values | match |
| p5_map.py, p9_map2.py | `ThreadPoolExecutor.map` with an in-body raise; caps 1/2/3/8; 20× stress at 16 threads | match CPython, 0/20 mismatches |
| p6_seq.py | slices/copies, bytearray mutation, dict | match (no-feature regression) |
| p7/p8 | uncaught OverflowError / IndexError under guided: stderr+rc identical to base | match |
| p10_fine.ail | very heavy body (min_block≈1, finest blocks) + late exception at 16 threads | match |
| p11_struct.ail | struct attribute in body | refused by name ("attribute is not allowed in the body") — acceptable |

Non-parallel program: `--debug-dir program.c` byte-identical to `/tmp/base`. Parallel-for program: C diff is purely additive + the probe-condition refactor. TSan (`-fsanitize=thread`, 16 threads, both schedules) clean on a `parallel for`, a map, and an exception program. Manifest `--check` rc=0. `test_ail_par_sched` passes; `test_ail_safetynet` passes uncapped (156 s) — it only failed under the 1.5 GB cap I applied, exactly as the report says.

**Speed (4 cores, my own runs):** heavy 0.09→0.05 s (~1.8x), ramp 52→50 ms (~1.04x), uniform 1.00x, tiny 23–27 ms (noise). Identical stdout everywhere.

**Report claims:** guided worker/min_block/fail-by-start-offset/PARRED-zeroing/unset-untouched — verified. Tests, PMAP "After", manifest — verified. Numbers heavy/uniform/tiny — verified. Ramp target **missed** (1.04x vs 1.15x) but named with numbers in `PMAP.md`, which the done-check allows; it is inherent to the specified rule (the probe measures the cheapest prefix, so `min_block` is too coarse for an increasing-cost ramp). perf_event denied (`paranoid=4`) — verified.

**Pre-existing:** none found.
**Unverified:** full `lab/race/run.py --quick` counts, ASan/UBSan, par_collatz timing (needs stdin input), instruction counts (no PMU).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=75 out_tokens=55265]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T17:33:27Z
