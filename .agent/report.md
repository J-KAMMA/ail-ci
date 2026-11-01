# job job-tup1-11011230  started 2026-11-01T03:33:05Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `4e6a7a5` on `job-tup1-11011230`.

- 25 probes: **9 typed / 16 general / 0 refused** before; **13 typed / 12 general / 0 refused** after (t02, t12, t13, t15 moved to typed).
- 18 boundary probes: 11 typed, 7 general, all matching CPython.
- `cmp.sh`: 43/43 probes, no differences.
- Required tests: 79 passed, 1 skipped (`no zig for --target windows`); manifest check clean.
- Added `docs/design/TUPLE_REACH.md`, `test_ail_tuple_reach.py` (18 tests), tests.d registration, DEVLOG entry, manifest pins.
[cost $0.0000, opencode tokens {"total": 8196465, "input": 202507, "output": 22024, "reasoning": 31198, "cache.write": 0, "cache.read": 7940736}]
    tool time: bash 22.7 min, edit 0.0 min, write 0.0 min
        481s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2900 python3 -m unittest -v test_ail_tuple_reach test_ail
        276s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; cd AIL_CURRE
        187s bash   cd /tmp/probes && time python3 cmp_c.py 2>&1 | tail -40
        133s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/t*.py /tmp/probes/b*.py; do bash ~/tools/cmp.sh "$p" "$P
         71s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1700 python3 -m unittest -v test_ail_tuples 2>&1 | tail -
         50s bash   cd /tmp/probes && python3 measure.py 2>&1 | tee measure2.out | tail -60
         40s bash   rm -rf /tmp/probes/build && cd /tmp/probes && python3 measure.py 2>&1 | tee measure2.out | tail -60
         30s bash   cd /tmp/probes && time python3 measure.py 2>&1 | tee measure.out | tail -80

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review: job-tup1-11011230 (commit `4e6a7a5`)

**What the change really does:** `tupcalls.call_user` records the argument type at every positional/keyword call site of an unannotated parameter; `finish_params` keeps a type only when all observations are known and identical; `make_sig` feeds it back and `function` spells tuple-containing types onto the parameter. `rewrite` repeats the lowering up to 4 rounds. Scalar hints are used only internally. Tests/docs/manifest added. This matches the report.

**Probes run** (`cmp.sh`, default + forced general, base = `/tmp/rbase` @ `work`):
- Pass (match CPython, or named refusal): p01 default int→float tuple, p02 default different shape, p03 list mutation, p04 dict mutation, p05 same list via two params, p06 required kw-only (named refusal both builds), p08 empty tuple, p09 dict overwrite after read, p10 function alias, p11 method, p12 param reassigned to another tuple, p13 mutation during iteration. Also r01–r05, r07–r10 (defaults, callbacks, recursion, pos+kw, call-after-use).
- **Fail: p07, r06.**

**Claims checked:** 25-probe totals 9/16 → 13/12 — verified from `measure.out`/`measure2.out`. 18 boundary probes 11 typed/7 general — verified from `measure_b.out`. 10 lab/compare `main.py` tuple rewrites identical base vs HEAD (hence C unchanged; `.ail` path untouched) — verified. Diff touches no runtime — verified. "79 passed, 1 skipped" — not re-run; only targeted modules re-run: `test_ail_tuple_reach` and `test_ail_safetynet` both ok (143 s, 0 failed).

**Defects (FIX):**
1. Scalar parameter hint overrides a later reassignment, producing a wrongly typed tuple. Probe `/tmp/rprobes/p07_scalar_reassign.py`:
```python
def f(n):
    n = "x"
    return n, (1, "a")
def main():
    print(f(1))
main()
```
Expected `('x', (1, 'a'))`; actual `(x, (1, 'a'))` on both default and forced-general builds. Base prints correctly. The pass infers `n: int` from `f(1)` and settles the return as `tuple[int, ...]`, then stores the string in an int field.
2. Annotating an unannotated method parameter changes how its mixed-type return is printed. Probe `/tmp/rprobes/r06_method_default.py`:
```python
class C:
    def m(self, t=None):
        if t is None:
            return "none"
        return t[0], t[1]
def main():
    c = C(); print(c.m()); print(c.m((1, "a")))
main()
```
Expected `none` then `(1, 'a')`; actual `none` then `<_AilT_i_s object>` on both builds. Base correct: `t` is now typed `_AilT_i_s`, but the function's return type stays unannotated (str vs tuple), so the caller prints the tuple class with the generic object repr.

Both defects are the pre-existing typed-path bugs also present when the annotations are written explicitly (`q_expl_scalar.py`, `q_expl_ann.py` fail identically on base), but they are newly reachable for previously-correct unannotated programs.

**Unverified:** full 79-test count from the worker's log; manifest `--check`; whole-suite behaviour (intentionally not run).

VERDICT: FIX
1. `/tmp/rprobes/p07_scalar_reassign.py` — expected `('x', (1, 'a'))`, actual `(x, (1, 'a'))`.
2. `/tmp/rprobes/r06_method_default.py` — expected `(1, 'a')` on the second line, actual `<_AilT_i_s object>`.
[cost $0.0254, opencode tokens {"total": 977289, "input": 65932, "output": 5520, "reasoning": 15853, "cache.write": 0, "cache.read": 889984}]
    tool time: bash 3.9 min
        144s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1100 python3 ../tools/par_check.py -j 2 test_ail_tu
         30s bash   cd /tmp/rprobes && for p in p01_def_widen p02_def_shape p03_als_list p04_als_dict p05_alias_two p06_kwonly p07
         28s bash   cd /tmp/rprobes && for p in r01_default_none r02_default_scalar r03_alias_other r04_callback r05_method_kw r06
         11s bash   cd /tmp/rprobes && cat > q_expl_ann.py <<'EOF' class C:     def __init__(self):         self.x = 0     def m(s
          9s bash   cd /tmp/rprobes && cat > p12_param_reassign_tuple.py <<'EOF' def g(t):     t = (1, 2)     return t[0], t[1]  d
          6s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p07_scalar_reassign.py /tmp/rbase 2>&1 | grep -v '^dir '; 
          2s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/r06_method_default.py /tmp/rbase 2>&1 | grep -v '^dir '; e
          1s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 - <<'EOF' import subprocess, sys, pathlib, hashlib roots=

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `de8f9b3` on `job-tup1-11011230`.

- Fixed defect 1: call-site types are no longer inferred for parameters the body reassigns (plain, augmented, loop, tuple rebind).
- Fixed defect 2: functions whose tuple return is not settled keep parameters unannotated and stay on the general path.
- Probes: p07, r06, and 11 new `/tmp/probes/v01`–`v11` cases all match CPython on default and forced-general builds.
- Tests on final commit: `test_ail_tuple_reach` (21), `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed.
- `update_manifest.py --check` passes; 17 lab/compare C builds byte-identical, remaining 3 `.py` builds fail identically on base and HEAD.
[cost $0.0451, opencode tokens {"total": 4039841, "input": 103282, "output": 12394, "reasoning": 17477, "cache.write": 0, "cache.read": 3906688}]
    tool time: bash 25.8 min, edit 0.0 min
        340s bash   cd /tmp/ccmp && for t in $(ls /home/runner/work/_temp/w2/lab/compare/src); do for f in main.ail main.py; do rm
        328s bash   cd /home/runner/work/_temp/w2 && timeout 1600 python3 tools/par_check.py -j 2 test_ail_tuple_reach test_ail_tu
        327s bash   cd /home/runner/work/_temp/w2 && timeout 1600 python3 tools/par_check.py -j 2 test_ail_tuple_reach test_ail_tu
        200s bash   cd /tmp/ccmp && for t in chain_relax rail_transfer scar_life tally_lang tree_fold; do rm -rf a b; mkdir a b; A
         76s bash   cd /tmp/rprobes && for p in *.py; do r=$(bash ~/tools/cmp.sh /tmp/rprobes/$p /home/runner/work/_temp/w2 2>&1 |
         69s bash   cd /tmp/rprobes && for p in p0*.py p1[0-3]*.py r0*.py r1[0-2]*.py; do [ -f "$p" ] || continue; r=$(bash ~/tool
         41s bash   cd /tmp/probes && cat > v01_reassign_routes.py <<'EOF' def f(n):     n = "x"     return n, (1, "a")  def main(
         38s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 - <<'EOF' p='test_ail_tuple_reach.py' s=open(p).read() s=

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** `tuplib.py` now records call-site argument types for unannotated parameters (positional and keyword), keeps an agreed tuple-containing type by spelling it as an annotation to force the typed path, re-runs lowering up to 4 rounds, and guards parameters the body rebinds and functions with unsettled tuple returns. Runtime/C is untouched.

**Probes (30, /tmp/rprobes/tup):** 25 match CPython on both builds. 5 differ on HEAD but match on base (`/tmp/rbase`), i.e. caused by this change. Worker's `v01`–`v11` re-run: 11/11 match on both builds. `a4` (required kw-only) is a named refusal; `c13` is a CPython `SyntaxError`.

**Defects (HEAD differs, base matches):**

1. Default argument values are not considered by inference.
```
def g(t="x"):
    return t
def main():
    print(g((1, "a")))
    print(g())
main()
```
Expected `(1, 'a')` then `x`, rc 0. Actual `(1, 'a')` then `IndexError: string index out of range`, rc 1. Same with `def g(t=None)` (expected `None`, actual `TypeError: 'NoneType' object is not subscriptable`). The sole call site `g((1,"a"))` annotates `t` as `(int,str)`, so the default is stored/returned as a tuple class.

2. `return None` / bare `return` is dropped before the mixed-return guard.
```
def g(t, flag):
    if flag:
        return t
    return None
def main():
    print(g((1, "a"), True))
    print(g((1, "a"), False))
main()
```
Expected `(1, 'a')` then `None`, rc 0. Actual `(1, 'a')` then `TypeError: 'NoneType' object is not subscriptable`, rc 1. `seen = [t for t in self.rets if t not in (None, 'none')]` hides the `None` path, so `rets_out` is set to the tuple and `mixed_ret` is never consulted. Same for `return` with no value and for `return t[0], t[1]` on the other branch (`c1`, `c2`, `d5`).

**Claims:**
- Reassignment guard: verified (`b2`/`b3`/`b4`, `v01`–`v05` match; inferred type not used).
- Mixed tuple return guard: **false for `None`/bare `return`** (defect 2); verified for non-`None` mixed returns (`c3`, `v06`–`v10`).
- Tests: verified, 6 modules, 0 failed (`test_ail_tuple_reach`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `update_manifest.py --check`: verified (clean).
- lab/compare C: verified — 17 builds byte-identical, the 3 `.py` failures identical on base.
- p07/r06: unverified (not re-run).
- No pre-existing differences found; runtime ownership not touched, so no extra 4b probe needed. Speed not relevant (generated C identical on the lab corpus; compile-time-only change).

VERDICT: FIX
[cost $0.0276, opencode tokens {"total": 1191378, "input": 84682, "output": 7051, "reasoning": 12285, "cache.write": 0, "cache.read": 1087360}]
    tool time: bash 10.0 min
        247s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 700 python3 ../tools/par_check.py -j 2 test_ail_tup
        169s bash   cd /tmp && rm -rf lc_head lc_base && mkdir -p lc_head lc_base W2=/home/runner/work/_temp/w2 run() { local wt=$
         82s bash   date; cd /tmp/rprobes/tup && rm -f /tmp/rprobes_tup_head.log; for p in *.py; do echo "=== $p"; bash ~/tools/cm
         30s bash   date; cd /tmp/probes && for p in v0*.py v1*.py; do r=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/_t
         25s bash   cd /tmp && rm -rf lc_head lc_base && mkdir -p lc_head lc_base W2=/home/runner/work/_temp/w2 run() { # wt outdi
         19s bash   for p in c1_mixed_none_annotated c2_return_none_bare d1_default_str d3_default_none d5_mixed_none a4_kwonly c1
         10s bash   for p in c1_mixed_none_annotated c2_return_none_bare d1_default_str d3_default_none d5_mixed_none; do d=$(mkte
          9s bash   date; cd /tmp && for p in b2_loop_rebind b3_aug_rebind b4_nested_rebind a2_method c1_mixed_none_annotated d1_d

FINAL VERDICT: FIX  2026-11-01T05:03:06Z
