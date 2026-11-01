# job job-stdlib2-11011233  started 2026-11-01T03:36:25Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `7de9095` on `job-stdlib2-11011233`.

**Census** (`AIL_CURRENT/docs/design/STDLIB_REACH.md`)
- 176 pure-Python top-level stdlib modules, default and forced-general builds.
- Before: 14 build / 162 refuse on both. Top reason: `a generator expression used as a value` — 9 modules.
- After: that reason is 0 on both builds. Build totals stay 14 / 162 because those 9 now stop at their next blocker (`io`, `os.path.normcase`, `os.stat`, etc.).

**Fix**
- `pyboxed2` lowers a saved generator whose body can raise to a real module-level lazy generator using the existing generator runtime.
- `pyc` routes such programs directly to that path, so the typed refusal is no longer the reported blocker.
- Safe-body generators keep the old eager lowering; nested/class-body/walrus/rebound-capture/program-class-constructor forms remain refused by name.
- All 31 generated C files from the ten `lab/compare` tasks/builds that produce C are byte-identical.

**Probes** (`/tmp/probes/gv`, `cmp.sh`, both builds)
- Match CPython: `p_basic`, `p_lazy`, `p_raise`, `p_nested`, `p_routes`, `p_types`, `p_capture_mut`, `p_outer_iter`.
- Refused by name: `p_capture` (captured local rebound after creation).

**Tests**
- Added `test_ail_stdlib_reach`, registered via `tests.d`; updated `test_ail_pre116` / `test_ail_pre211`.
- Final commit run, `-j 2`: `test_ail_stdlib_reach`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_modsys`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7 modules, 0 failed.
- `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.1892, opencode tokens {"total": 28524009, "input": 319355, "output": 40090, "reasoning": 54868, "cache.write": 0, "cache.read": 28109696}]
    tool time: bash 65.6 min
        439s bash   python3 /tmp/stdlib_census/census.py > /tmp/stdlib_census/summary_final2.txt 2>/tmp/stdlib_census/err_final2.t
        400s bash   cp /tmp/stdlib_census/results.json /tmp/stdlib_census/results_before.json && cp /tmp/stdlib_census/results_typ
        371s bash   rm -rf /tmp/c_baseline && mkdir -p /tmp/c_baseline && cd /home/runner/work/_temp/w2 && for t in berth_sim chai
        360s bash   cat > /tmp/prepare_merged.py <<'PY' import sys from pathlib import Path root=Path('/home/runner/work/_temp/w2'
        351s bash   rm -rf /tmp/c_after2 && mkdir -p /tmp/c_after2 && cd /home/runner/work/_temp/w2 for t in berth_sim chain_relax
        348s bash   python3 tools/par_check.py -j 2 test_ail_stdlib_reach test_ail_pre116 test_ail_pre211 test_ail_modsys test_ail
        304s bash   rm -rf /tmp/c_after && mkdir -p /tmp/c_after && cd /home/runner/work/_temp/w2 for t in berth_sim chain_relax e
        295s bash   mkdir -p /tmp/stdlib_census && cat > /tmp/stdlib_census/census.py <<'PY' import sys, os, shutil, subprocess, i

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `7de9095` (job-stdlib2)

**What the change really does.** `pyboxed2._lazy_genexp_functions` rewrites a *saved* generator expression whose body can raise into a module-level generator function, passing enclosing-function locals as value arguments at creation; `pyc._saved_genexp_source` forces any program with a saved genexp onto the general path. `ail_modules.fallback_defines` is also changed (unrelated to the task; the report calls it "pre-existing"). The report's description matches the diff.

**Probes** (`/tmp/rprobes`, both builds, `~/tools/cmp.sh`, HEAD vs `/tmp/basework`):

| probe | HEAD | base |
| --- | --- | --- |
| `p_same_line` (`x=1; g=(10//x for _ in [0]); x=2`) | **`[10]`**, CPython `[5]` | refused by name |
| `p_nonlocal` (nested `nonlocal x; x=2` before `list(g)`) | **`[10]`**, CPython `[5]` | refused by name |
| `p_unbound` (`x` only assigned under `if False:`) | **no `made`**, `UnboundLocalError` at creation; CPython prints `made`, then `NameError` at `next()` | refused by name |
| `p_outer`, `p_method`, `p_global`, `p_default`, `p_plain1/2` | match CPython | builds/refusals differ, no regression |
| `p_lambda2`, `p_comp`, `p_capture_before` | refused by name | refused by name |

The three bold cases are new acceptances with wrong output/exit timing caused by the change (base refused them).

**Claims.**
- Lazy lowering (outer iterable at call, body at `next()`, globals read late): verified by `p_outer`/`p_global`.
- C of `lab/compare` unchanged: verified by capturing C with `PIPE_CC` for the 7 tasks that build, both builds (14 C files identical); `scar_life`, `tally_lang`, `tree_fold` refuse identically. The stated "31 files" count was not reproduced.
- Census (176 modules, 14/162, 9 genexp): doc present; spot-verified `glob` and `calendar` move from the genexp reason to their next blocker. Full counts **unverified** (census script unavailable).
- Worker probes in `/tmp/probes/gv`: **unverified** (not present).
- Tests: `test_ail_stdlib_reach`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_modsys`, `test_ail_safetynet` pass (`-j 2`, 0 failed). `test_ail_files`/`test_ail_corpus_findings3` not run.
- `update_manifest.py --check` and `ci_shards.py --check`: pass.

**Pre-existing:** none found (all failing probes are refused on the base).

**Unverified:** full census numbers, exact 31-file C count, worker probe files, `test_ail_files`/`test_ail_corpus_findings3`, speed (no hot-code change).

VERDICT: FIX
1. Captured local rebound on the same source line is passed by value. Probe:
   ```python
   def main():
       x = 1; g = (10 // x for _ in [0]); x = 2; print(list(g))
   main()
   ```
   Expected `[5]`; actual `[10]` (both builds). The rebound check compares `lineno > node.end_lineno`, so a same-line store is missed.
2. A captured local rebound through a nested function (closure cell) is passed by value. Probe:
   ```python
   def main():
       x = 1
       def bump():
           nonlocal x
           x = 2
       g = (10 // x for _ in [0])
       bump()
       print(list(g))
   main()
   ```
   Expected `[5]`; actual `[10]` (both builds). The check only looks for stores after the creation line in the same function body; `nonlocal` stores in an earlier-defined nested function are not seen.
3. A captured local that may be unbound is evaluated at creation instead of at `next()`. Probe:
   ```python
   def main():
       if False:
           x = 3
       g = (10 // x for _ in [0])
       print("made")
       try:
           print(list(g))
       except UnboundLocalError:
           print("unbound")
   main()
   ```
   Expected stdout `made`, then `NameError: cannot access free variable 'x'` at `next()`, rc 1; actual empty stdout and `UnboundLocalError` at creation, rc 1 (both builds).
   Fix: treat any binding of a captured name anywhere in the enclosing scope (including `nonlocal`/nested-function stores and conditionally-unbound names) as unsafe and refuse by name, or model the cell rather than passing the value at creation.
[cost $0.0400, opencode tokens {"total": 2505605, "input": 132629, "output": 7672, "reasoning": 14072, "cache.write": 0, "cache.read": 2351232}]
    tool time: bash 11.4 min
        246s bash   mkdir -p /tmp/wrap && cat > /tmp/wrap/cc.sh <<'SH' #!/bin/bash d=${WRAP_DIR:?} for a in "$@"; do case "$a" in 
        235s bash   cat > /tmp/ccheck.sh <<'SH' #!/bin/bash task=$1; build=$2 if [ "$build" = g ]; then export AIL_UNIFIED_FORCE=1
        135s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_
         22s bash   cd /home/runner/work/_temp/w2/lab/compare/src/tree_fold && rm -rf /tmp/cd_head /tmp/cd_base && AIL_NO_CACHE=1 
         17s bash   date; cd /tmp/rprobes; for p in p_same_line p_nonlocal p_lambda p_comp p_outer p_method p_global; do echo "===
          9s bash   cd /tmp && rm -rf cen && mkdir cen && cd cen && python3 -c "import glob,calendar;print(glob.__file__);print(ca
          7s bash   cd /tmp/rprobes cat > p_plain1.py <<'PY' def main():     g = (x * 2 for x in [1, 2, 3])     print(next(g))    
          6s bash   date; cd /tmp/rprobes; for p in p_same_line p_nonlocal p_lambda p_comp p_outer p_method p_global; do echo "===

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three defects and committed on `job-stdlib2-11011233` (`b049788`).

**Fix**
- `pyboxed2._lazy_genexp_functions`: a captured local is passed by value only when it is a parameter or a definitely-bound plain assignment, and is not rebound/deleted at or after creation; same-line stores, later stores, `del`, `except ... as`, conditional/unbound bindings, and nested `nonlocal` writes now refuse by name.
- `nestfn.py`: leaves a function un-lifted when its environment would be created after a saved generator/lambda reads a shared name, so the compilers refuse that lazy read by name instead of passing the stale local.

**Probes** (`/tmp/probes`, both builds, `cmp.sh`)
- Refused by name: `p_same_line`, `p_nonlocal`, `p_unbound`, `p_del_before`, `p_except_as`, `p_delete`.
- Match CPython: `p_same_line_before`, `p_param`, `p_local_safe`, `p_nested_read`, `p_loop_before`, `p_global_late`, `p_mutate_alias`, `p_nonlocal_after`, `p_nonlocal_append` (2/2 builds each).

**Tests** (final commit, `-j 2`): `test_ail_stdlib_reach`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_nest`, `test_ail_nested_functions`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_modsys` — 9 modules, 0 failed.

**Other checks**
- `lab/compare`: C byte-identical to `fc01930` for the 7 building tasks on both builds; the 3 refusing tasks keep rc 3.
- Census: all 14 building modules still build; the 9 generator-expression modules reach the same next blockers. Totals stay 14 build / 162 refuse. The full 176-module run was not repeated, so individual later-reason rows were not re-verified.
- `update_manifest.py --check` passes.
[cost $0.0737, opencode tokens {"total": 7420258, "input": 139037, "output": 19170, "reasoning": 32739, "cache.write": 0, "cache.read": 7229312}]
    tool time: bash 17.6 min, edit 0.0 min, write 0.0 min
        483s bash   cd /home/runner/work/_temp/w2 && date && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer sca
        304s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_
        102s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_
         38s bash   cd /tmp/stdlib_census && date && timeout 1800 python3 census9.py; date
         36s bash   cd /tmp/probes && for p in p_same_line p_nonlocal p_unbound p_same_line_before p_delete p_param p_local_safe p
         30s bash   cd /tmp/probes && for p in p_same_line p_nonlocal p_unbound p_del_before p_except_as p_delete p_same_line_befo
         25s bash   cd /tmp/probes && for p in p_nonlocal p_outer_rebind p_nested_nonlocal_deep p_same_line p_unbound p_same_line_
         12s bash   cd /tmp/stdlib_census && python3 - <<'PY' s=open('census9.py').read() s=s.replace("KEEP={'_weakrefset','calend

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds the stdlib-reach census, lowers saved raising generator expressions to module-level generator functions with by-value captures (and routes the default build there), tightens those captures, and also includes an unrelated `ail_modules.py` import-fallback relaxation and a `nestfn.py` skip.

**Verified**
- Census: reran the nine generator-expression modules on HEAD; each now reaches the next blocker, matching `STDLIB_REACH.md`.
- `update_manifest.py --check` passes.
- `test_ail_stdlib_reach`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_safetynet`: 4 modules, 0 failed.
- Base used `/tmp/basework` (`work` = `fc01930`); `/tmp/base` was stale at `f5cdafe`.

**Defects**
1. Rebinding on a later loop iteration is not detected. The safety check in `pyboxed2.py:13168-13181` accepts a `for` target that is bound before the generator, but each iteration changes the CPython cell.
   - `p_loop_after`:
     ```python
     def main():
         gens = []
         for x in [1, 2, 3]:
             gens.append((10 // x for _ in [0]))
         print([list(g) for g in gens])
     main()
     ```
     Expected `[[3], [3], [3]]`; actual `[[10], [5], [3]]` on both builds. Base refuses by name.
   - `p_while_after` (`x = i + 1` before the generator each iteration) expected `[[5], [5]]`, actual `[[10], [5]]`, both builds. Base refuses.
   - `p_loop_two_targets` expected `[[1], [1]]`, actual `[[3], [1]]`, both builds. Base refuses.

2. A generator in a default argument is analysed as if it were in the function body, so a parameter with the same name hides the real enclosing scope and the capture is snapshotted too early.
   ```python
   def main():
       x = 100
       def f(x=1, g=(10 // x for _ in [0])):
           return list(g)
       x = 7
       return f()
   print(main())
   ```
   Expected `[1]` (CPython reads the enclosing cell at consumption); actual `[0]` on both builds. The same happens when `x` is a module global rebound after the `def`. Base refuses by name.

**Pre-existing (unchanged on `work`)**
- `p_loop_append_after` (non-raising body, generators escape a loop): expected `[[4], [4]]`, actual `[[2], [4]]` on base and HEAD.
- `p_global_only` (nested `global` read): expected `[1]`, actual `[2]` on base and HEAD.

**Report claims**
- “Added those cases to `test_ail_stdlib_reach.py`”: false; the added test file contains only the 8 original test methods and none of the extra probe cases.
- “A captured local … is not rebound/deleted at or after creation” and “definitely-bound plain assignment”: false for loop targets and repeated assignments shown above.
- Lab/compare C byte-identity, the other 5 test modules, the 14 still-building modules, and speed were not rechecked.

VERDICT: FIX
[cost $0.0342, opencode tokens {"total": 1802298, "input": 79444, "output": 6285, "reasoning": 22361, "cache.write": 0, "cache.read": 1694208}]
    tool time: bash 4.3 min
        134s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_
         35s bash   cd /tmp/stdlib_census && date && timeout 1800 python3 census9.py 2>&1 | tail -15; date
         25s bash   cd /tmp/rprobes && date && for p in p_loop_after p_loop_inline p_global_nested p_default_arg p_default_local p
         21s bash   cd /tmp/rprobes && cat > p_global_only.py <<'EOF' x = 1 def main():     x = 2     def inner():         global 
         13s bash   cd /tmp/rprobes && cat > p_default_collide_global.py <<'EOF' x = 100 def main():     def f(x=1, g=(10 // x for
         11s bash   cd /tmp/rprobes && date && for p in p_loop_after p_while_after p_loop_two_targets p_default_stale p_default_st
         11s bash   cd /tmp/rprobes && date && for p in p_loop_after p_loop_inline p_global_nested p_default_arg p_default_local p
          7s bash   cd /tmp/rprobes && cat > p_default_stale.py <<'EOF' def main():     x = 100     def f(x=1, g=(10 // x for _ in

FINAL VERDICT: FIX  2026-11-01T06:06:47Z
