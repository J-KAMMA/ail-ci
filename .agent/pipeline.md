# job job-std_enum-11020119  started 2026-11-01T16:29:49Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `9b828815` on `job-std_enum-11020119`.

- Root cause: CPython 3.12.10 changed `EnumType.__contains__`; CI uses 3.12.15 while local used 3.12.3.
- Fix: `enumlib.py` now emits version-aware `_ail_en_*_has`: old hash/value-map path before 3.12.10, `_call()` plus `ValueError` catch from 3.12.10.
- Required tests on final commit with 3.12.15: 51 run, 51 OK, 1 skipped (`test_ail_files`).
- Applied branch alone on `origin/integ` (`4d95350`), reran the five target modules: 31 tests, all OK.
- Probes: 4 programs × 2 builds × 2 interpreters = 16 comparisons, all byte-identical.
- Manifest check passes. No push.
[cost $0.0000, opencode tokens {"total": 11840254, "input": 335417, "output": 26422, "reasoning": 40975, "cache.write": 0, "cache.read": 11437440}]
    tool time: bash 80.1 min
        647s bash   P=/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 for m in test_ail_safetynet test_ail_virtual_dispatch te
        478s bash   P=/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 for m in test_ail_obj_refs test_ail_std_enum test_ail_un
        463s bash   P=/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 for m in test_ail_obj_refs test_ail_std_enum test_ail_un
        361s bash   P=/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 for m in test_ail_obj_refs test_ail_std_enum test_ail_un
        342s bash   python3 -m unittest -q test_ail_unified > /tmp/t_uni.log 2>&1; echo RC=$?; tail -40 /tmp/t_uni.log
        333s bash   python3 -m unittest -q test_ail_unified > /tmp/c_uni.log 2>&1; echo RC=$?; tail -30 /tmp/c_uni.log
        239s bash   P=/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 for m in test_ail_safetynet test_ail_virtual_dispatch; d
        236s bash   P=/opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 for m in test_ail_safetynet test_ail_virtual_dispatch; d

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** In `python/pkg-v12/enumlib.py`, the generated `_ail_en_<class>_has` is now selected by the compiler's `sys.version_info`: before 3.12.10 the old hash/value-map loop, from 3.12.10 `try: cls(value) ... except ValueError: False`; manifest hash updated, DEVLOG added. That matches the report.

**Tests (HEAD).**
- 3.12.15, `par_check.py -j 2` on the five named modules: 5/5 OK, 0 failed (549s).
- 3.12.3, `test_ail_std_enum`: OK (93s).
- `tools/update_manifest.py --check`: rc 0.

**Probes (both builds with `cmp.sh`).**
- `core.py` (3.12.15): matches CPython, including empty-enum TypeError, unhashable False, aliases, arg/list/attr/dict routes, mutation. Only difference is the pre-existing class-as-argument case noted below.
- `kinds.py` (3.12.15): both builds identical to CPython (Enum/IntEnum/StrEnum, cross-class, unhashable).
- `flags.py`, `reg_float2.py` (3.12.15): **regressions**, see defects.
- `noenum.py`: `--debug-dir` `program.c` is byte-identical between HEAD and `/tmp/base` (only report paths differ).
- On `/tmp/base` the old empty-enum/composite/unhashable failures reproduce, so the fix does address its targets.

**Report claims.** Root cause + new codegen path: verified. Target tests pass: verified. Lab/EDGE unchanged and passing on both interpreters: verified. Manifest: verified. "16 comparisons all byte-identical": **false** for Flag/IntFlag values outside the worker's probe set.

**Pre-existing (same on `/tmp/base`).** Calling `F(1.0)` directly raises `ValueError` in AIL while CPython returns `F.A`; passing an enum class as a function argument passes the member list, so `contains(Color, 1)` is False. Not blocking.

**Defects (introduced by this change on 3.12.10+).** New Flag `_has` routes through generated Flag `_call`, whose `if not isinstance(v, int): raise ValueError` is stricter than CPython's value-map lookup first. This is correct on 3.12.3 (old branch) but wrong on CI's 3.12.15.

1. Probe `/tmp/rprobes/reg_float2.py` lines 1–2: `1.0 in F`, `1.0 in IF` with `F(Flag)`, `IF(IntFlag)` values 1/2. CPython 3.12.15 prints `True` / `True`; HEAD both builds print `False` / `False`. `/tmp/base` prints `True` / `True`.
2. Same probe line 3: `IF.A in F`. CPython prints `True` (and `/tmp/base` prints `True`); HEAD both builds print `False`.

Unverified: instruction counts (no obvious hot-path slowdown; Flag valid-int lookup is still O(1)); Python 3.13+ (outside the stated 3.12 oracle — note empty-enum `in` returns False there, unlike 3.12.15).

VERDICT: FIX

1. `1.0 in Flag` / `1.0 in IntFlag` is now False; CPython 3.12.15 and the base give True. Source: `from enum import Flag, IntFlag; class F(Flag): A=1; class IF(IntFlag): A=1; print(1.0 in F, 1.0 in IF)` → expected `True True`, actual `False False` (both builds, 3.12.15).
2. `IF.A in F` is now False; CPython 3.12.15 and the base give True. Source: `from enum import Flag, IntFlag; class F(Flag): A=1; class IF(IntFlag): A=1; print(IF.A in F)` → expected `True`, actual `False`.
[cost $0.0301, opencode tokens {"total": 1445818, "input": 64641, "output": 9170, "reasoning": 18023, "cache.write": 0, "cache.read": 1353984}]
    tool time: bash 8.4 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup /opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 ..
         94s bash   cd /home/runner/work/ail-ci/ail-ci && (cd AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_std
         53s bash   cat > /tmp/rprobes/reg_float.py <<'EOF' from enum import Flag, IntFlag class F(Flag):     A = 1     B = 2 clas
         38s bash   cd /tmp/rprobes && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH bash ~/tools/cmp.sh /tmp/rprobes/fla
         36s bash   cat > /tmp/rprobes/flags.py <<'EOF' from enum import Flag, IntFlag  class F(Flag):     A = 1     B = 2     C =
         31s bash   cd /tmp/rprobes && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH bash ~/tools/cmp.sh /tmp/rprobes/cor
         28s bash   cd /tmp/rprobes && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH bash ~/tools/cmp.sh /tmp/rprobes/cor
         27s bash   cd /tmp/rprobes && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH bash ~/tools/cmp.sh /tmp/rprobes/kin

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `0a83a674`.

**Change:** generated Flag/IntFlag `_call` now looks the value map up (hash/equality) before rejecting non-`int` values, so `1.0 in F`, `1.0 in IF`, `IF.A in F`, and direct `F(1.0)` / `F(IF.A)` match CPython. Empty-enum `TypeError`, unhashable-`in` `False`, and new composites are unchanged. Added `test_flag_contains_matches_cpython`; updated DEVLOG and manifest.

**Probes:** `flags_full`, `flag_direct`, `reg_float2`, `flag_equal_routes`, `enum_contains_core`, `enum_contains_kinds`, `enum_contains_flags` — all match CPython on 3.12.3 and 3.12.15, both builds (14/14 module-interpreter runs; 28/28 build outputs).

**Tests on final commit:**
- 3.12.3, `par_check -j 2`: `test_ail_std_enum`, `test_ail_cov2`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 OK.
- 3.12.15: `test_ail_std_enum` OK; `test_ail_obj_refs`, `test_ail_safetynet`, `test_ail_unified`, `test_ail_virtual_dispatch` — 4/4 OK.
- `tools/update_manifest.py --check` rc 0.

Not pushed; only pre-existing untracked `.agent/pipeline.md` remains.
[cost $0.0375, opencode tokens {"total": 2909829, "input": 85757, "output": 10771, "reasoning": 16245, "cache.write": 0, "cache.read": 2797056}]
    tool time: bash 27.6 min, edit 0.0 min, write 0.0 min
        546s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_enum test_ail_cov2 test_ail
        365s bash   cd /tmp/probes && for py in /usr/bin/python3 /opt/hostedtoolcache/Python/3.12.15/x64/bin/python3; do for p in 
        360s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && /opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 ../tools
        115s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && /opt/hostedtoolcache/Python/3.12.15/x64/bin/python3 -m unitt
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_std_enum 2>&1 | tail -20
         48s bash   python3 - <<'PY' s=open('/tmp/probes/flag_equal.py').read() hdr=s[:s.index('class Box:')] i=s.index('def line(
         46s bash   python3 - <<'PY' s=open('/tmp/probes/flag_equal.py').read() # header through end of values loop idx=s.index("d
         36s bash   cd /tmp/probes && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH bash ~/tools/cmp.sh /tmp/rprobes/flag

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** generated Flag/IntFlag `_call` now tries the value-map lookup (catching `KeyError`/`TypeError`) before the non-`int` check, and on Python ≥ 3.12.10 generated `x in E` follows the new `EnumType.__contains__` by routing through the generated `_call` and catching only `ValueError`.

**Probes (HEAD vs CPython, both builds):**
- `q_float` (1.0/2.0/bool/1.5/`'1'`/None/zero, cross Flag/IntFlag/IntEnum values, direct calls): same stdout on 3.12.3 and 3.12.15.
- `q_context` (values via argument, list item, attribute, dict value; mutation after taking them): same on both versions.
- `q_unhash` (list/dict/set in all five enum kinds): same on both versions.
- `q_empty` (containment on empty Enum/IntEnum/StrEnum/Flag/IntFlag): same on both versions.
- `p_composite` (new Flag/IntFlag composites, negative, caching): same on both versions; base differs on 3.12.15 (False vs True), HEAD fixed.
- Non-enum program `q_nonenum`: `--debug-dir` C identical to base (only temp paths differ).
- Base comparison confirms HEAD fixes `F(1.0)`, `F(IF.A)`, unhashable-list `in`, empty-enum `in`, and new composites on 3.12.15.

**Claims:** `_call` lookup-before-int-check — verified; `1.0 in F/IF`, `IF.A in F`, `F(1.0)`, `F(IF.A)` — verified; empty-enum TypeError, unhashable-list False, composites — verified; added test/DEVLOG/manifest — verified. `update_manifest.py --check` rc 0. All 5 named modules pass on 3.12.15 (`-j 2`, 369 s); `test_ail_std_enum` and `test_ail_safetynet` pass on 3.12.3 (175 s). Not re-run on 3.12.3: `test_ail_obj_refs`, `test_ail_unified`, `test_ail_virtual_dispatch`.

**Pre-existing (does not block):** a custom unhashable object whose `__eq__` matches a member (`__hash__ = None`, `__eq__` → True) gives `w in F/IF` False on HEAD vs True on CPython 3.12.15; the base raises TypeError for the same probe, so the case was already wrong.

**Defects**

1. Non-flag `in` no longer hashes the value, so an exception from `__hash__` is swallowed. This is a regression from base (base matched CPython; HEAD does not).

Probe `/tmp/rprobes/q_hasherr.py` (3.12.15, both builds):
```python
from enum import Enum, IntEnum, StrEnum
class E(Enum):
    A = 1
class IE(IntEnum):
    A = 1
class S(StrEnum):
    A = 'a'
class B:
    def __hash__(self): raise RuntimeError('boom')
    def __eq__(self, other): return False
    def __repr__(self): return 'B()'
b = B()
for label, f in [('E', lambda: b in E), ('IE', lambda: b in IE), ('S', lambda: b in S)]:
    try:
        print(label, f())
    except RuntimeError as e:
        print(label, 'RuntimeError', e)
```
Expected (CPython and base): `E RuntimeError boom`, `IE RuntimeError boom`, `S RuntimeError boom`.
Actual HEAD (g and d): `E False`, `IE False`, `S False`.
Cause: `generated()`'s new `_has` calls `_call`, which compares members by `==` and never hashes; the old `_has` called `hash(v)` first.

VERDICT: FIX
[cost $0.0357, opencode tokens {"total": 1305503, "input": 75379, "output": 9165, "reasoning": 25439, "cache.write": 0, "cache.read": 1195520}]
    tool time: bash 24.5 min
        371s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH /opt/
        176s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && /usr/bin/python3 ../tools/par_check.py -j 2 test_ail_std_enu
        133s bash   cd /tmp/rprobes && for p in p_float p_unhash p_empty p_composite p_eqobj; do echo "===== $p (HEAD py3.12.3)"; 
        132s bash   export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH; cd /tmp/rprobes && for p in q_float q_unhash q_
        128s bash   export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH; python3 --version; cd /tmp/rprobes && for p in 
        121s bash   cd /tmp/rprobes && for p in q_float q_unhash q_empty q_context; do echo "===== $p BASE 3.12.3"; timeout 300 ba
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH nohup
        114s bash   cd /tmp/rprobes && for p in q_float q_unhash q_empty q_context; do echo "===== $p HEAD 3.12.3"; timeout 300 ba

FINAL VERDICT: FIX  2026-11-01T19:00:11Z
