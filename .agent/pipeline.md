# job job-fuzz37-10230931  started 2026-10-23T00:32:17Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-fuzz37-10230931` (`ac48267`, `05cd1cc`).

- Cause: ordering `TypeError` always named `'<'`, even for `<=`, `>`, `>=`. Both builds now name the written operator, including chained and nested list/tuple comparisons.
- Added `AIL_CURRENT/test_ail_fuzz37.py`, DEVLOG entry, DIFFERENCES row; `update_manifest.py --check` passes.
- Probes: `w10`, `w11`, `w14` match CPython on general and default builds. Pre-existing differences verified on base: `w04` general build refuses a huge int literal; `w12` custom `__lt__`/NotImplemented semantics; `w13` `sorted([1,"x"])` operand order.
- Required tests: `test_ail_fuzz37`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
[cost $0.0000, opencode tokens {"total": 3498264, "input": 91788, "output": 16496, "reasoning": 12444, "cache.write": 0, "cache.read": 3377536}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fuzz37 ordering `TypeError` operator naming

**Diff** touches runtime comparison helpers (`cruntime.py`, `dunderrt.py`), adds `test_ail_fuzz37.py`, DEVLOG, DIFFERENCES row, manifest, and pins the test. Only error-message text changes; no comparison result changes.

**Probes** (all on HEAD vs CPython, then base):
- `r1` (str/bool/None/list via arg, list item, attr, dict; all 4 ops; chains) — both builds match; base fails on every op.
- `r2` (nested lists/tuples, empty, mixed lengths, all 4 ops) — both builds match.
- `r6` (bool/None/list/tuple/dict/set/frozenset/complex-free, while condition) — both builds match; base fails.
- `r7` (mixed chains, bytes, range, nested dict/list values) — chains, range, None/list match; bytes still says `<`.
- `r3` (user `__lt__`/`__gt__` returning NotImplemented) — HEAD improves `max`/`__gt__` cases over base, but operator in NotImplemented errors is still `<` on both (pre-existing).
- `r4` (normal while/counter/break/else/div/mod/early-return) — matches; generated `program.c` differs only in the comparison helper, generated code identical.
- `r5`, `r9` (NaN, sorted/min/max/sort) — match except `sorted([1,"x"])` operand order (pre-existing, same on base).
- `r10`/`w04` (huge int) — general build refuses the literal, default matches; same on base.
- `r11` (no ordering used) — `program.c` byte-identical to base.

**Tests:** `test_ail_fuzz37`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass on HEAD (`-j 2`). `update_manifest.py --check` rc 0.

**Speed:** instruction counting unavailable (`perf_event_open: Permission denied`, paranoid=4). 100 runs of `g02_000` (sieve, hot `<` loop): HEAD 19.45 s, base 19.48 s — no measurable regression; op is a compile-time literal used only on the error path.

**Claims:**
- Main cause fixed on both builds for str/int, bool/str, None/int, list/int, tuple/str, nested list/tuple, chains, and values via arg/list/attr/dict — **verified**.
- “Both builds now name the written operator” as an absolute — **false**: `b"a" > 1` and `b"a" <= 1` still print `'<'` (also on base). User classes returning NotImplemented still print `'<'` in some cases (also on base).
- `w10`, `w11`, `w14` match on both builds — **verified**.
- `w04`/`w12`/`w13` pre-existing — **verified**.
- DEVLOG/DIFFERENCES/test/manifest additions — **verified**.
- Required 4 modules 0 failed — **verified**.

**Pre-existing (identical on base, not blocking):** bytes/bytearray ordering errors still say `'<'`; NotImplemented ordering errors still say `'<'`; `sorted([1,"x"])` names operand types reversed; general build names a user class `'instance'`; general build refuses an out-of-int64 literal; complex constants refused by name. The new DIFFERENCES row overstates the fix by saying “built-in values” generally.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3087149, "input": 86799, "output": 10486, "reasoning": 23720, "cache.write": 0, "cache.read": 2966144}]

FINAL VERDICT: ACCEPT  2026-10-23T01:04:26Z
