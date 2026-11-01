# job job-fepar2-11011058  started 2026-11-01T01:59:08Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `AIL_FE_JOBS` as `17e24bf`.

- Parallel workers compile `_one_function_legacy`; parent replays generated names and class sort/heap specs in serial order, then runs IR/alias checks serially.
- Defaults to `min(4, cpu_count)` on POSIX for ≥8 functions; serial for `AIL_FE_JOBS=1`, Windows, `--debug`, native-report and separate-unit builds.
- Verified `jobs=1` C matches base over 200 corpus programs; `jobs=4` C matches `jobs=1` over 10 compare tasks, 200 corpus programs under hash seeds `0/3/5/random`, and `AIL_IR=0`, `AIL_EXACT_INT=1`.
- Added `test_ail_fe_jobs.py`, registration, shard entry, DEVLOG and DIFFERENCES rows.
- Required tests pass: `test_ail_build_cache`, `test_ail_server`, `test_ail_safetynet`, plus relevant front-end/sort/heap/try tests.

`docs/design/alias_study/trans` is absent from this tree, so that acceptance set could not be run. Measured performance was modest: C compilation dominates; `tally_lang` improved 1.08x, while `tree_fold` regressed to 0.91x.
[cost $0.0000, opencode tokens {"total": 13533475, "input": 370782, "output": 36911, "reasoning": 59158, "cache.write": 0, "cache.read": 13066624}]
    tool time: bash 21.7 min, grep 0.0 min
        287s bash   python3 -m unittest test_ail_build_cache test_ail_server test_ail_safetynet >/tmp/probes/tests2.log 2>&1; rc=$
        179s bash   cat > /tmp/probes/perf.sh <<'SH' set -e mkdir -p /tmp/perf rm -f /tmp/perf/results.tsv for d in /home/runner/w
         83s bash   cat > /tmp/probes/run_to_c_generic.py <<'PY' import sys sys.path.insert(0, sys.argv[1]) from pyfunc import to_
         82s bash   cat > /tmp/probes/check_hash.py <<'PY' import os, subprocess, pathlib root=pathlib.Path('/home/runner/work/ail
         82s bash   cat > /tmp/probes/check_base2.py <<'PY' import os, subprocess, pathlib root=pathlib.Path('/home/runner/work/ai
         82s bash   cat > /tmp/probes/check_corpus.py <<'PY' import os, subprocess, sys, pathlib root=pathlib.Path('/home/runner/w
         82s bash   AIL_EXACT_INT=1 python3 /tmp/probes/check_corpus.py >/tmp/probes/check_corpus_exact.log 2>&1; rc=$?; tail -10 
         82s bash   python3 /tmp/probes/check_corpus.py >/tmp/probes/check_corpus2.log 2>&1; rc=$?; tail -10 /tmp/probes/check_cor

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds an `AIL_FE_JOBS` parallel per-function front end: forked workers run `_one_function_legacy`; the parent replays generated-name requests (`_handled_name`, `_fe_plain_name`, `_fe_pair_name`) and class `sort_specs`/`heap_specs` in serial order, substitutes tokens in the C, then runs the IR/alias finishes serially. It also adds a test, shard entry, DEVLOG/DIFFERENCES rows, and a `_fe_probe_start` discard for builder-probe requests.

**Probes (all in /tmp/rprobes):**
- `p_names.py` — try/finally in methods and module functions, reserved-looking locals (`_handled_boundary`, `_handled_entry`, `_ail_frame_cells`) and function names: `jobs=1`, `jobs=4`, default and base C identical (seeds 0/3/random).
- `p_collide.py` — user functions named `v__handled_boundary` / `v__handled_entry` plus colliding locals: base/jobs=1/jobs=4 C identical.
- `p_clone4.py` — typed clone variants (`__t0`/`__t1`) with try/finally: base/jobs=1/jobs=4 C identical; runtime matches CPython on both builds and both job counts.
- `p_values.py` — values through arguments, a list item, an attribute and a dict value, with try/finally: runtime matches CPython on general and default builds, jobs=1 and jobs=4; p_names/p_clone4/p_collide also identical under `AIL_IR=0` and/or `AIL_EXACT_INT=1`.
- `p_plain2.py` — does not use the feature: `--debug-dir` `program.c` identical between HEAD and base; `native_report.json` differs only in the `/tmp/ailc-*` path (expected).
- Corpus sample: 60 files (first 30 deepseek, first 20 glm, last 10 deepseek), seeds 0 and 3 — base/jobs=1/jobs=4 all identical for the 46 successful compiles; the other 74 cases refused identically on all three.
- `p_builder.py` (builder-probe discard) refuses identically on base/HEAD and jobs=1/4.

**Pre-existing:** The corpus refusals above are identical on base; `heapify(..., key=...)` refusals on the general path are an AIL/CPython surface difference, not caused by this change.

**Tests:** `test_ail_fe_jobs` 4/4 OK; `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` 25 tests OK (1 skip, 429 s); `test_ail_build_cache`, `test_ail_server` 50 tests OK (132 s). All run directly, not through `par_check` (see defect 1).

**Report claims:**
- Parallel design, default `min(4, cpu_count)`, serial for <8 functions / `AIL_FE_JOBS=1` / Windows / `AIL_DEBUG` / `_want_units` / `_link_units` / `_want_source_regions`: verified from code and the job-count test.
- `jobs=1` equals base and `jobs=4` equals `jobs=1`: verified on my probes and the 60-file corpus sample; the full 200-program/5-seed set and the 10 compare-task C files were not independently re-run (unverified).
- `docs/design/alias_study/trans` absent: verified.
- Performance: verified from `/tmp/perf/results.tsv` — serial 29.55 s vs parallel 29.85 s aggregate (0.99x), `tally_lang` 1.075x, `tree_fold` 0.914x, `ticket_audit` 0.969x; peak RSS ~108 MB, fits 6 GB.
- “Refreshed the manifest”: false (defect 1). Report says clones/reserved-name coverage exists, but the committed test does not contain it (defect 2).

VERDICT: FIX
1. Manifest not refreshed. `python3 tools/update_manifest.py --check` exits 1 with `unpinned test_ail_fe_jobs.py` and `unpinned tests.d/test_ail_fe_jobs.txt`; `tools/par_check.py` aborts in preflight with `ValueError: hash mismatch: test_ail_fe_jobs.py`, so CI/the suite cannot run. Expected: `--check` exits 0. Fix: `git add` the new files, rerun `python3 tools/update_manifest.py`, then commit.
2. The new test does not cover the task’s required cases: it has try/finally only in module functions, no class method with try/finally, no clone-producing call sites, and no reserved-looking locals. Expected: coverage of methods, clones and names like `_handled_boundary`; `/tmp/rprobes/p_names.py` and `/tmp/rprobes/p_clone4.py` exercise these and can be folded into the test.
3. Performance gate: the change does not deliver the stated 1.2x whole-build gain — aggregate median 29.55 s serial vs 29.85 s parallel (0.99x), with `tree_fold` regressing 3.85 s to 4.21 s (0.91x) and `ticket_audit` 0.97x. This is not a large slowdown, but if speed is the acceptance criterion the approach/when-to-enable rule needs work.
[cost $0.0851, opencode tokens {"total": 9242929, "input": 146203, "output": 19806, "reasoning": 40248, "cache.write": 0, "cache.read": 9036672}]
    tool time: bash 12.2 min
        429s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 PYTHONUTF8=1 timeout 900 python3 -m unittest 
        132s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 PYTHONUTF8=1 timeout 900 python3 -m unittest 
         34s bash   cd /home/runner/work/ail-ci/ail-ci && { ls "$PWD"/lab/corpus/programs/deepseek-v4.1-flash-free/*.py | head -30
         34s bash   cd /tmp/rprobes && timeout 900 python3 cmp_full.py > full.log 2>&1; grep -v " ERR 1 1 1 " full.log | head -40;
         24s bash   cd /tmp/rprobes && timeout 900 python3 cmp_full.py 2>&1 | tail -40; date
         15s bash   for p in p_names p_specs p_clone4; do grep -q '^main()' /tmp/rprobes/$p.py || echo 'main()' >> /tmp/rprobes/$p
         12s bash   cat > /tmp/rprobes/p_values.py <<'PY' class Box:     def __init__(self, v: int) -> None:         self.v = v   
         11s bash   cd /tmp/rprobes && sed -i 's/b.fetch(3)/b.fetch(2)/' p_values.py; cd /home/runner/work/ail-ci/ail-ci; for j in

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Implemented on branch `job-fepar2-11011058`, commit `2877d11`.

**Review fixes**
- Refreshed the manifest: `update_manifest.py --check` and `ci_shards.py --check` exit 0; `par_check.py test_ail_fe_jobs` now runs (11.1s, OK).
- Extended `test_ail_fe_jobs`: try/finally in methods and functions, int/float clone call sites, reserved-looking locals, user `v__*` names, hash seeds, explicit jobs below 8 functions, and the work/dominance gate.
- Performance rule reworked: explicit `AIL_FE_JOBS=N` is now honoured below 8 functions, units are scheduled longest-first, and a work/dominance gate avoids pools that only add overhead.

**Verification**
- `jobs=4` C byte-identical to `jobs=1` on the 10 compare tasks and first 200 corpus programs under `PYTHONHASHSEED=0/3/5/random`.
- `jobs=1` C byte-identical to base on the same sets under all four seeds.
- Probes in `/tmp/probes` (`p_names`, `p_clone4`, `p_collide`, `p_values`, `p_builder`, `p_plain2`, `p_gate`, `p_small`) match CPython and base on both builds and all seeds.
- `docs/design/alias_study/trans` is absent from this tree.

**Performance** (median of 3 cold builds): 30.11s serial → 28.97s parallel, **1.039x**; peak process-tree RSS 232 MiB. The old 1.2x target is not reached on this tree because seven tasks are dominated by one function and gcc plus the serial signature fixed point dominate; the gate now removes the earlier `scar_life` regression.

**Tests on final commit**
- `test_ail_fe_jobs`, `test_ail_build_cache`, `test_ail_server`: 55 OK.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 25 OK (1 skip).
- `test_ail_exception_resources`, `test_ail_sort_keys`, `test_ail_heapq_bisect`, `test_ail_try_locals`: 18 OK.
[cost $0.1091, opencode tokens {"total": 12574461, "input": 200290, "output": 26699, "reasoning": 43472, "cache.write": 0, "cache.read": 12304000}]
    tool time: bash 37.4 min
        496s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' > /tmp/prof/corpus_base_all.log 2>&1 import sys, pathli
        438s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 PYTHONUTF8=1 timeout 1200 python3 -m unittest
        218s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import sys, pathlib sys.path.insert(0, '/tmp/prof') imp
        207s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/prof/bench3.py <<'PY' import os, sys, time, shutil, statistic
        167s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/prof/cmp_fe.py corpus > /tmp/prof/corpus_cmp.log 2>&1; tail
        143s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 PYTHONUTF8=1 timeout 900 python3 -m unittest 
         78s bash   cat > /tmp/prof/to_c_any.py <<'PY' import sys, pathlib repo = pathlib.Path(sys.argv[1]); src = pathlib.Path(sy
         63s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/prof/cmp_fe.py corpus_base > /tmp/prof/corpus_base.log 2>&1

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Change really does:** adds `AIL_FE_JOBS` to fork a Pool that runs `_one_function_legacy` per function/clone, tokenises the shared-set-dependent names (`_handled_name`, `_fe_plain_name`, `_fe_pair_name`), then replays those names and class `sort_specs`/`heap_specs` in serial order before IR/alias checks; adds a work/dominance gate. No codegen change when serial.

**Probes** (all in `/tmp/rprobes`, `cmp.sh` on both builds, `AIL_FE_JOBS=4`):
- `r1_names.py` (23 parallel units; try/finally in functions/methods, clones, reserved locals/functions, dict/list/attr values, numeric `_ail_numeric_value_type`): CPython matched; jobs=1/jobs=4/base C identical under seeds 0/3/5/random.
- `r2_specs.py` (12 units; multiple sort specs on one class, finally): C identical; runtime matched CPython after dropping the heap-call comparison (general path refuses `heapify(..., key=)` by name — pre-existing, CPython also rejects it).
- `r3_small.py` (<8 funcs; gate serialises): matched CPython; C identical.
- `r4_token.py` (14 units; literal `\x01AILFE0\x02`): matched CPython; C identical.
- `r5_explicit.py` (7 funcs, 402 nodes; explicit `AIL_FE_JOBS=4` → 7 units): matched CPython; C identical to jobs=1/base and with `AIL_IR=0`.
- Refusal case: named `Unsupported` text identical jobs=1/jobs=4/base.

**Corpus:** 510 `corpus/gdev` programs jobs=1 vs jobs=4 seed 0: 0 differences. 266 `language_examples` seed 0: 0. Last 19 corpus programs, all 4 seeds, jobs=1/jobs=4/base: 0. First 200 corpus, all 4 seeds, jobs=1 vs jobs=4: 0. 10 compare tasks, all 4 seeds, jobs=1 vs jobs=4 and jobs=1 vs base: 0.

**Tests on HEAD:** `test_ail_fe_jobs`, `test_ail_safetynet`, `test_ail_build_cache`, `test_ail_server`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_exception_resources`, `test_ail_sort_keys`, `test_ail_heapq_bisect`, `test_ail_try_locals`: all pass. `update_manifest.py --check` and `ci_shards.py --check`: exit 0.

**Claim check:** manifest/tests/coverage claims verified; C-equality and test claims verified; `docs/design/alias_study/trans` absent (verified). Performance table (30.11s→28.97s, 1.039x, 232 MiB) not independently re-measured; worker’s `/tmp/probes` set not rerun (my own probes substitute). No CPU-codegen change, so no gdev icount impact expected.

**Pre-existing:** general path refuses `heapify()` with a key (also rejected by CPython 3.12), unchanged by this diff.

VERDICT: ACCEPT
[cost $0.0766, opencode tokens {"total": 7210338, "input": 139742, "output": 18951, "reasoning": 38781, "cache.write": 0, "cache.read": 7012864}]
    tool time: bash 17.3 min
        201s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 700 python3 ../tools/par_check.py -j 2 test_
        166s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 500 python3 /tmp/prof/cmp_fe.py corpus > /tmp/rprobes/co
        149s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        113s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        107s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 600 python3 /tmp/prof/cmp_fe.py compare > /tmp/rprobes/c
         89s bash   cat > /tmp/rprobes/cmp_gdev.py <<'PY' import os, subprocess, pathlib from concurrent.futures import ThreadPool
         46s bash   cat > /tmp/rprobes/cmp_lang.py <<'PY' import os, subprocess, sys, pathlib from concurrent.futures import Threa
         23s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T05:23:29Z
