# job job-pyreachs7-11051454  started 2026-11-05T05:54:50Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Two commits on `job-pyreachs7-11051454` (not pushed):

- `697c57a` fixes both review defects: loop-carried guarded locals are now hoisted before the outermost loop, and deleted captured names are refused by name except the compiler's `key=` sort lambda.
- `f95b7ce` adds regression tests for both cases.

Verification:
- Review probes and 11 extra probes match CPython on default and `AIL_UNIFIED_FORCE=1`.
- `test_ail_optional_locals` 9/9, `test_ail_unbound` 21/21, `test_ail_optional_structs` 7/7, `test_ail_safetynet` 5/5, `test_ail_files` 18 (1 skip), `test_ail_corpus_findings3` 2/2.
- All five codegen pins and all ten `.ail` C files byte-identical to `work`; manifest `--check` passes; `berth_sim` typed, 26/26.

Risk: berth typed wall time was 4830.8ms vs 2460.3ms (`~1.96x`); icount was unavailable, and the gate is stated as icount within 1.4x.
[cost $0.0000, opencode tokens {"total": 8148089, "input": 277212, "output": 19195, "reasoning": 41122, "cache.write": 0, "cache.read": 7810560}]
    tool time: bash 36.8 min
        381s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/compare/run_task.py --task berth_sim --langs ail,ail-py,pyth
        221s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/compare/run_task.py --task berth_sim --langs ail,ail-py,pyth
        219s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/compare/run_task.py --task berth_sim --langs ail,ail-py,pyth
        189s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/compare/run_task.py --task berth_sim --langs ail,ail-py,pyth
        172s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_corpus_findings3.py 2>&1 | tail -15
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_safetynet.py 2>&1 | tail -15
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_unbound.py 2>&1 | tail -6
        123s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_unbound.py 2>&1 | tail -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of pyreach s7 review-fix 2 (HEAD f95b7ce, base `work`)

**What the change really does:** `optlib.bind_guarded_locals` no longer inserts the guarded-local fallback inside a loop body when the first assignment is nested in a conditional; it inserts it before the outermost enclosing loop (only for a `Name`/`Constant` default). `unbound.py` no longer lets a nested scope read a name deleted in the enclosing function, except a lambda passed as `key=` to `sorted`/`min`/`max`/`.sort`. Plus two regression tests, DEVLOG and manifest hashes. This matches the report.

**Probes** (all in `/tmp/rprobes`, both builds via `cmp.sh`, compared to CPython and base):
- `t14_stale_aux.py` (review defect 1): HEAD and base both default/general; HEAD now `4 4` / `end 4 4` on both builds. Base differs. **Fixed.**
- `t4_del_closure_call.py` (review defect 2): HEAD exit 1, stdout `before` on both builds; base default printed `3`, exit 0. **Fixed.**
- `t14c_nested_loop`, `t14d_while`, `t14e_reset_in_loop`: match CPython on both builds.
- `t4b_del_in_branch`, `t4c_del_reassign`, `t4d_lambda_non_key`, `t4e_sort_key_del`, `t4f_sort_key_capture_del`, `t4g_sort_capture_ok`, `t4h_del_before_sort`, `t4i_closure_never_called`, `t4j_alias_after_del`, `t4l_param_branch`: all match CPython on both builds (refused-by-name/general where expected).
- `t14h_locals_before_loop`, `t4k_shadow_sorted`: both builds fail identically on base and HEAD (pre-existing unsupported shapes).

**Claims:** both named defects fixed — verified. Regression tests added — verified. `test_ail_optional_locals`, `test_ail_unbound`, `test_ail_safetynet` — 3/3 modules ok. Five codegen pins identical (`codegen_diff.py --base work`) and ten `.ail` sources 0 diff lines — verified. Manifest `--check` rc 0 — verified. `berth_sim` typed, 26/26 cases — verified (wall 4595.7 ms vs `.ail` 2297.1 ms, 2.0x). Not verified: per-module test counts (DEVLOG says `test_ail_unbound` 20/20, report 21/21), the worker's 11 extra probes, `test_ail_files`/`test_ail_corpus_findings3`, icount ratio (no `perf_event_open` permission, no valgrind).

**Pre-existing:** `t14g_hoist_order.py` (fallback default `g1` is itself only conditionally bound): CPython prints `iter 1`/`iter 2` then `UnboundLocalError` exit 1; base prints `iter 1` exit 1; HEAD prints nothing exit 1. The unbound-default fallback is already wrong on base (both differ from CPython), so this is the same pre-existing flaw, now hoisted earlier; it does not block.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1678613, "input": 63049, "output": 5995, "reasoning": 27489, "cache.write": 0, "cache.read": 1582080}]
    tool time: bash 8.7 min
        241s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_optional_locals test_ail_unbound test_ail_
        185s bash   date; python3 lab/compare/run_task.py --task berth_sim --langs ail,ail-py,python --icount none --out /tmp/r-be
         49s bash   date; for f in lab/compare/src/*/main.ail; do out=$(python3 tools/codegen_diff.py --base work --source "$(cat 
         12s bash   date; for p in /tmp/rprobes/t4*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep 
          8s bash   date; for p in /tmp/rprobes/t14*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep
          7s bash   cat > /tmp/rprobes/t4g_sort_capture_ok.py <<'EOF' def main() -> None:     xs = [0, 1, 2]     w = [30, 10, 20] 
          4s bash   cat > /tmp/rprobes/t4l_param_branch.py <<'EOF' def f(n: int, c: bool) -> None:     def inner() -> int:        
          3s bash   cat > /tmp/rprobes/t4j_alias_after_del.py <<'EOF' def main() -> None:     x = 3     def f() -> int:         re

## full suite
test_ail_fuzz_findings

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed the regression in `AIL_CURRENT/python/pkg-v12/aliasrefuse.py`:
- Normalized `__ail_checked_list[T]` return annotations when detecting containers.
- Recognized returned list elements after nested-list lowering (`g[0]` → `g[0].v`).

Verified:
- `test_ail_fuzz_findings` — 23 tests OK
- `test_ail_unbound` + `test_ail_optional_locals` — 30 tests OK
- `test_ail_ir_rulex` — 7 tests OK

Committed as `66eb186`.
[cost $0.0000, opencode tokens {"total": 3985458, "input": 156385, "output": 11084, "reasoning": 13061, "cache.write": 0, "cache.read": 3804928}]
    tool time: bash 8.6 min
        183s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_unbound test_ail_optional_locals 2>&1 | tail -30
        110s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings 2>&1 | tail -60
         44s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings 2>&1 | tail -30
         43s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -q test_ail_fuzz_findings.FuzzFindings.test_second_refere
         32s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ir_rulex 2>&1 | tail -30
         21s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings.FuzzFindings.test_second_references_are_cpytho
         19s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings.FuzzFindings.test_second_references_are_cpytho
         15s bash   cd /tmp/ailbase/AIL_CURRENT && python3 -m unittest -q test_ail_fuzz_findings.FuzzFindings.test_second_referenc

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T08:14:12Z
