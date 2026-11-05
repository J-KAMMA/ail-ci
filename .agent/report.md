# job job-fz227-11050703  started 2026-11-04T22:04:12Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Made the fix and committed it. Summary:

**Cause:** int/int `/` was lowered as `(double)a / (double)b` in four places — the IR and legacy typed emitters, the unified scalar specialisation, and the non-big arms of both boxed operator runtimes. Each operand was rounded before the single division, so once either exceeded 2^53 the result could be one ulp off. CPython's `long_true_divide` rounds the exact quotient once.

**Fix:** new runtime fragment `IDIVEXACT` with `ail__idiv_exact` (CPython's 55-bit quotient + sticky remainder, rounded once). Typed paths call `ail_fdiv_i`; the unified/boxed paths call `ail__idiv_exact`. Float operands, `//`, `%` and small ints are untouched. New IR op `idiv` is registered in `ir.py`, `verify.py`, `effects.py`, `emit_c.py`.

**Probes** (all via `bash ~/tools/cmp.sh`, g + d, and manual `AIL_IR=0/1`, plus `AIL_EXACT_INT=1`):
- `fz227.py` original reproducer: both builds same.
- `m1,m2,m10,m11,m12,m13.py` minimized forms: all same.
- `p_intdiv.py` (argument, list item, attribute, dict value, negatives, INT64 limits, `0/-3`, zero divisor caught): g/d same.
- `p_intdiv_small.py` (small/boundary 2^53, negative): g/d same, IR 0/1 same, exact-int IR 0/1 same.
- Signature: `DIFF|cpython='False 3746 2.9562089861714024e+16' ail='False 3746 2.9562089861714028e+16'` — now gone.

**Tests:** `test_ail_fz227` 3/3; `test_ail_safetynet test_ail_files test_ail_corpus_findings3` 25 passed, 1 skipped (ran on the final code; only docs/manifest changed after).

**Other differences seen:** none in these probes. The fuzz program still falls back to the general path due to the pre-existing alias refusal at `al18 = v10` (documented behavior, output matches CPython).

Committed as `2ad53b0` on `job-fz227-11050703`; manifest updated and `--check` clean.
[commandcode stop=end_turn turns=109 out_tokens=43791]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Here's my review.

## What the change really does

Adds `ail__idiv_exact` (CPython `long_true_divide`: 55-bit quotient + sticky remainder, rounded once) and routes int/int `/` through it in four emitters: the legacy typed emitter (`ail_fdiv_i`), the IR lowering (new `idiv` op → `ail_fdiv_i`), the unified scalar path (`ail__idiv_exact`), and the non-big arms of both boxed runtimes. `//`, `%`, and float `/` are untouched. That matches the report.

## Probes (all `bash ~/tools/cmp.sh <p> $PWD`, plus `AIL_IR=0/1`, `AIL_EXACT_INT=1`, `--static`)

- `pfull_fz227.py` (full program from the task): HEAD g+d same; BASE g+d show the exact reported DIFF (`...4024` vs `...4028`). IR/exact/unified-IR modes same. **Fix confirmed.**
- `p1_sweep.py` (450 pairs: 2^53±1, 2^54, 2^62, INT64 bounds, negatives, 300 random close-bit-length pairs, list items): HEAD g+d same; BASE 186 g and 93 d diff lines. Rounding/tie/sign handled.
- `p2b_flow.py` (argument, list item, dict value, attribute; incl. `0/-3` → `-0.0`, bools, zero-divisor caught): HEAD g+d same; BASE both differ. Fix reaches these paths.
- `p3b_aug.py` (`/=`): HEAD same; BASE g differs.
- `p6b_min.py`, `p6c_min2.py` (INT64_MIN / ±1, ±3, /2^63, /itself): same.
- `p7_sites.py` (f-string, comprehension, lambda, condition, tuple/dict value): same.
- `p10_effect.py` (unused `a / z`): still raises on both builds/IR — `idiv` correctly treated as raising.
- `p11_mutate.py` (list/bytearray slice-copy then mutate): same.
- `p8_big.py`, `p9_bigov.py` (exact-int bignums, OverflowError): same.
- `a_nodiv.py`: default-build C **byte-identical** to base; general build **not** (see defect 1).
- `test_ail_fz227 test_ail_safetynet` on HEAD: **2 modules, 0 failed**.
- Manifest `--check`: clean. Commit trailer present.

## Claims

| claim | verdict |
|---|---|
| cause = `(double)a/(double)b` in the four places; `ail__idiv_exact`/`ail_fdiv_i` | verified |
| float `/`, `//`, `%` untouched | verified |
| **small ints untouched** | **false** — every int/int now takes the exact path in typed/unified non-big builds |
| IR op registered in ir/verify/effects/emit_c | verified (also `lower.py`) |
| reproducer gone on both builds | verified |
| fuzz program falls back to general path (alias `al18 = v10`) | verified (compile note names line 113) |
| no other differences | incomplete: pre-existing dynamic int|float case (below) |
| tests 3/3 + 25 passed/1 skipped | fz227+safetynet verified; the other two modules not run per instructions |

## Defects

1. **Programs that do not use int division get a dead helper (C not unchanged).** `REQUIRES['FDIV']` and `REQUIRES['OBJ2']` pull in `IDIVEXACT` unconditionally, and `OBJ2` also inlines it, bypassing the codebase's `/*P:div<*/` PIECES gate.
   - Probe `/tmp/rprobes/f_only.py` (float-only `/`, default build): expected `program.c` identical to base; actual `+24` lines (`ail__idiv_exact`, `#include <math.h>`), 31 diff lines. Same for `/tmp/rprobes/a_nodiv.py` with `AIL_UNIFIED_FORCE=1`.
   - (`cruntime.emit(['TYPES','STDIO','OBJ2'])` even produces **two** definitions; no current caller does that, so latent.)
2. **`test_ail_fz227::FLOW_CASE` does not reproduce the finding.** Its values (`2^62/3`, `2^63-1/7`, dict/attr `2^62/3`) all give identical output with and without the fix — so the required argument/list-item/attribute/dict variants don't exercise the changed code.
   - Probe: the test's exact `FLOW_CASE` text as `/tmp/rprobes/flow_case.py`. Expected on base: the finding's DIFF; actual on base: `g same stdout`, `d same stdout`. (`DIRECT_CASE` does fail on base, so the module isn't useless.) Triggering values such as `6976454540695398849 / 3684474835157277` work (`p2b_flow.py`: base DIFF, HEAD same).
3. **Report's "small ints are untouched" is false, with a real common-case slowdown.** All int/int `/` now takes the exact path. 30M small-int divisions (`(i+7)/3`, identical output): base 0.04 s, HEAD 0.31 s (~8x). Not a large end-to-end regression (no `bench/apps` program divides ints; gdev's divisions are float/Fraction) and the approach is right, but the claim is wrong; the big-int build already shows the fix — a `±2^53` magnitude fast path.

## Pre-existing (not caused by this change)

- `p4b_dynamic.py` (int|float union collapsed to `double`): default build still prints `2579201891511368.0` where CPython prints `2579201891511367.5`; identical on base. HEAD's general build incidentally fixed it.
- `p6_min.py` `-INT64_MIN` → `OverflowError` (unary neg, not division).
- DIFFERENCES id `C?-job-fz227-1` does not follow the `C?-<branch>-N` form used by other rows (`C?-job-fz227-11050703-1`).

## Unverified

- The worker's own `/tmp/probes` files were not re-run (ran equivalents).
- `test_ail_files`, `test_ail_corpus_findings3` (not run per instructions).
- Instruction counts: `tools/icount.c` fails with `perf_event_open: Permission denied` here; wall clock used.
- `needs_libm()` omits `IDIVEXACT`/`ldexp`; a `--static` build still succeeded on this glibc (latent risk only).

VERDICT: FIX
1. `REQUIRES['FDIV']`/`REQUIRES['OBJ2']` include `IDIVEXACT` unconditionally (and `OBJ2` inlines it), so `/tmp/rprobes/f_only.py` and `a_nodiv.py` (general build) emit a dead `ail__idiv_exact`; expected C identical to base, actual +24 lines. Gate it with the `/*P:div<*/` PIECES mechanism / add it to `ctx.parts` only for int division.
2. `test_ail_fz227.py::FLOW_CASE` values do not reproduce the bug (`/tmp/rprobes/flow_case.py` on base: expected DIFF, actual `same stdout` both modes); use triggering values such as `6976454540695398849 / 3684474835157277`.
3. Report claim "small ints are untouched" is false and the common case is ~8x slower on a division-only loop (base 0.04 s vs HEAD 0.31 s per 30M divisions); add the `±2^53` fast path the big-int build already uses, or correct the claim.
[commandcode stop=end_turn turns=67 out_tokens=64332]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
## Report

Fixed all three review defects, plus a fourth division site the new tests exposed. Committed as `1d89d03`.

**Fixes**
1. **Dead helper**: `FDIV` no longer requires `IDIVEXACT`; a new `IFDIV` fragment holds `ail_fdiv_i` (requires `DIE`, `IDIVEXACT`). The boxed helper/arm is gated by a new `biggate` piece `idiv` (`ail_op_truediv`, `ail_op_idiv`, `ail__idiv_exact`) resolved via new `/*D<*/.../*D|*/.../*D>*/` blocks, computed for every build (not just big). `REQUIRES['OBJ2']` and the inline injection removed; the v1 `OBJ` runtime is gated the same way. **`f_only.py` (typed) and `a_nodiv.py` (general) C is now byte-identical to base** (`diff` empty); also checked `a_nodiv` typed, `p_flooronly` typed/general, `p_floatonly` typed.
2. **Test didn't reproduce**: `FLOW_CASE` now uses `6976454540695398849 / 3684474835157277` etc. (base: DIFF in both builds; HEAD: same) and adds `AUG_CASE` (`/=`), bools, and the ±2^53 boundary. This exposed the legacy numeric-value path behind `/=`, `a = a / b`, `a += b / c`, which always took its float formula; it now uses the int formula when neither operand is floating.
3. **Small-int slowdown**: `ail_fdiv_i`, the unified scalar path and the boxed non-big arms now use plain double division when both operands are within ±2^53 (conversions exact, one IEEE division correctly rounds), exact path otherwise. 20M-iteration loop: 0.02 s HEAD, 0.02 s base.

**Probes** (`bash ~/tools/cmp.sh`, both builds unless noted)
- `fz227.py` full program: g/d same. `p_intdiv.py`: same (base: both DIFF). `p_flow_new.py`: same (base: g+d DIFF). `p_aug2.py`: ir0/ir1/general same (base: g+d DIFF). `p_flooronly.py`, `p_floatonly.py`: same. `p_fastpath.py` (169 boundary pairs + 100 random in-range): same. `p_bigdiv.py` (`AIL_EXACT_INT=1`): same. `p1_sweep.py`: same. The finding's reported DIFF is gone on both builds.
- v1 boxed build called directly: no-division runtime has 0 `ail__idiv_exact`, int-division runtime has 2.

**Tests** (final code): `test_ail_fz227` 4/4; `test_ail_safetynet` 5/5; `test_ail_files` 18 (1 skip); `test_ail_corpus_findings3` 2/2. Manifest `--check` clean.

**Other differences (pre-existing, not touched)**: dynamic `int|float` union collapsed to `double` still prints `2579201891511368.0` vs CPython `2579201891511367.5`; `-INT64_MIN` raises `OverflowError` (unary neg, not division). Residual: a *general-build* float-only `/` still routes through `ail_op_truediv`, so its C keeps the exact-helper arm (result correct; base C differs). The contributor's earlier "small ints untouched" claim is now true semantically, via the ±2^53 fast path.
[commandcode stop=end_turn turns=131 out_tokens=93507]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review report — fz227 (commits `2ad53b0`, `1d89d03`)

**What the change really does.** int/int `/` is lowered to a new exact helper (`ail__idiv_exact`, CPython long_true_divide: 55-bit quotient + sticky, rounded once) in the IR emitter, the legacy typed emitter (including the numeric-value path behind `/=`), the unified scalar path and the boxed truediv runtimes; operands within ±2^53 keep plain double division. The helper/arm is gated by a new `biggate` piece `idiv`. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, general `g` + default `d`; base = `/tmp/base`):

| probe | HEAD | base |
|---|---|---|
| r1_fz.py full fuzzer program | g/d same | g/d DIFF (exact signature) |
| r2_exact.py 33 cases: ±2^53 boundary, INT64_MIN, negatives, arg/list/dict/attribute, `/=`, `+= b/c`, bools, mixed float | same | DIFF (2 sites) |
| r3_zero.py 0/±3, zero via var/arg/list/dict, `/=0`, int/0.0 | same | same |
| r4_float.py float `/`, `//`/`%` on large ints, mixed | same | same |
| r5_nofeature.py (no `/`) | same; **C identical** typed, general, forced v1 | — |
| r6_floatonly.py | same; typed C identical; forced-general C differs only by dead helper/arm | same output |
| r7_sweep.py 634 pairs (cross-product of 2^53±, INT64_MAX, 2^62, randoms) | same | DIFF |
| r8_big.py 1400 random pairs incl. 2^k±2 | same | — |
| r9_mut.py mutation after division, bytearray slice, INT64_MIN as divisor/dividend, dict | same | same |

Also same: `--exact-int` (default and forced-general), `AIL_IR=0`, forced v1 (`AIL_GENERAL=v1 AIL_UNIFIED_FORCE=1`).

**Tests:** `test_ail_fz227` (4 tests, 8.7 s) and `test_ail_safetynet` pass (`par_check -j 2`: 2 modules, 0 failed). Manifest `--check` rc=0. `test_ail_fz227`'s three division cases do DIFF on base in both builds — the test is meaningful.

**Speed:** `perf_event_open` is denied on this runner, so `tools/icount.c` cannot run; used wall time and C diffs. A 20M-iteration int/int division loop: 0.02 s HEAD, 0.02 s base (matches the report). gdev `g03_020` C identical; `g05_034`/`g12_022` C differs only by the helper + new arm, outputs identical to base.

**Claims:** gating (verified), FLOW_CASE reproduces on base (verified), fast path (verified), manifest (verified), test counts (verified). Gating by the literal `ail_obj_truediv`/`ail_op_truediv` name is safe: every `ast.Div` emission site maps to that name, and `operator.truediv` is rewritten to a `Div` BinOp.

**Residual (disclosed, not a defect):** a general-build float-only `/` still carries the helper and the unreachable int arm, so its C differs from base; output is identical.

**Pre-existing / unverified:** the report's other pre-existing differences (dynamic `int|float` union printing, `-INT64_MIN` OverflowError) were not re-tested on base; v1 helper-count 0/2 was not re-checked directly (behaviour was).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=42 out_tokens=42623]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T00:42:17Z
