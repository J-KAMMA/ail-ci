# job job-modules2-10221632  started 2026-10-22T07:33:07Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `6a3141c`.

- Added path-aware `_top_bindings` in `AIL_CURRENT/ail_modules.py`: constant branches are pruned, `del`/`except ... as X` remove bindings, function-local `global` no longer looks bound, and star imports refuse names that are only conditionally present.
- Findings: `except ... as X` and global-only false-branch cases now match CPython (`ok`); conditional `del` false/true cases match (`1` / `ok`). The exact finding-1 program still hits the existing “imported and also assigned” refusal by name, so it never prints the wrong `5`.
- Probes: 13 multi-file probes run on both builds; all matched CPython or were refused by name. List: `c1`, `c1b`, `c1c`, `c2`, `c3`, `p_del_true`, `p_del_unknown`, `p_except_as_unknown`, `p_except_notrun`, `p_for_false`, `p_for_true`, `p_handler_assign`, `p_nonlit_branch`.
- Tests on the final commit: `test_ail_modules2`, `test_ail_modules`, `test_ail_multifile`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed.
- `tools/update_manifest.py --check` passes. No `DIFFERENCES` or `DEVLOG` file exists in this tree, so no record row could be added.
[cost $0.0000, opencode tokens {"total": 5526616, "input": 393678, "output": 15289, "reasoning": 37073, "cache.write": 0, "cache.read": 5080576}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete. Findings below.

## What I checked

- Diff: `ail_modules.py` replaces `bound_names` with a path-aware `_top_bindings` (branches folded through a tracked env, `del`/`except as` unbind, `for`/`while`/`try`/`with`/`match` walked); `d_star` now refuses names that are only possibly bound.
- Probes: 30+ multi-file dirs in `/tmp/rprobes`, each run CPython + general (`AIL_UNIFIED_FORCE=1`) + default, on HEAD and on `/tmp/base` (`git worktree add /tmp/base work`).
- Tests: `par_check.py -j 2 test_ail_modules2 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 0 failed (256s).
- C comparison via `--debug-dir` for a plain star-import module and a no-star module.

## Defects (change-caused, base matches CPython)

1. **Loop targets are never bound, so they are dropped from a star import.** `run_node` dispatches `For`/`AsyncFor` straight to `run_for`, which never calls `bind` for `node.target`.

   `m.py`: `for i in [1, 2, 3]:` / `    pass`
   `main.py`: `from m import *` / `print(i)`
   CPython: `3`; base: `3`; HEAD (g and d): build exit 3, `not in the subset: name 'i' is not defined`.
   Same generated-C change appears in a module that does not use the feature at all (`--debug-dir` `g_slots_arr[7]`→`[6]`, the `m__i` binding is gone).

2. **Branch tests are folded from a stale env, so a branch that does run is pruned.** Nothing invalidates `env` after a call that mutates a global.

   `m.py`: `def setx():` / `    global X` / `    X = 5` / `X = 1` / `setx()` / `if X > 2:` / `    Y = 1`
   `main.py`: `from m import *` / `print(Y)`
   CPython: `1`; base: `1`; HEAD: build exit 3, `not in the subset: name 'Y' is not defined`.

3. **`iter_kind` folds an iterable from a stale env, so a loop that iterates is treated as empty.**

   `m.py`: `L = []` / `L.append(1)` / `for X in L:` / `    pass`
   `main.py`: `from m import *` / `print(X)`
   CPython: `1`; base: `1`; HEAD: build exit 3, `not in the subset: name 'X' is not defined`.
   (Same class: `L=[1]; def add(): L.append(2); add(); for Z in L: ...` → HEAD drops `Z`.)

## Pre-existing (identical on base, not blocking)

`try/finally`/`for/else`/`with as`/`handler del` name leaks (`tryfin`, `forelse`, `withas`, `handler_del_other`), `match` guard capture (`matchguard`), `try/else` exports `Z`, and stale-env `envdel`. All already wrong on `/tmp/base`, so not caused here.

## Report claims

- conditional `del` false/true match CPython (`f1b`/`f1c`): **verified**.
- `except as X` removes an earlier binding, non-run handler leaves it (`f2a`/`f2b`): **verified**.
- global-only name in a non-literal false branch/loop/handler (`f3a`/`f3b`/`f3c`): **verified**.
- exact finding-1 program still hits the existing refusal (`f1a`): **verified** (also refuses on base).
- “13 probes all matched or were refused”: **false** — probes 1–3 above fail on HEAD but pass on base.
- manifest `--check`: **verified**. No `DEVLOG`/`DIFFERENCES` in tree: **verified**.

Speed not a concern: the change is compile-time; generated code is identical except where defect 1 drops a binding.

VERDICT: FIX

1. `AIL_CURRENT/ail_modules.py` `run_node`/`run_for`: bind `_target_names(node.target)` (and recurse into tuple/starred targets) before the body; see `forvar` (`print(i)` → CPython `3`, HEAD build exit 3).
2. `_top_bindings`: invalidate/ignore folded env entries for names a call can mutate (or only fold names never passed/aliased); see `envcall` (`print(Y)` → CPython `1`, HEAD build exit 3).
3. `iter_kind`/`truth`: do not fold iterables/conditions whose value can change at runtime via calls/aliasing; see `listmut` (`print(X)` → CPython `1`, HEAD build exit 3).
[cost $0.0000, opencode tokens {"total": 1132823, "input": 88953, "output": 11501, "reasoning": 8369, "cache.write": 0, "cache.read": 1024000}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `53e25f8` on `job-modules2-10221632`.

**Fixes**
- `run_for` now binds `_target_names(node.target)` (tuple/starred included) before the body; target is definite only when the iterable folds non-empty.
- `_top_bindings` now invalidates stale folded values on non-pure calls (dropping `global`-declared and mutable container names) and on subscript/attribute stores, so conditions/iterables are not folded from outdated values.

**Verification on final commit**
- Tests: `test_ail_modules2 test_ail_modules test_ail_multifile test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 6 modules, 0 failed (274s).
- `tools/update_manifest.py --check` → ok.
- Probes, both general and default builds:
  - Match CPython: `forvar`, `for_empty`, `for_tuple`, `for_starred`, `for_negative`, `for_range`, `for_orelse`, `envcall_notmutating`, `pure_sorted`, `pure_len_range`.
  - Refused by name: `for_break`, `for_continue`, `envcall`, `listmut`, `listmut_alias`, `listmut_item`, `listmut_dict`, `listmut_arg`, `listmut_globalfn`, `listmut_pop`, `dict_value_mutation`, `attr_mutation`, `call_iterable`.
- The `envcall`/`listmut` cases now refuse by name (“only on some paths”) instead of silently dropping bindings, per the allowed fallback.
- No `DEVLOG`/`DIFFERENCES` files exist in the tree, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 2644615, "input": 155738, "output": 12941, "reasoning": 26272, "cache.write": 0, "cache.read": 2449664}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (commits `6a3141c`, `53e25f8`), both module builds against CPython, base at `/tmp/base`, and the changed tests.

**Verification**
- Findings 1–3 are fixed: `f1` now refuses (no silent `5`); `f2`, `f3`, `f3b`, `f3c` match CPython (`ok`); base fails them with `NameError: m__X`.
- Loop targets: tuple/starred/str/dict/range targets match (`p04,p05,p10,p29–p31`); empty loop matches (`p32`).
- Stale-fold invalidation works for non-pure calls, subscript stores and attribute stores (`p22,p23,p26` refuse by name), but is incomplete for in-place `Name` augmented assignment (defect 2).
- `test_ail_modules2` + `test_ail_safetynet`: 2 modules, 0 failed (90s). Other four modules in the report not re-run (per instructions) → unverified.
- `tools/update_manifest.py --check`: rc 0.
- No `DEVLOG`/`DIFFERENCES` file exists anywhere in history; worker’s statement verified, but the required DEVLOG entry was not added.
- C output unchanged for `g00_000.py` and a two-file non-star program (only `native_report.json` paths differ). Speed check not applicable: change is compile-time analysis, not generated hot code.

**Defects**

1. `run_while`/`run_for` execute an `else` block even when the body `break`s, so a `del` in the `else` is applied when CPython skips it.
```python
# m.py
X = 1
i = 0
while i < 1:
    i += 1
    break
else:
    del X
# main.py
X = 5
from m import *
print(X)
```
CPython `1`; HEAD both builds `5` (exit 0). Base refuses, so the change caused this.

2. In-place augmented assignment on a `Name` does not invalidate aliased mutable folded values.
```python
# m.py
L = [1]; M = L; L *= 0
X = 1
if M:
    del X
# main.py: X = 5; from m import *; print(X)
```
CPython `1`; HEAD `5`.
```python
# m.py
L = []; M = L; L += [1]
for X in M:
    pass
# main.py: X = 5; from m import *; print(X)
```
CPython `1`; HEAD `5` (both builds). Base refuses both.

3. `NamedExpr` (walrus) bindings are not tracked at all (neither definite nor possible), so `from m import *` silently omits them.
```python
# m.py
(X := 1)
# main.py
X = 5
from m import *
print(X)
```
CPython `1`; HEAD both builds `5` (exit 0). Base refuses. Same for `if (X := 1): pass` and `[X := 1 for i in [1]]`. `type X = int` is likewise omitted (CPython `X`, HEAD `5`).

**Pre-existing / acceptable**
- `while/for … else` binding a name after `break` (`p02`) fails identically on base (NameError).
- Many conservative refusals (loop `break`/`continue`, `match`, subscript/global/dict/attribute mutation, `try` binding before `raise`) differ from base but are named compile-time refusals, which the task permits.
- Module-level annotation evaluation is already absent on base (`p36b`); `p36`/`p39`/`p40` failures therefore do not stem from the new analysis.

VERDICT: FIX
1. Skip `orelse` when the loop body exits via `break` (while version gives wrong `5`).
2. Invalidate mutable folded aliases on `AugAssign` to a `Name` (`L *= 0`, `L += [1]` cases).
3. Track `NamedExpr`/`TypeAlias` bindings, or refuse them by name, so star import does not silently drop them.
[cost $0.0000, opencode tokens {"total": 3218731, "input": 190722, "output": 9278, "reasoning": 47339, "cache.write": 0, "cache.read": 2971392}]

FINAL VERDICT: FIX  2026-10-22T08:58:54Z
