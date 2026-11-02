# job job-reintenum4-11021117  started 2026-11-02T02:18:12Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Final commit `8d87b44` on `job-reintenum4-11021117`.

- Probes `rev_gt`, `rev_order2`, `bytes_order`, `rev_unrel` match CPython on both builds; enum build keeps the `MUL` guard, class-only build does not.
- Manifest `--check` passes.
- All targeted tests pass: `test_ail_reintenum4`, `test_ail_stdtop1`, `test_ail_stdlib5`, `test_ail_dunders`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (7/7, 0 failed).

No further steps; only the pre-existing untracked `.agent/pipeline.md` remains.
[cost $0.0000, opencode tokens {"total": 9203217, "input": 759958, "output": 19829, "reasoning": 49414, "cache.write": 0, "cache.read": 8374016}]
    tool time: bash 39.5 min
        867s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 -X utf8 -B ../tools/par_check.py -j 2 -
        831s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null && python3 tools/update_mani
        190s bash   cd /home/runner/work/ail-ci/ail-ci && for p in bytes_order rev_gt rev_order2; do echo ==== $p; bash ~/tools/cm
         85s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='/tmp/probes/rev_order2.py' s=open(p).read() s=s.repl
         85s bash   cat > /tmp/probes/rev_order2.py <<'EOF' from decimal import Decimal from fractions import Fraction from enum i
         84s bash   mkdir -p /tmp/probes && cat > /tmp/probes/rev_gt.py <<'EOF' from decimal import Decimal from fractions import 
         83s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/rev_gt.py $PWD > /tmp/probes/head_gt2.lo
         82s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/rev_gt.py $PWD > /tmp/probes/head_gt3.lo

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

Change: adds `_ail_en_cmp` so IntEnum/IntFlag ordering returns `NotImplemented` for Decimal/Fraction, marks `_ail_intenum` so Decimal/Fraction conversion/equality consumes a member's value, reworks the runtime instance-ordering branch to route the `NotImplemented` case to the reflected Decimal/Fraction method, and gates the pre-`ail__mul_slow` MUL guard on the program having an enum base class.

Claims:
- `_ail_en_cmp`, marker, runtime ordering change, `dunderrt.patch(enum=...)`: verified in diff.
- `rev_gt`/`rev_order2`/`bytes_order`/`rev_unrel` match CPython: verified by equivalent probes p1, p3, p4, p7, p8 (IntEnum/IntFlag all operators, both directions, parameter/list/dict/attribute, big ints, bool, negative, NaN). `rev_unrel` C is byte-identical to base.
- Enum build keeps the MUL guard, class-only build does not: verified (p4 has it; p5b/`rev_unrel` do not).
- Manifest `--check`: verified clean.
- Tests: re-ran `test_ail_reintenum4`, `test_ail_safetynet`, `test_ail_dunders`: 3/3 ok, 0 failed. The other four modules in the report were not re-run (unverified).
- Commit `8d87b44`, clean tree except `.agent/pipeline.md`: verified.

Pre-existing (identical on base): plain `Enum` vs Decimal error text (`'>' E and Decimal`); Fraction vs StrEnum (`'<' Fraction and object`); `A() < B()` / `R() > L()` TypeErrors; `Decimal * C.B` etc.

Defects:

1. StrEnum ordering against Decimal regressed. Probe `/tmp/rprobes/p8.py`:
   ```python
   from decimal import Decimal
   from enum import StrEnum
   class S(StrEnum): A = "a"
   def show(f):
       try: print(repr(f()))
       except Exception as e: print(type(e).__name__ + ": " + str(e))
   show(lambda: S.A > Decimal("0.5"))
   show(lambda: S.A < Decimal("0.5"))
   show(lambda: S.A >= Decimal("0.5"))
   show(lambda: S.A <= Decimal("0.5"))
   ```
   CPython: `'>' ... between 'S' and 'decimal.Decimal'`, `'<' ... between 'S' and 'decimal.Decimal'`, `'>=' ...`, `'<=' ...`.
   HEAD: all four print `TypeError: '<' not supported between instances of 'decimal.Decimal' and 'S'`.
   Base: same four TypeErrors but with the correct operator and operand order (`'>' ... 'S' and 'Decimal'`). So `8d87b44` changed the operator/order: the new unconditional `ail2n_dec_frac(b)` route sends `S.A.__lt__`'s `NotImplemented` into Decimal's method, which raises instead of returning `NotImplemented`. It should only take this route for an `_ail_intenum` left operand (or leave non-IntEnum programs on the old path).

2. A class-only program that returns `NotImplemented` (no enum) still gets different C, so the gating is incomplete. Probe `/tmp/rprobes/p5ni.py`:
   ```python
   class A:
       def __lt__(self, other):
           return NotImplemented
   class B:
       def __gt__(self, other):
           return True
   print(A() < B())
   ```
   Base C vs HEAD C: HEAD adds `ail2n_dec_frac()` and the new instance-ordering branch; base does not. Behavior is unchanged (both raise the pre-existing TypeError instead of CPython's `True`), but per the “programs not using the feature must keep their C” rule the new ordering branch, like the MUL guard in the last review, needs to be gated to programs with an enum.

Unverified: instruction-count impact; `test_ail_stdtop1`, `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3`.

VERDICT: FIX
1. StrEnum left operand vs Decimal: all four operators now report `'<'` with reversed operands; limit the `ail2n_dec_frac` reflection route to IntEnum/IntFlag operands (see `/tmp/rprobes/p8.py`).
2. `safetyrt.patch_notimplemented`'s new ordering branch changes C for non-enum programs that use `NotImplemented`; gate it on enum use as was done for the MUL guard (see `/tmp/rprobes/p5ni.py`).
[cost $0.0000, opencode tokens {"total": 3512374, "input": 280077, "output": 13051, "reasoning": 31278, "cache.write": 0, "cache.read": 3187968}]
    tool time: bash 19.6 min
        276s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -X utf8 -B ../tools/par_check.py -j 2 t
        167s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p1.py $PWD > /tmp/rprobes/h1.log 2>&1 &
        153s bash   cd /tmp/rprobes && python3 - <<'PY' p='p3.py'; s=open(p).read() s=s.replace('class MyInt(int):\n    pass\n',''
        102s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p1.py /tmp/base > /tmp/rprobes/b1.log 2
         86s bash   cat > /tmp/rprobes/p8.py <<'EOF' from decimal import Decimal from fractions import Fraction from enum import S
         85s bash   cat > /tmp/rprobes/p7.py <<'EOF' from decimal import Decimal from fractions import Fraction from enum import I
         65s bash   cat > /tmp/rprobes/p8.py <<'EOF' from decimal import Decimal from fractions import Fraction from enum import S
         63s bash   cd /tmp && rm -rf dbg && mkdir dbg && cp /tmp/rprobes/p2.py dbg/p.ail && cd dbg && AIL_NO_CACHE=1 AIL_QUIET_FA

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `14eb530`.

- **Defect 1:** Decimal/Fraction reflection now runs only for an IntEnum/IntFlag left operand (`ail2n_intenum`); StrEnum keeps the original operator/operand-order TypeError.
- **Defect 2:** `safetyrt.patch_notimplemented(enum=...)` emits the new ordering branch only for enum programs. Class-only programs now generate C byte-identical to base (`p5ni`/`rev_notimpl_unrelated`, `rev_unrel`).

Probes on both builds: `rev_strenum_dec`, `rev_gt`, `rev_order2`, `bytes_order` match CPython; `p1`/`p8` retain only the pre-existing Decimal/Fraction type-name text differences with correct operators and operand order.

Tests: `test_ail_reintenum4`, `test_ail_dunders`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (514s). Manifest `--check` clean.
[cost $0.0000, opencode tokens {"total": 3438753, "input": 269315, "output": 10681, "reasoning": 12901, "cache.write": 0, "cache.read": 3145856}]
    tool time: bash 30.8 min, edit 0.0 min
        518s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -X utf8 -B ../tools/par_check.py -j 2 t
        516s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -X utf8 -B ../tools/par_check.py -j 2 t
        271s bash   cd /tmp/probes && rm -f /tmp/probe_*.log && i=0; for f in rev_strenum_dec.py rev_gt.py rev_order2.py bytes_ord
        183s bash   cd /tmp/rprobes && for f in p8.py p1.py; do echo "=== $f"; bash ~/tools/cmp.sh /tmp/rprobes/$f /home/runner/wo
        172s bash   cd /tmp/probes && for f in rev_strenum_dec.py rev_gt.py; do echo "=== $f"; bash ~/tools/cmp.sh /tmp/probes/$f 
         89s bash   ls -d /tmp/base 2>/dev/null && cd /tmp/base && git log --oneline -1; cd /tmp/rprobes && for f in p8.py p5ni.py
         83s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/p8.py /tmp/base 2>&1 | tail -3; d=$(ls -dt /tmp/cmp* | head -1); e
          7s bash   cd /tmp && for name in p5ni rev_unrel; do rm -rf cgen_head cgen_base cgen_head_dbg cgen_base_dbg; mkdir -p cge

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review report

**Change (one line):** `_ail_en_cmp` makes IntEnum/IntFlag ordering return `NotImplemented` for Decimal/Fraction; the runtime reflects such comparisons only for an IntEnum left operand and only when the program contains an enum, and Decimal/Fraction unwrap `_ail_intenum` operands.

**Review defects**
1. IntEnum/IntFlag vs Decimal/Fraction: fixed. `rev_gt.py`, `rev_strenum_dec.py`, and my `rv_eqdec.py`/`rv_customcmp.py` match CPython (including reflected, dunder, negative, 10**30, NaN, equality). StrEnum keeps the operator-specific TypeError.
2. Class-only C: fixed. `p5ni.py` and `rev_unrel.py` compile byte-identically to `/tmp/base` (3272540).

**Probes (both builds unless noted)** — `rev_gt`, `rev_strenum_dec`, `rev_order2`, `bytes_order`, `rv_eqdec`, `rv_customcmp`: match CPython. `rv_containers`: only pre-existing Decimal-vs-Fraction sorted/min mismatch. `p1`/`p8`: pre-existing text differences only (also `'<'` and `'object'` wording, not just module prefix; identical on base). `rv_decfr`: identical on base.

**Pre-existing:** `decimal.Decimal` vs `Decimal` type-name prefix; Decimal-vs-Fraction ordering in sorted/min; Fraction reflected error text; `C.B < Q()` on a custom `__gt__` object (same on base).

**Claims:** defect fixes verified; class-only C identity verified; manifest `--check` clean; `update_manifest.py` clean. The “p1/p8 only type-name” wording is imprecise (additional pre-existing text differences), but no regression. Worker’s test claim for files/corpus not re-run.

**Tests:** `test_ail_reintenum4`, `test_ail_dunders`, `test_ail_safetynet` — 3 modules, 0 failed, 274s, `-j 2`.

**Unverified:** instruction-count/speed impact; worker’s `test_ail_files`/`test_ail_corpus_findings3` rerun (not required here).

VERDICT: ACCEPT
[cost $0.0362, opencode tokens {"total": 1990376, "input": 98577, "output": 8344, "reasoning": 17983, "cache.write": 0, "cache.read": 1865472}]
    tool time: bash 26.2 min
        276s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1700 python3 -X utf8 -B ../tools/par_check.py -j 2 t
        184s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p8 p1; do echo "=== $f"; timeout 200 bash ~/tools/cmp.sh /tmp/r
        170s bash   cat > /tmp/rprobes/rv_decfr.py <<'EOF' from decimal import Decimal from fractions import Fraction print(sorted
        167s bash   cd /home/runner/work/ail-ci/ail-ci && for f in rev_gt rev_strenum_dec; do echo "=== $f"; timeout 300 bash ~/to
        109s bash   cd /home/runner/work/ail-ci/ail-ci && for f in rev_order2 bytes_order p8 p1; do echo "=== $f"; timeout 150 bas
         85s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/rv_customcmp.py <<'EOF' from enum import IntEnum, IntFlag, Enum, S
         85s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 400 bash ~/tools/cmp.sh /tmp/rprobes/rv_customcmp.py /tmp/base >
         84s bash   cat /tmp/rprobes/p8.py; echo ===BASE; cd /home/runner/work/ail-ci/ail-ci && timeout 250 bash ~/tools/cmp.sh /t

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T06:12:34Z
