# job job-decexact2-11020111  started 2026-11-01T16:11:29Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

**What was fixed**
- Every successful return of a Decimal/Fraction prelude function now runs the outermost `exact_depth == 1` visibility check, not just the tail return (`pyboxed2.py`). This closes leaks through source-level early returns: `round(Fraction(2)**100)`, `(Fraction(2)**100)//1`, `math.floor/ceil(Decimal(2)**100)`, `hash(Fraction(2)**100)` now stop with `OverflowError: integer overflow in int()`.
- A store to a getter-only property (`Fraction(1,2).numerator = 3`) now raises CPython's `AttributeError` instead of silently shadowing it.

**Verification**
- Probes on both builds: `p_roundfrac`, `p_floordivfrac`, `p_dec_mathfloor`, `p_leaktyped`, `p_hashfrac` stop loudly; `p_numassign`, `p_prop`, `p_accept`, `p_frac_small` match CPython; `p_exact_ret` matches CPython with `AIL_EXACT_INT=1`.
- `lab/compare` Python tasks: the 6 that build have byte-identical `program.c`; the other 4 refuse identically.
- Tests: `test_ail_int64_default`, `test_ail_stdtop1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (542 s).
- `tools/update_manifest.py` and `--check` clean.
- Committed as `4d02142`.
[cost $0.0000, opencode tokens {"total": 4305555, "input": 96718, "output": 10272, "reasoning": 17701, "cache.write": 0, "cache.read": 4180864}]
    tool time: bash 17.6 min, edit 0.0 min
        543s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_int64_default test
        142s bash   cat > /tmp/cdiff.sh <<'EOS' #!/bin/bash set -u REPO=/home/runner/work/ail-ci/ail-ci task=$1; tree=$2; tag=$3 o
        100s bash   cd /tmp/probes && for p in p_roundfrac p_floordivfrac p_dec_mathfloor p_leaktyped p_numassign p_hashfrac; do e
         99s bash   cd /tmp/probes && for p in p_roundfrac p_floordivfrac p_dec_mathfloor p_leaktyped p_numassign p_hashfrac; do e
         73s bash   cd /tmp/probes && cat > p_frac_small.py <<'EOF' from fractions import Fraction print(Fraction(1, 3) + Fraction
         45s bash   cd /tmp/probes && for p in p_accept p_frac_small p_prop; do echo "===== $p ====="; timeout 400 bash ~/tools/cm
         43s bash   rm -rf /tmp/dbgtest && mkdir -p /tmp/dbgtest && cd lab/compare/src/ticket_audit && time AIL_NO_CACHE=1 AIL_QUI
          9s bash   rm -rf /tmp/dbgex && mkdir -p /tmp/dbgex && cd /tmp && cp /tmp/probes/p_roundfrac.py /tmp/dbgex/p.py && cd /tm

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `job decexact2` (Decimal/Fraction exact returns + property stores)

**What the change really does.** In `pyboxed2._emit_function` it rewrites every `ail_exact_leave(cx); AIL_FRAME_LEAVE(cx, f); return AIL_OK;` of an exact prelude function to run the `exact_depth == 1` visibility scan first (regex, all indentation/one-line forms), and in `_assign_target` it turns a store to a getter-only `@property` into `ail_raise_c(..., AIL_B_ATTRIBUTEERROR, ...)` instead of `ail_inst_setattr_chk`.

**Verified (both builds, HEAD + `/tmp/base` where relevant):**
- Review defect 1 fixed: `round(Fraction(2)**100)`, `(Fraction(2)**100)//1`, `math.floor/ceil(Decimal(2)**100)`, `hash(Fraction(2)**100)`, and the list/dict/`n+1`/`n*2`/`n%7` variant now exit 1 with `OverflowError: integer overflow in int()`; base printed the big ints.
- No false positive on legitimate early returns: `round(Fraction(7,2))`, `__floor__`, `__ceil__`, `divmod`, `hash(Fraction(1,3))` (small), `math.floor/ceil(Decimal("2.5"))`, `round(Decimal("2.675"),2)`, `int(Decimal("123"))`, `Decimal(1)/Decimal(3)`.
- Acceptance values (default prec, prec=50, sqrt, `2**100`, `1e30+1`) match CPython on both builds.
- `AIL_EXACT_INT=1`: the same big early-return probes print the big value and match CPython.
- Direct `Fraction(...).numerator/denominator = ...` now raises CPython's AttributeError; user property setter, subclass setter, plain attribute, and an unrelated class with the same attribute name all still work.
- No-Decimal generated C byte-identical HEAD vs base (custom class/dict/loop program and `lab/compare/echo_pack`); `native_report.json` differs only in temp paths.
- `test_ail_int64_default`, `test_ail_safetynet`: 2 modules, 0 failed (394 s). `tools/update_manifest.py --check` clean.

**Claims.** All worker claims verified except the property fix is over-broad (see defect 1): it is exact for a direct `Fraction`, not for a subclass that overrides the inherited property with a plain attribute.

**Defects**
1. New regression, caused by this change: a subclass that shadows an inherited getter-only property with a plain class attribute is now rejected.
   - Probe `/tmp/rprobes/p14_subplain.py` (also `p15_subplain2.py`):
     ```python
     class A:
         @property
         def x(self): return 1
     class B(A):
         x = 0
     b = B(); b.x = 7; print(b.x)
     ```
   - CPython: `7`, exit 0. HEAD (g and d): exit 1, `AttributeError: property 'x' of 'A' object has no setter`. Base accepted the store (exit 0, printed `1`; the read was already wrong, but the store was not).
   - `read_only` ignores later shadowing entries in the class chain; it should fall back to `setattr` (or refuse by name) when a subclass replaces the property with a non-property.
2. Minor: for an inherited read-only property the message names the defining class, not the object's type. `p16_submsg.py` (`class C(A): pass; C().x = 5`): CPython stderr `property 'x' of 'C' object has no setter`; HEAD `property 'x' of 'A' object has no setter`.

**Pre-existing** (identical on base): `hash(Fraction(1,3))` is `1000006` where CPython gives `1537228672809129301`; the subclass-plain-attribute *read* already returned the base getter value (p14 base printed `1`).

**Unverified:** wider suite/other test modules, gdev `icount` (no-Decimal C is byte-identical, so no change expected), Decimal-heavy runtime speed.

VERDICT: FIX
1. Do not raise for a store to a getter-only property when a subclass in `class_order` shadows that name with a non-property entry; `p14_subplain.py` must assign (base behaviour) rather than exit 1.
2. Use the runtime type's name in the `AttributeError` text (or match CPython otherwise) for inherited properties: `p16_submsg.py` expected `... of 'C' object ...`, actual `... of 'A' object ...`.
[cost $0.0000, opencode tokens {"total": 1590186, "input": 65378, "output": 6474, "reasoning": 21374, "cache.write": 0, "cache.read": 1496960}]
    tool time: bash 15.7 min
        395s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_int64_default test
        190s bash   cd /tmp/rprobes && for p in p1_roundfrac p2_floordivfrac p3_dec_mathfloor p4_leaktyped p5_hashfrac p6_legit p7
        112s bash   cd /tmp/rprobes && export AIL_EXACT_INT=1 && for p in p1_roundfrac p2_floordivfrac p3_dec_mathfloor p6_legit; 
         87s bash   cd /tmp/rprobes && for p in p6_legit p7_prop p8_propuser; do echo "===== BASE $p ====="; timeout 300 bash ~/to
         51s bash   cd /tmp/rprobes && cat > p17_accept.py <<'EOF' from decimal import Decimal, getcontext print(Decimal(1) / Deci
         43s bash   cd /home/runner/work/ail-ci/ail-ci && grep -l -i "decimal\|fraction" lab/compare/src/*/main.py; echo '--- none
         41s bash   cd /tmp/rprobes && for p in p1_roundfrac p3_dec_mathfloor; do echo "===== BASE $p ====="; timeout 300 bash ~/t
          7s bash   cd /tmp/rprobes && cat > p10_roprop.py <<'EOF' class A:     def __init__(self):         self._x = 1     @prope

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defects and committed as `0c187ff`.

- Subclass plain attributes now shadow inherited properties for both store and read (`p14`, `p15`, `p18`, `p19`, `p20` match CPython on both builds).
- Inherited read-only property errors now name the run-time type (`p16`: `C`, `D`).
- Confirmed already fixed: early-return big-int leaks (`p_roundfrac`, `p_floordivfrac`, `p_dec_mathfloor`, `p_leaktyped`, `p_hashfrac` stop loudly) and `Fraction.numerator` assignment (`p_numassign` matches).
- Acceptance/small/exact probes still match: `p_accept`, `p_frac_small`, `p_prop`, `p_exact_ret`.
- Tests: `test_ail_int64_default`, `test_ail_stdtop1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 552 s, 0 failed.
- `python3 tools/update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 2740359, "input": 143732, "output": 9289, "reasoning": 21450, "cache.write": 0, "cache.read": 2565888}]
    tool time: bash 13.1 min, edit 0.0 min
        553s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2700 python3 tools/par_check.py -j 2 test_ail_int64_default test
        149s bash   cat > /tmp/probes/p15_subplain2.py <<'EOF' class A:     @property     def x(self):         return 1 class B(A)
         63s bash   cd /tmp/probes && echo '===== p_exact_ret (AIL_EXACT_INT=1) =====' && AIL_EXACT_INT=1 timeout 900 bash ~/tools
         13s bash   cd /tmp/probes && for p in p14_subplain p15_subplain2 p16_submsg p18_subplain_mixed p19_subplain_setter p20_su
          6s bash   cd /tmp/probes && for p in p14_subplain p16_submsg p19_subplain_setter; do echo "===== $p ====="; timeout 900 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.re
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2700 python3 tools/par_check.py -j 2 test_ail_int64_default test

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review: `job decexact2` (property store follow-up)

**What the change really does.** Commit `4d02142` rewrites every successful `return AIL_OK` in an exact prelude function to run `ail_exact_visible` before leaving the exact depth, and makes a store to a getter-only property raise `AttributeError` naming the run-time class instead of silently setting an instance attribute. Commit `0c187ff` adds `_class_defines_plain_attr` and uses it, for read and store, to let a subclass's plain class attribute shadow an inherited property. This broadly matches the report, but the shadow test excludes the property owner class itself.

**Probes (HEAD, both `g`/`d`; base `/tmp/base` where needed):**
- Early-return leaks fixed: `p1_roundfrac`, `p2_floordivfrac`, `p3_dec_mathfloor`, `p4_leaktyped`, `p5_hashfrac` all stop with `OverflowError: integer overflow in int()`, exit 1. Verified.
- Subclass plain attribute: `p14_subplain`, `p15_subplain2`, `p23_annshadow`, `p26_setter_plain_deep` match CPython; `p16_submsg` matches the run-time class name. Verified.
- `p27_frac_ro_via` (attribute, list item, dict value): matches. `p_prop_setter_inherit`, `p_deeper_prop` match.
- Non-feature program: `plain.py` `program.c` byte-identical base vs HEAD. Verified.
- **New defect found:** `/tmp/rprobes/p_sameclass_after.py`:

```python
class A:
    @property
    def x(self):
        return 1
    x = 0
a = A()
print(a.x)
a.x = 5
print(a.x)
```

  CPython: `0`, `5`, exit 0. HEAD (both builds): `1`, then `AttributeError: property 'x' of 'A' object has no setter`, exit 1. Base: `1`, `1`, exit 0. So the exit-1 is caused by this change. Same for the subclass form `/tmp/rprobes/p_attr_after_prop2.py` (CPython `4`,`8`; HEAD `3`, then the same AttributeError; base `3`,`3`, exit 0).

**Pre-existing (same on base and HEAD, does not block):**
- Reading an inherited property when a subclass defines a plain *method* of the same name still returns the property value (e.g. `p_submethod_read`: `B 1` vs CPython's bound method).
- Reading a class-body attribute assigned after a `@property` of the same name returns the getter (`...+after`: `1`/`3` vs CPython `0`/`4`). Only the read is pre-existing; the new store error above is not.
- `hash(Fraction(1,3))` differs (`p6_legit`).
- `del f.numerator` is refused at compile time (`not in the subset: del on a Attribute`).

**Claims:** early-return leaks — verified; `Fraction.numerator` assignment — verified by `test_read_only_property_assignment_stops`; subclass plain-attribute shadowing — verified for `p14`/`p15`; run-time type in inherited errors — verified; `p18`/`p19`/`p20` — unverified (files absent); `p_accept`/`p_frac_small`/`p_exact_ret` — unverified directly (acceptance tests pass); "5 modules, 552 s" — I reran only the changed module plus safetynet; `update_manifest.py --check` — verified clean.

**Tests:** `test_ail_int64_default` + `test_ail_safetynet` on HEAD: 2 modules, 407 s, 0 failed. Other three modules were not rerun.

**Unverified:** snapshot/`icount` (non-Decimal C is byte-identical, so no change expected); `p18`–`p20`; the other three test modules.

VERDICT: FIX
1. A class that assigns a plain class attribute after a getter-only `@property` of the same name no longer stores to the instance: HEAD raises `AttributeError: property 'x' of 'A' object has no setter` (exit 1), while CPython stores and prints (`p_sameclass_after.py`: expected `0\n5\n`, actual HEAD `1\nAttributeError...`; base exits 0). The store blockers only consider more-derived classes (`d != c`), so the owner's own later plain binding is ignored; include the owner when `_class_defines_plain_attr(c, attr)` is true (same for the read path, which already reads the property instead of the class attribute on base too).
[cost $0.0217, opencode tokens {"total": 947361, "input": 46332, "output": 4993, "reasoning": 15268, "cache.write": 0, "cache.read": 880768}]
    tool time: bash 11.5 min
        408s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_int64_defaul
        156s bash   cd /tmp/rprobes && for p in p1_roundfrac p2_floordivfrac p3_dec_mathfloor p4_leaktyped p5_hashfrac p6_legit; d
         68s bash   cd /tmp/rprobes && cat p6_legit.py; echo ===; timeout 600 bash ~/tools/cmp.sh /tmp/rprobes/p6_legit.py /tmp/ba
         20s bash   date; cd /tmp/rprobes && for p in p23_annshadow p26_setter_plain_deep p27_frac_ro_via; do echo "##### $p HEAD"
         17s bash   cd /tmp/rprobes && for p in p_submethod_read p_deeper_prop p_prop_setter_inherit p_del_roprop p_attr_after_pro
          8s bash   cd /tmp/rprobes && cat > p_attr_after_prop2.py <<'EOF' class A:     @property     def x(self):         return 
          6s bash   date; cd /tmp/rprobes && for p in p14_subplain p15_subplain2 p16_submsg p18_subplain_mixed p19_subplain_setter
          4s bash   date; cd /tmp/rprobes && cat > p_sameclass_after.py <<'EOF' class A:     @property     def x(self):         re

FINAL VERDICT: FIX  2026-11-01T17:39:10Z
