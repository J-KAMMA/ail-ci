# job job-pre24-10240316  started 2026-10-23T18:16:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed `C.__name__` (the only fuzz67 item still differing). `del c.attr` and class-body earlier-name reads remain refused by name.

- Commit: `f618f44` (`pre24: return a class value's __name__ on both builds`)
- Changed: general-path attribute lowering, runtime class lookup, `test_ail_pre24.py`, `ail_check.py`, DEVLOG/DIFFERENCES, manifest.
- Probes (`cmp.sh`, g+d builds):
  - `p_name_static.py` — static/subclass/class-body shadowing: both same as CPython.
  - `p_name_dynamic.py` — argument, list item, instance attribute, dict value: both same.
  - `p_name_alias.py` — aliasing/reassignment: both same.
- Tests on final commit: `test_ail_pre24`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 26 run, OK, 1 skipped (Windows target, no zig).
- `update_manifest.py --check`: exit 0.
[cost $0.0000, opencode tokens {"total": 3552403, "input": 122981, "output": 8199, "reasoning": 12455, "cache.write": 0, "cache.read": 3408768}]
    tool time: bash 8.6 min
        463s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS=-Werror=incompatible-pointer-types python3 -B -m unittest -v
         14s bash   mkdir -p /tmp/probes cat > /tmp/probes/del_attr.py <<'EOF' class C:     def __init__(self):         self.attr 
         13s bash   mkdir -p /tmp/probes cat > /tmp/probes/p_name_static.py <<'EOF' class C:     pass   class D(C):     pass   cla
         12s bash   for p in /tmp/probes/p_name_static.py /tmp/probes/p_name_dynamic.py /tmp/probes/p_name_alias.py; do echo "####
          5s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -B -m unittest -v test_ail_pre24 2>&1 | tail -40
          4s bash   cat > /tmp/probes/p_name_dynamic.py <<'EOF' class C:     pass   class D(C):     pass   class E:     __name__ =
          0s bash   ls -la && git log --oneline -10 && git status
          0s bash   git add AIL_CURRENT/ail_check.py AIL_CURRENT/docs/spec/DEVLOG.md AIL_CURRENT/docs/spec/DIFFERENCES.md AIL_CURR

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Diff reviewed**: runtime `__name__` branch in `ail_inst_getattr` plus a compile-time fold in `expr_Attribute`; tests/manifest/docs updated.

**Probes** (all under `/tmp/rprobes`, run on HEAD and `/tmp/base` with `cmp.sh`):

**Defects**

1. Class body referencing its own name now returns a value instead of failing.
```python
class C:
    x = C.__name__
print(C.x)
```
CPython: exit 1, stdout empty (`NameError`). HEAD: exit 0, stdout `C` (both builds). Base stdout/exit matched CPython. The report's claim that class-body earlier-name reads “remain refused by name” is false for this form.

2. Rebinding a class name at module scope now returns the old class name.
```python
class C:
    pass
C = 5
try:
    print(C.__name__)
except AttributeError as e:
    print("AE", type(e).__name__)
```
CPython: `AE AttributeError`. HEAD: `C` (both builds). Base matched CPython. Variant with a conditional rebinding (`p13_cond.py`) also gives `AE` vs `C`.

3. A parameter shadowing the class name returns the class-statement name, not the argument's.
```python
class C: pass
class D(C): pass
def f(C):
    return C.__name__
print(f(D), f(C))
```
CPython: `D C`. HEAD: `C C` (both builds). Base failed (empty stdout, exit 1), so this is an incompletely fixed argument case explicitly claimed by the report.

Cause: the compile-time fold and the new runtime class-name branch are reached even when `C` is rebound/shadowed, and the class name resolves to its dedicated class slot rather than the current binding.

**Pre-existing** (identical on base): `del c.attr` named refusal; `del C` (`KeyError: 'C'`); `getattr(C, "__name__")` (`NotImplementedError`); local/nested class (`not in the subset`); `int.__name__` (`not in the subset`); `C.__name__ = "X"` (`AttributeError`); class-body earlier local variable (`not in the subset`).

**Claims**: basic static/subclass/class-body-assignment and dynamic-through-`k`/list/attribute/dict/alias cases pass; worker probes `p_name_static`, `p_name_dynamic`, `p_name_alias` pass on HEAD. `del c.attr` refusal verified. `update_manifest.py --check` exit 0. No-feature `--debug-dir` diff shows only the new runtime branch; user code unchanged. `test_ail_pre24` and `test_ail_safetynet` pass.

**Unverified**: `test_ail_files`/`test_ail_corpus_findings3` (not re-run per reviewer scope); speed (`perf_event_open` is denied in this container, so `icount` cannot run).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1299182, "input": 49011, "output": 6034, "reasoning": 15849, "cache.write": 0, "cache.read": 1228288}]
    tool time: bash 4.6 min
        126s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre24 test_ail_safetynet 2>&1 | tail -25; 
         37s bash   date; for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep
         26s bash   date; for p in p2_selfbody p3_reassign p6_param p7_getattr p4_del p8_localclass p9_builtin; do echo "##### BAS
         26s bash   date; for p in p2_selfbody p3_reassign p6_param p7_getattr p4_del p8_localclass p9_builtin; do echo "##### $p"
         16s bash   date; for p in p_name_static p_name_dynamic p_name_alias class_earlier; do echo "##### HEAD worker $p"; bash ~
         16s bash   cat > /tmp/rprobes/p11_setname.py <<'EOF' class C:     pass C.__name__ = "X" print(C.__name__) EOF cat > /tmp/
          8s bash   date; for p in p11_setname p13_cond; do echo "##### BASE $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base
          7s bash   rm -rf /tmp/dbg_head2 /tmp/dbg_base2 /tmp/dbg_out_h /tmp/dbg_out_b cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -B

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three reviewer defects and committed as `c46fadc`.

- Class-body own-name read now raises `NameError` instead of returning the class name.
- Module-scope rebinding (`C = 5`, conditional, `global C`) now shadows the class object and gives `AttributeError`.
- Parameter/local shadowing now reads the binding (`f(D), f(C)` → `D C`).

Probes in `/tmp/probes/` (all matched CPython on both builds; 11 programs):
`p_basic`, `p_rebind`, `p_conditional`, `p_shadow`, `p_global`, `p_body`, `p_scope` — same stdout/exit on both builds.
`p_body_own`, `p_body_own2`, `p_body_own3`, `p_body_own_attr` — exit 1, empty stdout, `NameError` on both builds.

Required tests on final commit: `test_ail_pre24`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (252s). `update_manifest.py --check` passes. Pre-existing `C.__name__ = "X"` difference remains unchanged.
[cost $0.0000, opencode tokens {"total": 2145015, "input": 157285, "output": 7556, "reasoning": 16014, "cache.write": 0, "cache.read": 1964160}]
    tool time: bash 11.5 min, edit 0.0 min
        254s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre24 test_ail_s
        209s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_c
        126s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre24 test_ail_s
         44s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_basic p_rebind p_conditional p_shadow p_global p_body p_body_
         29s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_static p2_selfbody p3_reassign p5_shadow p6_param p11_setnam
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_static p2_selfbody p3_reassign p5_shadow p6_param p12_classb
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre24 2>&1 | tai
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (2 commits, HEAD `c46fadc`). Read the diff; probes in `/tmp/rprobes/`, each run on HEAD and `/tmp/base`.

**Defects**

1. `pyboxed2.py:4975-4977` — the new `C.__name__` constant shortcut ignores `ctx.clo_index`, unlike `expr_Name` at 4277-4279.
```python
class C:
    pass
def outer():
    C = 5
    return (lambda: C.__name__)()
try: print(outer())
except AttributeError: print("AE")
```
CPython/base: `AE`. HEAD (both builds): `C`. A lambda cell holding `5` is misread as the class.

2. `pyboxed2.py:4267-4276` — unconditional `NameError` for a class-body own-name read, even when the module global is already bound.
```python
C = 5
class C:
    x = C
print(C.x)
```
CPython: `5` (exit 0). HEAD: `NameError: name 'C' is not defined` (exit 1, both builds). Base was different (`AttributeError: 'type' object has no attribute 'x'`), so this is a new wrong result, and it contradicts the report's “raises NameError like CPython” claim. Correct rule: only unbound names raise NameError.

**Verified claims**
- Module-scope rebinding (`C = 5`, conditional, `global C`): correct — r8, r9, r11, r14.
- Parameter/local shadowing: correct — r13, r17, plus `test_ail_pre24`.
- `C.__name__` through argument/list/dict/instance attribute, with class-body `__name__` assignment: correct — r7.
- `test_ail_pre24` + `test_ail_safetynet` on HEAD: 2 modules, 0 failed (120 s).
- `update_manifest.py --check`: exit 0.
- Class-body own-name via comprehension now matches: r5 (base differed).

**Unverified**
- Worker's 11 `/tmp/probes/` results were not rerun; our probes found boundaries they missed.
- `test_ail_files`, `test_ail_corpus_findings3` not rerun (review scope only required pre24 + safetynet).
- Speed: `tools/icount.c` cannot run here (`perf_event_open: Permission denied`, paranoid=4). The added branch is one predicted-not-taken tag test per attribute read.
- Non-feature programs: default-build generated C is byte-identical; the general path differs only by the unavoidable 6-line runtime branch added to `ail_inst_getattr`.

**Pre-existing (identical on base)**
- `class C: x = (lambda: C)()` → compiler `RecursionError` (r6).
- Duplicate `class C` definitions → `duplicate AIL name: C` (r4, r12).
- Class-body earlier-name access → named refusal (r15).
- `C.__name__ = "X"` still fails after assignment (r18); first `C.__name__` read is now fixed.

VERDICT: FIX
1. `pyboxed2.py:4975` add `ctx.clo_index` (and `ptr_names`/`free_names`) to the shortcut guard: r1 expects `AE`, currently prints `C`.
2. `pyboxed2.py:4267` do not raise NameError when the class name has a live module binding: r3 expects `5`, currently exits 1 with `NameError`.
[cost $0.0000, opencode tokens {"total": 2618954, "input": 67604, "output": 7089, "reasoning": 25093, "cache.write": 0, "cache.read": 2519168}]
    tool time: bash 4.5 min, write 0.0 min
        122s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/update_manifest.py --check 2>&1 | t
         39s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/rprobes/r*.py; do echo "===== $f ====="; bash ~/to
         24s bash   cd /tmp/base && date && for f in /tmp/rprobes/r1_lambda_cell_shadow.py /tmp/rprobes/r2_nonlocal_shadow.py /tmp
         24s bash   cd /tmp && rm -rf perf && mkdir -p perf && cd perf && date && for p in g11_034 g14_040 g25_034; do src=$HOME/c
         16s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/rprobes/r13_local_shadow.py /tmp/rprobes/r14_globa
         16s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/rprobes/r16_comp_target.py /tmp/rprobes/r17_nested
         13s bash   cd /tmp && rm -rf cchead ccbase && mkdir -p cchead ccbase && cat > /tmp/rprobes/plain.py <<'EOF' def add(a, b)
          8s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in /tmp/rprobes/r18_set_name_attr.py; do echo "===== $f HE

FINAL VERDICT: FIX  2026-10-23T19:04:20Z
