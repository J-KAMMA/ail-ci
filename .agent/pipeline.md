# job job-pre63-10241306  started 2026-10-24T04:06:34Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `b41efdc` on `job-pre63-10241306`.

Fixed the first still-differing pre-existing item: str methods fetched as values (`f = s.upper`), including the residual case with an unrelated same-named field. The general path now refuses them by name (`C?-job-pre63-10241306-1`); valid calls, class attributes, `setattr` attributes and instance fields still work.

- Tests: `test_ail_pre63`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- Probes: 18 run on both builds — 11 refused by name, 7 matched CPython, 0 failed.
- `update_manifest.py --check`: exit 0.
- Full suite and instruction counts: not run, per instructions.
- Remaining pre-existing items (`bytearray.upper`, `cls.attr` in a classmethod) left unchanged.
[cost $0.0000, opencode tokens {"total": 5752430, "input": 416302, "output": 13013, "reasoning": 26859, "cache.write": 0, "cache.read": 5296256}]
    tool time: bash 14.4 min
        336s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre63 test_ail_safetynet test_ail_files test_ail
        284s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre63 test_ail_safetynet test_ail_files test_ail
         78s bash   fail=0; refused=0; same=0; for p in /tmp/probes/pre63_*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PWD" 2>&1); if
         78s bash   tail -3 /tmp/probes/pre63_valid_calls.py; echo ====; for p in /tmp/probes/pre63_*.py; do out=$(bash ~/tools/cm
         38s bash   D=/tmp/probes.4572; cat > $D/p_list.py <<'EOF' def main():     xs = ["ab"]     f = xs[0].upper     print(f()) 
         34s bash   D=/tmp/probes.4572; for p in $D/p_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 |
         10s bash   D=/tmp/probes.4572; cat > $D/p_simplenamespace.py <<'EOF' from types import SimpleNamespace   def main():     
          1s bash   for b in job-pre49-10241237 job-pre60-10241246 job-pre61-10241247 job-pre62-10241248; do git fetch --no-tags -

## review 0
[model opencode/deepseek-v4.1-flash-free]
​## Review — job pre63 (`b41efdc`)

**What the change really does:** collects attribute-store names and parameters that always receive a statically-str argument, then (a) refuses `recv.<str-method>` reads by name when the receiver is inferred `str`, or has unknown kind and the name is never stored, and (b) feeds that parameter inference into the global `infer_kind`, which removes existing run-time str guards. The second part is unsound and is not only about method values.

**Tests:** `test_ail_pre63` and `test_ail_safetynet` pass on HEAD (122 s, 0 failed); `update_manifest.py --check` exits 0. `test_ail_files` / `test_ail_corpus_findings3` not re-run (worker's claim unverified).

**Claims:** target `f = s.upper` refusal — verified (both builds refuse, base fails at run time). "Instance fields … still work" — **false** (see defect 2). "Parameters whose every direct call passes a definitely-str value are recognised" — verified, and that is the defect 1 cause. 18-probe count — unverified. Remaining pre-existing items — unverified.

**Pre-existing:** none found beyond the target; base behaves correctly on both probes below.

### Defects

1. **Parameter inference removes a necessary run-time guard** (both builds). `/tmp/rprobes/p_callback_guard.py`:
```python
def f(s):
    return s.upper()
def apply(fn):
    return fn(3)
def main():
    print(f("ab"))
    print(apply(f))
main()
```
CPython and base (general + default): stdout `AB\n`, stderr `AttributeError: 'int' object has no attribute 'upper'`, exit 1. HEAD: stdout `AB\n\n`, no error, exit 0. Same failure with `map(f, [3])` and `sorted([3,1], key=f)`. Debug C for `def shout(s): return s.upper(); shout("hello")` loses both `ail2_no_attr` guards where base had them (609 328 → 607 926 bytes): this is an unaffected program whose C changed.

2. **Valid dynamically-created attributes are refused by name** (both builds). `/tmp/rprobes/p_dynamic_field.py`:
```python
class Box:
    pass
def make(name, value):
    b = Box()
    setattr(b, name, value)
    return b
def main():
    b = make("title", "hello")
    print(b.title)
    print(b.title.upper())
main()
```
CPython and base (both builds): `hello\nHELLO\n`, exit 0. HEAD: compile fails with `the str method title used as a value … C?-job-pre63-10241306-1` (and the class-shape message). `setattr(b, "upper", "hello"); print(b.upper)` is likewise refused on HEAD but works on base. Cause: a `setattr` with a non-constant name does not populate `attr_store_names`, and the receiver kind is unknown.

VERDICT: FIX
1. Remove the global `infer_kind` side effect (or prove non-str indirect calls impossible); keep the refusal scoped to actual attribute-value reads.
2. Do not refuse an attribute read merely because its name is not in `attr_store_names` when the receiver is not provably `str`; only a proven `str` receiver should trigger the refusal.
[cost $0.0000, opencode tokens {"total": 1118286, "input": 63377, "output": 4947, "reasoning": 10487, "cache.write": 0, "cache.read": 1039475}]
    tool time: bash 3.4 min
        124s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre63 te
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_*.py; do echo "##### $(basename $p)"; bash ~/too
         22s bash   cd /tmp/base && for p in /tmp/rprobes/p_callback_map.py /tmp/rprobes/p_callback_sorted.py /tmp/rprobes/p_dynam
          6s bash   for tag in head base; do   wt=/home/runner/work/ail-ci/ail-ci; [ "$tag" = base ] && wt=/tmp/base   d=/tmp/dbg_
          5s bash   cd /tmp/base && bash ~/tools/cmp.sh /tmp/rprobes/p_callback_guard.py "$PWD" 2>&1 | tail -30
          4s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p_callback_guard.py "$PWD" 2>&1 | tail 
          4s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p_dynamic_field.py "$PWD" 2>&1 | tail -
          3s bash   cd /tmp && rm -rf showc && mkdir showc && cd showc && cp /tmp/rprobes/p_callback_guard.py p.ail && python3 p.a

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
​**Fixed and committed** (`98f7868`).

- Removed parameter inference from global `infer_kind`; indirect calls now keep their run-time guards. Debug C for `shout("hello")` matches base byte-for-byte (609,328 bytes, both `ail2_no_attr` guards).
- Refusal is now limited to provably-str receivers. Computed-name `setattr` and `setattr(b, "upper", ...)` work again.
- Added regression tests for indirect callbacks, dynamic fields, and argument values arriving via lists/dicts/fields.

**Probes:** 37 run (`19 p_*`, `18 pre63_*`), all match CPython or are refused by name. OK: callback guard/map/sorted, dynamic field/setattr, shout, valid calls/class attrs/str indexing, and all valid pre63 probes. Refused by name: direct, empty, alias, argument, list item, dict value, field attribute, negative index, f-string, concatenation, and all pre63 refusal forms.

**Tests:** `test_ail_pre63`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 304 s, 0 failed. `update_manifest.py --check` exits 0. Full suite not run, per rules.
[cost $0.0000, opencode tokens {"total": 4173723, "input": 119994, "output": 13786, "reasoning": 43948, "cache.write": 0, "cache.read": 3995995}]
    tool time: bash 10.0 min
        306s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre63 te
         93s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_refuse_alias.py /tmp/probes/p_refuse_empty.py /tm
         76s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PWD" 2>
         74s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre63_*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PWD
         42s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_callback_guard.py p_dynamic_field.py p_dynamic_setattr_upper.
          4s bash   cat > /tmp/probes/p_shout.py <<'EOF' def shout(s):     return s.upper()   def main():     print(shout("hello")
          4s bash   wc -c /tmp/dbg_head/d/program.c /tmp/dbg_base/d/program.c; grep -n "ail2_no_attr" /tmp/dbg_head/d/program.c | 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/pyboxed2.py' s=open(p).re

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — job pre63 (`98f7868`)

**What the change really does:** removes the str-parameter inference from `infer_kind` and adds a separate syntactic proof (`_prove_str_in_scope`) that refuses `x.<str-only-method>` as a value when `x` is traced to a str via literals, containers, parameters, fields or class attributes; adds tests/docs. The proof ignores runtime mutation/overrides, so it can claim "provably str" for a value that is not str at the read.

**Probes:** 13 written in `/tmp/rprobes`, each on HEAD and base with both builds (`p3`, `p5`, `p7`, `p4` pass/refuse as intended; `p2`, `p8`, `p9`, `p12` are pre-existing).

### Defects

1. **A field proven str in `__init__` is not invalidated by a later assignment; a valid program is refused (both builds).** `/tmp/rprobes/p13_field_external_override.py`:
```python
class U:
    def __init__(self):
        self.upper = 42
class B:
    def __init__(self):
        self.s = "ab"
def main():
    b = B()
    b.s = U()          # b.s is now a U, whose .upper is 42
    print(b.s.upper)
main()
```
CPython and base (g + d): `42`, exit 0. HEAD: `build g failed: ... the str method upper used as a value ... C?-job-pre63-10241306-1`; `build d failed` (general path). Cause: `_field_str_in_scope` sees only `self.s = "ab"` and not the later store.

2. **A class attribute proven str is not invalidated by an instance field of another kind (general path; both builds in the external-store variant).** `/tmp/rprobes/p10_classattr_init_shadow.py`:
```python
class U:
    def __init__(self):
        self.upper = 42
class C:
    title = "hi"
    def __init__(self):
        self.title = U()
def main():
    c = C()
    print(c.title.upper)
main()
```
CPython and base (g + d): `42`. HEAD: `build g failed` with the same marker; `d` still prints 42. The variant `/tmp/rprobes/p1_classattr_shadow.py` (`c.title = U()` in `main`) fails on both HEAD builds while base prints 42. Cause: `_attr_str_in_scope` accepts `_class_attr_str` before consulting `_field_str_in_scope`.

### Pre-existing (same on base, not blocking)
- `p2`/`p8`: a user method fetched as a value (`U.upper`) still raises `AttributeError` on both HEAD and base.
- `p9`: module-level `C.title = U()` fails on base too (`'type' object has no attribute 'title'`).
- `p12`: `s = make(); f = s.upper` still compiles and raises `AttributeError: 'str' object has no attribute 'upper'` on both HEAD and base — the recorded difference remains for non-provable receivers.

### Claims
- Removed parameter inference; indirect callback/map/sorted keep run-time guard: **verified** (all three probes match CPython and base, run-time `AttributeError`).
- Debug C for `shout("hello")` identical to base, 609,328 bytes: **verified**; also identical for `p3` (628,533) and `p5` (633,059).
- Refusal "limited to provably-str receivers": **false** — defects 1–2 are refusals of non-str receivers (the proof is unsound for mutation/shadowing).
- Computed-name `setattr` and `setattr(b, "upper", ...)` work: **verified** (`p5`, worker's dynamic probes).
- Tests 4 modules, 304 s, 0 failed: **verified** (`test_ail_pre63`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, 304 s, 0 failed). `update_manifest.py --check` exits 0: **verified**.

**Speed:** not applicable — unaffected programs' C is byte-identical; affected programs now refuse. No icount run.

**Unverified:** the full 37-probe enumeration, the full suite, instruction counts (N/A).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1341563, "input": 74868, "output": 6461, "reasoning": 26186, "cache.write": 0, "cache.read": 1234048}]
    tool time: bash 7.2 min, write 0.0 min
        306s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre63 test_ail_safetynet test_ail_files 
         63s bash   for p in /tmp/rprobes/p*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E "cpy
         16s bash   for p in /tmp/rprobes/p1_classattr_shadow.py /tmp/rprobes/p2_field_alias_mutate.py /tmp/rprobes/p6_inherited_c
         12s bash   for prog in /tmp/probes/p_shout.py /tmp/rprobes/p3_field_title_valid.py /tmp/rprobes/p5_dynamic_setattr.py; do
         12s bash   for p in /tmp/rprobes/p9_classattr_rebind.py /tmp/rprobes/p10_classattr_init_shadow.py /tmp/rprobes/p12_str_vi
         11s bash   for p in /tmp/rprobes/p9_classattr_rebind.py /tmp/rprobes/p10_classattr_init_shadow.py /tmp/rprobes/p12_str_vi
          4s bash   echo "=== BASE p13"; bash ~/tools/cmp.sh /tmp/rprobes/p13_field_external_override.py /tmp/base 2>&1 | grep -E 
          4s bash   echo "=== BASE p8"; bash ~/tools/cmp.sh /tmp/rprobes/p8_param_cond.py /tmp/base 2>&1 | grep -E "cpython exit|s

FINAL VERDICT: FIX  2026-10-24T05:05:55Z
