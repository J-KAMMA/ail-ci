# job job-covisin1-11011014  started 2026-11-01T01:15:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed on `job-covisin1-11011014` as `d77d22b`.

- Module census: non-name `isinstance()` refusals went from 9/148 `pkg-v12` modules to 0.
- Added static handling for nested/empty tuples, module type constants, aliases and module attributes; general path handles run-time class/tuple specs via `ail2_dyn_isinstance`.
- Preserved side-effecting module assignments during type-constant expansion.
- Probes: 15 matching CPython on default + general builds, covering tuples/constants/attributes, subclasses, `bool` vs `int`, and values through arguments/list items/attributes/dict values. Three unrelated probes are refused by name on both builds; documented the remaining run-time builtin-type-value refusal.
- `lab/compare`: 10/10 AIL sources generate byte-identical C vs base; 7/10 CPython sources identical, with the other 3 refused identically by both trees.
- Final commit tests: 91 passed, 1 platform skip (`test_ail_covisin1`, `test_ail_tuples`, `test_ail_modconst`, `test_ail_py_typed_gaps`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`); `update_manifest.py --check` exits 0.
[cost $0.0668, opencode tokens {"total": 7919977, "input": 110600, "output": 17947, "reasoning": 26950, "cache.write": 0, "cache.read": 7764480}]
    tool time: bash 44.9 min
        700s bash   python3 /tmp/census_base/tools/fallback_census.py --jobs 2 --timeout 120 -o /tmp/census_base.jsonl $(ls /tmp/b
        582s bash   mkdir -p /tmp/census_cur/tools /tmp/census_base/tools cp lab/census/fallback_census.py /tmp/census_cur/tools/f
        532s bash   mkdir -p /tmp/testlogs; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT ( timeout 3600 python3 -m unittest -v t
        327s bash   cat > /tmp/cidcmp.sh <<'SH' #!/bin/bash set -u task=$1 src=/home/runner/work/ail-ci/ail-ci/lab/compare/src/$ta
        317s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT ( timeout 3600 python3 -m unittest -v test_ail_covisin1 test_ai
        100s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p_static_tuple p_constants p_runtime_classes p_builtin_runtime p_
         56s bash   cat > /tmp/cidcmp_ail.sh <<'SH' #!/bin/bash set -u task=$1 src=/home/runner/work/ail-ci/ail-ci/lab/compare/src
         29s bash   cat > /tmp/probes/p_sideeffect.py <<'PY' class A: pass class B(A): pass  TYPES = (int, str) NESTED = ((float, 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `isinstance(x, T)` with a non-name type

**What the change really does:** adds `_isinstance_names` (flatten nested tuples, empty → `False`) to the typed/general paths, a runtime `ail2_dyn_isinstance` for class/tuple specs, and a *scope-insensitive* `tuplib` source rewrite that inlines module-level type tuples/aliases into `isinstance` specs and drops the now-unread assignments. The report omits that the inlining ignores local scopes and statement order.

**Probes** (`bash ~/tools/cmp.sh`; base = `/tmp/base`):
- `p1_basic` (tuple/nested/empty/constants/subclasses/bool) — matches on g+d. ✔
- `p5_values` (arg/list item/attribute/dict value, runtime classes) — matches on g+d. ✔
- cross-module `TYPES`, `Shape`, and alias `K` — matches on g+d; base refuses. ✔
- `p2`, `p3`, `p6`, `p11`, `p12` — refused by name on HEAD; also refused on base (message differs). Not defects.
- `p7`, `p9`, `p10` — **wrong output**, base refused. ✘

**Claims:**
- Census 9→0: unverified (not re-run).
- Static tuple/attribute/constant and runtime class handling: verified by probes/tests.
- Side effects preserved: verified by `test_ail_covisin1` (passed).
- 10/10 lab/compare C identical: spot-checked 3/10 — `program.c` identical; rest unverified.
- Tests: `test_ail_covisin1`, `test_ail_tuples`, `test_ail_safetynet` all pass (3 modules, 0 failed); `update_manifest.py --check` exits 0. Verified.
- Report claim "preserves side-effecting module assignments" is true, but the inlining silently overrides shadowed/mutated names — false as a general correctness claim.

**Defects:**
1. Module type alias is inlined ignoring a shadowing parameter (`p7_shadowclass.py`):
   ```python
   class A: pass
   class B: pass
   K = A
   def f(K):
       print(isinstance(A(), K), isinstance(B(), K))
   f(B)
   f(A)
   print(isinstance(A(), K))
   ```
   Expected (CPython): `False True` / `True False` / `True`
   Actual (g+d): `True False` / `True False` / `True`

2. Local rebinding of a module alias is ignored (`p9_localshadow.py`):
   ```python
   class A: pass
   class B: pass
   K = A
   def g():
       K = B
       print(isinstance(A(), K), isinstance(B(), K))
   g()
   print(isinstance(A(), K))
   ```
   Expected: `False True` / `True`
   Actual (g+d): `True False` / `True`

3. Inlining ignores statement order (`p10_order.py`):
   ```python
   class A: pass
   class B: pass
   def f(x):
       print(isinstance(x, K))
   f(A())
   K = B
   f(A())
   ```
   Expected (CPython): `NameError: name 'K' is not defined`, exit 1, empty stdout.
   Actual (g+d): prints `False` twice, exit 0.

All three programs were refused by name on the base tree, so the change causes a new wrong-answer.

VERDICT: FIX

1. `tuplib._expand_isinstance_type_constants` expands constants without checking lexical scope: a parameter/local rebinds the name but the isinstance spec is still inlined with the module value (probes 1 and 2 above).
2. The same expansion ignores execution order, so a use before the assignment becomes a constant instead of CPython's `NameError` (probe 3 above). Limit expansion to unshadowed names whose binding dominates the use, or fall back to the general/dynamic path.
[cost $0.0222, opencode tokens {"total": 1302995, "input": 56462, "output": 5986, "reasoning": 10723, "cache.write": 0, "cache.read": 1229824}]
    tool time: bash 5.8 min
        265s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_cov
         30s bash   cd /home/runner/work/ail-ci/ail-ci; for t in chain_relax tree_fold ticket_audit; do for wt in /home/runner/wor
          7s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p9_localshadow p10_order; do echo "=== $p"; bash ~/tools/cmp.sh /
          7s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p7_shadowclass p8_aliascall; do echo "=== $p"; bash ~/tools/cmp.s
          6s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p1_basic p2_shadow; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/rp
          5s bash   cd /home/runner/work/ail-ci/ail-ci; d=$(mktemp -d /tmp/crossXXXX); cp /tmp/rprobes/cross/*.py $d/; cd $d; pyth
          5s bash   mkdir -p /tmp/rprobes/cross2 && cat > /tmp/rprobes/cross2/util.py <<'PY' class A: pass class B: pass K = A  de
          4s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p2_shadow p3_aug p6_emptyconst; do echo "=== $p BASE"; bash ~/too

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `181f479`.

**Fixes**
- `tuplib._expand_isinstance_type_constants` now expands only when the name resolves to the module binding and the assignment precedes the use's top-level statement.
- Handles parameters, locals, nested functions/lambdas, comprehension targets, class-body shadowing, `global`/walrus bindings, and extra module bindings.
- Assignments are dropped only when no unexpanded module read remains, so shadowed locals no longer force an unbuildable builtin-type tuple to stay.

**Probes** (`bash ~/tools/cmp.sh`, default + general)
- Review defects `p7_shadowclass`, `p9_localshadow`, `p10_order`: match CPython (p10 exits 1, empty stdout).
- Added `p20_scopes`, `p21_order_class`, `p22_order_before`, `p24_builtin_shadow`, `p25_nested_scope_tuple`, `p26_alias_chain`: all match.
- `p23_builtin_order` refused by name on both builds, never answered wrongly.
- Prior 15 probes still match.

**Verification**
- Module census: 148 `pkg-v12` modules, 0 “non-name type argument” refusals.
- `lab/compare`: 10/10 AIL sources generate byte-identical C.
- Tests on final commit: `test_ail_covisin1`, `test_ail_tuples`, `test_ail_modconst`, `test_ail_py_typed_gaps`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 96 tests, OK, 1 platform skip.
- `update_manifest.py --check` exits 0; five regression tests added to `test_ail_covisin1`.
[cost $0.0515, opencode tokens {"total": 2968130, "input": 99063, "output": 13505, "reasoning": 33418, "cache.write": 0, "cache.read": 2822144}]
    tool time: bash 35.3 min, edit 0.0 min, read 0.0 min
        770s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/census_fix.jsonl && timeout 3000 python3 /tmp/census_cur/tool
        716s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3500 python3 -B -m unittest test_ail_tuples test_ail
        421s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3500 python3 -B -m unittest test_ail_covisin1 test_a
         99s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_static_tuple p_constants p_runtime_classes p_dynclass p_attr_
         22s bash   cd /tmp/probes cat > p20_scopes.py <<'PY' class A: pass class B: pass class C: pass K = A  def outer(K):     d
         18s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p7_shadowclass p9_localshadow p10_order p1_basic p5_values; do 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_basic p5_values p7_shadowclass p9_localshadow p10_order; do 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p7_shadowclass p9_localshadow p10_order p1_basic p5_values; do 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Diff.** `tuplib._expand_isinstance_type_constants` rewrites module-level type constants into literal type specs at each `isinstance()` use before the tuple pass, with scope/order guards and assignment dropping; `pyboxed2`/`pyfunc`/`dunders` flatten nested tuples and add a dynamic `ail2_dyn_isinstance` fallback for non-name elements. Tests: `test_ail_covisin1` added via `tests.d`.

**Verified claims**
- `lab/compare` 10/10 `main.ail`: generated `program.c` byte-identical HEAD vs base `9afd6e4`.
- `test_ail_covisin1` + `test_ail_safetynet`: 2 modules, 0 failed.
- Review probes `p7_shadowclass`, `p9_localshadow`, `p10_order` on HEAD match CPython (exit 1 / empty stdout for p10).
- The new scope/order guard works for parameter/local/comprehension/class shadowing cases covered by the added tests.

**Defects (wrong answer / wrong exit, absent on base — base refuses by name)**
1. **Attribute value re-read at use instead of the value captured at assignment.** Probe `p11_attr_snapshot.py`:
```python
class A: pass
class B: pass
class Box: pass
b = Box(); b.t = A
T = b.t
b.t = B
print(isinstance(A(), T), isinstance(B(), T))
```
CPython: `True False`. HEAD default and general: `False True`. The assignment is dropped and `T` is replaced by `b.t` at the later use, after `b.t` changed.

2. **Names inside a constant are re-evaluated after rebinding.** Probe `p8_rebind_class.py`:
```python
class A: pass
class B: pass
T = (A,)
A = B
print(isinstance(A(), T), isinstance(B(), T))
```
CPython: `False False` (the tuple captured old `A`). HEAD both builds: `True False`.

3. **Forward references inside a constant are silently resolved.** `p4_forward_alias.py` (`K = C` before `class C: pass; print(isinstance(C(), K))`): CPython exits 1 with `NameError`; HEAD both builds exit 0 and print `True`. `p5_nested_forward.py` (`T = (K,); print(isinstance(1, T)); K = str`): CPython exits 1; HEAD exits 0 printing `False`. `is_type` checks only that `K`/`C` exists somewhere, not that it is bound at the assignment.

Root cause: `is_type`/`where[name] < index` validates only the outer assignment's position; `expand_value` then re-evaluates the element expressions at the use site, losing CPython's snapshot semantics.

**Pre-existing / other**
- `T = (ValueError, KeyError)` and a module constant used from a class body are still named refusals on both HEAD and base (`name 'int'/'ValueError' is not defined`, module tuple note); not caused by this change, but the "must never be refused" scope is not fully met.
- Module census (`148`, 0 refusals) and `p23_builtin_order` were not re-run; unverified.

VERDICT: FIX
1. `p11_attr_snapshot.py`: expected `True False`; actual `False True` (both builds) — attribute re-read after mutation.
2. `p8_rebind_class.py`: expected `False False`; actual `True False` (both builds) — element rebound before use.
3. `p4_forward_alias.py`: expected exit 1, empty stdout; actual exit 0, `True`. `p5_nested_forward.py`: expected exit 1, empty stdout; actual exit 0, `False` — unbound name inside a constant resolved.
[cost $0.0260, opencode tokens {"total": 1150177, "input": 54887, "output": 6076, "reasoning": 18238, "cache.write": 0, "cache.read": 1070976}]
    tool time: bash 5.6 min, write 0.0 min
        131s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_cov
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_covisin1 t
         44s bash   cd /tmp/ctmp && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_ra
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; timeout 300
          5s bash   cd /tmp/base && for p in p4_forward_alias p5_nested_forward p8_rebind_class p3_class_body_order p1_exc_const p
          4s bash   cd /tmp/ctmp && rm -rf h/echo_pack b/echo_pack out/h_echo_pack out/b_echo_pack; src=/home/runner/work/ail-ci/a
          3s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p9_rebind_alias p10_lambda_isinstance; do echo "===== $p HEAD";
          2s bash   cd /home/runner/work/ail-ci/ail-ci && echo HEAD; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/p11_attr_snapsho

FINAL VERDICT: FIX  2026-11-01T03:23:45Z
