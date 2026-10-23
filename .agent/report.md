# job job-pre6-10240010  started 2026-10-23T15:10:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first remaining difference from the task: `__slots__` was ignored on the general path.

**Change**
- `pyboxed2.py` now records literal `__slots__` names, including inherited slots; non-literal `__slots__` is refused by name.
- `cruntime.py` enforces slot-only stores with CPython’s `AttributeError` messages; `setattr()` uses the checked store too.
- Added `AIL_CURRENT/test_ail_pre6.py`, registered it in `ail_check.py`, added a DEVLOG entry, and refreshed the manifest.

**Commit:** `8c7368a`

**Probes** (`bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`)
- `slots.py`, `slots_simple.py`, `slots_empty.py`, `slots_string.py`, `slots_inherit.py`, `slots_aliasing.py`, `slots_setattr.py`, `slots_classattr.py`, `slots_dict.py`, `slots_exception.py`, `slots_noslots.py`: same stdout on both `g` and `d` builds (including exit codes).
- `slots_dynamic.py`: refused by name on both builds: `__slots__ ... is not a string or a tuple/list of strings`.

**Tests on final commit**
- `test_ail_pre6`: 2 passed
- `test_ail_safetynet`: 5 passed
- `test_ail_files`: 18 passed, 1 skipped
- `test_ail_corpus_findings3`: 2 passed
- Targeted `test_ail_dunders` slots case: passed
- Targeted `test_ail_hot_ops` slots case: passed
- `update_manifest.py --check`: exit 0

No push was performed.
[cost $0.0000, opencode tokens {"total": 6013914, "input": 144466, "output": 15274, "reasoning": 14430, "cache.write": 0, "cache.read": 5839744}]

## review 0 failed to run: [model opencode/deepseek-v4.1-flash-free] (no final text) [cost $0.0000, opencode tokens {"total": 514619, "input": 40019, "output": 2572, "reasoning": 4828, "cache.write": 0, "cache.read": 467200}] 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `8c7368a` Enforce `__slots__`

Reviewed diff, probed HEAD vs `/tmp/base` (work), ran `test_ail_pre6` + `test_ail_safetynet` (`-j 2`, both pass), `update_manifest.py --check` (0).

### Defects

1. **Builtin exception instances now reject all new attribute stores** (regression; base matches CPython). Builtin class objects are allocated with zeroed memory in `ail_ctx_init` (`cruntime.py:16493`) and never get `n_slots = -1`, so `n_slots == 0` makes `ail_inst_setattr_chk` (`cruntime.py:16429`) treat every builtin exception class as slot-only.
   Probe `/tmp/rprobes/b1.py`:
   ```python
   try:
       raise ValueError('boom')
   except ValueError as e:
       e.custom = 5
       print(e.custom)
   ```
   CPython/base: `5`, exit 0. HEAD g+d: `AttributeError: 'exception' object has no attribute 'custom'`, exit 1. Fix: initialise `slot_ids`, `class_attr_ids` and `n_slots = -1` for builtin classes (or exempt builtin classes from the check).

2. **Wrong `AttributeError` message for assigning a method on a slots instance.** `_class_readonly` collects only `class_attrs`, not `methods`. Probe `/tmp/rprobes/s1.py`:
   ```python
   class C:
       __slots__ = ('a',)
       def f(self): return self.a
   c = C()
   try: c.f = 3
   except AttributeError as e: print(e)
   ```
   CPython: `'C' object attribute 'f' is read-only`; HEAD g+d: `'C' object has no attribute 'f'`. Same for class attributes added at runtime. This contradicts the report’s “CPython’s AttributeError messages”.

3. **Non-slots programs get different generated C.** `/tmp/rprobes/n1.py` has a class with class attributes but no `__slots__` and is never instantiated; HEAD’s `program.c` adds `g_attr_answer` / `g_attr_name` declarations and intern calls that are absent on base. Caused by the unconditional `self.attr_names.update(aname for aname, _ in class_attrs)` (`pyboxed2.py:2962`); gate it on classes that actually have slots.

### Verified / claims
- Main literal case is fixed: `s1`, `s2`, `s3` match CPython on both builds for slots/aliases/setattr/inheritance (except defect 2).
- Empty/string/list `__slots__`, inherited slots, and `__dict__` in `__slots__` behave correctly (`s2`); non-literal `__slots__` is refused by name on the general path (`s6`, `s8`).
- Report’s test results for `test_ail_pre6` and `test_ail_safetynet`, DEVLOG, and manifest: verified.
- `test_ail_files` / `test_ail_corpus_findings3` not rerun (not required for review): unverified.
- Speed: **unverified** — `/tmp/icount` cannot open `perf_event_open` (EPERM) on this runner; the new branch is on every instance store.

### Pre-existing
- `del c.attr` is refused by name on both HEAD and base (`s5`), so not caused here.
- The other fuzz67 items (class-body earlier-name reference, `C.__name__`) were not addressed, as the task asked only for the first.

VERDICT: FIX
1. Initialise builtin classes with `n_slots = -1` (and null slot arrays) so caught builtin exceptions accept attributes; probe `b1` expects `5`, HEAD gives `AttributeError`.
2. Include method names (and runtime-added class attrs) in the read-only set; probe `s1` expects `'C' object attribute 'f' is read-only`, HEAD gives `'C' object has no attribute 'f'`.
3. Stop adding class-body attribute names to `attr_names` for classes without `__slots__`; probe `n1` should generate the same `g_attr_*` set as base.
[cost $0.0000, opencode tokens {"total": 1395964, "input": 56868, "output": 6491, "reasoning": 20989, "cache.write": 0, "cache.read": 1311616}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects in `e10dd95`:

- Builtin exception classes now get `n_slots = -1` (and null arrays), so caught exceptions accept attributes again; class arrays are freed in GC/destroy.
- `_class_readonly` now includes method names (excluding internal setter keys), so `c.f = 3` gives `'C' object attribute 'f' is read-only`.
- Class-body names enter `attr_names` only for classes with `__slots__`; `n1` now emits the same `g_attr_*` set as base.

Probes (both `g`/`d` builds):
- `/tmp/rprobes/b1.py`, `s1.py`: same stdout as CPython.
- `/tmp/rprobes/n1.py`: generated `g_attr_*` set identical to base.
- `/tmp/probes/slots_exc_attrs.py`, `slots_method_ro.py`: same stdout as CPython.
- Existing `slots*.py` probes: all match; `slots_dynamic.py` refused by name on both builds.

Final-commit tests (`-j 2`): `test_ail_pre6`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_dunders`, `test_ail_hot_ops`, `test_ail_nonecrash` — 7 modules, 0 failed. Manifest `--check` exit 0. No push.

Note: assignment to a class object after definition (`C.x = 10`) is still a pre-existing compiler refusal on both HEAD and base; it was not part of this change.
[cost $0.0000, opencode tokens {"total": 3068845, "input": 82218, "output": 10262, "reasoning": 12909, "cache.write": 0, "cache.read": 2963456}]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 1915309, "input": 71877, "output": 7507, "reasoning": 17045, "cache.write": 0, "cache.read": 1818880}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T17:53:42Z
