# job job-fuzz49-10231204  started 2026-10-23T03:05:09Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed.
[cost $0.0000, opencode tokens {"total": 20534702, "input": 527416, "output": 47624, "reasoning": 76526, "cache.write": 0, "cache.read": 19883136}]
(cut off after 100 minutes)

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `git diff work..HEAD` (7 files: in-place dunder dispatch in `dunderrt.py`/`safetyrt.py`, kind clearing in `pyboxed2.py`, new `test_ail_fuzz49.py`, manifest/shards).

**Probes** (`/tmp/rprobes`, HEAD and `/tmp/base`; `bash ~/tools/cmp.sh`):
- Match CPython on both builds: p01 alias, p02 attr→other type, p03 list/dict/subscript→other type, p04 iteration mutation, p06 wrong type, p07 subclass, p08 global, p12 int += instance, p14 arg/return, p15 `__isub__` NI, p16 `__iand__` NI, p17 NI chain, p20 `None` return, p21/p29/p30 kind change then method/attr/list, p22 attr alias, p24 unused `__iadd__`, p25 loop in function, p26 bytearray alias `+=` (base was wrong, HEAD fixes), p27 deque `*=`, p31 bytearray bad type, p32 `a += a`, p35 neg/abs, p44 imul/ior/ixor NI, p46 module-level def.
- Pre-existing (identical on base): p09 `TypeError` says `+` not `+=`; p13 object repr; p18 `__ipow__`; p19 `__itruediv__`; p28 bytearray `*=` alias; p33 negative/huge `__len__`; p34 huge int overflow; p40/p45 loop/lambda with plain `__add__`.
- `tools/update_manifest.py --check` rc 0. `test_ail_fuzz49` (58.9s) and `test_ail_safetynet` (122.1s) pass.
- g11_034 (general-path class program) and p13 produce byte-identical C on base/HEAD (same sha), so no speed change there; p36 shows +9 KB C for bytearray-only programs.

Claims: `__iadd__` before `__add__`, `-= *= &= |= ^=`, container/attr targets, NotImplemented fallback, and straight-line kind change are verified. “Stops trusting the class kind after an augmented assignment” is **false** for code emitted before the assignment (loop back-edge, pre-built lambda). The worker report is empty/cut off, so its self-check listing and `test_ail_files`/`corpus_findings3` runs are unverified.

VERDICT: FIX
1. Loop-carried type change still uses the stale class kind. Clearing the kind only after emitting the augmented statement does not affect statements already emitted earlier in the same loop body.
   Probe `/tmp/rprobes/p41_loop_iadd_add.py`:
   ```python
   class B:
       def foo(self): return "B"
       def __add__(self, o): return B()
   class A:
       def __init__(self): self.n = 0
       def foo(self): return "A"
       def __iadd__(self, o): return B()
   a = A()
   i = 0
   while i < 3:
       print(a.foo())
       a += 1
       i += 1
   print("done")
   ```
   CPython: `A B B done` (exit 0). HEAD g and d: `A A A done` (exit 0). Base: `A` then `TypeError` (exit 1), so this change turns a loud failure into a silent wrong answer. (The same stale-kind weakness exists on base with plain `__add__` — p40 — but not on this probe.)
   Fix: pre-scan the function/module for augmented-assignment targets and do not assign an `instance:` kind to those names, or demote them before/at loop entry.
2. Same cause for a lambda compiled before the type-changing augmented assignment.
   Probe `/tmp/rprobes/p43_lambda_kind.py`:
   ```python
   class B:
       def foo(self): return "B"
   class A:
       def __init__(self): self.n = 0
       def foo(self): return "A"
       def __iadd__(self, o): return B()
   a = A()
   f = lambda: a.foo()
   print(f())
   a += 1
   print(f())
   ```
   CPython: `A B` (exit 0). HEAD g and d: `A A` (exit 0). Base: `A` then `TypeError` (exit 1).
[cost $0.0000, opencode tokens {"total": 3587671, "input": 183337, "output": 13874, "reasoning": 34940, "cache.write": 0, "cache.read": 3355520}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both reviewer defects.

**Cause/fix:** Clearing an `instance:` kind only after emitting `a += b` left earlier loop statements and earlier lambdas using the stale class. Now the compiler pre-scans all augmented-assignment targets (`_aug_target_names`) and never settles an `instance:` kind for those names, including a method's `self`.

**Commit:** `9ac8a58`

**Probes (both `g`/`d` builds):**
- Reviewer: `p41_loop_iadd_add.py`, `p43_lambda_kind.py` — now match CPython.
- New `/tmp/probes/rv49_*`: loop module, loop/for argument, lambda global, closure local, `__add__`-only loop, zero/negative primitive results, special-math loop (`__add__/__radd__/__mul__/__neg__/__abs__/__bool__/__len__`), alias/list-item/dict-value/attribute targets, and `-= *= &= |= ^=` type changes — all 9 match CPython on both builds.
- `p40`/`p45` (plain `__add__` loop/lambda) also now match.
- Remaining `rprobes` diffs are unchanged pre-existing ones: p09, p13, p18 (`__ipow__`), p19, p28, p33, p34.

**Final-commit tests:** `test_ail_fuzz49` 13 OK (72.9s); `test_ail_safetynet` 5 OK (119.5s); `test_ail_files` 18 OK, 1 skipped (18.8s); `test_ail_corpus_findings3` 2 OK (44.4s). `update_manifest.py --check` rc 0.
[cost $0.0000, opencode tokens {"total": 3043895, "input": 75387, "output": 9440, "reasoning": 13148, "cache.write": 0, "cache.read": 2945920}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
Review complete.

**Change reviewed:** `81eab3e` (in-place dunder dispatch) + `9ac8a58` (aug-target kind suppression), HEAD `9ac8a58`; base `/tmp/base` @ `work`.

**Probes run** (`/tmp/rprobes`, `bash ~/tools/cmp.sh` on both `g`/`d`):
- Match CPython: `r49_ni_radd_other`, `r49_imul_ni_rmul`, `r49_ibit_ni`, `r49_ibit_ni_inst`, `r49_iadd_type_then_int`, `r49_iadd_arg_dictattr` (argument/list-item/dict-value/attribute targets), `r49_iter_after_aug`, `r49_compare_hash_after_aug`, `r49_global_aug`, `r49_nonlocal_aug`, `r49_iter_mutate_aug`, `r49_self_loop`, `r49_self_lambda`, `r49_container_inplace2`, plus regressions `p38–p46`, `p05,p14–p17,p20,p21,p29,p30,p44`, and all 9 worker `rv49_*` probes.
- Fixed by this change (base wrong, HEAD matches): `p26/p32`, `r49_iter_mutate_aug`, `r49_global_aug`, `r49_nonlocal_aug`, `r49_self_lambda`, `r49_str_concat_aug*`, `r49_container_inplace2`.
- Pre-existing (identical on base): `p09` (`+=` vs `+` in TypeError text), `p13` (default repr), `p18` (`__ipow__`), `p19` (`__itruediv__`), `p28` (bytearray `*=` alias), `p33` (negative/huge `__len__`), `p34` (huge-int mul), `r49_str_format_after_aug` (empty-spec f-string uses `__str__` not `__format__`), and bytearray `b += b` not raising CPython's `BufferError` (neither build does; HEAD's alias data now matches).

**Claims:** all verified — p41/p43 fixed, loop/lambda/closure/global/nonlocal/`self` cases correct, 9 `rv49_*` pass, p40/p45 match, listed pre-existing diffs agree, tests pass (`test_ail_fuzz49` 13 OK, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 0 failed), `update_manifest.py --check` rc 0.

**Speed:** `tools/icount.c` cannot run here (`perf_event_open: Permission denied`, `perf_event_paranoid=4`). Fallback: C is byte-identical for `g11_034`, `g04_028` and a no-feature program; wall time on a 2M `+=` loop with an unused `__iadd__` class was 0.054s on both, and a 1M `a += 0; a.meth()` loop 0.052s vs 0.050s. No large slowdown. Note: programs that pull in the bytes prelude (e.g. any `import re`) now get the in-place runtime text because the injected `bytearray` class defines `__iadd__`; output is unchanged (`g01_030` matches), so this is benign, not a defect.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 9802316, "input": 156732, "output": 18472, "reasoning": 49128, "cache.write": 0, "cache.read": 9577984}]

FINAL VERDICT: ACCEPT  2026-10-23T05:50:45Z
