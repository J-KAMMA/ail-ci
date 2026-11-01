# job job-std_contextlib-11011755  started 2026-11-01T08:56:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed as `11f75dd` on `job-std_contextlib-11011755`.

**Result:** 10 of 12 `lab/stdlib/contextlib` programs build and match CPython 3.12 stdout/exit; `redirect_stdout`/`redirect_stderr` remain refused by name and are recorded as the follow-up.

**Changes:** `_AilExitStack` (enter_context, push, callback, pop_all, close, suppression/unwinding), `_AilChdir`, and builtin exception-hierarchy handling for `issubclass(exc_type, ...)` in `__exit__`. Programs, `RESULTS.md`, `DIFFERENCES.md`, `DEVLOG.md`, and `test_ail_std_contextlib.py` (registered via `tests.d`) are in the commit.

**Tests (final commit):**
- `test_ail_std_contextlib` — 10 programs + 2 refusal checks OK
- `test_ail_pre181`, `test_ail_pre197`, `test_ail_fuzz56`, `test_ail_cov2` — OK
- `test_ail_safetynet` — OK
- `test_ail_files` — OK (1 skipped)
- `test_ail_corpus_findings3` — OK
- `tools/update_manifest.py --check` — OK

**Probes (all `/tmp/probes`, both g and d builds matched CPython stdout and exit):**
`ctx_chdir_probe`, `ctx_chdir_values`, `ctx_exc_hierarchy`, `ctx_hierarchy`, `ctx_exitstack_cb`, `ctx_exitstack_errors`, `ctx_exitstack_suppress`, `ctx_stack_callbacks`, `ctx_stack_body_error`, `ctx_stack_push_pop`, `ctx_stack_no_with`.

**Generated C:** byte-identical for all 10 `main.ail`; for `main.py`, the 5 that compile are byte-identical and the other 5 are refused identically before and after.
[cost $0.0314, opencode tokens {"total": 2276201, "input": 78209, "output": 10544, "reasoning": 11320, "cache.write": 0, "cache.read": 2176128}]
    tool time: bash 45.3 min
       1064s bash   cd AIL_CURRENT && for t in test_ail_cov2 test_ail_files test_ail_corpus_findings3; do echo "===== $t"; timeout
       1012s bash   cd /tmp && rm -rf /tmp/cgen_new /tmp/cgen_old && mkdir /tmp/cgen_new /tmp/cgen_old fail=0 for t in /home/runne
        288s bash   cd AIL_CURRENT && for t in test_ail_pre181 test_ail_pre197 test_ail_fuzz56 test_ail_safetynet; do echo "===== 
         83s bash   ls -la /tmp/probes && cd /tmp/probes && for p in ctx_*.py; do echo "########## $p"; bash ~/tools/cmp.sh "$p" /
         78s bash   cd /tmp/probes && for p in ctx_*.py; do echo "########## $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-c
         70s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo MANIFEST_OK && cd AIL_C
         39s bash   cd AIL_CURRENT && timeout 1800 python3 -B -m unittest -v test_ail_std_contextlib 2>&1 | tail -40
         31s bash   cd /tmp && rm -rf /tmp/cgen_test && mkdir /tmp/cgen_test && cd /tmp/cgen_test && AIL_NO_CACHE=1 AIL_QUIET_FALL

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds `_AilExitStack` (`enter_context`, `push`, `callback`, `pop_all`, `close`) and `_AilChdir` to `prelude_with.py`, maps `ExitStack`/`chdir` in `withlib.py`, and rewrites `issubclass(exc_type, BuiltinExc)` to a name-hierarchy helper `_ail_exc_is`. This matches the report.

**Probes** (run with `cmp.sh` on HEAD and base `49052ba`; both g/d builds):

| probe | result |
|---|---|
| `p_user_exc_exception.py` | HEAD wrong, base correct: regression |
| `p_user_exc_lookup.py` | HEAD wrong, base refused by name |
| `p_stack_close_raise.py` | HEAD wrong, base refused by name |
| `p_stack_close_suppress.py` | HEAD wrong, base refused by name |
| `p_callback_common.py` | same as CPython |
| `p_chdir_return.py` | same as CPython |
| `p_noctx.py` | same as CPython; generated `program.c` identical to base |

**Defects (reproduced on HEAD; none pre-existing):**

1. `_ail_exc_is` breaks `issubclass(exc_type, Exception)` for user exception classes. A user class extending a builtin is absent from `_ail_exc_bases`, so the check returns false. The base used `isinstance(exc, Exception)` and was correct.
```python
class MyError(Exception):
    pass

class CM:
    def __enter__(self):
        return self
    def __exit__(self, t, e, tb):
        print(issubclass(t, Exception))
        return True

with CM():
    raise MyError("boom")
```
Expected: `True`. Actual: `False` (both builds). Likewise `class MyKey(KeyError)` with `issubclass(t, LookupError)` prints `False` instead of `True`.

2. `ExitStack.close()` does not implement CPython's `__exit__` unwinding: managers receive `None` instead of the exception raised by an earlier callback, and a manager returning true does not suppress it.
```python
from contextlib import ExitStack

class Swallow:
    def __enter__(self):
        return self
    def __exit__(self, t, e, tb):
        print("outer", None if t is None else t.__name__)
        return True

def bad():
    raise ValueError("cb")

stack = ExitStack()
stack.push(Swallow())
stack.callback(bad)
try:
    stack.close()
    print("close returned")
except ValueError as e:
    print("close raised", e)
```
Expected:
```
outer ValueError
close returned
```
Actual:
```
outer none
close raised cb
```
With two pushed managers, both print `none` instead of `ValueError` (`p_stack_close_raise.py`).

**Report claims:**
- 10/12 build and match CPython: verified by `test_ail_std_contextlib` passing.
- `redirect_stdout`/`redirect_stderr` refused by name: verified.
- Test claim that the ten programs exercise `callback` and `close`: **false** — no lab program calls either, so the committed test cannot catch defect 2.
- `test_ail_std_contextlib` + `test_ail_safetynet` on HEAD: verified (0 failed).
- `update_manifest.py --check`: verified.
- Generated C byte-identical for the ten `lab/compare` tasks: partially verified (`p_noctx` and two `main.py` files identical; `tally_lang` fails identically on base and HEAD); not all ten checked.
- Other listed tests (`pre181`, `pre197`, `fuzz56`, `cov2`, `files`, `corpus_findings3`): unverified per review scope.
- Pre-existing: `tally_lang` compile failure is identical on base and HEAD; no probe difference was pre-existing.
- Speed: not checked; change is confined to programs using `contextlib`, not hot default code.

VERDICT: FIX
[cost $0.0261, opencode tokens {"total": 823910, "input": 59953, "output": 5500, "reasoning": 19257, "cache.write": 0, "cache.read": 739200}]
    tool time: bash 14.4 min
        370s bash   date; cd /tmp && rm -rf ccheck && mkdir ccheck; for t in ticket_audit tally_lang ledger_bin; do for side in ne
        348s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         39s bash   cd /tmp/rprobes && for p in p_user_exc_exception.py p_user_exc_lookup.py p_stack_close_raise.py p_stack_callba
         26s bash   cat > /tmp/rprobes/p_noctx.py <<'EOF' class CM:     def __init__(self):         self.seen = []     def __enter
         19s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base2 work >/tmp/base2add.log 2>&1; tail -3 /tmp/b
         16s bash   cd /tmp/rprobes && cat > p_chdir_return.py <<'EOF' import os from contextlib import chdir  old = os.getcwd() d
         15s bash   cd /tmp/rprobes && cat > p_stack_close_suppress.py <<'EOF' from contextlib import ExitStack  class Swallow:   
         11s bash   cd /tmp && rm -rf dbg_new dbg_base && mkdir dbg_new dbg_base && cp /tmp/rprobes/p_noctx.py dbg_new/p.py && cp 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `6299a7c`.

- **Defect 1:** `_ail_exc_is` now follows the program’s `class Name(Base)` links, so `MyError(Exception)` and `MyKey(KeyError)` resolve `Exception` / `LookupError` correctly.
- **Defect 2:** `ExitStack.close()` now calls `__exit__(None, None, None)`, passing an earlier callback’s exception to lower managers and honoring suppression.
- Lab coverage now actually exercises `callback`/`close` and user exception subclasses.

Verification:
- 12/12 probes in `/tmp/probes/` match CPython on both g/d builds.
- Required tests on final commit: 9 modules, 0 failed (`contextlib`, `pre181`, `pre197`, `fuzz56`, `cov2`, `exception_context`, `safetynet`, `files`, `corpus_findings3`).
- `update_manifest.py --check`: OK.
- All 10 `lab/compare` `main.ail` generated C byte-identical to base `49052ba`.

Known documented limits remain: `redirect_stdout`/`redirect_stderr` refused by name; `callback` max two positional args; callable object with `__exit__` treated as callback by `push`.
[cost $0.0559, opencode tokens {"total": 5236172, "input": 120138, "output": 14605, "reasoning": 23157, "cache.write": 0, "cache.read": 5078272}]
    tool time: bash 49.1 min, edit 0.0 min
       1198s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_std
        685s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_std
        477s bash   cd /tmp && rm -rf ccheck && mkdir ccheck && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer 
        139s bash   cd /tmp/probes && for p in p_*.py; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ai
        137s bash   cd /tmp/probes && for p in p_*.py; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ai
        128s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo MANIFEST_OK; cd /tmp/pr
         88s bash   cd /tmp && rm -rf ccheck2 && mkdir ccheck2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfe
         73s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_std_contextlib -v 2>&1 | tail -

## review 1
[model opencode-go/deepseek-v4.1-flash]
# Review: contextlib ExitStack, chdir, exception hierarchy

**What the change really does.** It maps `contextlib.ExitStack` and `chdir` to new prelude classes (`_AilExitStack`, `_AilChdir`), replaces `isinstance` inside `__exit__` with a builtin-exception-name walk (`_ail_exc_is`) that now also follows the program's `class Name(Base)` links, makes `ExitStack.close()` unwind via `__exit__(None,None,None)`, and adds 12 lab programs plus `test_ail_std_contextlib`. This matches the report.

**Probes (HEAD, general `g` and default `d`, via `~/tools/cmp.sh`).**
- `p_userchain`, `p_user_exc_chain/exception/lookup`: user classes through `Exception`/`KeyError`/`LookupError` correct on both builds.
- `p_close_suppress`, `p_close_raise`, `p_close_chain`, worker `p_stack_close_*`: callback error passed to lower managers, suppressed by a true `__exit__`, propagated otherwise, correct.
- `p_push_callable_true`, `p_callback_true`, `p_close_callable_true`, `p_mutate_unwind`, `p_enter_raises`, `p_manager_raises`, `p_stack_container`, `p_popall`, `p_noctx`: all match CPython.
- `p_nonfeature` (no contextlib, uses `with open`/`with CM`): `--debug-dir` `program.c` byte-identical HEAD vs base (`/tmp/base2`).
- Lab/compare: all ten `main.ail` generated C in the base/HEAD artifacts (`/tmp/cgen-base`, `/tmp/cgen-cur`) is identical.
- `p_issubclass_tuple` (`issubclass(ty, ())` before `issubclass(ty, (A, ValueError))`) crashes the compiler with `IndexError` in `dunders.py:1186`, but the same probe crashes identically on base → **pre-existing**, not blocking.

**Defects**

1. **`_AilChdir` cannot be reused/nested: it saves one cwd string instead of CPython's `_old_cwd` stack** (`prelude_with.py:270-280`).
```python
# /tmp/rprobes/p_chdir_reuse2.py
import os
from contextlib import chdir
base = os.getcwd()
os.makedirs("rprobe_a", exist_ok=True)
full = os.path.join(base, "rprobe_a")
c = chdir(full)
with c:
    with c:
        pass
print("outer back", os.getcwd() == base)
```
Expected (CPython): `outer back True`; actual (both builds): `outer back False`. The outer `__enter__` overwrites `self.old`, so the outer `__exit__` does not restore `base`. A list/stack (as in CPython) fixes it.

2. **`ExitStack.push(None)` reports the wrong error type** (`prelude_with.py:232`, `callable()` decides callback vs manager).
```python
# /tmp/rprobes/p_push_none.py
from contextlib import ExitStack
s = ExitStack()
try:
    s.push(None)
    s.close()
except Exception as e:
    print(type(e).__name__, e)
```
Expected (CPython): `TypeError 'NoneType' object is not callable`; actual (both builds): `AttributeError 'NoneType' object has no attribute '__exit__'`. This is not one of the limits declared in `DIFFERENCES.md`.

**Claims checked.**
- Both reported review defects fixed: **verified** (probes above; lab `custom_manager.py`/`exitstack_basic.py`).
- 12/12 worker probes in `/tmp/probes` match on both builds: **verified** (ran all twelve).
- `test_ail_std_contextlib.py` and `test_ail_safetynet`: **verified** (`par_check.py -j 2`, 2/2 ok, 339 s).
- `update_manifest.py --check`: **verified** (rc 0).
- Ten `lab/compare` `main.ail` C byte-identical: **verified from the given artifacts**; I did not rebuild all ten.
- Known limits (redirects refused, callback ≤2 positional args, callable object with `__exit__` treated as callback): **verified/declared** (redirect test passes; `push` callable-manager form is refused by name).

**Unverified.** The other 7 test modules in the worker's 9-module run were not rerun (per review rules); instruction-count/speed was not checked (the change only affects contextlib paths, not gdev hot code).

VERDICT: FIX
[cost $0.0533, opencode tokens {"total": 3027404, "input": 98383, "output": 12777, "reasoning": 37012, "cache.write": 0, "cache.read": 2879232}]
    tool time: bash 14.4 min, write 0.0 min
        341s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_a
        205s bash   cd /tmp/rprobes && for p in p_*.py; do echo "===== $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/$p /home/
        140s bash   cd /tmp/probes && for p in p_user_exc_chain.py p_user_exc_exception.py p_user_exc_lookup.py p_stack_close_chai
         58s bash   cd /tmp/rprobes && for p in p_chdir_reuse2.py p_close_chain.py p_callback_true.py p_issubclass_tuple.py p_ente
         25s bash   cd /tmp/isst && i=0; for t in "A, ValueError" "ValueError, TypeError" "A, B" "B, TypeError" "()"; do i=$((i+1)
         15s bash   cat > /tmp/rprobes/p_issub_empty.py <<'EOF' class M:     def __enter__(self):         return self      def __e
         13s bash   cd /tmp && rm -rf cunf && mkdir cunf && cp /tmp/rprobes/p_nonfeature.py cunf/p.ail && cd cunf && for tag in ba
         12s bash   cat > /tmp/rprobes/p_caller_cm.py <<'EOF' from contextlib import ExitStack   class CM:     def __enter__(self)

FINAL VERDICT: FIX  2026-11-01T11:44:39Z
