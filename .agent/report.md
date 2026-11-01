# job job-lazymod1-11020209  started 2026-11-01T17:20:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `746e101`.

- Review defect: raising non-subscript earlier bindings (`SIZE = 1 // Z`, `SIZE = 1 + T`) are now refused by name instead of raising at program start. Local single-return helper calls are folded so existing computed-value cases (`N = make(); SIZE = 1 << N`) still work.
- Added a 3-program refusal test to `test_ail_lazymod1`.
- Probes on both builds: 6 safe cases match CPython; 8 raising cases refused by name (`p_div_unfold`, `p_binop_unfold`, `p_mod_unfold`, `p_shift_unfold`, `p_pow_unfold`, `p_compare_unfold`, `p_unary_unfold`, `p_call_arg_raise`).
- Tests: `test_ail_lazymod1 test_ail_modsys test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 5/5 ok, 0 failed.
- `update_manifest.py --check`: clean. All 10 `lab/compare/src/*/main.ail` still return `None` from `merge_program`, so their C is unchanged.
[cost $0.0000, opencode tokens {"total": 3010213, "input": 92022, "output": 10321, "reasoning": 22878, "cache.write": 0, "cache.read": 2884992}]
    tool time: bash 6.1 min, edit 0.0 min
        319s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_lazymod1 test_ail_
         27s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 -m unittest test_ail_lazymod1 -v 2>&1 | 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_safe_shift p_safe_default_arg p_safe_earlier p_safe_neg_empty
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && for p in p_div_unfold p_bino
          1s bash   mkdir -p /tmp/probes && cat > /tmp/probes/cmpdir.sh <<'SH' #!/bin/bash # cmpdir.sh DIR WORKTREE: run DIR/main.
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 -m unittest test_ail_lazymod1.EffectfulV
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git rev-list --count HEAD && git show --stat HEAD | head -60 && ls AIL_C

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — lazymod1 (work..746e101)

**What the change really does:** during a lazy module split it now folds calls to *any* single-`return` local function (including imported ones), and `raising_bad_expr` refuses unfoldable `BinOp`/`UnaryOp`/`Compare`/f-string/subscript module-level bindings.

**Prior review defect:** fixed. `p_div_unfold` and `p_binop_unfold` are refused by name on both HEAD builds (CPython prints `calling\nbefore\n`, exit 1); base refused too.

**New defect (introduced; base refuses):**
1. `fold_function_call` folds a function imported from another module using the *caller's* namespace (`child = env.new_child()` at `ail_modules.py:1515`), ignoring `owner`. A same-named caller global can make an actually raising helper look safe, so the binding is hoisted and the exception fires at program start, losing earlier stdout.
   Probe `/tmp/rprobes/p_xmod_raise2`:
   - `other.py`: `X = 0`; `def make(): return 1 // X`
   - `lib.py`: `print("before")`; `from other import make`; `X = 1`; `print("mid")`; `SIZE = make()`; `def f(a=SIZE): return a`
   - `main.py`: `import lib` inside `g()` after `print("calling")`.
   Expected CPython: stdout `calling\nbefore\nmid\n`, `ZeroDivisionError`, exit 1. Base: compile-time refusal by name. Actual HEAD (both builds): stdout empty, `ZeroDivisionError`, exit 1.

**Claims:** refusal probes (8) verified on both builds; safe probes (`p_safe_*`, 6) match CPython on both builds; manifest `--check` clean; all 10 `lab/compare/src/*/main.ail` still return `None` from `merge_program`. The claim that only "local" helpers are folded is false: imported helpers are folded too, which is the defect above.

**Tests:** `test_ail_lazymod1 test_ail_safetynet test_ail_modsys test_ail_files test_ail_corpus_findings3` — 5/5 ok, 0 failed.

**Unverified:** speed (change is compile-time only); C byte-diff for non-feature programs beyond lab/compare.

VERDICT: FIX
1. Cross-module helper folding uses the caller's env, so `/tmp/rprobes/p_xmod_raise2` loses `calling\nbefore\nmid\n` and raises at program start on HEAD (empty stdout, exit 1) while CPython prints those three lines before `ZeroDivisionError`; base refused by name. Fold only functions owned by the module being split, or evaluate the body with the owner module's env.
[cost $0.0000, opencode tokens {"total": 1704322, "input": 79281, "output": 5409, "reasoning": 32816, "cache.write": 0, "cache.read": 1586816}]
    tool time: bash 6.3 min
        193s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        154s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ai
         16s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in p_safe_shift p_safe_default_arg p_safe_earlier p_safe_neg_e
          5s bash   cd /tmp && mkdir -p rprobes/p_posonly rprobes/p_posonly_rebind cat > rprobes/p_posonly_rebind/lib.py <<'PY' pr
          4s bash   date; cd /home/runner/work/ail-ci/ail-ci; for d in p_stale_list p_stale_dict p_stale_attr p_safe_helper p_div_
          2s bash   cd /tmp && mkdir -p rprobes/p_xmod_raise cat > rprobes/p_xmod_raise/other.py <<'PY' X = 0 def make():     retu
          2s bash   cd /tmp && mkdir -p rprobes/p_xmod_raise2 cat > rprobes/p_xmod_raise2/other.py <<'PY' X = 0 def make():     re
          1s bash   cd /tmp && mkdir -p rprobes/p_globals_rebind cat > rprobes/p_globals_rebind/lib.py <<'PY' print("before") X = 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `bca79f2`.

- Defect: imported helpers were folded with the caller's namespace. `fold_function_call` now folds only functions owned by the split module; imported functions/classes are treated as unsafe instead of analyzed in the caller's env.
- Probes: all `/tmp/probes` and `/tmp/rprobes` cases (28) on both builds — safe cases match CPython, raising cases refused by name. Added `p_xmod_raise3` (no `print("mid")`), also refused; `p_xmod_safe` is refused by name.
- Tests: `test_ail_lazymod1 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 4/4 ok, 0 failed; `test_ail_modsys` — 1/1 ok.
- `update_manifest.py --check`: clean. All 10 `lab/compare/src/*/main.ail` still return `None` from `merge_program`.
- Added a two-program regression test and a DEVLOG entry.
[cost $0.0000, opencode tokens {"total": 2395407, "input": 53844, "output": 6638, "reasoning": 15949, "cache.write": 0, "cache.read": 2318976}]
    tool time: bash 5.2 min, edit 0.0 min
        238s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_lazymod1 test_ail_
         44s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_modsys 2>&1 | tail
         24s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probe_all.log; for p in /tmp/probes/p_* /tmp/rprobes/p_*; do n=
          2s bash   cd /tmp/base && for p in p_xmod_raise3 p_xmod_safe; do echo "##### $p BASE"; timeout 300 bash /tmp/probes/cmpd
          2s bash   cd /home/runner/work/ail-ci/ail-ci && echo "### HEAD xmod2" && timeout 300 bash /tmp/probes/cmpdir.sh /tmp/rpr
          1s bash   mkdir -p /tmp/rprobes/p_xmod_raise3 /tmp/rprobes/p_xmod_safe && cat > /tmp/rprobes/p_xmod_raise3/other.py <<'P
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /tmp/base && echo "### BASE xmod2" && timeout 300 bash /tmp/probes/cmpdir.sh /tmp/rprobes/p_xmod_raise2 "$P

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — lazymod1 (work..bca79f2)

**What the change really does:** folds calls to single-`return` helpers owned by the split module so their values count as known, refuses unfoldable `BinOp`/`UnaryOp`/`Compare`/f-string/subscript module statements as raising, and stops folding/analysing helpers or classes owned by another module.

**Prior review defect — fixed.** `p_div_unfold` and `p_binop_unfold` are now refused by name on both builds (`function-level import lib ...`), instead of raising at program start. (`/tmp/base` actually also loses the output on these two, so the original claim "base matches CPython" was false, but HEAD now refuses safely.)

**New defect (introduced; base refuses, HEAD is wrong)**
`fold_function_call` treats a helper call as a constant computed from the analysis env, so `need_name` sees an immutable value and hoists the binding past an effectful statement that changes what the helper reads.

`p_helper_effect/lib.py`:
```python
print("before")
N = 0
def bump():
    global N
    N = 5
def make():
    return N
bump()
SIZE = make()
def f(a=SIZE):
    return a
```
CPython: `calling\nbefore\n5\n`, exit 0. HEAD (g and d): `calling\nbefore\n0\n`, exit 0. Base: refused by name.

`p_helper_effect_raise/lib.py` (same but `N=1`, `bump` sets `N=0`, `make` returns `1 // N`):
CPython: `calling\nbefore\n` + `ZeroDivisionError`, exit 1. HEAD (g and d): `calling\nbefore\n1\n`, exit 0. Base: refused by name. The hoisted call runs before `bump()`, so both the value and the exception order differ.

**Pre-existing (not blocking):** `p_default_capture` (helper default captured at def time) gives empty stdout + `ZeroDivisionError` on both base and HEAD; `p_comp_elt` is wrong on base and now refused on HEAD. `p_comp_iter`, `p_posonly_kw`, `p_dup_arg` are refused on both.

**Checks:** `test_ail_lazymod1 test_ail_safetynet` 2/2 ok, 0 failed (153s). `update_manifest.py --check` exit 0. All 10 `lab/compare/src/*/main.ail` still return `None` from `merge_program`. Worker claims about imported helpers (`p_xmod_raise*`, `p_xmod_safe` refused) verified.

**Unverified:** worker's full 28-probe set; `test_ail_files` and `test_ail_corpus_findings3` not re-run.

VERDICT: FIX
1. Local-helper folding hoists a binding above an effect that changes the value the helper reads (probes `/tmp/rprobes/p_helper_effect`, `/tmp/rprobes/p_helper_effect_raise`). Expected `calling\nbefore\n5\n` / `calling\nbefore\n` + `ZeroDivisionError` exit 1; actual HEAD (both builds) `calling\nbefore\n0\n` exit 0 and `calling\nbefore\n1\n` exit 0. Base refuses both by name. A folded helper value must not be treated as position-independent: keep the effectful-range check unless the call's result is provably independent of mutable state (or refuse such earlier bindings by name).
[cost $0.0000, opencode tokens {"total": 1580784, "input": 97100, "output": 6145, "reasoning": 28451, "cache.write": 0, "cache.read": 1449088}]
    tool time: bash 3.0 min, write 0.0 min
        154s bash   cd /home/runner/work/ail-ci/ail-ci && ls tools/par_check.py AIL_CURRENT/test_ail_lazymod1.py 2>&1; date; cd AI
          7s bash   cd /tmp/base && date; for p in p_comp_iter p_comp_elt p_default_capture p_posonly_kw p_dup_arg; do echo "#####
          6s bash   cd /tmp/base && date; for p in p_div_unfold p_binop_unfold p_xmod_raise p_xmod_safe; do echo "##### $p BASE"; 
          5s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in p_comp_iter p_comp_elt p_default_capture p_posonly_kw p_d
          3s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in p_helper_effect p_helper_effect_list; do echo "##### $p H
          2s bash   cd /home/runner/work/ail-ci/ail-ci && date; echo "##### p_helper_effect_raise HEAD"; timeout 300 bash /tmp/pro
          2s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 bash /tmp/probes/cmpdir.sh /tmp/rprobes/p_helper_effect "$PW
          2s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in p_div_unfold p_binop_unfold p_xmod_raise p_xmod_raise2 p_

FINAL VERDICT: FIX  2026-11-01T18:10:03Z
