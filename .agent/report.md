# job job-fuzz25-10230626  started 2026-10-22T21:27:49Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
- Commit `f16a6e2` (`fuzz25: reject non-int slice bounds instead of using index 0`).
- Fixed cause: the general path took a slice bound's `.i` payload without checking its tag, so `float`/`str`/`list`/`tuple` bounds silently became index 0. Bounds are now checked; `None` stays omitted, and other types raise CPython's `TypeError`.
- Added `AIL_CURRENT/test_ail_fuzz25.py` (2 tests, wrong-typed bounds and bounds from variables/arguments/list items/dict values/attributes); registered it in `ail_check.py`.
- Probes: p1, p2, p4–p6, p8–p9, p11, p13–p16 match CPython on both builds. p11 was the first no-error stdout difference and is fixed; p13/p15/p16 confirm lists, tuples, `None`, negatives, steps and sources.
- Other differences seen, not fixed: p3/p7/p12 hit int64 literal/negation overflow or non-BMP refusals; p10 prints a different `reversed` object repr; p17 (`__index__` slice bound) remains unsupported on HEAD and was already wrong in the base.
- Final-commit tests (`-j 2`): `test_ail_fuzz25`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 passed, 0 failed. `update_manifest.py --check` OK.
- This export has no `DEVLOG`/`DIFFERENCES` files, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 3345621, "input": 102488, "output": 12347, "reasoning": 15554, "cache.write": 0, "cache.read": 3215232}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review**

Change: `bound()` in `pyboxed2.py` now tag-checks slice bounds whose static kind is not `int`/`bool`, treats `None` as omitted, and raises `TypeError` otherwise; `test_ail_fuzz25` added and manifest updated.

**Probes**
- `pA` wrong-typed bounds via variables/args/list items/dict values/attributes, str+list+tuple: HEAD matches CPython on both builds; base silently slices. Fix verified.
- `pB` `None`, `bool`, negatives, reverse: matches.
- `pC` function-returned and arithmetic bounds: matches.
- `pD` branch-reassigned wrong types: one difference remains on HEAD (`branch2`), base has three; pre-existing/incomplete, not the blocker.
- `pE`/`pE2` unreachable-branch reassignment to `None`: **new regression** below.
- `pG` program without slicing: generated `program.c` byte-identical to base.

**Defect**

1. Stale `'none'` kind drops a live integer bound. `infer_kind` records `None` from an unreachable branch, and the new `if kind == 'none': return '0','0'` omits the bound without any runtime tag check.

```python
def main() -> None:
    s = "abcdef"
    x = 2
    if False:
        x = None
    print(repr(s[x:]), repr(s[:x]))
main()
```

Expected (CPython): `'cdef' 'ab'`  
Actual on HEAD, both builds: `'abcdef' 'abcdef'`  
Base: correct (`'cdef' 'ab'`), so the change introduced this. Same failure for `while False:` and `for ... in range(0):` reassignments.

**Checks**
- `test_ail_fuzz25`, `test_ail_safetynet`: 2 passed, 0 failed.
- `update_manifest.py --check`: OK.
- Worker claim that the check covers a "variable" is false for branch-reassigned variables.
- Probe lists and other-difference claims in the report could not be independently reproduced; unverified.
- Speed not measured: `perf_event_open` is denied in this runner. The change adds a runtime check to non-statically-int bounds (including valid negative literals).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1145135, "input": 49076, "output": 6933, "reasoning": 7526, "cache.write": 0, "cache.read": 1081600}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `9738f40`.

- `bound()` now trusts only syntactic int/bool literals (including `+/-` literals); all other slice bounds get a runtime tag check. This eliminates the stale `'none'` shortcut and also the analogous stale int/bool case across unreachable/reachable branches.
- Added `test_stale_bound_kind_from_unreachable_branch` covering `if False`, `while False`, `for range(0)`, stale float/str kinds, reachable `None`/float reassignment, list and tuple slices.

Probes (`bash ~/tools/cmp.sh`, both builds):
- `pE` unreachable if/while/for reassignment: same stdout.
- `pD` reachable/static branch reassignment to str, None, float: same stdout.
- `pF` bounds from args/list items, None/bool/negative/reverse/huge: same stdout and error for zero step.
- `pG` empty/negative/huge slices, aliasing, attribute/dict bounds, str multiplication by 0/negative, list/tuple: same stdout.

Final commit tests (`-j 2`): `test_ail_fuzz25`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 passed, 0 failed. `update_manifest.py --check` OK. No `DEVLOG`/`DIFFERENCES` files exist in this export.
[cost $0.0000, opencode tokens {"total": 876579, "input": 46959, "output": 5643, "reasoning": 4393, "cache.write": 0, "cache.read": 819584}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review of `work..HEAD` (2 commits, `9738f40` HEAD)**

**What changed:** `pyboxed2.bound()` now skips the tag check only for syntactic int/bool literals and `None`; every other slice bound is stored in a temp and checked at run time (`ail2_argerr(..., 7, ...)`). Plus `test_ail_fuzz25.py` and manifest wiring.

**Probes run (`bash ~/tools/cmp.sh`, general + default):**
- `p1` wrong-type lo/hi/step via arg, list item, tuple, dict, attribute, both sequence kinds: **same**
- `p2` negative/huge/out-of-range bounds, empty strings, reverse, `str*n` for 0/negative: **same**
- `p4` stale kinds from `if False`/`while False`/`for range(0)`, reachable None/float/str reassignment: **same**
- `p5` `None`/bool/int str, `s[::0]`, `s[::-0]`: **same**
- `p6` bounds from arithmetic/`int()`/`math.floor`, nested slicing: **same**
- `p7` deleted/unbound variable used as bound: **same** (UnboundLocalError)
- `p8` attribute reassigned to a wrong type: **same**
- `p11` literal float/str/list/tuple/dict/huge bounds, `None:"x"`, multiple wrong bounds: **same**
- `p3`/`p12` evaluation order with side-effecting/raising later bounds: **DIFF — defect below**
- `z.py`/`z2.py` (no non-literal slice bound): generated C byte-identical to base, output same.
- `p10` `enum.IntEnum` bound: CPython succeeds; base silently slices wrong; HEAD raises `TypeError`. Pre-existing unsupported `__index__`, not introduced by this change.

**Defect (caused by the change):**
1. Wrong-type checking happens before the remaining bound expressions are evaluated. CPython evaluates lower, upper and step expressions first (left to right), then converts them; the new emitted check aborts immediately after evaluating a wrong bound. Probe:
```python
def side(x):
    print("side", x); return x
def boom():
    print("boom"); raise RuntimeError("boom")
def main() -> None:
    s = "abcdef"
    try: print(s[1:"x":side(2)])
    except Exception as e: print("A", type(e).__name__)
    try: print(s[1:"x":boom()])
    except Exception as e: print("B", type(e).__name__)
main()
```
Expected (CPython and base on the second case):
```
side 2
A TypeError
boom
B RuntimeError
```
Actual on HEAD (both builds):
```
A TypeError
B TypeError
```
The lower-bound variant `s[side(1.0):side(3)]` likewise omits `side 3`, and `s[1.0:boom()]` reports `TypeError` where base/CPython report `ZeroDivisionError`. Fix by evaluating all three bounds into temps first, then performing the three tag checks in lower/upper/step order.

**Claim check:** literal-only fast path — verified; stale-kind removal — verified; `test_ail_fuzz25` added and passing — verified; worker probes `pD,pE,pF,pG` same stdout on both builds — verified; four final test modules passing — verified (`fuzz25`, `safetynet`, `files`, `corpus_findings3`: 4/4); `update_manifest.py --check` — verified; no `DEVLOG`/`DIFFERENCES` — verified. Claim that pF covered a zero step: verified via `s[::False]` (exit 1, same as CPython).

**Speed:** `perf_event_open` is denied here (`perf_event_paranoid=4`), so `tools/icount.c` could not measure instructions. Wall time over 300 runs was unchanged on `g01_006` and `g08_020`; `g00_010` C is identical. A 30M-iteration variable-bound slice microbenchmark on the general path ran 0.09s base vs 0.11–0.13s HEAD (~20–40%), not a large regression.

VERDICT: FIX
1. Slice bounds are type-checked too early: later bound expressions are skipped and their exceptions are masked. Probe `p12`/`p3`; expected `side 2`, `A TypeError`, `boom`, `B RuntimeError`; actual `A TypeError`, `B TypeError`.
[cost $0.0000, opencode tokens {"total": 2490657, "input": 67724, "output": 10480, "reasoning": 16037, "cache.write": 0, "cache.read": 2396416}]

FINAL VERDICT: FIX  2026-10-22T22:14:09Z
