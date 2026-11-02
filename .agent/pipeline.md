# job job-prog21-11021442  started 2026-11-02T05:43:05Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect in `AIL_CURRENT/ail_cpython_hybrid.py`: `abs(<bool>)` (including `abs(+x)`/`abs(-x)`) is now refused by name and falls back to CPython, while `abs(int(x))`, `int(bool)` and `str(bool)` still accelerate.

Probes (`/tmp/probes`, hybrid + both `cmp.sh` builds): direct/assigned/`+x`/`-x` bool `abs`, `int(abs(x))`, `abs(int(x))`, `int(bool)`, `str(bool)`, `str(+bool)`, bool passed to an int `abs` helper — all match CPython; bool `abs` returns 1/0 now.

Added regression `test_abs_bool_operand_stays_in_cpython`; `update_manifest.py --check` clean. Tests on the final tree: `test_ail_prog21`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass (`-j 2`).

Committed as `a00041d`. No codegen changed.
[cost $0.0000, opencode tokens {"total": 2190546, "input": 67051, "output": 10229, "reasoning": 12658, "cache.write": 0, "cache.read": 2100608}]
    tool time: bash 12.8 min
        360s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog21 test_ail_cpython_hybrid 
        283s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog21 test_ail_cpython_hybrid 
         33s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog21
         19s bash   cat > /tmp/probes/run_hy.py <<'PY' import json, os, subprocess, sys, glob from pathlib import Path root = Path
         19s bash   cd /tmp/probes && cat > p_boolabs2.py <<'PY' def abs_bool(x: bool) -> int:     return abs(x)  def abs_bool_ass
         17s bash   cd /tmp/probes && cat > p_abs_after_int_bool.py <<'PY' def f(x: bool) -> int:     return abs(int(x))  def main
         17s bash   cd /tmp/probes && for f in p_abs_bool.py p_abs_bool_assign.py p_abs_bool_uadd.py p_abs_bool_usub.py p_abs_neg_
         16s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/probes/run_hy.py $PWD

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change really does (one line):** it only tightens the hybrid safety proof in `AIL_CURRENT/ail_cpython_hybrid.py`: `abs` of a bool-typed parameter (direct, assigned, `+x`, `-x`) is now refused, while `abs(int(...))`, `int(bool)`, and `str(bool)` remain accepted; test/docs/manifest updated. No codegen touched.

**Last review's defect — fixed.** `/tmp/rprobes/rv01_abs_bool.py` (direct + assigned) and `rv02_abs_bool_forms.py` (`abs(+x)`, `abs(-x)`, `abs(True)`, `abs(False)`): HEAD hybrid refuses every bool-`abs` clone with `a call can raise or have side effects` and prints `1 0 ...` matching CPython. Base hybrid accelerated them and printed `True False ...`, reproducing the reported defect. `abs(int(x))` still accelerates (`rv02` `e`).

**Boundaries probed** (hybrid HEAD vs CPython, all SAME; all `cmp.sh` general/default builds also SAME):
- `rv01` bool abs direct/assign; `rv02` bool literal and `+`/`-` forms; `rv03` int/float abs (`INT64_MAX`, `-0.0`, `-inf`); `rv04` bool passed to an int `abs` helper; `rv05` bool via attribute/list item/dict value; `rv06` abs of int with bool return annotation; `rv07` `str(bool)`, `int(bool)`, `str(+bool)`; `rv09` int `abs(-x)`, `abs(+x)`, `abs(abs(x))`; `rv13` bool-returning bool abs; `rv14` `int(abs(bool))` now refused (was accelerated on base; safe fallback, output correct).
- No-feature programs: `rv08` and ten `lab/compare/src/*/main.ail` `program.c` are byte-identical HEAD vs base (`--debug-dir`). `rv03`/`rv08` default-build C also identical.
- Eight prog21 programs: acceleration sets identical HEAD vs base (e.g. `g22_022.shift_and_add_multiply` still accelerated); no-input stdout/exit match on both.

**Claims checked:** fixed defect (verified); `abs(int(x))/int(bool)/str(bool)` still accelerate (verified); regression test present and `test_ail_prog21` passes (verified); 5/5 modules pass `-j 2` (verified); `update_manifest.py --check` rc 0 (verified); commit `a00041d`, no codegen change (verified); `abs` probe set matches (verified for the analogous shapes I wrote).

**Pre-existing (identical on base, does not block):**
- `/tmp/rprobes/rv11_int_neg_bool.py`: in a bool-parameter int-returning clone, `return int(-x)` and `return -x` give CPython `-1 0 -1 0` but HEAD hybrid `-1 0 True False`. Same acceptance and output on base; general/default builds match CPython. Not caused by this change.

**Unverified:** speed (not measured; no generated-code change), full suite (not run by design), the eight programs with non-empty stdin (no-input acceleration sets unchanged).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 768967, "input": 91379, "output": 6550, "reasoning": 9278, "cache.write": 0, "cache.read": 661760}]
    tool time: bash 11.2 min
        282s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog21 test_ail_cpython_h
        110s bash   cd /tmp/rprobes && cat > run8.py <<'PY' import json, os, subprocess, sys, shutil from pathlib import Path root
         81s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir dbg_head dbg_base && for t in berth_sim chain_relax echo_pack led
         42s bash   cd /tmp/rprobes && cat > rv14_int_abs_bool.py <<'PY' def f(x: bool) -> int:     return int(abs(x))  def main()
         40s bash   cd /tmp/rprobes && cat > rv13_abs_bool_retbool.py <<'PY' def f(x: bool) -> bool:     return abs(x)  def g(x: b
         38s bash   cd /tmp/rprobes && cat > rv11_int_neg_bool.py <<'PY' def f(x: bool) -> int:     return int(-x)  def g(x: bool)
         30s bash   cd /tmp/rprobes && cat > rv09_abs_int_sign.py <<'PY' def a(x: int) -> int:     return abs(-x)  def b(x: int) -
         16s bash   cd /tmp/rprobes && python3 run_hy.py /tmp/base 2>&1 | tail -40

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T07:28:25Z
