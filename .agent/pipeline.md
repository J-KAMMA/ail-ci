# job job-fuzz34-10230815  started 2026-10-22T23:16:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

**What was found**
- `p01`–`p03` matched CPython on both builds.
- `p04_lazy.py` was the first silent diff: generator expressions were materialized eagerly, so list mutations after creation were lost.
- `p07_nested_gen.py` exposed a second cause: tuple-element genexps were hoisted by `tupexpr.py` into eager list comprehensions.
- `p08_rebind.py` exposed a third cause: enclosing locals were copied by value, so later rebinding was invisible.
- `p05`, `p06`, `p09`, `p10` now also match on both builds.

**Fix**
- `AIL_CURRENT/python/pkg-v12/pyboxed2.py`: lowered genexps to module-level generator functions; outermost iterable eager, the rest lazy; late-bound locals passed as getter lambdas.
- `AIL_CURRENT/python/pkg-v12/tupexpr.py`: kept tuple-element `GeneratorExp` lazy instead of hoisting to a list.
- Added `AIL_CURRENT/test_ail_fuzz34.py` covering laziness, tuple genexps, late-bound locals, and exhaustion.

**Verification**
- `test_ail_fuzz34`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- `tools/update_manifest.py --check`: clean.
- Commit: `fddc543` on `job-fuzz34-10230815`.

Note: this export has no `DIFFERENCES.md` or `DEVLOG.md`, so no rows or devlog entry were added. `.agent/pipeline.md` remains untracked and untouched.
[cost $0.0000, opencode tokens {"total": 10257460, "input": 428386, "output": 23898, "reasoning": 49272, "cache.write": 0, "cache.read": 9755904}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — `fddc543` (job-fuzz34)

Read the diff (new `_lower_genexps` in `pyboxed2.py`, `tupexpr.py` `kind != 'iter'`, MANIFEST, `test_ail_fuzz34.py`). Created base worktree `/tmp/base`, wrote ~46 probes in `/tmp/rprobes/`, ran `cmp.sh` on HEAD and on the base for every divergence, ran the required test modules and `update_manifest --check`, and checked a non-generator program's C.

### Defect found (introduced by the change)
Assignment expressions (walrus) **inside** a generator expression must bind in the enclosing scope (CPython), but the new lowering copies the element/conditions into a module-level generator function, where the walrus target becomes a local of that function. `_free_reads` only sees `Load` names, so nothing carries the value back out.

- `/tmp/rprobes/p43_walrus_in.py`
  ```python
  def f():
      n = 1
      g = ((n := x) for x in [1, 2, 3])
      out = list(g)
      return out, n
  print(f())
  ```
  CPython `([1, 2, 3], 3)` — base (both builds) `([1, 2, 3], 3)` — **HEAD (g and d) `([1, 2, 3], 1)`** (silent wrong answer).
- `/tmp/rprobes/p44_walrus_cond.py` (walrus in the `if`): CPython `([2, 3], 6)`, base matches, **HEAD `([2, 3], 0)`**.
- `/tmp/rprobes/p45_walrus_new.py` (new name): CPython/base `([1, 2], 2)`; **HEAD now refuses to compile** (`not in the subset: name 'm' is not defined`) — a program that worked before.

All three pass on base, fail on HEAD, on both the general and default builds. Cause: `_lower_genexps`/`make_def` in `AIL_CURRENT/python/pkg-v12/pyboxed2.py:1683` ignores `ast.NamedExpr` targets.

### Pre-existing / noted (identical divergence on base, not blocking)
- `p01` closure rebinding across a nested `def` (`[2]` vs `[1]`), `p03` genexp in class body, `p09` genexp as the first iterable of another genexp, `p29` walrus in the enclosing function, `p18`/`big1` dict view laziness: all identical on base.
- `p19` (set mutated after creation): base `[2, 4]`, HEAD `[2, 4, 6]`, CPython raises `RuntimeError: Set changed size during iteration`. The missing size-change check is pre-existing; the change only altered which wrong value is printed.

### Claims check
- "lowered genexps to generator functions / tuple genexps lazy / late-bound getters": verified by behaviour (lazy/rebind/escape/exhaust probes match CPython, `p09` still pre-existing).
- "4 modules 0 failed": verified (fuzz34, safetynet, files, corpus_findings3 → 0 failed).
- "update_manifest --check clean": verified.
- "no DIFFERENCES.md / DEVLOG.md": verified (absent).
- Non-genexp C unchanged: verified — `program.c` byte-identical on HEAD vs base for a list-comp program and a loop-only program.
- Speed: **unverified** — `perf_event_open` is denied on this runner, `tools/icount` unusable.

VERDICT: FIX
1. Walrus inside a generator expression binds to the generated generator function's scope instead of the enclosing scope. Source `/tmp/rprobes/p43_walrus_in.py`: expected CPython `([1, 2, 3], 3)`, actual HEAD (both builds) `([1, 2, 3], 1)`, base `([1, 2, 3], 3)`. Same for `/tmp/rprobes/p44_walrus_cond.py` (expected `([2, 3], 6)`, actual `([2, 3], 0)`) and `/tmp/rprobes/p45_walrus_new.py` (expected `([1, 2], 2)`, actual: compile refusal `name 'm' is not defined`). Fix `_lower_genexps` to propagate `NamedExpr` targets to the enclosing scope (or refuse named expressions inside generator expressions by name).
[cost $0.0000, opencode tokens {"total": 2310652, "input": 87333, "output": 12057, "reasoning": 30398, "cache.write": 0, "cache.read": 2180864}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `71638a4`.

- Walrus inside a generator expression is now refused by name on both builds: `not in the subset: the walrus operator (:=) inside a generator expression; ...`
- Detection skips real nested scopes, so a walrus inside a lambda within a genexp still works.
- Probes: 11/11 passed — `p43`/`p44`/`p45`, module-level, nested comprehension, argument/list-item/attribute/dict-value sources all refused by name on `g` and `d`; lambda-scope and list-comp-outside probes matched CPython.
- Tests on final commit: `test_ail_fuzz34`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed.
- `update_manifest.py --check` clean. Repo has no `DEVLOG.md`/`DIFFERENCES.md`, so no entries were added.
[cost $0.0000, opencode tokens {"total": 1261830, "input": 52613, "output": 6188, "reasoning": 10709, "cache.write": 0, "cache.read": 1192320}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: fuzz34 generator-expression work (`fddc543`, `71638a4`)

I read the diff, ran 36 probes on HEAD and the base worktree (`/tmp/base`), re-ran the targeted tests, and checked the report claims.

### Defects introduced (regressions)

1. **Free names are resolved as module globals/builtins even when an enclosing comprehension target, `with ... as`, or walrus shadows them.** The lowering does not model these bindings, so the generated module-level generator reads the wrong name.
   ```python
   x = 100
   def f():
       return [list(x + y for y in [1]) for x in [5]]
   print(f())
   ```
   CPython and base: `[[6]]`. HEAD (g and d): `[[101]]`.
   Same with a builtin shadow: `[list(len + y for y in [1]) for len in [5]]` → expected `[[6]]`, HEAD raises `TypeError: unsupported operand type(s) for +: 'function' and 'int'`.
   Also reproduced with `(x := 5)` and `with Ctx() as x` before the genexp: expected `[6]`, HEAD `[101]`.

2. **The outermost iterable is evaluated at creation but not `iter()`-ed at creation.** CPython calls `iter()` immediately, so a non-iterable raises at creation and `__iter__` side effects run at creation; the lowering defers both to first consumption.
   ```python
   print("before")
   try:
       g = (x for x in 5)
       print("created")
   except TypeError:
       print("type error at creation")
   else:
       print(list(g))
   ```
   CPython and base: `before` / `type error at creation`. HEAD: `before` / `created` / `type error at consumption`.
   Ordering probe: `g = (x for x in It([1, 2]))` → expected `iter called` before `made`; HEAD prints it after.

3. **Generated names can collide with a user local, producing invalid C.**
   ```python
   def f(_ail_genexp_1):
       g = (_ail_genexp_1 + x for x in [1, 2])
       return list(g)
   print(f(10))
   ```
   CPython and base: `[11, 12]`. HEAD (g and d): build fails with `duplicate parameter 'pv__ail_genexp_1'`. The fresh-name pool excludes module-scope names but not function locals/lambda/comprehension bindings.

### Pre-existing (identical on base, not blocking)
- Enclosing-closure rebinding is still not seen: `n=1; def inner(): return (i+n ...); n=7` → `[1]`, CPython `[7,8]` (`p01`, `r_closure_genexp`).
- Genexps inside lambda bodies and default arguments are not lowered: `r_lambda_lazy` `[1,2]` vs `[1,2,3]`; `r_default_lazy` same.
- Dict/set mutated after creation does not raise the CPython `RuntimeError` (`p18`, `p19`, `r_source_dict`).
- Inner genexp used as another genexp's first iterable stays eager (`p09`); class-body genexp still fails (`p03`); walrus statement after a genexp is not treated as late (`p29`).

### Claims checked
- fuzz34 + safetynet + files + findings3 on HEAD: **4 modules, 0 failed** — verified.
- `update_manifest.py --check`: clean — verified. No DEVLOG/DIFFERENCES files — verified.
- Walrus in a genexp refused by name on both builds; walrus in a lambda inside a genexp works — verified.
- "lowers each generator expression" is **false** (lambda/default/class-body/first-iterable nested cases above).
- "Fixed and committed as `71638a4`" is incomplete: the laziness fix is `fddc543`; `71638a4` is only the walrus refusal.
- Speed: `perf_event_open` is denied in this runner, so `tools/icount.c` cannot measure. `g02_010`, `g04_006`, `g12_036` produce identical output; their genexps run once, so there is no measured hot-path change (unverified).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1871892, "input": 99402, "output": 10363, "reasoning": 29007, "cache.write": 0, "cache.read": 1733120}]

FINAL VERDICT: FIX  2026-10-23T00:10:37Z
