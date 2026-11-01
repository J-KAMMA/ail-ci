# job job-std_numbers-11020343  started 2026-11-01T18:43:48Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `160550f`.

**Fixes**
- `register` is now a virtual runtime registration: timing/control flow respected, returns the class, adds no base, and covers subclasses.
- Registered classes no longer inherit `real` / `imag` / `conjugate`.
- `issubclass(UserClass, numbers.X)` now checks the runtime table.
- Parameter shadowing of a from-imported ABC, registration before the class definition, and combined register decorators are named compile-time refusals.

**Probes** (`/tmp/probes/rev_*.py`, both `cmp.sh` builds)
- Match CPython: registration order, uncalled function, `if False`, method/function call, registration twice, subclass, `issubclass` timing, decorator, return value, values via argument/list/attribute/dict, virtual-attribute absence.
- Refused by name: parameter shadowing, early registration, register decorator with another decorator, non-name registration target.

**Verification**
- `test_ail_std_numbers`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass (362s); `test_ail_std_numbers` re-run after adding regressions (277s).
- `update_manifest.py --check`: clean.
- No `lab/compare` source imports `numbers`, so their generated C is unchanged.
[cost $0.0000, opencode tokens {"total": 6950470, "input": 85486, "output": 17831, "reasoning": 33841, "cache.write": 0, "cache.read": 6813312}]
    tool time: bash 20.3 min, edit 0.0 min, read 0.0 min
        401s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_numbers test_ail_safetynet 
        363s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_numbers test_ail_safetynet 
        277s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_numbers
         34s bash   cd /tmp/probes && for p in rev_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail
         34s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > rev_reg_order.py <<'EOF' import numbers class A: pass print(is
         26s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_std_numbers.NumbersLabTests.
         19s bash   cd /tmp/probes && for p in rev_reg_early.py rev_reg_early2.py rev_reg_early3.py rev_reg_order.py rev_reg_in_fu
         18s bash   cd /tmp/probes && cat > rev_values_paths.py <<'EOF' import numbers  class Money:     def __init__(self, n: int

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2
**Review report — job-std_numbers (work..HEAD, HEAD `160550f`)**

**What the diff really does.** It replaces the compile-time "add an ABC base" handling of `register` with a runtime virtual-registration table (`_ail_num_register`), moves `@numbers.X.register` to a registration call inserted after the class statement, makes `issubclass(UserClass, numbers.X)` a runtime lookup (`_ail_num_issubclass`), and turns early/non-name/parameter-shadowing cases into named refusals. Plus test regressions, DEVLOG/DIFFERENCES/RESULTS and manifest hashes. This matches the report except for the decorator helper gating bug below.

**Verified**
- Review defect 1 fixed: `rev_reg_order`, `rev_reg_cond`, `reg_in_cond` match CPython on both builds.
- Review defect 2 fixed: `rev_reg_virtual` prints `False False False` / `False False`; `reg_nonnum_base` now builds and matches (base refused it).
- Review defect 3 handled: `rev_param_shadow2` is refused by name (`binds the name Number itself`).
- Subclass coverage/timing/return/twice: `reg_sub_only`, `reg_then_subclass_after`, `reg_twice`, `isc_after_reg` match.
- Values via arg/list/dict/attribute: `reg_paths` matches.
- Early register, non-name target, double register decorators refused by name: `reg_early`, `reg_nonname`, `decorator_double`.
- `test_ail_std_numbers` + `test_ail_safetynet`: 2/2 pass (279 s). `update_manifest.py --check` rc=0.
- Non-numbers C unchanged: `program.c` byte-identical HEAD vs `/tmp/base` for a plain program (only `native_report.json` paths differ); `numberslib.run` returns early without `import numbers`.

**Defects**
1. A register decorator used without any `isinstance`/`issubclass`/`register` call fails to build, because the decorator branch inserts `_ail_num_register(...)` but never adds `'register'` to `used`, so `registry_helper` is emitted as `''`.
   Probe `/tmp/rprobes/decorator_only.py`:
   ```python
   import numbers
   @numbers.Real.register
   class A: pass
   @numbers.Number.register
   class B: pass
   print(A.__name__, B.__name__)
   ```
   Expected CPython rc 0, stdout `A B`. Actual both `cmp.sh` builds: compile rc 3, `not in the subset: the name '_ail_num_register' is not a known function/class/builtin`. `/tmp/base` builds it and prints `A B` (regression). Same for `decorator_attrs.py` (`@register` + `hasattr`) and `decorator_only3.py` (`@register` + ordinary use). Fix: `used.add('register')` in the decorator branch (or emit the registry helper whenever a registration expression was inserted).

**Pre-existing (identical on `/tmp/base`, not blocking)**
- `register_param_shadow.py`: a parameter named like the class is still statically registered (reversed booleans); identical on base.
- `reg_abc_base.py`: abstract ABC subclass can be instantiated (documented ABCMeta follow-up); identical on base.
- Class decorators are not applied at all (`plain_class_deco*`, `decorator_combined_attr`); unrelated to numbers, identical on base. Consequence: the report's "register decorator combined with another decorator is refused" is only true for two *register* decorators (`decorator_double`); a non-register class decorator is stripped earlier, so `decorator_plus_other` builds.

**Unverified.** `test_ail_files` and `test_ail_corpus_findings3` not re-run (outside the targeted scope); speed not measured (only programs importing `numbers` are affected; no hot-path change).

VERDICT: FIX
1. Decorator-only registration is broken by helper gating: `/tmp/rprobes/decorator_only.py` expected stdout `A B` (rc 0), actual compile rc 3 `not in the subset: the name '_ail_num_register' is not a known function/class/builtin` on both builds; `/tmp/base` prints `A B`. Add `used.add('register')` in the decorator lowering branch.
[cost $0.0000, opencode tokens {"total": 1318355, "input": 30444, "output": 7189, "reasoning": 20946, "cache.write": 0, "cache.read": 1259776}]
    tool time: bash 8.5 min
        280s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 840 python3 tools/par_check.py -j 2 test_ail_std_numbers test_ai
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup python3 tools/par_check.py -j 2 test_ail_std_numbers test_ail_safe
         35s bash   cd /tmp/rprobes && for p in rev_reg_order rev_reg_cond rev_reg_virtual rev_param_shadow2 nested_subclass neste
         19s bash   cd /tmp/rprobes && for p in reg_cond_class reg_try_class reg_reassign reg_name_change isc_after_reg reg_abc_ba
         10s bash   cd /tmp/rprobes && for p in register_param_shadow rev_reg_order rev_reg_virtual; do echo "######## BASE $p"; t
         10s bash   cd /tmp/rprobes && for p in reg_nonnum_base reg_multi_inherit reg_then_subclass_after; do echo "######## $p"; 
          6s bash   cd /tmp/rprobes && for p in decorator_only decorator_only2; do echo "######## BASE $p"; timeout 150 bash ~/too
          5s bash   cd /tmp/rprobes && cat > decorator_attrs.py <<'EOF' import numbers  @numbers.Real.register class Money:     pa

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed review defect 1: decorator-only registration now marks `register` as used, so the runtime helper is emitted. Added a decorator-only regression case.

Probes: `decorator_only`, `decorator_attrs`, `decorator_only3`, `decorator_only_isc`, `decorator_plus_other`, `rev_reg_order`, `rev_reg_cond`, `rev_reg_virtual` all match CPython on both builds; `decorator_double` remains refused by name. `decorator_combined_attr` still differs, but that is the pre-existing class-decorator limitation noted in the review.

Tests: `test_ail_std_numbers`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` = 4/4 pass (375s); `update_manifest.py --check` rc=0.

Committed as `9c67b05`.
[cost $0.0000, opencode tokens {"total": 530824, "input": 17464, "output": 3063, "reasoning": 2009, "cache.write": 0, "cache.read": 508288}]
    tool time: bash 7.1 min, edit 0.0 min
        376s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1700 python3 tools/par_check.py -j 2 test_ail_std_numbers test_a
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/decorator_*.py /tmp/rprobes/rev_reg_*.py; do echo 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in decorator_only decorator_attrs decorator_only3 decorator_only_i
          2s bash   cd /home/runner/work/ail-ci/ail-ci && for p in decorator_only decorator_attrs decorator_only3; do echo "===== 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1700 python3 tools/par_check.py -j 2 test_ail_std_numbers test_a
          0s bash   pwd && git status && git log --oneline -8 && ls

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Review report — job-std_numbers (work..HEAD, HEAD `9c67b05`)**

**What the diff does.** `work..HEAD` is two commits: `160550f` replaces compile-time `register` base injection with a run-time virtual table (including subclass names), moves `issubclass(UserClass, …)` to run time, refuses parameter shadowing of ABC names and early/combined-decorator registration; `9c67b05` adds `used.add('register')` so a decorator-only registration emits the helper. The report describes only the second commit; the first is also in the diff and fixes review 1's three defects.

**Verified claims.**
- Decorator-only fix: `decorator_only`, `decorator_attrs`, `decorator_only3`, `decorator_only_isc`, `decorator_plus_other` match CPython on both builds.
- Review 1 defects: `rev_reg_order`, `rev_reg_cond`, `rev_reg_virtual` match CPython on both builds; `rev_param_shadow2` is now a named refusal (acceptable).
- `decorator_double` refused (named note); `decorator_combined_attr` differs identically on base (pre-existing class-decorator limitation).
- My probes `rv_values` (argument/list/attribute/dict), `rv_kinds` (all five kinds and re-registration), `rv_deco_sub` (decorator then subclass), `rv_holder` (aliases/containers), `rv_isc_func` (uncalled vs called `issubclass`) all match on both builds; alias `issubclass` is a named refusal.
- Tests: `test_ail_std_numbers`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` = 4/4 pass (284s/169s). `update_manifest.py --check` rc=0.
- Non-`numbers` codegen: a non-numbers probe's `program.c` is byte-identical HEAD vs `/tmp/base`; only `native_report.json` paths differ. Diff scope confirms no compare/benchmark source changed.

**Pre-existing (identical on `/tmp/base`, do not block).**
- Parameter shadowing a user class name in a `register` target registers the top-level class (`register_param_shadow`: False/True vs CPython True/False).
- ABCMeta abstract-method instantiation check absent (`reg_abc_base`).
- Non-numbers class decorator combined with `@register` loses the decorator (`decorator_combined_attr`).
- Builtin-number subclasses refused by name (`rv_builtin_sub`).

**Unverified.** Speed: the new code runs only in programs importing `numbers`; no hot-path/benchmark source changed. Not all 10 compare tasks rebuilt (one arbitrary non-numbers program plus diff scope checked).

VERDICT: ACCEPT
[cost $0.0251, opencode tokens {"total": 1095554, "input": 60689, "output": 4465, "reasoning": 17152, "cache.write": 0, "cache.read": 1013248}]
    tool time: bash 11.2 min
        285s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1700 python3 tools/par_check.py -j 2 test_ail_std_numbers 
        170s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_files test_a
        117s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in $(cd /tmp/rprobes && ls r3_*.py reg_*.py isc_after_reg.py n
         33s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in r3_redef r3_redef2 reg_reassign reg_name_change r3_nestedsu
         28s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in rev_reg_order rev_reg_cond rev_reg_virtual rev_param_shadow
         19s bash   mkdir -p /tmp/rprobes; cd /tmp/rprobes cat > rv_values.py <<'EOF' import numbers class Money: pass class Sub(M
          7s bash   date; cd /tmp/base; for p in reg_abc_base register_param_shadow; do echo "===== $p on BASE"; timeout 90 bash ~
          5s bash   date; cat /tmp/rprobes/decorator_combined_attr.py; cd /home/runner/work/ail-ci/ail-ci; echo "===== HEAD"; time

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T21:16:09Z
