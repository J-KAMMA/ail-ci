# job job-fbpmap3-11071051  started 2026-11-07T01:55:48Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `ec8299f` on `job-fbpmap3-11071051`.

- Regenerated `lab/race/RESULTS.md` from the full suite: silent races 0, safe matched 17/18, **safe GIL-free 17/18**, no TSan reports, `safe/shared_append.py` typed parallel.
- Added `lab/race/append/p11_try.py`; `run.py` asserts the named `parallel for cannot be inside try` refusal and compares its `range` twin with CPython. `test_ail_par_append` now asserts that refusal too.
- Fixed the worker-cap drop: `ail_par_buf_run` now takes the cap, sets `ail_par_cap`/`ail_par_cap_inside` like `ail_par_run_n`, and `PARBUF` requires `PARN`.
- Probes: p01–p09 and p11 match at 1/2/4/16 threads, default and guided; p10 speedup 2.67x, RSS 1.94x.
- Tests passed: `test_ail_par_append`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; manifest `--check` passes.

Note: `test_ail_typed_parallel` still has one pre-existing failure — it expects `Thread`-body appends refused, which conflicts with the D3 target requiring `safe/shared_append.py` to build typed. Left unchanged as it is outside this job's allowed files.
[cost $0.0000, opencode tokens {"total": 7764780, "input": 152892, "output": 17420, "reasoning": 28516, "cache.write": 0, "cache.read": 7565952}]
    tool time: bash 29.0 min
        416s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -m unittest test_ail_safetynet test_ail
        298s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -m unittest test_ail_par_append test_ai
        220s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 lab/race/run.py 2>&1 | tail -8
        211s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 lab/race/run.py 2>&1 | tail -10
        211s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 lab/race/run.py 2>&1 | tail -8
        140s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 -m unittest test_ail_par_append test_ai
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_par_append test_ai
         14s bash   cd /tmp/probes && rm -rf capapp_dbg2 && python3 -B /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fbpmap3 fix-up (commit `ec8299f`)

**What the change really does:** commits the corrected `lab/race/RESULTS.md`, adds `p11_try` (assert the named `parallel for cannot be inside try` refusal plus a `range` twin) to the append runner/test, and passes the region's worker cap into `ail_par_buf_run`, which now sets `ail_par_cap`/`ail_par_cap_inside` exactly as `ail_par_run_n` and makes `PARBUF` require `PARN`.

**Verified (probes in `/tmp/rprobes/`, HEAD vs `/tmp/base`):**
- Defect 1 fixed: `git show HEAD:lab/race/RESULTS.md` has 0 `REPORT` rows, `safe GIL-free 17 of 18`, `safe/shared_append.py` = typed parallel. My `lab/race/run.py --quick` (run in a throwaway worktree) printed silent 0 / matched 17/18 / GIL-free 17/18 and its generated table matched the committed one except the "(quick)" header and elapsed time.
- Defect 2 fixed: `p11_try` is refused by name and its `range` twin matches CPython (`38 37 0`); `test_ail_par_append` asserts the refusal.
- Cap fix works: `_ail_par_range(0,100,2)` + append generated C calls `ail_par_buf_run(..., v__par_cap1)` (base omits it); `cap_app`, `cap_app_many`, `cap_app_exc`, `cap_str`, `cap_float`, `cap_listval`, `cap_zero`, `cap_neg`, `cap_empty` match their `range` twins at 1/2/4/16 threads, default and `guided`; `shared_append` prints 10 in all cases.
- No-feature C unchanged: `map_int`, `par_collatz`, `g00_000`, `g00_010`, `t001`, `t306` byte-identical to base; append programs differ only by the expected new argument.
- Tests: `test_ail_par_append`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass; `update_manifest.py --check` passes.
- Report's pre-existing `test_ail_typed_parallel` failure confirmed pre-existing (same failure on `/tmp/base`).

**Report claims:** all verified. p10 measured 2.63x at 4 threads, RSS 1.94x (report says 2.67x; run-to-run variance, not false).

**Pre-existing (not caused by this change):** `par_range` inside `try` refused on both trees; `par_range` unknown on the forced general path on both; Thread-target append test failure on both.

**Unverified:** the partial-buffer join through a caught exception — still unobservable (try-around-loop, list-parameter, module-global and class-field append shapes are all refused by name on both trees), so the join is only exercised by the uncaught `p04` path and the refusal in `p11`.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2512450, "input": 85446, "output": 8905, "reasoning": 18739, "cache.write": 0, "cache.read": 2399360}]
    tool time: bash 10.4 min
        213s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/head ec8299f 2>&1 | tail -2 && cp lab/race/RESULTS
        183s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_fil
        156s bash   cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_par_append test_ail_safetynet 2>&1 
         25s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/hashcmp.sh <<'EOF' #!/bin/bash WT=$1; out=$2; shift 2 rm -rf 
         13s bash   cd /tmp/head && timeout 900 python3 lab/race/append/run.py --quick 2>&1 | tail -12; echo "=== git diff append 
          6s bash   cd /tmp/head/AIL_CURRENT && timeout 600 python3 -m unittest test_ail_typed_parallel.Refusals.test_by_name 2>&1
          4s bash   cat > /tmp/rprobes/cap_zero.py <<'EOF' def main():     out = []     for i in _ail_par_range(0, 50, 0):        
          3s bash   mkdir -p /tmp/capwork && cd /tmp/capwork && rm -f *.exe; for f in cap_app cap_app1 cap_app_exc cap_app_many; d

## full suite
test_ail_typed_parallel

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `4915594`.

- Failure: `test_ail_typed_parallel.Refusals.test_by_name` still expected scoped-thread `out.append(...)` to be refused, but D3 now buffers/joins those appends, which is required for `lab/race/safe/shared_append.py` to build typed.
- Fix: moved that shape into a differential test (`THREAD_APPEND`) comparing length/sum with CPython at 1, 3, and 16 threads; updated the module docstring and manifest hash.
- Verified: `test_ail_typed_parallel` (17 tests) and `test_ail_par_append` (2 tests) pass; `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2204154, "input": 96273, "output": 5146, "reasoning": 11343, "cache.write": 0, "cache.read": 2091392}]
    tool time: bash 2.1 min, edit 0.0 min
         38s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_typed_parallel 2>&1 | tail -80
         38s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_typed_parallel 2>&1 | tail -60
         38s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_typed_parallel 2>&1 | tail -120
          7s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_par_append 2>&1 | tail -60
          1s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_typed_parallel.Differential.test_thread_appends 2>&1 | tail 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -20 && python3 tools/update
          0s bash   git show --stat HEAD; echo "=== PREV ==="; git show --stat HEAD~1 | head -60
          0s bash   cd AIL_CURRENT && git diff d187f89 HEAD --stat && git diff d187f89 HEAD -- python/pkg-v12/parallel.py python/p

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T05:36:49Z
