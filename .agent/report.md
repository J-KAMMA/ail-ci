# job job-setord1-11080650  started 2026-11-07T21:50:31Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
**Fixed and committed** (`6bd501c` + `caff23a` on `job-setord1-11080650`).

**What broke:** `test_ail_re_value` isn't on this older base — it lives on `origin/integ`. I fetched integ into a temp worktree, applied my job's diff there, and reproduced the failure: that test's ALIAS program does `s = {7}`, `sp = s.pop`, then prints `s` after the pop. My set-order refusal rejected the print (and the typed path the pop), even though a set of 0 or 1 elements has only one possible order.

**Fix (general path only):**
- `pyboxed2._small_set_names`: statically proves names whose every binding is an empty `set()`/`frozenset()` or a one-element display and that nothing grows (`add`/`update`/`intersection_update`/`symmetric_difference_update`); `_refuse_set_walk` lets those and one-element displays through. Everything else reaching the name is still caught at run time.
- `ail2_refuse_set_order`: refuses only `len > 1`.
- `ail_meth_set_pop`: returns the only element of a one-element set (`KeyError('pop from an empty set')` stays; two-plus still refused).
- `test_ail_setorder.py` gains `s6` (singleton print/pop/walk + empty-name walk match CPython on general and default builds).

**Verification on the final commit `caff23a`, `-j 2`:**
- `test_ail_safetynet` + `test_ail_files`: 23 tests, OK (1 skip), 116.7 s.
- `test_ail_corpus_findings3` + `test_ail_setorder` (6) + `test_ail_sets_general`: 12 tests, OK, 122.7 s.
- Earlier on the same code: `test_ail_int_dict_set`, `test_ail_collections`, `test_ail_gaps_api1/api2`, `test_ail_lang_gaps`, `test_ail_refusal_messages`, `test_ail_dict_delete` — all OK.
- `test_ail_re_value` on `origin/integ` + full job diff + this fix: **5/5 OK**; ALIAS matches CPython (exit 3) on both builds.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds, `/tmp/probes/`): `p01`–`p14`, `e1`–`e4`, `s3`–`s5`, `t1`, `t2` match CPython (empty/singleton print, str, repr, list, tuple, f-string, iteration, len/sorted/sum, singleton pop, order-free ops/comparisons, keyed sort, unhashable display, aliasing); `p03`–`p07`, `p13` refused by name; `s4` (two elements) refused at build. Two known residuals on this base: `s1`'s `s.pop` bound-method alias raises `AttributeError` (this base predates integ's bound-method support; it matches on integ), and `s2`'s `frozenset([9])` (one element via a list argument, not a proven-small display) stays refused.

`tools/update_manifest.py --check` passes; only `.agent/pipeline.md` remains untracked.
[commandcode stop=end_turn turns=131 out_tokens=72254]

## review 0
[model commandcode/deepseek-v4.1-flash]
I found a clear regression. Writing the report.

## Review: `job-setord1-11080650` (caff23a, 6bd501c)

**What the change really does:** it narrows the set-iteration-order refusal from "any non-empty set" to "any set with more than one element", and adds `python/pkg-v12/pyboxed2.py:_small_set_names`, a per-body static scan that skips the compile-time refusal for a name whose every binding is `set()`/`frozenset()`/a ≤1-element display, plus one-element displays themselves. This matches the report.

### Defect (caused by the change)

A **one-element display is exempted at compile time without looking at its element**, and the run-time `ail2_refuse_set_order` only inspects the top-level value. So a singleton set holding a *multi-element* set is no longer refused and now prints AIL's insertion order with exit 0 — base refused it by name.

Probe `/tmp/rprobes/n1.py`:
```python
def main():
    print({frozenset([3, 1, 2])})
main()
```
- expected (CPython): `{frozenset({1, 2, 3})}` exit 0
- HEAD general build: `{frozenset({3, 1, 2})}` exit 0 — **wrong output**
- base: named refusal, exit 1 (`walking a set or frozenset shows an order...`)

The same hole applies to a name whose proven-small set holds a nested set (also `str`/`repr`/f-string of it). This is a refusal silently turned into wrong output, the exact failure mode the feature exists to prevent.

### Verified claims
- `_refuse_set_walk` / `_small_set_names` / `ail2_refuse_set_order` (`>1`) / singleton `ail_meth_set_pop`: as described — verified by reading and by probes `p1 p3 p6 p7 p9 p12 p13 p14 v1 v2 v3 v4 r1 r2 r7` (singleton and empty print/list/tuple/f-string/iteration/pop, empty `pop` → `KeyError`, two-element `pop` refused, typed `set[int]` singleton OK).
- Recursion into nested defs excluded: `q4`/`q5`/`q6`/`q8`/`r3` (attribute, dict value, closure, default-arg) grow the set and are still refused or are prefix-identical to base.
- `test_ail_setorder` + `test_ail_safetynet` on HEAD, `-j 2`: 2 modules, 0 failed (27.7s / 86.7s).
- `s6` exists and passes; `frozenset([9])` (one element from a list) still refused (`p10`, `v7`).

### Unverified
- `test_ail_re_value` 5/5 on `origin/integ`: I could **not** reproduce it — `git apply` of the job diff onto `origin/integ` fails (context drift; integ has no `ail2_refuse_set_order` and a different `pop` that already returns the first element). My integ run was the unmodified tree, so the claim stands unverified on this reviewer's evidence.

### Pre-existing (identical on base)
- `"%s" % (s,)` and `"{}".format(s)` print insertion order (`u1`, `u2`).
- `print([{30,10,20}])` prints insertion order (`n2`).
- Non-singleton `pop()` refused (`r4:/tmp/base`).

I did not run speed probes (change is in a refusal guard, not hot code) — unverified.

VERDICT: FIX
1. One-element displays and proven-small names bypass the refusal without checking their elements, so a nested multi-element set now prints AIL order instead of being refused. Probe `/tmp/rprobes/n1.py`: `print({frozenset([3, 1, 2])})`; expected `{frozenset({1, 2, 3})}` (CPython) or a named refusal; actual `{frozenset({3, 1, 2})}`, exit 0. Base correctly refused. Make the compile-time exemption recurse into the display's elements (or keep the run-time guard on the inner values).
[commandcode stop=end_turn turns=39 out_tokens=104425]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed the reviewer's defect and committed as `13b365d`.

**Defect fix:** `ail2_refuse_set_order` now uses a recursive `ail2_set_order_hidden` that descends through a set's single element and through tuples/frozensets (the only containers a set can hold) and refuses when any reachable set has >1 element. This closes the hole for a one-element display or a name proven small whose element is itself a multi-element set. Top-level lists/tuples are still not descended (pre-existing behaviour, unchanged).

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both `g` and `d` builds):
- `n1`–`n5` (nested set in display, name, str/repr/f-string, tuple element, deeper frozenset): refused by name, exit 1 — matches the allowed outcome.
- `p1` (`{frozenset([1])}`, `{(1,2)}`, `{frozenset()}`, `{(1,frozenset([2]))}`), `p4` (singleton/empty print, pop, walk, f-string, list/tuple), `p7` (order-free `len`/`in` on a nested singleton): match CPython on both builds.
- `p2` (argument), `p3` (attribute/dict value/list item), `n6`/`n7` (`list`/`tuple` of nested singleton): refused by name.
- `p6` (`frozenset([9])`): still refused at compile time, as on base.

**Tests on final commit `13b365d`** (`python3 -m unittest -q`, max 2 parallel): `test_ail_setorder` 7/7, `test_ail_sets_general` 4/4, `test_ail_corpus_findings3` 2/2, `test_ail_safetynet` 5/5, `test_ail_files` 18 (1 skip). `update_manifest.py --check` exit 0.

**Not verified:** `test_ail_re_value` does not exist on this base (it lives on `origin/integ` and the reviewer also could not reproduce it). The singleton `s = {7}`/`s.pop`/print path it relies on is unchanged and still matches CPython (`p4`).
[commandcode stop=end_turn turns=45 out_tokens=31998]

## review 1
[model commandcode/deepseek-v4.1-flash]
Stopping here per the time box. Report:

## What the change really does
`work..HEAD` makes sets/frozensets of 0–1 elements order-free on the general path: `_small_set_names` exempts names whose every binding is an empty/one-element display or `set()`/`frozenset()`, one-element displays are exempted, `ail2_refuse_set_order` refuses only when a reachable set has >1 element (descending through the single element, tuples and frozensets), and `set.pop()` returns the only element. The last commit (`13b365d`) adds the recursive descent so a singleton holding an order-showing element is still refused; it touches only `pyboxed2.py`, `test_ail_setorder.py`, docs and manifest. That matches the report.

## Task requirement (the point of the job)
`test_ail_re_value` is absent from this base (true: worktree `work`/`/tmp/base` has no such file); it is on `origin/integ`. I merged the branch into a `/tmp/integ` worktree at `origin/integ`: `cruntime.py`/`pyboxed2.py` auto-merged cleanly (only docs/manifest conflicted), and

- `test_ail_re_value` **ok** (5 tests), `test_ail_setorder` **ok** (7 tests), `-j 2`, 0 failed.

So the change does make the named module pass on the integration branch, and the report's explanation is correct.

## Tests on HEAD (`13b365d`)
`test_ail_setorder` + `test_ail_safetynet`: 2 modules, **0 failed**. (`test_ail_setorder` has 7 tests; `s7` does test nested-singleton refusal on general and default.)

## Probes (`cmp.sh`, both g and d builds)
- `c1`: singleton set via argument, list item, attribute, dict value and nested singleton — matches CPython.
- `a2`: `{frozenset([1])}`, `{(1,frozenset([2]))}`, `{frozenset()}` match; `{frozenset([frozenset…])}`, `{frozenset([3,1,2])}`, `{(frozenset([2,1]),)}` refused by name (base refuses too).
- `c2`: nested multi-element set via argument and dict value refused at run time, never printed wrong.
- `a3`/`b1`/`b3`/`b4`/`b7`/`b8`: singleton/empty print, pop, iteration, argument and return, remove-to-empty — match; 2-element pop refused by name (same as base).
- `a4`: pop of `{frozenset([3,1,2])}` gives `sorted(x)`/`len` right; printing the popped inner set is refused (base refused too).
- `b5`: `{-1}`, `{1.5}`, `{True}`, `{'a'}`, `{None}`, `{(1,)}` match.
- `d1`/`d2`: mutation during singleton iteration (direct and via a helper) raises `RuntimeError: Set changed size during iteration` as CPython, both builds.
- `a9` (no sets): output matches; `--debug-dir` C differs from base only in the runtime prelude (singleton pop branch + guard helper) — no program-body hunk.
- Refusals still narrower than CPython (`t.add(8); print(t)`, `v.update([]); print(v)`, `print(alias)`) are all refusals on base as well.

## Report claims
- Recursive `ail2_set_order_hidden` fix: **verified** (code + a2/c2).
- Their n/p probe set: consistent with mine; not rerun individually — **unverified**.
- `test_ail_setorder` 7/7, safetynet 5/5: **verified**. sets_general/corpus_findings3/files: **unverified** (not required for this job).
- `test_ail_re_value` 5/5 on integ: **verified**. `s={7}`/pop/print path: **verified**.
- Speed: **unverified** — `perf_event_open` denied; the only extra work per printed non-set is one tag compare in an inlined helper (old code also compared tags), so no hot-loop change is expected.

## Pre-existing (not blocking)
- `sp = s.pop` bound-method alias is unsupported on this base (`AttributeError`), as the report says; it works on integ.
- Tuple-unpacking `a, b = s` and `[*s]` use `ail2_unpack_iter`, which never calls the set guard; the diff does not change those sites, so any divergence there predates this change.

No defect attributable to the change; the required module passes on the integration branch and the added fix is exercised by a test.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=53 out_tokens=37549]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T01:22:39Z
