# job job-pre62-10241248  started 2026-10-24T03:49:46Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Fixed the first pre-existing item from the pre39 review (the task file's list was blank): run-time out-of-int64 float values reaching `int()` still stopped with `integer overflow` instead of CPython's big integer.

- Added front-end constant propagation for simple function returns, locals/closures, augmented/annotated assignments, omitted defaults, `float("...")`, global reads and keyword method wrappers. Such values are refused by name; values that fit, non-finite values, branches, mutations and rebound names are unchanged.
- Commit `0d4118a`; `test_ail_pre62.py` added and registered, DEVLOG/DIFFERENCES updated, manifest `--check` passes.

Tests on final commit: `test_ail_pre62`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 327s, 0 failed. Adapted pre39/pre40 target tests also pass 4/4.

Probes (`bash ~/tools/cmp.sh`, both builds): 18 refused by name, 7 matched CPython, 5 pre-existing differences identical on base:
- Refused: function return (plain/negative/local/container), `float("1e300")`, omitted default, closure, augmented/annotated assignment, method keyword, keyword wrapper, global read, upper bound.
- Matched: in-range returns/boundaries, passed default, int values, non-finite, branch order, mutated local list.
- Still pre-existing: `**kwargs`, module list/dict/attribute values, rebound function — verified unchanged on base.
[cost $0.0000, opencode tokens {"total": 4883255, "input": 133623, "output": 18457, "reasoning": 32895, "cache.write": 0, "cache.read": 4698280}]
    tool time: bash 13.6 min
        329s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre62 test_ail_safetynet test_ail_files test_ail
         83s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() # fix known.get
         83s bash   cd /tmp && python3 -m unittest -v test_pre39_adapt test_pre40_adapt > /tmp/pre3940c.log 2>&1; rc=$?; tail -12 
         64s bash   git show origin/pre39:AIL_CURRENT/test_ail_pre39.py | sed "s|ROOT = Path(__file__).resolve().parent|ROOT = Pat
         47s bash   WT=/home/runner/work/ail-ci/ail-ci; cd /tmp/probes; for f in p_*.py pre62_*.py; do out=$(bash ~/tools/cmp.sh "
         47s bash   WT=/home/runner/work/ail-ci/ail-ci; cd /tmp/probes; for f in p_*.py pre62_*.py; do out=$(bash ~/tools/cmp.sh "
         37s bash   WT=/home/runner/work/ail-ci/ail-ci; cd /tmp/probes; for f in p_*.py; do echo "===== $f"; bash ~/tools/cmp.sh "
         34s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() pre=Path('/tmp/

## review 0
[model opencode/deepseek-v4.1-flash-free]
​**What the change does:** It adds a large AST constant-propagation pass that refuses, at compile time, `int()` of a propagated finite float outside int64 (returns, locals/closures, assignments, defaults, `float("...")`, globals, wrapper/method parameters). It does not change generated C.

**Target:** Reproduced. `p01` (`def value(): return 1e300; print(int(value()))`) exits 1 with `integer overflow` on base and is now refused by name on both builds.

**Defects (caused by this change; base matches CPython):**

1. Unreachable conversions are refused — the parameter/dead-code scan ignores control flow.
```
def take(x=1e300, flag=False):
    if flag:
        return int(x)
    return 0
print(take())
```
Expected `0`; actual both builds fail with `int() of a float outside int64: 1e+300`. Base prints `0`. Same for `p05` (expected 7), `p10` (expected 0), `p17` (expected 3), and even a dead literal:
```
if False:
    print(int(1e300))
print("ok")
```
Expected `ok`; actual compile refusal (base prints `ok`).

2. Method handling keys only on the bare attribute name across all classes, ignoring the receiver.
```
class A:
    def take(self, x):
        return int(x)
class B:
    def take(self, x):
        return x
print(B().take(x=1e300))
```
Expected `1e+300`; actual both builds fail with `int() of a float outside int64: 1e+300`. Base prints `1e+300`. Same with `p08` (expected `5`).

**Pre-existing:** `p19` (`if flag: return 1e300 ... int(value(True))`) differs identically on base and HEAD; `float = ...` shadowing is already refused by base; `**kwargs` calls are already refused by base.

**Claims:** list-blank claim verified; target difference verified on base; new propagation routes verified from the diff; “branches … unchanged” is false for wrapper defaults/dead code (defects 1–2); commit `0d4118a`, manifest `--check` rc0, `test_ail_pre62` + `test_ail_safetynet` pass (0 failed). `test_ail_files`/`test_ail_corpus_findings3` and the 18/7/5 probe counts were not re-run.

**Other:** `p06` (no feature) produces byte-identical `program.c` to base; no speed check needed. Not checked: full suite.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1175545, "input": 51953, "output": 5338, "reasoning": 20567, "cache.write": 0, "cache.read": 1097687}]
    tool time: bash 4.3 min
        124s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre62 te
         29s bash   cd /tmp/rprobes && date && for f in p01_target_runtime.py p02_dead_branch_wrapper.py p03_method_collision.py p
         24s bash   cd /tmp/rprobes && cat > p19_branch_true.py <<'EOF' def value(flag):     if flag:         return 1e300     ret
         23s bash   cd /tmp/rprobes && date && for f in p*.py; do echo "===== HEAD $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f /home/
         23s bash   cd /tmp/rprobes && for f in p02_dead_branch_wrapper.py p03_method_collision.py p05_dead_if_false.py p08_unrela
         18s bash   cd /tmp/rprobes && for f in p15_float_shadow_func.py p16_float_shadow_class.py p17_wrapper_dead_nested.py p18_
          5s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p20_kwargs_in_range.py /tmp/base 2>&1 | tail -15; echo ===
          4s bash   cd /tmp/rprobes && cat > p15_float_shadow_func.py <<'EOF' def float(v):     if v:         return 1.5     retur

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `AIL_CURRENT/ail_chatgpt.py`:
- Conversions in unreachable/conditional code (branches, loops, after `return`) are no longer refused.
- Methods are mapped per class; only a direct constructor receiver of the owning class is checked.

Commit: `e9faf0b`. Added 9 regression cases to `test_ail_pre62.py` (13 refused, 19 matching), DEVLOG updated, manifest `--check` rc0.

Required tests on final commit: `test_ail_pre62`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed, 0 failed (280s, `-j 2`).

New probes (`/tmp/probes/fix62_*`, both builds): dead after return, conditional expression, dead method branch, receiver collision, two same-named methods, dead while, dead try/finally, unconditional negative — all match CPython except the unconditional negative, which is refused by name. Reviewer probes p01/p02/p03/p05/p08/p10/p17/p23 now match or are refused as intended; p19 remains the pre-existing base/HEAD difference, and p04/p15/p16/p18/p20/p21/p22 are pre-existing base behaviours.
[cost $0.0000, opencode tokens {"total": 1517752, "input": 51336, "output": 7195, "reasoning": 13973, "cache.write": 0, "cache.read": 1445248}]
    tool time: bash 7.8 min, edit 0.0 min, read 0.0 min
        282s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre62 test_ail_safetynet test_ail_files 
         61s bash   cd /tmp/rprobes && date && for f in p*.py; do echo "===== $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f /home/runne
         47s bash   cd /tmp/probes && for f in *.py; do out=$(bash ~/tools/cmp.sh /tmp/probes/$f /home/runner/work/ail-ci/ail-ci 2
         30s bash   cat > /tmp/probes/fix62_dead_after_return.py <<'EOF' def take(x=1e300):     return 7     return int(x)  print(
         22s bash   cd /tmp/rprobes && for f in p12_int64_bounds.py p15_float_shadow_func.py p16_float_shadow_class.py p18_other_a
         20s bash   cd /tmp/probes && for f in p_kwargs.py pre62_attr_source.py pre62_dict_value_source.py pre62_list_item_source.
          8s bash   cd /tmp/rprobes && for f in p01_target_runtime.py p02_dead_branch_wrapper.py p03_method_collision.py; do echo 
          0s bash   python3 -m py_compile AIL_CURRENT/test_ail_pre62.py && python3 tools/update_manifest.py && python3 tools/updat

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** adds compile-time constant propagation in `ail_chatgpt.py` to refuse `int()` of a finite float outside int64 reached through module globals, locals, simple function returns, defaults, closures, and class-method keyword arguments; the follow-up commit restricts this to unconditional code and per-class method receivers. This matches the report’s description, but the implementation has false-positive cases.

**Probes that fail (HEAD vs base, both builds):**

1. **Method positional arguments are mis-indexed after `self`; the checker falls back to the default.** `_bound_argument(node, name, index)` uses the method’s positional index including `self`, but call `args` exclude the receiver.
```python
class Box:
    def take(self, x=1e300):
        return int(x)

print(Box().take(1.5))
```
CPython/base: exits 0, prints `1`. HEAD: both builds refused with `p.ail:5:7: int() of a float outside int64: 1e+300`. Same for `def take(self, a, x=1e300)` called as `Box().take(1, 1.5)`.

2. **A previous local/module constant is not cleared when the name is reassigned a non-constant value.** `_Int64CallChecker._store` (ail_chatgpt.py:605) only records scalar values and never removes a stale one.
```python
def g(v):
    if v:
        return 1.5
    return 2.5

def f():
    x = 1e300
    x = g(True)
    return int(x)

print(f())
```
CPython/base: exits 0, prints `1`. HEAD: refused with `int() of a float outside int64: 1e+300`. Same defect for module scope, tuple assignment (`x, y = 1.5, 2.5`), multi-target (`x = y = 1.5`), and `(x := 1.5)`; all print `1` on base and are refused on HEAD.

**Remaining unaddressed route (pre-existing):** positional method calls are not detected at all, e.g. `Box().take(1e300)` with `def take(self, x): return int(x)` still compiles and exits 1 with `integer overflow` on both HEAD and base (`m3`, `m11`).

**Pre-existing differences:** `p19_branch_true` is identical on base/HEAD (runtime `integer overflow`); `p04/p15/p16` and `p18` are refused/fail on base too; `p20/p22` were refused on base as `**kwargs`, so both are refusals, though the report’s “pre-existing base behaviours” wording is imprecise.

**Claims:** unreachable/conditional and per-class receiver fixes verified (p02,p03,p05,p07,p08,p10,p13,p17,p23); `test_ail_pre62` (13 refused / 19 matching) and `test_ail_safetynet` pass; DEVLOG/manifest `--check` verified. The C for a no-feature program (`r8_no_feature.py`) is byte-identical to base (`program.c` only; native report differs only in temp paths). I did not rerun `test_ail_files`/`test_ail_corpus_findings3` per the review rules.

**Unverified:** worker’s 4-module test claim for the two modules I did not rerun.

VERDICT: FIX

1. Positional method arguments with a receiver are treated as omitted; an in-range positional value is replaced by an out-of-int64 default and valid programs are refused (`m1`, `m2`; expected `1`, actual compile refusal).
2. Reassigning a name to a non-constant value (including tuple/multi-target and walrus assignment) leaves the earlier out-of-int64 constant in place, refusing valid programs (`m6`, `m7`, `m9`, `m10`; expected `1`, actual compile refusal).
3. The task’s stated cause is only partly fixed: positional method calls such as `Box().take(1e300)` still compile and fail at run time with `integer overflow` (`m3`, `m11`; base behaves the same).
[cost $0.0000, opencode tokens {"total": 1165993, "input": 91631, "output": 10719, "reasoning": 16347, "cache.write": 0, "cache.read": 1047296}]
    tool time: bash 5.5 min
        126s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         61s bash   date; cd /tmp/rprobes; for f in p*.py; do out=$(bash ~/tools/cmp.sh /tmp/rprobes/$f /home/runner/work/ail-ci/a
         34s bash   date; cd /tmp/rprobes2 cat > m1_method_pos_ok.py <<'EOF' class Box:     def take(self, x=1e300):         retur
         32s bash   date; cd /tmp/rprobes; for f in p01_target_runtime.py p12_int64_bounds.py p18_other_attr_call.py p20_kwargs_in
         28s bash   mkdir -p /tmp/rprobes2; cd /tmp/rprobes2 cat > r1_list_mut_module.py <<'EOF' x = [1e300] x[0] = 1.5 print(int(
         18s bash   date; cd /tmp/rprobes2 cat > m6_unknown_reassign_module.py <<'EOF' def g(v):     if v:         return 1.5     
         17s bash   date; cd /tmp/rprobes; for f in p04_float_shadow.py p15_float_shadow_func.py p16_float_shadow_class.py p19_bra
          8s bash   date; cd /tmp/rprobes2 && cat > m11_method_pos_no_default.py <<'EOF' class Box:     def take(self, x):        

FINAL VERDICT: FIX  2026-10-24T04:42:47Z
