# job job-fuzz47-10231202  started 2026-10-23T03:03:44Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-fuzz47-10231202` (`8155e45`).

**Cause/fix:** `pyboxed2._hoist_defaults` treated tuple defaults as immutable literals (`ast.literal_eval` accepts `([],)`), so `def f(t=([],))` rebuilt the tuple per call and shared no state. Added `ast.Tuple` to `_HOISTED_DEFAULTS` (`AIL_CURRENT/python/pkg-v12/pyboxed2.py:1049`).

**Probes (`/tmp/probes`, both g/d builds):**
- Shared mutable defaults: p01 list, p08 dict/set/bytearray, p09 multiple lists, p13 caller alias — same as CPython.
- Fixed case: p15 tuple+list (was `([1],)` each call; now `([1],), ([1,1],), ([1,1,1],)`); p16 nested tuple; p17 tuple dict/set; p18 keyword-only tuple; p19 bytearray; p21 combined; p23 method tuple; p24 dict/attribute paths — all same.
- Immutable/global capture: p20b empty/negative/int64-max tuple; p20 huge `10**30` still errors (pre-existing “integer overflow”, not silent); p03/p14 keyword/typed defaults — same.
- Refusals by name: p02 required kw-only, p04 `**dict`, p05 positional-only, p06/p07/p10/p11 wrong arg counts/keywords, p12 default referencing a parameter, p22 first-class function with defaults — all refused, never silent.

**Tests:** `test_ail_fuzz47` 8 tests OK; `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all OK (`-j 2`, final commit). `test_ail_fuzz1` also run: its 27 non-generator tests passed, 2 pre-existing failures because `tools/difffuzz.py` is absent from this export.

`update_manifest.py --check` passes. `DEVLOG`/`DIFFERENCES` files do not exist in this export, so no entries were added; documented here instead.
[cost $0.0000, opencode tokens {"total": 3833830, "input": 80430, "output": 12156, "reasoning": 10300, "cache.write": 0, "cache.read": 3730944}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change:** one-line addition of `ast.Tuple` to `_HOISTED_DEFAULTS` in `pyboxed2.py`, plus `test_ail_fuzz47.py` and manifest pin.

**Verified**
- The reported bug is real and fixed: `/tmp/rprobes/r23_noargs.py` on base prints `([1],)` three times; on HEAD both builds match CPython (`([1],)`, `([1, 1],)`, `([1, 1, 1],)`).
- Tuple-default probes match CPython on both builds: mutable list/dict/set/bytearray inside tuples, nested tuples, keyword-only, `*args`+`**kw` defs, methods/static/class methods, generators, recursion, global aliases, attribute/list/dict paths, separate defaults, star-unpacking, heterogeneous/empty/None/int64-boundary tuples, large tuples, mutation-during-iteration.
- `**dict` calls, positional-only, wrong arg counts, default-referencing-parameter are named compile-time refusals (acceptable).
- Programs without tuple defaults: `--debug-dir` C is byte-identical between base and HEAD on both builds.
- `test_ail_fuzz47`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`); `update_manifest.py --check` passes. No `DEVLOG`/`DIFFERENCES` exists in the export, as reported.
- Speed: no hot-code effect; non-users' C is unchanged, and users build the default once at init instead of per call.

**Defect (caused by the change):** hoisting introduces/extends the fixed module-global name `_ail_default_N`, which can overwrite a valid user global.

`/tmp/rprobes/r27b_collision_tuple.py`
```python
_ail_default_0 = 99

def f(t=([],)):
    return t

def main():
    print(_ail_default_0)
    print(f())

main()
```
- Expected (CPython and base): `99` then `([],)`.
- Actual on HEAD (both builds): `([],)` then `([],)` — the hoisted `_ail_default_0 = ([],)` clobbers the user's variable.

**Pre-existing (identical on base):** method defaults resolve class-body names against module scope (`r19_classscope.py`); list defaults already suffer the same `_ail_default_0` collision (`r28_collision_list.py`); nested-class/`**dict`/decorator constructs are refused or unsupported.

VERDICT: FIX
1. `_hoist_defaults` uses `_ail_default_%d` without checking existing module bindings; a tuple default now silently overwrites a user global with that name (probe `r27b_collision_tuple.py`, expected `99\n([],)`, got `([],)\n([],)` on both builds, while base matches CPython). Generate collision-free names (and apply the same to all hoisted defaults).
[cost $0.0000, opencode tokens {"total": 1260552, "input": 53694, "output": 8724, "reasoning": 22710, "cache.write": 0, "cache.read": 1175424}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the collision: hoisted defaults now take the first `_ail_default_N` not bound or mentioned anywhere in the program (all hoistable default kinds), with match/import/handler/argument names included.

- Commit: `e20e183`
- Probes: 12/12 match CPython on both builds (`c01`–`c12`: tuple/list/dict/set/comp/call defaults; assignment, def, class, import, loop/except, match, `global`, parameter-name collisions; 3 simultaneous user names)
- Tests on final commit: `test_ail_fuzz47` 10 OK, `test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2 OK
- `update_manifest.py --check`: passes
- Extra: `test_ail_fuzz3`/`test_ail_fuzz3n` pass; `test_ail_fuzz1` has 1 error/1 failure because `tools/difffuzz.py` is absent from this export (unrelated to the change)
- No `DEVLOG`/`DIFFERENCES` exists in this export, so no records were edited.
[cost $0.0000, opencode tokens {"total": 1839917, "input": 56547, "output": 7892, "reasoning": 6262, "cache.write": 0, "cache.read": 1769216}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `e20e183` (plus `e005848`, `8155e45`); no source edits or commits.

**Change:** tuple defaults are now hoisted and evaluated once, and hoisted `_ail_default_N` names skip every name bound or mentioned in the tree.

**Probes** (`cmp.sh`, both builds unless stated):
- q01/q05/q10/q12 tuple with lists/dicts/sets, identity across calls, explicit args, recursion, list/attribute/dict delivery: same.
- q02/q03 class and staticmethod tuple defaults, class attr `_ail_default_0`: same.
- q07/q08/q11/q19b empty, unpacked, heterogeneous, keyword-only, positional-only, empty-tuple identity: same.
- q06 plus worker c01–c12 collision via assignment, def, class, import, loop/except, match, `global`, parameters, comprehension: 12/12 same; remaining q06 difference is a pre-existing class-object repr.
- q13 (no feature) and q14 (list defaults): generated `program.c` identical to `/tmp/base` (only report paths differ).
- q22/q23 wrong counts, q24 async, q19 `id`/tuple comparison: refused by name on HEAD and base.

**Pre-existing (identical on base):** nested-def tuple default not shared (q20); class-scope method default reads module value (r19); g22 failure; huge-int exit difference (p20).

**Tests on HEAD:** `test_ail_fuzz47`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all ok (256s); `test_ail_fuzz3`/`fuzz3n` ok; `test_ail_fuzz1` has 1 failure/1 error from missing `tools/difffuzz.py`, exactly as reported. `update_manifest.py --check` passes.

**Claims:** verified — 12/12 probes, listed tests, manifest check, absence of DEVLOG/DIFFERENCES. Speed unverified: `icount`/perf is denied (`perf_event_paranoid=4`); the g08 C diff removes one tuple allocation per call, so no plausible slowdown.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3693530, "input": 144374, "output": 11039, "reasoning": 35013, "cache.write": 0, "cache.read": 3503104}]

FINAL VERDICT: ACCEPT  2026-10-23T04:19:21Z
