# job job-fuzz55-10231353  started 2026-10-23T04:54:28Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Fixed**
- `g.close()` on a suspended generator marked it done without running `try/finally`; now it resumes with `GeneratorExit`, runs cleanup, returns `None` on normal close, propagates other exceptions, and raises `RuntimeError: generator ignored GeneratorExit` if the generator yields during cleanup.
- Added the internal `GeneratorExit` builtin (not an `Exception` subclass) in `cruntime.py`; close logic in `safetyrt.py`.
- Commit: `6b57b84`

**Tests on final commit**
`test_ail_fuzz55` (5 new tests), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **4/4 modules passed, 0 failed**. Manifest updated and `--check` passes.

**Self-check probes** (both builds, `cmp.sh`)
- Match CPython: `g01_send`, `g02_close_finally` (the fix), `g08_wrong_types`, `g10b_empty_zero`, `g12_close_exc`, `g13_close_states`, `g15_close_containers`, `g16_double_close_yield`.
- Refused by name: `g03`/`g17` (`except GeneratorExit`), `g04`/`g07` (`yield from` as a value), `g09` (`.throw()`), `g11` (`BaseException`).
- Pre-existing differences, not caused by this change: `g05` generator expressions passed to functions (eager/over-consuming; `sink` sees a list), `g06` genexpr late binding/reuse and OOM, `g10` missing `StopIteration.value`, `g14` closing a `yield from` outer generator does not close its inner generator, and unfinished generators get no exit finalizer.

**Records**
This export contains no `DEVLOG` or `DIFFERENCES.md`, so no entry/row could be added; the change and test docstring document the difference.
[cost $0.0000, opencode tokens {"total": 4366674, "input": 108585, "output": 13475, "reasoning": 15750, "cache.write": 0, "cache.read": 4228864}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Reviewed** `git diff work..HEAD` (commit `6b57b84`). Base worktree: `/tmp/base`.

**Probes** (run on HEAD and base via `~/tools/cmp.sh`):
- Match CPython both builds: `p01_finally`, `p02_exc_hierarchy` (`except Exception` correctly does not catch `GeneratorExit`), `p04b_yield_cleanup` (ignored close -> RuntimeError; later next re-raises GeneratorExit), `p05_raise_finally`, `p06_nested`, `p07_send`, `p08_containers`, `p09_loop_close`, `p10_unstarted_args`, `p15_except_yield`, `p16_reentrant`, `p17_after_exc`.
- Refusals by name verified: `except GeneratorExit`, `except BaseException`, `.throw()`, `yield from` as a value.
- **`p03_bare_except` differs (both builds)** — see defect 2.
- **`p11_nameerror_anchor` differs on the general build (`d` is fine)** — see defect 1.
- `p12_with`: HEAD calls `__exit__(None,...)` instead of `(GeneratorExit,...)`; base did not call `__exit__` at all. This is the limitation already declared in `withlib.py` for non-`Exception` exceptions, now reachable via `GeneratorExit`.

**Tests**: `test_ail_fuzz55`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` = 4/4 pass (199s). `test_ail_unbound` fails 2 tests (`test_exception_classes`, general path, ir 0 and 1). Manifest `--check` passes, but `test_ail_fuzz55` is not registered in `ail_check.MODULES`/`tools/ci_shards.json` and is not pinned, so CI will never run it.

**Claims**: close-finally fix, `GeneratorExit` not an `Exception`, RuntimeError on yield-during-cleanup, refusals, and 4/4 modules all *verified*. Pre-existing genexpr/`yield from` claims not re-tested (*unverified*). Speed not measured: `perf_event_open` is denied on this runner; the change only adds one branch per `yield`.

**Pre-existing/documented**: `with` `__exit__` receives `None` for non-`Exception` exceptions (declared in `withlib.py`); genexpr/`StopIteration.value`/`yield from`-close gaps from the report not re-verified.

VERDICT: FIX

1. **`except NameError` no longer catches `UnboundLocalError` on the general path (regression).** The edit at `cruntime.py:16461` reformatted the exact one-line anchor that `pyboxed2.py:2183` string-replaces; the anchor no longer matches, so the `AIL_B_UNBOUNDLOCALERROR -> AIL_B_NAMEERROR` base patch is silently dropped. Probe:
   ```python
   def f():
       try:
           y = x
           x = 1
           print(y)
       except NameError as e:
           print("caught", type(e).__name__, e)
   f()
   ```
   Expected (CPython and base, both builds): `caught UnboundLocalError cannot access local variable 'x' where it is not associated with a value`, exit 0. Actual HEAD general build only: no stdout, exit 1, stderr `UnboundLocalError: cannot access local variable 'x' where it is not associated with a value`. This also fails `test_ail_unbound.test_exception_classes` (general, ir 0/1). Keep the anchor line one physical line or update the anchor.

2. **Bare `except:` in a generator no longer catches the close request (silent wrong answer, both builds).** Bare except is lowered to `except Exception` (pyfunc.py:15953), justified by "every exception the program can raise is an Exception subclass"; the new `GeneratorExit` derives from `BaseException`, so it escapes. Probe:
   ```python
   def k():
       try:
           yield 1
       except:
           print("caught bare")
       finally:
           print("fin k")
   c = k(); print(next(c)); print("close->", c.close()); print("closed")
   ```
   Expected CPython: `1`, `caught bare`, `fin k`, `close-> None`, `closed`. Actual HEAD (both builds): `1`, `fin k`, `close-> None`, `closed` — the bare handler and subsequent code are skipped. Either make bare `except:` catch `GeneratorExit` (a `BaseException` root), or refuse bare `except:` inside generator cleanup by name.
[cost $0.0000, opencode tokens {"total": 3062453, "input": 152652, "output": 10593, "reasoning": 26504, "cache.write": 0, "cache.read": 2872704}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in commit `6a3e2cb`.

- Restored the one-line `c->base` anchor and updated `pyboxed2.py`, so `except NameError` catches `UnboundLocalError` again on the general path.
- Bare `except:` now also matches `GeneratorExit` (explicit `except Exception:` still does not).
- Added the bare-except case to `test_ail_fuzz55`; registered/pinned it in `ail_check.MODULES`, `tools/ci_shards.json`, and `MANIFEST.json`.

Verification on final commit:
- Probes (both builds, all match CPython): `p03_bare_except`, `p03b_bare_vs_exception`, `p03c_bare_as`, `p03d_bare_reraise`, `p03e_bare_raise_value`, `p03f_bare_nested`, `p11_nameerror_anchor`.
- Tests: `test_ail_fuzz55`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_unbound` — **51 run, OK (1 skipped)**.
- `update_manifest.py --check` and `ci_shards.py --check` pass.

This export contains no `DEVLOG`/`DIFFERENCES` file, so no rows were added.
[cost $0.0000, opencode tokens {"total": 1619190, "input": 97189, "output": 6312, "reasoning": 5801, "cache.write": 0, "cache.read": 1509888}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — `6a3e2cb` (fuzz55 fixes)

**Diff reviewed:** 2 commits, 7 files (runtime `GeneratorExit`, close injection, bare-except matching, anchor restoration, new test/pins).

**Probes** (HEAD, both general and default builds, via `~/tools/cmp.sh`):
- Match CPython: `p01_close_send_mutation`, `p03_nested_swallow`, `p05_raise_finally`, `p06_nested`, `p07_send`, `p08_containers`, `p09_loop_close`, `p10_unstarted_args`, `p11_nameerror_anchor`, `p18_nested_gen_close`, `p19_except_yield_close`, `p21_bare_normal`, `p25_close_iter`, `p26_send_after_ignored`, `p27_else_close`, plus `p02_exc_hierarchy`, `p03_bare_except`, `p02b_ge_prop`, `p04b_yield_cleanup2`.
- Refused by name (acceptable): `except GeneratorExit`, `except BaseException`, `.throw()`, `yield from` as a value.

**Claims verified**
- `except NameError` catches `UnboundLocalError` again on the general path: verified (`p11` both builds; `test_ail_unbound` passes). Anchor text and `PREAMBLE`/thread preamble match.
- Bare `except:` catches `GeneratorExit`; `except Exception:` does not: verified (`p03`, `p02_exc_hierarchy`, `p21`).
- `test_ail_fuzz55` added and registered in `ail_check.MODULES`, `ci_shards.json`, `MANIFEST.json`: verified; `update_manifest.py --check` and `ci_shards.py --check` both rc 0.
- No `DEVLOG`/`DIFFERENCES` in this export: verified.
- Exact worker probe files `p03b`–`p03f` are not in this worktree, so their literal list is *unverified*; equivalent probes pass.

**Tests** (`par_check.py -j 2`): `test_ail_fuzz55`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_unbound` — 5/5 modules, 0 failed (218 s).

**Pre-existing (not blocking)**
- `p12/p23/p24` (`with` around `yield`, closed): closed generator now calls `__exit__(None,...)` instead of `(GeneratorExit,...)`; base did not call `__exit__` at all. This is the limitation already declared in `withlib.py` for non-`Exception` exceptions, newly reachable via `GeneratorExit`.
- `p20` generator expression passed to `next()` crashes with "unknown iterator kind" identically on base and HEAD.

**Speed:** not measured — `perf_event_open` is denied on this runner (`paranoid=4`). The change adds one branch per `yield`; no hot-path structural change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3209802, "input": 185606, "output": 11126, "reasoning": 28110, "cache.write": 0, "cache.read": 2984960}]

FINAL VERDICT: ACCEPT  2026-10-23T06:00:07Z
