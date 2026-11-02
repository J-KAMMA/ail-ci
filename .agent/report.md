# job job-rbcovisin1-11021332  started 2026-11-02T04:32:59Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `18ede7a` on `job-rbcovisin1-11021332`.

- Re-applied `covisin1` diff; conflicts resolved keeping both fixes: the local-shadow refusal now applies only to names that shadow a class/builtin type, preserving the new runtime-`isinstance` support.
- `python3 tools/update_manifest.py` and `--check`: pass.
- `python3 tools/diff_ids.py`: not present anywhere in the repo, so it could not be run.
- Final-commit tests, all OK: `test_ail_covisin1` (17), `test_ail_tuples` (26), `test_ail_modconst` (26), `test_ail_py_typed_gaps` (9), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skip), `test_ail_corpus_findings3` (2), `test_ail_dunders` (11).
- Probes (`bash ~/tools/cmp.sh`, default + general): `p_isinst_runtime.py` match, `p_isinst_scope.py` match, `p_kwctor.py` match; `p_decorated_kw.py`, `p_isinst_shadow_class.py`, `p_isinst_builtin_runtime.py` refused by name on both builds.
[cost $0.0000, opencode tokens {"total": 2772656, "input": 76894, "output": 8612, "reasoning": 10798, "cache.write": 0, "cache.read": 2676352}]
    tool time: bash 11.5 min
        341s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && export AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible
        313s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && export AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible
         18s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && export AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_isinst_runtime.py /tmp/probes/p_isinst_scope.py /
          6s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-covisin1-11020842 2>&1 | tail -5
          2s bash   cat > /tmp/probes/p_isinst_scope.py <<'PY' class A: pass class B: pass K = A  def f(K):     print(isinstance(A
          0s bash   cd /home/runner/work/ail-ci/ail-ci && head -5 DEVLOG.md; echo ---; head -5 AIL_CURRENT/DEVLOG.md; echo ---; py
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo manifest_check=$?; git st

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Reviewer report.

**What the diff really does:** re-applies `covisin1` faithfully (18 files vs the fetched intended diff; only conflict-context and the retained base local-shadow guard differ). It adds runtime/ nested-tuple `isinstance` support, module type-constant expansion, and keyword construction through module-bound class names, plus its tests/DEVLOG/manifest.

**Report claims**
- Re-applied diff, conflict fix narrows local-shadow refusal: verified.
- `update_manifest.py --check`: verified (exit 0).
- `tools/diff_ids.py` absent: verified.
- Test counts: `test_ail_covisin1` has 17 methods; ran it plus `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_tuples`, `test_ail_modconst`, `test_ail_py_typed_gaps`, `test_ail_dunders` on HEAD (0 failed, ~6 min).
- Probe claims (runtime/scope/ctor match; shadow/decorated refusals): verified with equivalents.
- C unchanged for non-feature programs: two gdev programs (`g12_012`, `g12_030`) built byte-identical executables on HEAD and base.

**Pre-existing:** none found; the mismatches below are new (base refused by name).

**Unverified:** instruction counts — `perf_event_open` is denied in this runner.

**Defect**
1. Non-type values/elements in the `isinstance()` type argument are silently skipped instead of raising CPython's `TypeError`; this can even invert the answer.
   Probe `/tmp/rprobes/p_nontype_before_match.py`:
   ```python
   print(isinstance(1, (5, int)))
   print("after")
   ```
   Expected (CPython): empty stdout, exit 1, `TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union`.
   Actual HEAD (default and general): stdout `True\nafter`, exit 0.
   Base: named compile refusal (`isinstance() with a non-name type argument`).
   Same defect with a scalar/nested element or an argument: `print(isinstance(1, 5))` → HEAD `False\nafter`/exit 0; `def f(x,t): return isinstance(x,t); print(f(1,5))` → HEAD `False`/exit 0 (both CPython: TypeError/exit 1). The new `ail2_dyn_isinstance` returns 0 for any spec that is not `AIL_T_CLASS`/`AIL_T_TUPLE`, so non-class values must be refused at compile time or raise at run time.

VERDICT: FIX
1. Fix the non-type `isinstance` second argument handling described above (probe `p_nontype_before_match.py`: expected TypeError/exit 1, actual `True\nafter`/exit 0; also `p02_nontype_scalar.py`, `p_isinst_badtype.py`).
[cost $0.0540, opencode tokens {"total": 3989096, "input": 115973, "output": 9805, "reasoning": 32022, "cache.write": 0, "cache.read": 3831296}]
    tool time: bash 7.8 min
        207s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_covisin1
        155s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_tuples t
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p02_nontype_scalar p03_object_bytes p04_container_spec p07_kw_c
         19s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in p_kw_kwargs p_kw_basic p_isinst_empty p_isinst_nonname 
         11s bash   cd /tmp/perf && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$(basename $wt); for f in g12_012 
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_isinst_badtype p18_none_spec p21_isinstance_nonclass_name p32
          6s bash   cd /tmp/rprobes && cat > p_rebind_unrelated.py <<'PY' class A: pass class B(A): pass class C: pass A = C print
          4s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_kw_kwargs p_isinst_empty p_isinst_nonname p_call_para p_call_

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `4967cbc`.

**What changed**
- `ail2_dyn_isinstance` now raises CPython's `TypeError` for a non-type spec instead of returning false; nested tuple elements raise too.
- The generated check tests `cx->exc_pending` after a dynamic spec, preserving CPython short-circuit order.
- Restored named compile refusals for unsupported builtin/typing names (`object`, `complex`, ...), local shadowing of builtin type names, union/parameterised type expressions, and list/set/dict literal specs.
- Updated manifest pins and DEVLOG.

**Probes** (default + general; `bash ~/tools/cmp.sh`)
- `/tmp/probes/fix_isinst_valid.py`: both builds same stdout/exit 0 as CPython.
- `/tmp/probes/fix_isinst_bad.py`: both builds same stdout/exit 0 (covers scalar, `None`, list item, dict value, attribute, module global, argument, tuple/nested before/after match, empty tuples, caught `TypeError`).
- Review probes `p_nontype_before_match`, `p02_nontype_scalar`, `p_isinst_badtype`, `p14`, `p15`, `p18`, `p21`, `p32`, `p33`: exit 1 / same stdout on both builds.
- `p03_object_bytes`, `p17_list_spec`, `p23_union_spec`: compile-refused by name on both builds.

**Tests**
- Final commit required set: `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- Also on the same code tree: `test_ail_tuples`, `test_ail_modconst`, `test_ail_py_typed_gaps`, `test_ail_dunders`, `test_ail_class_reach` — 0 failed (`test_ail_class_reach` had been failing on the previous HEAD; it passes now).
- `tools/update_manifest.py --check`: exit 0.
[cost $0.0531, opencode tokens {"total": 3813116, "input": 105530, "output": 11565, "reasoning": 32277, "cache.write": 0, "cache.read": 3663744}]
    tool time: bash 27.4 min, edit 0.0 min
        452s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_class_re
        401s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_covisin1
        398s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "check exit $?"; cd AIL_C
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_tuples t
         55s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null && python3 tools/update_mani
         30s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null && python3 tools/update_mani
         23s bash   cat > /tmp/probes/fix_isinst_valid.py <<'PY' class A: pass class B(A): pass class Box: pass box = Box(); box.t
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_nontype_before_match p02_nontype_scalar p_isinst_badtype p01_

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the diff really does:** re-applies `covisin1` (module-bound class keyword construction and run-time/nested-tuple `isinstance`) and adds the review fix so a non-type `isinstance` spec raises CPython's `TypeError`; the report matches the diff.

**Claims checked**
- Re-applied diff: verified — file list matches the fetched intended diff; the only conflict change is retaining the base local-shadow guard.
- `ail2_dyn_isinstance` raises `TypeError` for scalar/`None`/nested tuple elements: verified.
- Generated check tests `cx->exc_pending` and preserves short-circuit order: verified.
- Named refusals restored (`object`, union, parameterised, list/set/dict, local shadow): verified.
- `update_manifest.py --check`: verified exit 0. `tools/diff_ids.py` absent: verified.
- Test claims: verified — `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_class_reach`, `test_ail_tuples`, `test_ail_modconst`, `test_ail_py_typed_gaps`, `test_ail_dunders`, 0 failed.

**Probes** (default + general; all match CPython or are refused by name)
- `z1_nested_order`: non-type before/after match and nested tuples — TypeError on both builds.
- `z2_values`: class through argument, list item, dict value, attribute — matches.
- `z3_builtin_values`: `int`/`str` as values and in a tuple — matches.
- `z4_rebind_catch`, `z5_catch_short`: caught `TypeError`, rebinding, short-circuit — matches.
- `z6_empty`, `z7_condclass`, `z8_delname`, `z10_star`, `z11_shadow_param`, `z12_object_var`: empty/nested-empty correct; unsupported forms refused by name.
- Worker probes `fix_isinst_valid.py`, `fix_isinst_bad.py`, and prior `p_*` probes — all match.
- Base `/tmp/base`: all dynamic-type probes are named compile refusals, so none of the above is pre-existing.

**No-feature C:** `g12_012` and `g12_030` generated C identical on HEAD and base (only `native_report.json` path metadata differed).

**Pre-existing:** none found.
**Unverified:** instruction counts (no hot-path change); wider suite (left to integrator).

VERDICT: ACCEPT
[cost $0.0359, opencode tokens {"total": 2531288, "input": 82486, "output": 7229, "reasoning": 19813, "cache.write": 0, "cache.read": 2421760}]
    tool time: bash 14.8 min
        459s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_covisin1
        257s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_tuples t
         30s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/cdbg_head /tmp/cdbg_base; for wt in /home/runner/work/ail-ci/a
         24s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/fix_isinst_valid.py /tmp/probes/fix_isinst_bad.py; do
         18s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_class_re
         17s bash   cd /home/runner/work/ail-ci/ail-ci; date; for f in p14_nontype_first p15_nontype_nested p18_none_spec p01_nont
         16s bash   cd /home/runner/work/ail-ci/ail-ci; for f in p03_object_bytes p17_list_spec p23_union_spec p21_isinstance_nonc
         15s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/z*.py; do echo "=== HEAD $(basename $f)"; bash ~/too

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T07:13:21Z
