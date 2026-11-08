# job job-rbsetord2_rr1-11081819  started 2026-11-08T09:20:19Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `job-setord2` (`fd0162e..c7a948e8`) on the current tree; `job-rbsetord2-11081135` had only its export commit, no work commits.

- Commit: `2bc6999b` (not pushed, per rules)
- `tools/diff_ids.py` is absent on this tree; `tools/update_manifest.py` regenerated pins and `--check` passes.
- Tests on final commit (`par_check.py -j 2`): `test_ail_setorder`, `test_ail_sets_general`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed.
- Probes (general + default), all match CPython: `p_coll2`, `p_typed_dense`, `p_tuple`, `p_tuple_rt`, `p_pop_empty`, `p_frozen`, `p_str_order_free`, `p_set_display` — 8/8.
[cost $0.0000, opencode tokens {"total": 3563793, "input": 83838, "output": 11577, "reasoning": 16346, "cache.write": 0, "cache.read": 3452032}]
    tool time: bash 12.1 min
        385s bash   python3 tools/par_check.py -j 2 test_ail_setorder test_ail_sets_general test_ail_safetynet test_ail_files test
        278s bash   python3 tools/par_check.py -j 2 test_ail_setorder test_ail_sets_general test_ail_safetynet test_ail_files test
         40s bash   cd /tmp/probes && : > results.txt; for p in p_coll2 p_typed_dense p_tuple p_tuple_rt p_pop_empty p_frozen p_st
          9s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-rbsetord2-11081135 2>&1 | tail -3; git log --oneline FETCH
          8s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-setord2-11080819 2>&1 | tail -5; echo EXIT:$?
          1s bash   git status && git log --oneline -10 && git branch -a | head -30
          1s bash   python3 tools/update_manifest.py 2>&1 | tail -20; echo EXIT:$?; python3 tools/update_manifest.py --check 2>&1 
          0s bash   git add DEVLOG.md AIL_CURRENT/manifest.d/27.txt AIL_CURRENT/manifest.d/37.txt AIL_CURRENT/manifest.d/45.txt AI

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: re-applied `setord2` set-order emulation

**What the change really does.** Replaces the setord1 "refuse any set walk/pop" rules with a CPython-3.12 hash-table emulation for deterministic elements (int/bool/None/float/tuples) on the boxed path and on typed `set[int]`; str/bytes sets keep insertion order (unrefused); adds CPython's constant-folding of >2-element set displays; rewrites `test_ail_setorder`, `test_ail_sets_general`, DIFFERENCES, DEVLOG.

**Re-application fidelity.** The five relevant files are byte-identical to the accepted branch (`cruntime.py`, `pyboxed2.py`, `pyfunc.py`, `test_ail_setorder.py`, `test_ail_sets_general.py`, `docs/spec/DIFFERENCES.md`); `DIFFERENCES.md` only keeps newer base rows. `tools/diff_ids.py` genuinely absent. `update_manifest.py --check` passes. The defects below are inherited from the accepted change, not conflict-resolution mistakes.

**Tests (HEAD, final commit):** `test_ail_setorder`, `test_ail_sets_general`, `test_ail_safetynet` — pass (`-j 2`, 0 failed). Worker's 8 probes re-ran 8/8 match.

**Probes on HEAD (general `g` / default `d`), compared with base `/tmp/base`:**

| probe | result |
|---|---|
| `p_popgrow`, `p_types`, `p_flow` | match CPython |
| `p_min1` / `p_finger` | **wrong pop order** (base: named runtime refusal) |
| `p_typed_finger` | typed/default match; **general wrong after growth** |
| `p_ops2` / `p_typed_ops` (typed mode) | **difference order wrong** |
| `p_frozen_keys` | **wrong order**, set of frozensets (base: named refusal) |

### Defects

1. **`set.pop()` finger is wrong after an insertion that follows a pop.** `/tmp/rprobes/p_min1.py`:
```python
s = set()
for i in range(8): s.add(i * 10)
print(s.pop())
s.add(64)
print(s.pop())
```
Expected (CPython): `0` then `70`; actual HEAD `g`/`d`: `0` then `64`. `ail_setx_rebuild` remaps `fin` for CPython-table sets from a live-entry count, and `ail_setx_ct_resize` never resets it to 0, so `pop` starts at the wrong slot (the re-added 64 reuses slot 0). `p_finger` drains `[64,70,40,…]` vs CPython `[70,40,…,64]`. Related: `p_typed_finger` (annotated `set[int]`, 40→80 growth) general `p2` = `5120`, CPython `512` (typed/default match).

2. **`a - b` / `difference` / typed `difference_update` do not implement CPython's copy-and-delete path.** `/tmp/rprobes/p_ops2.py`:
```python
c = set()
for i in range(40): c.add(i * 128)
print(list(c - {0, 128}))
```
Expected `[256, 384, 512, 640, …]`; actual `[256, 512, 640, 384, …]` on `g` and `d`. CPython copies `a` and deletes when `len(a)>>2 > len(b)`; `ail_setx_filter` always filters into a fresh set. Typed path also wrong (`p_typed_ops.py`: `minus` and `difference_update`), while the current test only uses sizes that take the filter path.

3. **Sets/tuples of `frozenset` of ints now print AIL's insertion order instead of being refused.** `/tmp/rprobes/p_frozen_keys.py`:
```python
s = {frozenset([1]), frozenset([2]), frozenset([3]), frozenset([4]), frozenset([5])}
print(list(s))
```
Expected (deterministic CPython hash): `[frozenset({2}), frozenset({3}), frozenset({1}), frozenset({5}), frozenset({4})]`; actual: `[{1},{2},{3},{4},{5}]`. `ail_setx_det` treats `frozenset` (and tuples containing it) as non-deterministic, but the change removed setord1's named refusal, so the wrong order is silent. Base refuses by name.

**Pre-existing:** none found for these probes (base refuses each by name at build or run time, so every defect above is a new wrong output, not an identical base difference).

**Unverified:** instruction counts/speed (`gdev` set programs) were not measured; `test_ail_files` and `test_ail_corpus_findings3` were not re-run (only touched modules + safetynet per instructions); memory-ownership stress beyond the alias probes in `p_flow` (which matched).

VERDICT: FIX

1. `p_min1.py` (`/tmp/rprobes`): expected pop sequence `0, 70`; actual `0, 64` on general and default. `ail_setx_rebuild`/`ail_setx_ct_resize` must not corrupt/reset the CPython pop finger.
2. `p_ops2.py`, `p_typed_ops.py`: `c - {0,128}` expected `[256,384,512,640,…]`; actual `[256,512,640,384,…]`. Implement CPython's copy-and-delete difference heuristic (and the typed `difference_update`).
3. `p_frozen_keys.py`: expected CPython order `[fs2,fs3,fs1,fs5,fs4]`; actual insertion order. Emulate frozenset-of-int hashes or refuse the walk by name.
[cost $0.0000, opencode tokens {"total": 3326290, "input": 121709, "output": 9651, "reasoning": 32818, "cache.write": 0, "cache.read": 3162112}]
    tool time: bash 3.8 min, write 0.0 min
        132s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         38s bash   cd /tmp/probes && cat results.txt 2>/dev/null | tail -20; echo ===; for p in p_coll2 p_typed_dense p_tuple p_t
          9s bash   cd /tmp/rprobes && for p in p_popgrow p_ops; do echo "######## $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /ho
          9s bash   cd /tmp/rprobes && for p in p_types p_flow; do echo "######## $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /hom
          5s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p_ops2.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -60
          5s bash   cd /tmp/rprobes && for p in p_finger p_frozen_keys; do echo "#### base $p"; bash ~/tools/cmp.sh /tmp/rprobes/$
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p_finger.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -4
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p_finger.py /tmp/base 2>&1 | tail -15

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed on `job-rbsetord2_rr1-11081819` as `c3ae6357`.

**Fixes (cruntime.py)**
1. `pop()` finger: `ail_setx_rebuild` now preserves the CPython-table slot cursor (`fin`) instead of recomputing it from dense-entry indices; resize keeps the numeric cursor as CPython does.
2. `a - b` / `difference` / `difference_update` / typed `-=`: now use CPython's `len(a)>>2 > len(b)` copy-and-delete path, keeping a's table layout, with the dummy-resize rule.
3. Sets of frozensets/tuples-of-frozensets: `ail_setx_det` now recurses into frozensets; `ail_frozenset_hash` already matches CPython, so these walk/pop in CPython order.

**Tests (final commit, `-j 2`):** `test_ail_setorder`, `test_ail_sets_general`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed.

**Probes (general `g` and default `d`, all match CPython):**
- New: `p_pop_boundary`, `p_typed_pop_boundary`, `p_diff_boundary`, `p_typed_diff_boundary`, `p_frozen_boundary` — 5/5.
- Reviewer's: `p_min1`, `p_finger`, `p_typed_finger`, `p_ops2`, `p_typed_ops`, `p_frozen_keys` — 6/6.
- Regression: `p_ops`, `p_types`, `p_flow`, `p_popgrow` — 4/4.

`test_ail_setorder` gained S8–S10; DIFFERENCES/DEVLOG updated; `tools/diff_ids.py` is absent, `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 7261892, "input": 171677, "output": 16250, "reasoning": 26925, "cache.write": 0, "cache.read": 7047040}]
    tool time: bash 15.1 min, read 0.0 min, edit 0.0 min, write 0.0 min
        299s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_set
        289s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_set
        120s bash   python3 --version; find / -name "setobject.c" 2>/dev/null | head; ls /usr/lib/python3.*/ 2>/dev/null | head
         61s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && cd AIL_CURRENT && timeout 600 python
         45s bash   for p in /tmp/probes/p_pop_boundary /tmp/probes/p_typed_pop_boundary /tmp/probes/p_diff_boundary /tmp/probes/p
         24s bash   cd /tmp/probes && for p in p_pop_boundary p_typed_pop_boundary p_diff_boundary p_typed_diff_boundary p_frozen_
         22s bash   cd /tmp/rprobes && for p in p_min1 p_finger p_typed_finger p_ops2 p_typed_ops p_frozen_keys; do echo "########
         21s bash   cd /tmp/rprobes && for p in p_min1 p_finger p_typed_finger p_ops2 p_typed_ops p_frozen_keys; do echo "########

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review: `job-rbsetord2_rr1-11081819` (commits `2bc6999b`, `c3ae6357`)

**What the diff really does.** Re-applies the accepted setord2 change (CPython hash-table order emulation for boxed sets and typed `set[int]`, removal of the set-walk/`pop` refusals, plus the compiler's frozenset-constant folding reproduction) and adds the worker's three fixes: keep `pop()`'s slot finger across rebuilds, `difference`/`-=` copy-and-delete heuristic, `ail_setx_det` recursion into frozensets. That matches the report.

**Tests.** `python3 tools/par_check.py -j 2 test_ail_setorder test_ail_sets_general test_ail_safetynet` → 3 modules, 0 failed on HEAD. `tools/update_manifest.py --check` → rc 0. `tools/diff_ids.py` is absent (confirmed).

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, general `g` and default `d`; ~25 programs in `/tmp/rprobes`):
- match CPython: `p_iter`, `p_hash` (None/float/bool/frozenset hash collisions), `p_copy` (copy/frozenset/ctor/update over sizes and dummies), `p_alias` (aliasing, copy independence), `p_str`/`p_strpop` (str/bytes order-free), `p_ctor2`, `p_typed`/`p_typed2` except sdu, `p_diff` except sdu, `p_pop` (finger after add/growth/clear/dummy-resize, empty, all delivery routes), `p_iterable` except sdu.
- unchanged C: `n_feat.py`, `n_loop.py` via `--debug-dir` vs `/tmp/base` → byte-identical `program.c`.

**Defect (new: base refuses this program by name, HEAD builds and answers wrong).**

1. `symmetric_difference_update` / `^=` uses `a ^ b` and swaps bodies, while CPython mutates `a` in place from the *other* set's table order. Wrong on the boxed set, on typed `set[int]`, on `^=`, and with any iterable argument. Code: `ail_setx_symmetric_difference_update_set` (`cruntime.py:16961`) and `ail_iset` `^=`; identical in upstream `c7a948e8`, so the accepted change carries it too.
```python
def main():
    c = {8, 16, 24, 32, 40}
    c.symmetric_difference_update({16})
    print(list(c))
main()
```
Expected `[32, 8, 24, 40]`; actual `[8, 24, 32, 40]` (g and d). Typed `set[int]` `q ^= t` shows the same class of mismatch (`p_typed2`: expected `[0, 128, 64, 192, …]`, actual `[128, 0, 136, …]`).

**Report claims.** pop finger — verified; difference heuristic (both sides of `len(a)>>2 > len(b)`) — verified; frozenset keys — verified; 5 test modules 0 failed — the 3 I ran pass, `test_ail_files`/`test_ail_corpus_findings3` not re-run (not required for the reviewer); listed probes — not re-run; `diff_ids.py` absent and manifest check — verified.

**Pre-existing (identical on `/tmp/base`, do not block):**
- `KeyError("'pop from an empty set'")` double-quoted vs CPython's `KeyError('pop from an empty set')`.
- A set of tuples-of-scalars that the compiler specializes to `_AilS_…` (when its only use is `list(s)`-style) walks in insertion order (`p_width` `tup`, `y3`), not the CPython table order; base produces the same output.

**Unverified.** Speed (no `tools/icount.c` run; change is set-specific and gdev programs I sampled do not exercise sets); the worker's own probe files; `test_ail_files`/`test_ail_corpus_findings3`.

VERDICT: FIX
1. `symmetric_difference_update`/`^=` (boxed, typed `set[int]`, and iterable-argument forms) computes `a ^ b` instead of CPython's in-place update, so the resulting iteration order is wrong though the set contents are right. Probe `/tmp/rp2/sdu_min.py` (`q = set(range(0,240,8)); q.symmetric_difference_update({8,16,240}); print(list(q))`): expected `[0, 128, 136, …, 112, 240, 120]`, actual `[128, 0, 136, …, 240, 112, 120]` on both builds; minimal `c={8,16,24,32,40}; c.symmetric_difference_update({16})` → expected `[32, 8, 24, 40]`, actual `[8, 24, 32, 40]`. Base refuses the walk by name, so this is not pre-existing.
[commandcode stop=end_turn turns=58 out_tokens=77006]

FINAL VERDICT: FIX  2026-11-08T10:37:24Z
