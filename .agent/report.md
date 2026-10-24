# job job-perf4-10240813  started 2026-10-23T23:13:58Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. The first part (`s += x` in place) was already in the baseline.

- Added a compiler rule for small leaf loops with scalar numeric returns; it inlines `parse_int64_decimal` and `parse_int64_decimal_bytes` in `csv_table` (`AIL_CURRENT/python/pkg-v12/pyfunc.py:36423`).
- Profile/Amdahl: removing parse saved 7.3% on the 132 MB run, but inlining its call boundary saved 20% (1.24 s -> 0.99 s). Safe chunk ownership only saved 1.6%, so that path was rejected.
- Final `compare.py --base 64d53b2 --app csv_table`: `12.1/14.6/6.1/6.9` ms, AIL/base `0.841 [0.814,0.852] faster` (was `0.995 tie`); RSS `5.5/5.5/3.3/3.6` MiB; binary `111/107/20/1928` KiB.
- Tests: 9 targeted modules including `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, 0 failed.
- Probes: `/tmp/probes/loop_inline.py`, `/tmp/probes/loop_inline_objects.py`; both builds match CPython on every case.
- Commits: `3edd935` (change) and `c5472ff` (final results); `MANIFEST` check passes.
[cost $0.0000, opencode tokens {"total": 12798525, "input": 351565, "output": 76439, "reasoning": 5721, "cache.write": 0, "cache.read": 12364800}]
    tool time: bash 17.9 min, edit 0.0 min, todowrite 0.0 min
        276s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_safetynet tes
        261s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 ../tools/par_check.py -j 2 test_ail_i
         68s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 bench/compare.py --smoke --app binary_cursor_reco
         52s bash   python3 bench/compare.py --app csv_table 2>&1 | tee /tmp/csv_before.txt
         48s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_integer_codec
         28s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 bench/compare.py --app csv_table 2>&1 | tee /tmp/
         28s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 bench/compare.py --app csv_table 2>&1 | tee /tmp/
         27s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 bench/compare.py --base 64d53b2 --app csv_table 2

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Review of job-perf4-10240813** (`3edd935`, `c5472ff`)

**Change.** `pyfunc.py` adds `_single_loop_inlinable`: a function whose body is one `for`, no other loop/try/with/yield/await, no user-function calls, scalar `int`/`float` return, ≤12 statements / ≤180 nodes gets `__attribute__((always_inline)) static inline`. I checked the emitted C for `csv_table_main.ail`: exactly 4 new attributes vs base, all on the declaration+definition of `parse_int64_decimal` and `parse_int64_decimal_bytes`; no other function changed.

**Probes (all in /tmp/rprobes unless noted).**
- `q1_shapes.ail`: early return, `break`, `continue`, float loop, loop with a local `str` temporary (cleanup path), `range` loop. HEAD and base both exit 0, identical output, values as expected; the new attribute fires on 5 of these functions.
- `q2_sources.ail`: values via argument, list item, struct attribute and dict value, with list/dict mutation between calls. Both exit 0, identical output (`2352000` total, individually correct).
- `q3_nofeature.ail` (while loop + str-returning `for`): `--debug-dir` C is byte-identical to base; outputs identical.
- `/tmp/probes/loop_inline.py` and `loop_inline_objects.py` re-run with `cmp.sh`: both builds match CPython; a `--strict` compile confirms they do reach `pyfunc` and every loop function gets the attribute.
- Python `p5_nofeature.py` debug C identical to base (only temp paths differ in `native_report.json`).
- One AIL dict-annotation probe (`q2` first form) is refused identically on base and HEAD (pre-existing refusal, not a defect).

**Tests.** `test_ail_safetynet` pass (88 s, 0 failed); `test_ail_integer_codec`, `test_ail_csv_writer`, `test_csv_group_scan` pass, 0 failed.

**Speed.** Committed JSON confirms the reported `12.1/14.6/6.1/6.9 ms`, ratio `0.841 [0.814, 0.852]`, RSS `5.5/5.5/3.3/3.6 MiB`, binary `111/107/20/1928 KiB`. Independently, the HEAD vs base `csv_table` binaries on a 12.6 MB generated input gave best user time 0.33 s vs 0.40 s with byte-identical output (consistent with the claimed ~16–18%). Instruction counts via `tools/icount.c` could not be taken: `perf_event_open` is denied on this runner. gdev programs build on the Python/general path (no `always_inline` emitted even for matching functions), so they do not exercise this AIL-codegen change.

**Claims.** `s += x` already in baseline: verified (`ail_str_cat` in-place append present in `work`, no cruntime diff). New rule / two parse functions inlined: verified. Compare numbers, manifest check, probe output, commit list: verified. Profile/Amdahl percentages and the rejected chunk-ownership 1.6% measurement: unverified (not reproduced). Worker's remaining six test modules: unverified (not run).

**Pre-existing.** The AIL dict annotation refusal and Python list-comprehension strict refusal reproduce identically on base.

Unverified: profile percentages, chunk-ownership experiment, non-run test modules, instruction counts (perf EPERM).

VERDICT: ACCEPT
[cost $0.0582, opencode tokens {"total": 4658052, "input": 143443, "output": 14744, "reasoning": 23961, "cache.write": 0, "cache.read": 4475904}]
    tool time: bash 3.1 min
         90s bash   cd /home/runner/work/ail-ci/ail-ci && (nohup bash -c 'cd AIL_CURRENT && AIL_NO_CACHE=1 python3 ../tools/par_ch
         19s bash   date; for p in /tmp/rprobes/p1_shapes.py /tmp/rprobes/p2_sources.py /tmp/rprobes/p3_methods.py /tmp/rprobes/p4
         15s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 timeout 400 python3 ../tools/par_check.py -j 
         12s bash   cd /tmp && rm -rf gdev_h gdev_b && mkdir -p gdev_h gdev_b && for wt in h b; do root=/home/runner/work/ail-ci/a
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/loop_inline.py /tmp/probes/loop_inline_objects.py; 
          8s bash   cd /tmp && python3 - <<'EOF' import random random.seed(1) with open('/tmp/big.csv','w') as f:     for i in ran
          6s bash   cd /tmp && rm -rf dbg3h dbg3b && mkdir -p dbg3h dbg3b && for w in h b; do root=/home/runner/work/ail-ci/ail-ci
          4s bash   cd /tmp && rm -rf qh qb && mkdir -p qh qb && for p in q1_shapes q2_sources; do for w in h b; do root=/home/run

FINAL VERDICT: ACCEPT  2026-10-24T00:09:19Z
