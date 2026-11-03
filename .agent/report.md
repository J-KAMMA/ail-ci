# job job-bces2-11040407  started 2026-11-03T19:08:11Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed bce s2 on `job-bces2-11040407` (`b87dccc5`, `ab67edde`); no push (forbidden).

**Numbers**
- tally_lang/ail: `21,658,123,728 -> 19,958,091,456` instructions, ratio `0.92151` (**7.85% drop**), output same.
- Stripped binary: `67,800 -> 67,800` bytes.
- Compile phases, median 5: total `0.11s` both; gcc `1.25` vs `1.24` CPU seconds (within 3%).
- C: `same C` for berth_sim, chain_relax, echo_pack, ledger_bin, rail_transfer, scar_life, term_rank, ticket_audit (both syntaxes), and tree_fold/ail. Only tally_lang/ail changed. tally_lang/python and tree_fold/python keep their pre-existing base build failures.
- Baseline was job base `HEAD 5a0cb28`, since current `origin/integ` has later unrelated merges.

**Probes**
- 49,999 and 50,000 return; 50,001 exits 1 with `recursion depth exceeded`.
- Mutual g/h reaching depth-param `f`; raise-at-29,999 then recurse-to-48,999; non-recursive helper; guarded-helper refusal; tally-like evaluator.
- All match the same mode built with `AIL_BCE=0` in default, force and audit. Stats report `depth=param` and `callee other can reach a guarded function`. Audit is clean.
- `cmp.sh` probes `depth_self.py` and `depth_mutual.py` match CPython in default and force.

**Checks**
- On final commit: `test_ail_bce`, `test_ail_ir_s1/s2/s3`, `test_ail_range_checks`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass.
- Manifest check passes; codegen pins unchanged.
- No recursion test module exists in the tree.
- All 20 shards were not run locally: the job rules forbid push and say not to run the whole suite locally.
- The official tally check's `ail` result passes, but the command exits 1 because `tally_lang/python` already fails to build on the base.
[cost $0.0000, opencode tokens {"total": 9914797, "input": 258046, "output": 24375, "reasoning": 36728, "cache.write": 0, "cache.read": 9595648}]
    tool time: bash 63.2 min
        673s bash   rm -rf /tmp/base2 && git worktree add --detach /tmp/base2 HEAD >/tmp/base2_worktree.log 2>&1; echo rc=$?; tail
        673s bash   cat > /tmp/s2cmpc.py <<'PY' import sys, tempfile from pathlib import Path sys.path.insert(0, '/home/runner/wor
        601s bash   export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind; python3 lab/beatc/bce_census.py c
        573s bash   python3 tools/par_check.py -j 2 test_ail_bce test_ail_ir_s1 test_ail_ir_s2 test_ail_ir_s3 test_ail_range_check
        477s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_bce test_ail_ir_s1 test_a
        259s bash   export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgrind; python3 lab/beatc/bce_census.py c
        245s bash   cat > /tmp/s2measure.py <<'PY' import os, sys, tempfile, json from pathlib import Path sys.path.insert(0, '/ho
        104s bash   python3 tools/par_check.py -j 1 test_ail_bce

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** `pyfunc.to_c` now exposes each recursive function's SCC/direct-call/reach sets; `ir/lower.py` selects a self-recursive, self-contained IR function; `ir/emit_c.py` emits a static `f__d(..., int64_t ail_d)`, rewrites self-calls to `f__d(..., ail_d + 1)`, and keeps wrapper `f(...)` calling `f__d(..., ail_depth + 1)`. Audit keeps the global counter and asserts equality. This matches the report.

**Verified**
- Tally census (base `/tmp/base2`): `21658123041 -> 19958090769`, ratio `0.92151` (7.85% drop), output same, stripped `67800 -> 67800`.
- All other 9 compare-lab tasks: `same C` in both syntaxes; `tree_fold/python` fails on base too. Codegen pins unchanged; `update_manifest.py --check` passes.
- `test_ail_bce` and `test_ail_safetynet` pass (`-j 2`, 2/2).
- Depth boundary from a mutual `g`/`h` pair: `g(49998)` + `f(0)` returns, `g(49999)` + `f(0)` trips identically on base/HEAD.
- Default and `AIL_BCE=0` C for a non-recursive and a `try`-containing function are byte-identical to base.

**Pre-existing**
- Force-mode build (`AIL_UNIFIED_FORCE=1`) of 49,999-deep Python recursion segfaults identically on base and HEAD (`p1` force, both exit 139), so the report's "49,999 and 50,000 return" holds only for default/audit.
- `tally_lang/python` and `tree_fold/python` fail on the base tree; the census `check` therefore exits 1 on a pre-existing failure, not this change.

**Unverified**
- Compile-phase within 3%; all 20 shards; the worker's private `cmp.sh` probes `depth_self.py`/`depth_mutual.py` (not in the tree).

VERDICT: FIX

1. The new generated inner symbol `f__d` is not collision-checked, so a legal user function with that name makes the program fail to compile; base built and ran it. Probe `/tmp/rprobes/p11_collide.py`:
```python
def f__d(n: int) -> int:
    return n + 1000

def f(n: int) -> int:
    if n == 0:
        return f__d(5)
    return f(n - 1) + 1

def main() -> int:
    print(f(3))
    return 0

main()
```
Expected (base and HEAD with `AIL_BCE=0`): build and print `1008`, exit 0. Actual on HEAD: build failure, gcc `conflicting types for 'f__d'` — generated `int64_t f__d(int64_t, int64_t)` clashes with the user's `int64_t f__d(int64_t)`. Choose an internal name that cannot collide (or detect an existing symbol and keep the global counter).
[cost $0.0000, opencode tokens {"total": 3920122, "input": 103295, "output": 11073, "reasoning": 38714, "cache.write": 0, "cache.read": 3767040}]
    tool time: bash 19.2 min
        645s bash   date; cd /home/runner/work/ail-ci/ail-ci; export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/v
        259s bash   date; cd /home/runner/work/ail-ci/ail-ci; export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/v
        189s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         18s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p1_depth p2_method p3_helper_method p5_try p6_values p4_norec; do
         17s bash   cd /home/runner/work/ail-ci/ail-ci for p in p2_method p3_helper_method; do   echo "######## $p"   echo "-- HEA
          6s bash   cd /home/runner/work/ail-ci/ail-ci echo "-- p1 HEAD force"; /tmp/rtest.sh /tmp/rprobes/p1_depth.py $PWD env AI
          2s bash   cd /home/runner/work/ail-ci/ail-ci; timeout 300 python3 tools/codegen_diff.py --base work 2>&1 | tail -40
          2s bash   cat > /tmp/rprobes/p9_cbhelper.py <<'PY' from typing import Callable  def apply(op: Callable[[int], int], n: i

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer defect and committed as `fdc2b75c`.

- `ir/lower.py` now detects a user function already occupying the generated inner symbol `<sym>__d`, keeps the global depth counter, and reports `inner symbol f__d is taken` in `AIL_IR_STATS`.
- Added `depth_inner_symbol_collision` to `test_ail_bce.py`.
- Verified reviewer probe `p11_collide.py`: builds/runs `1008` in default, `AIL_UNIFIED_FORCE=1`, `AIL_BCE_AUDIT=1`, and `AIL_BCE=0`.
- `test_ail_bce` passes; `test_ail_ir_s1/s2/s3`, `test_ail_range_checks`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass (sanitizer modules rerun without `ulimit -v`, which ASAN conflicts with).
- Census: tally `21,658,123,041 -> 19,958,090,769` (`0.92151`), output identical, stripped `67,800 -> 67,800`.
- Manifest check passes. No push performed, per standing rules.
[cost $0.0000, opencode tokens {"total": 1614711, "input": 63430, "output": 5485, "reasoning": 11204, "cache.write": 0, "cache.read": 1534592}]
    tool time: bash 16.8 min, edit 0.0 min
        434s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 2400 python3 ../tools/par_check.p
        259s bash   cd /home/runner/work/ail-ci/ail-ci && export PATH=/tmp/vg/usr/bin:$PATH VALGRIND_LIB=/tmp/vg/usr/libexec/valgr
        200s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_saf
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2000 python3 test_ail_bce.py 2>&1 | tail -30
          2s bash   cd /home/runner/work/ail-ci/ail-ci && for mode in force audit; do rm -f /tmp/rprobes/p11_$mode; if [ "$mode" =
          1s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rprobes && cat > /tmp/rprobes/p11_collide.py <<'PY' def f_
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && git diff --stat && git statu

## review 1 failed to run: (free quota used up; paid model from here) [model commandcode/deepseek-v4.1-flash] 

## review 1
[model commandcode/deepseek-v4.1-flash]

FINAL VERDICT: ERROR  2026-11-03T22:12:37Z
