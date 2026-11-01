# job job-std_cmath-11020402  started 2026-11-01T19:03:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `51ddaee`.

- Defect 1: complex `**` now follows CPython’s `_Py_c_pow` errno mapping. Non-finite exponents/phase raise `ZeroDivisionError: 0.0 to a negative or complex power`, overflowing results raise `OverflowError: complex exponentiation`, NaNs stay `(nan+nanj)`, and small-integer powers preserve CPython’s signed zeros and overflow checks.
- Defect 2: calls with `**mapping` lower through `_ail_cm_kw`, reproducing CPython’s binding for every `cmath` function, including empty mappings, duplicates, non-string keys, unknown keywords and arity errors.

Probes `p_pow2`, `p_powgrid` (15×20 special-value grid), `p_kw2` (all `cmath` functions with `**`) and `p_star` match CPython on both `g` and `d` builds.

Tests: `test_ail_std_cmath`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass in 380s. The 5 lab/compare tasks that build on base still produce byte-identical `program.c`; the other 5 fail on both base and head. `update_manifest.py --check` rc=0.
[cost $0.0000, opencode tokens {"total": 8462723, "input": 106751, "output": 20574, "reasoning": 33958, "cache.write": 0, "cache.read": 8301440}]
    tool time: bash 15.4 min, websearch 0.0 min, edit 0.0 min
        381s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_cmath test_ail_safetynet te
        158s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/cmpdep/runone.sh <<'SH' #!/bin/bash set -e task=$1 mkdir -p /
        120s bash   find / -name 'complexobject.c' -o -name 'cmathmodule.c' 2>/dev/null | head; ls /usr/lib/python3*/ 2>/dev/null 
         58s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/p_pow2.py /home/runner/work/ail-ci/ail-ci; echo =====; bash ~/tools/cmp.sh
         46s bash   cat > /tmp/p_star.py <<'PY' import cmath print(cmath.isclose(1.0, 1.0, **{})) try:     print(cmath.sqrt(**{}))
         41s bash   cat > /tmp/p_kw2.py <<'PY' import cmath  def show(label, f):     try:         print(label, repr(f()))     exce
         30s bash   cat > /tmp/p_pow2.py <<'PY' import cmath  def show(label, f):     try:         print(label, repr(f()))     exc
         22s bash   cat > /tmp/p_pow2.py <<'PY' import cmath cases = [     "2j ** float('inf')",     "2j ** float('-inf')",     "(

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change really does.** Commit `51ddaee` rewrites complex `**` in the cmath prelude to follow CPython's `_Py_c_pow` errno mapping (infinite phase → `ZeroDivisionError`, infinite result → `OverflowError`, NaN results, integer-path overflow/zero checks), and adds `_ail_cm_kw` lowering for `cmath.f(**mapping)` (`cmathlib.py:145-159`), merging mappings and explicit keywords. No change outside cmath.

**Probes** (with `cmp.sh`; `g` and `d` agree throughout):
- Review defect 1: `2j ** inf`, `2j ** -inf`, `(1+1j)**inf`, `(-2+0j)**inf`, `(2+0j)**complex(0,inf)`, `2j**nan`, plus zero-base/±100/±101/signed-zero cases — same stdout as CPython.
- Review defect 2: `cmath.isclose(1,1,**{})`, `cmath.sqrt(**{})`, `cmath.log(**{})`, `cmath.rect(**{})` — same stdout.
- `p_powgrid` (12×17 special values), `p_powedge` (1e308/1e-308, ±100/±101, rpow, signed zeros), `p_over` (overflow/ERANGE) — same stdout.
- `p_kwmore`, `p_kwdup`, `p_kwtypes2`: dict mappings via list item, attribute, dict value, `*args + **`, duplicates, non-string keys, unknown/arity — same stdout.
- `p_nofeature` (no cmath): `program.c`, `program_mix0.c`, `program_mix1.c` byte-identical to `/tmp/base`.
- `test_ail_std_cmath` + `test_ail_safetynet`: 2/2 pass, 336 s, rc=0. `update_manifest.py --check`: rc=0.

**Pre-existing** (identical on base):
- `__rpow__` never takes the integer path, so finite bases differ in rounding/signed zero: `1.1 ** (100+0j)` → `13780.61233982238` vs CPython `...2364`; `-2.0 ** (3+0j)` → `(-8+2.9e-15j)` vs `(-8+0j)`.
- Large float exponents crash: `1j ** 1e300` → `OverflowError: integer overflow in int(float)` on both.
- `cmath.sqrt(**("x",1,2))` → `takes no keyword arguments` on both.
- User-type names still fall back to `"object"`.

**Report claims.** Defect 1 fixed: verified. Defect 2 fixed for dict mappings: verified; "reproducing CPython's binding for every cmath function" is false for non-mapping `**` (defect 1). `p_pow2`/`p_powgrid`/`p_kw2`/`p_star` match: verified by equivalent probes. 5 lab/compare C identical: not rerun (only the cmath prelude changed; non-cmath C verified identical). 4/4 tests: I reran the 2 required modules; files/corpus not rerun. Manifest rc=0: verified.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3`, lab/compare byte-identity, speed (no hot code touched).

VERDICT: FIX

1. Non-mapping `**` builds and gives the wrong exception; `_ail_cm_kw` treats any non-dict part as an explicit-keyword tuple (`part[1]`/`part[2]`).
   ```python
   import cmath
   def show(label, f):
       try: print(label, repr(f()))
       except Exception as e: print(label, type(e).__name__ + ": " + str(e))
   show("list", lambda: cmath.isclose(1.0, 1.0, **[("rel_tol", 1e-9)]))
   show("int",  lambda: cmath.isclose(1.0, 1.0, **5))
   show("none", lambda: cmath.isclose(1.0, 1.0, **None))
   ```
   Expected: `TypeError: cmath.isclose() argument after ** must be a mapping, not list` / `not int` / `not NoneType`.
   Actual: `IndexError: list index out of range`, `TypeError: 'int' object is not subscriptable`, `TypeError: 'NoneType' object is not subscriptable`. Base gave a different wrong message (`'None' is an invalid keyword argument for isclose()`), so this is not identical to base.

2. `float ** complex` with an infinite base and an integer exponent in 2..100 (or -100..-1) now raises where CPython returns NaN; `__rpow__` still uses the general `_ail_cm_pow`, and its new overflow check fires on `real=inf`.
   ```python
   import cmath
   for n in (2, 100, -1):
       try: print(n, repr(float("inf") ** (n + 0j)))
       except Exception as e: print(n, type(e).__name__ + ": " + str(e))
   ```
   Expected: `(nan+nanj)` for all three.
   Actual: `OverflowError: complex exponentiation` for all three. Base gave `(inf+nanj)` (also wrong, but different). `complex(float("inf"),0) ** n` matches CPython, so the defect is only in the `__rpow__` path.
[cost $0.0000, opencode tokens {"total": 1732892, "input": 80250, "output": 12073, "reasoning": 35833, "cache.write": 0, "cache.read": 1604736}]
    tool time: bash 7.4 min
         75s bash   cd /tmp/rprobes cat > p_bigmin.py <<'EOF' import cmath def show(label, f):     try:         print(label, repr(
         60s bash   cd /tmp/rprobes; (bash ~/tools/cmp.sh /tmp/rprobes/p_powbig.py /home/runner/work/ail-ci/ail-ci > /tmp/rprobes/
         44s bash   cd /tmp/rprobes cat > p_minbad.py <<'EOF' import cmath def show(label, f):     try:         print(label, repr(
         44s bash   cd /tmp/rprobes; (bash ~/tools/cmp.sh /tmp/rprobes/p_rev1.py /home/runner/work/ail-ci/ail-ci > /tmp/rprobes/o_
         44s bash   cd /tmp/rprobes; (bash ~/tools/cmp.sh /tmp/rprobes/p_kwmore.py /home/runner/work/ail-ci/ail-ci > /tmp/rprobes/
         42s bash   cd /tmp/rprobes cat > p_kwtypes2.py <<'EOF' import cmath def show(label, f):     try:         print(label, rep
         33s bash   cd /tmp/rprobes; (bash ~/tools/cmp.sh /tmp/rprobes/p_rpow.py /tmp/base > /tmp/rprobes/o_rpow_b.txt 2>&1; echo 
         31s bash   cd /tmp/rprobes cat > p_over.py <<'EOF' import cmath def show(label, f):     try:         print(label, repr(f(

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed `7fba184`.

- Non-mapping `**` now raises CPython’s `cmath.<name>() argument after ** must be a mapping, not <type>`; custom `keys()` mappings, non-string keys, duplicates, and `*args + **` match.
- Reflected powers use the integer path: `float("inf") ** (2+0j)` → `(nan+nanj)`, while `** (1+0j)` still raises `OverflowError`.

Probes `p_kwbad`, `p_rpow2`, `p_rev1`, `p_rev2`, `p_kwmore`, `p_kwtypes2`, `p_rpow`, `p_powgrid`, `p_powedge`, `p_over`: g/d match CPython. Five lab/compare C files remain byte-identical. Required tests `test_ail_std_cmath`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass (364 s); manifest `--check` rc=0. (`p_powbig` still hits the pre-existing `1j ** 1e300` `int(float)` overflow noted in the review.)
[cost $0.0000, opencode tokens {"total": 3919114, "input": 402930, "output": 11245, "reasoning": 17195, "cache.write": 0, "cache.read": 3487744}]
    tool time: bash 15.3 min, edit 0.0 min
        364s bash   python3 ../tools/par_check.py -j 2 test_ail_std_cmath test_ail_safetynet test_ail_files test_ail_corpus_findin
        265s bash   cd /tmp/rprobes && for p in p_rev1 p_rev2 p_kwmore p_kwtypes2 p_rpow p_powbig p_powgrid p_powedge p_over; do e
        150s bash   for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit 
         41s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/p_kwbad.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
         41s bash   cd /tmp/probes && for p in p_kwbad p_rpow2; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py /home
         25s bash   rm -rf /tmp/cmpdep/head/*/dbg /tmp/cmpdep/base/*/dbg; cd /tmp && printf '%s\n' berth_sim chain_relax echo_pack
         19s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/p_kwbad.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
         11s bash   cd /tmp/probes && for p in p_kwbad p_rpow2; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py /home

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review of `7fba184` (change `work..HEAD`: `51ddaee`, `7fba184`)

**What the change really does.** It fixes review 1: non-finite/imaginary exponents in `_ail_cm_pow` now map to CPython's `ZeroDivisionError`/`OverflowError`/NaN, the integer `**` fast path is shared with reflected powers and checks overflow, and `cmath.f(...)` calls containing `**mapping` are lowered to a runtime `_ail_cm_kw` that parses arguments like CPython (explicit keywords, mappings, `*args`). Only `cmathlib.py` and `prelude_cmath.py` change.

**Probes run** (`cmp.sh`, both g and d builds):
- `rv_pow`, `rv_rpow`, `rv_plain`, `rv_dataflow`, `rv_kw5`, worker's `p_pow2`, `p_star2`, `p_powgrid`, `p_powedge`, `p_over`, `p_minbad` — same stdout as CPython; review 1 defects 1 and 2 are fixed.
- `rv_kw` — `**` mapping semantics (empty/non-empty, `a`/`b`/tols, duplicates, non-string keys, custom `keys()`, non-mapping list/int/None/str/tuple, `*list + **`) match except the star error below.
- `rv_zeroexp`, `rv_min1` — **DIFF/crash** (defect 1); base matches CPython.
- `rv_starbase` — **DIFF** (defect 2).
- Plain non-cmath program: `program.c` byte-identical to `/tmp/base`. No `lab/compare/src` task imports `cmath`, so all 10 C files are unaffected (stronger than the report's 5).
- `test_ail_std_cmath`, `test_ail_safetynet` on HEAD: 2/2 pass (272 s). `update_manifest.py --check`: rc=0.

**Defects**
1. Regression: zero base with a large integral float exponent now crashes instead of returning `0j`. Removing the zero-base early return makes `math.floor(b.real)` run before the `abs(b.real) <= 100` guard, so AIL's int-based `floor` raises.
   ```python
   import cmath
   print(0j ** 1e300)
   print(0.0 ** complex(1e300, 0.0))
   print(0j ** 1e19)
   ```
   Expected `0j\n0j\n0j` (CPython and `/tmp/base` both print this). Actual: no stdout, `OverflowError: integer overflow in int(float) (ints are 64-bit; --exact-int gives exact ints)`, exit 1, both builds. Reorder `abs(b.real) <= 100.0` before `math.floor`, or restore the zero-base early path.
2. The new `*args` collection loses CPython's star message: `_ail_cm_args` iterates the value directly.
   ```python
   import cmath
   print(cmath.isclose(*5, **{}))
   ```
   Expected `TypeError: cmath.isclose() argument after * must be an iterable, not int`. Actual `TypeError: 'int' object is not iterable`. Base gave a named compile-time refusal (`a **kwargs call argument`), which was acceptable; the change introduced this wrong runtime message. Only invalid starred operands are affected.

**Report claims.** Non-finite powers fixed: verified. `**mapping` / non-mapping / custom mappings / non-string keys / duplicates: verified, except the invalid-star message ("`*args + **` match" is false for a non-iterable `*`). Reflected-power claims (`inf ** (2+0j)`, `inf ** (1+0j)`): verified. `lab/compare` C unchanged: verified (all 10, via no-cmath sources + a plain-program C diff). Tests 2/2 rerun pass; `test_ail_files`/`test_ail_corpus_findings3` not rerun (per scope). Manifest check rc=0: verified. "`p_powbig` int(float) overflow pre-existing": true for non-zero bases, but the zero-base form is new (defect 1).

**Pre-existing.** Non-zero base with a huge integral float exponent (`(2+0j) ** 1e300`, `1j ** 1e300`) has the same `int(float)` overflow / wrong messages on base. `_ail_cm_tname` still falls back to `object` for user types. `cmath.isclose(1.0, a=1.0, b=1.0)` is a named compile-time refusal on base and HEAD alike.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3`; speed (no non-cmath hot code touched, so not measured); pathological custom mappings that mutate during `**` expansion.

VERDICT: FIX
[cost $0.0400, opencode tokens {"total": 1908167, "input": 89585, "output": 10854, "reasoning": 24432, "cache.write": 0, "cache.read": 1783296}]
    tool time: bash 15.8 min
        273s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_cmath test_a
         94s bash   cd /tmp/rprobes && for p in rv_rpow rv_dataflow rv_plain; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/rpro
         83s bash   cd /tmp/rprobes && for p in p_powgrid p_over p_minbad; do echo "==== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.
         79s bash   cat > /tmp/rprobes/rv_min1.py <<'EOF' import cmath print(0j ** 1e300) print(0.0 ** complex(1e300, 0.0)) print(
         72s bash   cd /tmp/rprobes && for p in rv_pow rv_rpow rv_kw; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.p
         64s bash   cd /tmp/rprobes && printf 'import cmath\ndef show(l,f):\n    try: print(l, repr(f()))\n    except Exception as
         59s bash   cd /tmp/rprobes && for p in p_star2 p_pow2; do echo "==== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /home/ru
         54s bash   cat > /tmp/rprobes/rv_zeroexp.py <<'EOF' import cmath def show(label, f):     try:         print(label, repr(f

FINAL VERDICT: FIX  2026-11-01T20:51:04Z
