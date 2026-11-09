# job job-fbred4_rr2-11091430  started 2026-11-09T05:31:05Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `1616293` on `job-fbred4_rr2-11091430`.

- Cause: fbred4 changed PARRED accumulators to `volatile int64_t **` (write-back through pointers), but `test_ail_par_reduce_rt`'s C harness still passed an `int64_t *` array, so `ail_red_combine` dereferenced accumulator values as pointers and SIGSEGV'd at 2/4/16 threads.
- Fix: updated `red_rerun`, `c_rerun`, `red_child` (and `test_ail_par_sched`'s `REDUCE` harness, same stale ABI) to build pointer arrays. No compiler/runtime change.
- Probes: 11/11 (`p_acc_try`, `p_acc_try_zero`, `p_acc_arg`, `p_acc_list`, `p_acc_dict`, `p_acc_attr`, `p_acc_two`, `p_acc_small`, `p_acc_edge`, `p_acc_alias`, `p_acc_called_twice`) match CPython on the default build; general path refuses `par_range` by name.
- Tests on final commit, `-j 2`: 6/6 modules pass, 0 failed (`test_ail_par_reduce_rt`, `test_ail_par_sched`, `test_ail_par_reduce`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`); `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 3822212, "input": 86738, "output": 9812, "reasoning": 11998, "cache.write": 0, "cache.read": 3713664}]
    tool time: bash 11.5 min, edit 0.0 min
        375s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 test_ail_par_reduce_rt test
        266s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 test_ail_par_reduce_rt test
         15s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_par_reduce_rt 2>&1 | tail -60
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_acc_*.py; do out=$(PYTHONPATH=$PWD/AIL_CURRENT ba
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_acc_*.py; do echo "=== $(basename $p)"; PYTHONPAT
          3s bash   cd AIL_CURRENT && timeout 600 python3 test_ail_par_reduce_rt.py diff 50 asan 2>&1 | tail -80
          2s bash   cat > /tmp/probes/p_acc_attr.py <<'EOF' from ail import par_range  class Box:     def __init__(self):         
          2s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_acc_try.py <<'EOF' par_range = range  def term(i: int) -> int:    

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete.

**What the change does:** Updates only the C test harnesses in `test_ail_par_reduce_rt.py` and `test_ail_par_sched.py` to the PARRED accumulator ABI that is already in the runtime (`typedef void (*ail_red_rerun)(..., volatile int64_t **)`, `ail_red_combine(..., volatile int64_t **accp)`), building `volatile int64_t *accp[] = {&acc[...]}`. No compiler/runtime file changes. Matches the report.

**Diff review:** `DEVLOG.md`, two `manifest.d` hash updates, two test files. No `bench/apps`/example changes.

**Probes (HEAD):** all 11 worker `p_acc_*` probes plus my 5 (`rp_wide_two` n=2M two accumulators, `rp_wide_exc` catchable ZeroDivision at i=1.5M, `rp_wide_zero` first-iteration exception, `rp_empty_neg` n=0/negative/`range(5,2)`, `rp_capture_mut` dict/list/attr captured then mutated) match CPython on the default build; general path refuses `par_range` by name. Same results on `/tmp/base` (change is test-only). Non-feature `program.c` from `--debug-dir` is byte-identical to base.

**Test reproduction:** base `test_ail_par_reduce_rt` fails (par child exit 139/SIGSEGV, `cases 300 differences 53`); HEAD passes all 4 thread counts. Base `test_ail_par_sched` passes (stayed sequential as reported); HEAD passes. On HEAD, `-j 2`: `test_ail_par_reduce_rt`, `test_ail_par_sched`, `test_ail_par_reduce`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` exits 0.

**Claims:** all verified. No compiler/runtime change, so no hot-code speed check applies.

Pre-existing: none relevant.

Unverified: whether `test_ail_par_sched`'s 200000-term workload would ever cross into the wide path on this machine (it passes either way).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 976058, "input": 26475, "output": 4983, "reasoning": 11480, "cache.write": 0, "cache.read": 933120}]
    tool time: bash 7.3 min
        261s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_par_reduce_rt test
         75s bash   cd /tmp/base/AIL_CURRENT && time timeout 900 python3 test_ail_par_reduce_rt.py diff 300 2>&1 | tail -12; echo 
         29s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_par_reduce 2>&1 | 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_acc_*.py; do echo "=== $(basename $p)"; PYTHONPAT
         15s bash   cd /tmp/base/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_par_reduce_rt 2>&1 | tail -25; echo "E
          9s bash   cd /tmp/base/AIL_CURRENT && time timeout 900 python3 -m unittest -q test_ail_par_sched 2>&1 | tail -15; echo "
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "=== $(basename $p)"; PYTHONPATH=$PW
          7s bash   cd /tmp/base && for p in /tmp/rprobes/rp_wide_exc.py /tmp/rprobes/rp_wide_two.py /tmp/rprobes/rp_capture_mut.p

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-09T07:13:26Z
