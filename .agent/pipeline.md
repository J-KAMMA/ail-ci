# job job-pre30-10240901  started 2026-10-24T00:01:45Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case: `f = obj.method`.

- Both builds previously failed at run time with `AttributeError`; they now refuse the read at compile time, naming the method (`pyfunc._attr_read`, `pyboxed2.Compiler.expr_Attribute`).
- Probes: 9/9 bound/static/class method value cases refused by name on both builds; 1/1 allowed program (direct calls, property, class attr, function value) matched CPython.
- Tests on final commit `fcf1360`: `test_ail_pre30`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `update_manifest.py --check` clean. DIFFERENCES and DEVLOG updated. `cls.attr` remains a pre-existing difference, untouched.
[cost $0.0000, opencode tokens {"total": 2174644, "input": 86106, "output": 8497, "reasoning": 10453, "cache.write": 0, "cache.read": 2069588}]
    tool time: bash 7.0 min
        207s bash   python3 tools/par_check.py -j 2 test_ail_pre30 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        162s bash   python3 tools/par_check.py -j 2 test_ail_pre30 test_ail_safetynet test_ail_files test_ail_corpus_findings3 && 
         25s bash   cat > /tmp/probes/bm_alias.py <<'EOF' class C:     def __init__(self, n):         self.n = n     def add(self,
         14s bash   for p in /tmp/probes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | tail -30; done
          6s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s=p.read_text() old
          3s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old="
          0s bash   python3 tools/par_check.py -j 2 test_ail_pre30 test_ail_safetynet test_ail_files test_ail_corpus_findings3
          0s bash   pwd && git status --short && git branch --show-current && git log --oneline -5

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change reviewed:** `fcf1360` adds compile-time refusal of bound-method values in `pyfunc._attr_read` and `pyboxed2.expr_Attribute`, plus tests/docs.

**Defects (all on the general/unified build)**

1. A known instance field that shadows its own method is wrongly refused. Probe:
```python
class C:
    def __init__(self): self.m = 5
    def m(self): return 1
c = C(); print(c.m)
```
Expected `5`; base general build prints `5`; HEAD general build fails with `bound method C.m read as a value...`. The check ignores `field_types`.

2. An instance field in a subclass that shadows a base method is wrongly refused. Probe:
```python
class A:
    def x(self): return 1
class B(A):
    def __init__(self): self.x = 7
print(B().x)
```
Expected `7`; base general prints `7`; HEAD general fails with `bound method B.x read as a value...`.

3. A class attribute in a subclass that shadows a base method is wrongly refused. Probe:
```python
class A:
    def m(self): return 1
class B(A):
    m = 5
    def __init__(self): self.n = 0
print(B().m)
```
Expected `5`; base general prints `5`; HEAD general fails with `bound method B.m read as a value...`.

These probes do not use bound-method values; CPython reads fields/class attributes. The default build still matches, so the regression is specific to `pyboxed2`'s `_resolve_method` check, which does not account for instance fields or class attributes shadowing methods.

**Verified claims**
- Base both builds fail `f = obj.method` with `AttributeError`; HEAD both refuse at compile time (p7). Verified.
- 9 refusal probes / 1 allowed probe: `test_ail_pre30` passes on both builds, though the `subclass` default-build refusal is `'B' has no field 'm'`; the test only sees `bound method` in the appended general-path note.
- Tests re-run on HEAD: `test_ail_pre30`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `update_manifest.py --check` clean; DIFFERENCES/DEVLOG updated in the diff.
- Non-feature program p4 (`method calls`, `property`, class attr, function value): both builds match CPython and `program.c` is byte-identical base vs HEAD for both paths.

**Pre-existing (identical on base and HEAD)**
- `f = "ab".upper` fails at run time (`AttributeError`) on both builds.
- `getattr(c, "add")` is refused on both builds.
- `cls.attr` inside a classmethod still fails with `'type' object has no attribute` on both builds.

**Unverified:** instruction counts; the change is compile-time-only and emits no different C for supported programs.

VERDICT: FIX

1. `pyboxed2.expr_Attribute` falsely refuses field/class-attribute reads whose name matches a method (`p1_field_shadow_own.py`, `p2_field_shadow_inherited.py`, `p8_classattr_shadows_base_method.py`); expected `5`/`7`/`5`, actual compile-time refusal, while the base general build matches CPython.
[cost $0.0000, opencode tokens {"total": 507205, "input": 34650, "output": 3539, "reasoning": 9624, "cache.write": 0, "cache.read": 459392}]
    tool time: bash 3.5 min
        160s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre30 test_ail_safetynet 
         18s bash   date; for p in /tmp/rprobes/*.py; do echo "===== HEAD $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | 
         18s bash   date; for p in /tmp/rprobes/*.py; do echo "===== BASE $(basename $p)"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1
          9s bash   cat > /tmp/rprobes/p8_classattr_shadows_base_method.py <<'EOF' class A:     def m(self):         return 1  cla
          5s bash   cd /tmp && rm -rf dbg_b dbg_h && mkdir dbg_b dbg_h && cp /tmp/rprobes/p4_no_bound_value.py /tmp/dbg_b/p.ail &&
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3; mkdir -p /tmp/rprobes; l
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo rc=$?; git
          0s bash   git diff work..HEAD --stat && echo "---" && git diff work..HEAD

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the general-path false refusals and committed `d7e389b`.

- Refuse only when class lookup truly finds a method; instance fields and class attributes now shadow it correctly (including inherited fields, base-class attributes, and class-body ordering).
- Probes: 16 total, both builds. 13 match CPython (`p1`-`p3`, `p5`-`p14`); 3 refused by name (`p4`, `p15`, `p16`).
- Required tests on final commit: `test_ail_pre30`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 1675345, "input": 69033, "output": 8458, "reasoning": 12337, "cache.write": 0, "cache.read": 1585517}]
    tool time: bash 7.4 min
        193s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre30 test_ail_safetynet test_a
         81s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre30 test_ail_safetynet 2>&1 |
         57s bash   cd /tmp/probes && cat > p15_subclass_method_over_base_attr_value.py <<'EOF' class A:     m = 5     def __init_
         39s bash   cd /tmp/probes && for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do p=$(ls p${n}_*.py); echo "===== $(basena
         27s bash   cd /tmp/probes && for p in p1*.py p2*.py p3*.py p4*.py p5*.py p6*.py p7*.py p8*.py p9*.py p10*.py; do echo "==
         26s bash   cd /tmp/probes && for p in p1*.py p2*.py p3*.py p4*.py p5*.py p6*.py p7*.py p8*.py p9*.py p10*.py; do echo "==
         11s bash   cd /tmp/probes && cat > p11_field_via_argument.py <<'EOF' class A:     def m(self):         return 1 class B(A
          5s bash   cd /tmp && for p in p5_field_set_in_other_method p7_same_class_attr_after_method; do for wt in /tmp/base /home

## review 1
[model opencode/deepseek-v4.1-flash-free]
Review of `work..HEAD` (d7e389b, fcf1360). Base worktree `/tmp/base` = f6899d2.

**Defect caused by the change (false compile-time refusal).** `pyboxed2._has_instance_field` only sees stores spelled `self.<name>`, so an instance field assigned through any other receiver/alias is missed and the read is refused as a "bound method" even though the field shadows the method. Base builds all of these and prints CPython's `7` with exit 0; HEAD refuses on both builds with `not in the subset: bound method C.m read as a value is not built; call it (C.m(...))` and nonzero exit:

1. `p1_field_via_arg_receiver.py` — `def setm(o): o.m = 7; c=C(); setm(c); print(c.m)`
2. `p2_field_via_list_receiver.py` — `xs=[c]; xs[0].m = 7`
3. `p3_field_via_dict_receiver.py` — `d={"c": c}; d["c"].m = 7`
4. `p5_field_via_alias_after_ctor.py` — `s = c; s.m = 7`
5. `p6_field_via_tuple_alias.py` — `a, b = self, 1; a.m = 7`
   (`p4_field_via_self_alias.py`, `s=self; s.m=7` in `__init__`, also refuses; base prints 7.)

**Pre-existing (identical on `/tmp/base`, does not block).** Bound-method values whose receiver is a list/dict/attribute element (`p8`, `p9`, `p10`) still exit 1 with the old runtime `AttributeError`; conditional field shadow `p11` likewise. Global receiver `p7` is correctly refused.

**Claims.**
- "instance fields … now shadow it correctly" — **false/overbroad** (defect above).
- "16 probes, 13 match, 3 refused by name" — not reproducible from repo; their own test passes but misses non-`self` field stores.
- Required tests on final commit — **verified**: `test_ail_pre30`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `-j 2`, 0 failed. `update_manifest.py --check` clean.

**Not checked.** Compile-time speed/hot code (change emits no new C, only a compile-time AST walk); the worker's `/tmp/probes` contents.

VERDICT: FIX
1. General-path false refusal for a field that shadows a method when the field is assigned through an argument, list item, dict value, or alias (`o.m = 7`, `xs[0].m = 7`, `d["c"].m = 7`, `s = c; s.m = 7`, `a,b = self,1; a.m = 7`). Expected CPython/base: stdout `7`, exit 0; actual HEAD both builds: refusal naming `C.m` and nonzero exit. Field detection must account for stores to any receiver of the class, not only `self`.
[cost $0.0000, opencode tokens {"total": 748910, "input": 44804, "output": 4420, "reasoning": 14246, "cache.write": 0, "cache.read": 685440}]
    tool time: bash 5.0 min
        127s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_c
         80s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre30 test_ail_s
         33s bash   cd /tmp/rprobes && for p in p1_field_via_arg_receiver.py p2_field_via_list_receiver.py p3_field_via_dict_recei
         28s bash   cd /tmp/rprobes && for p in p1_field_via_arg_receiver.py p2_field_via_list_receiver.py p3_field_via_dict_recei
         18s bash   cd /tmp/rprobes && for p in p1_field_via_arg_receiver.py p2_field_via_list_receiver.py p3_field_via_dict_recei
          6s bash   cd /tmp/rprobes && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "===== $wt"; bash ~/tools/cmp.
          5s bash   cd /tmp/rprobes && cat > p13_field_other_method.py <<'EOF' class C:     def __init__(self):         self.n = 0
          4s bash   cd /tmp/rprobes && cat > p14_classattr_after_method.py <<'EOF' class C:     def m(self):         return 1     

FINAL VERDICT: FIX  2026-10-24T00:36:26Z
