# job job-fdgpu2-11070727  started 2026-11-06T22:28:09Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed. The reviewer's Defect 1 is resolved, and the fix keeps the loop on the device/kernel path.

## What was wrong
`gpu.prepare` lowered `math.sqrt(x)` to an `IfExp` whose negative arm was `1.0 / 0.0`, so `sqrt(-1)` raised `ZeroDivisionError` where CPython raises `ValueError("math domain error")`, breaking a caller's `except ValueError`. Replacing that arm with a call to the surface's `_ail_math_sqrt` didn't work either: the typed path refuses that name by name, so the whole program fell back to the general path (kernel gone, `ignored` note).

## The fix
`math.sqrt(x)` in a marked statement now lowers to `_ail_gpu_sqrt(float(x))`, a plain typed helper that `gpu.prepare` injects: zero returned unchanged, NaN → NaN, positives via `ail_fsqrt` (correctly rounded), negatives raise `ValueError("math domain error")`. The kernel builder intercepts that call and emits its sqrt op (`GK_FDIV` → CPU replay). A hand-written `** 0.5` is still refused. Added `Programs.test_sqrt_of_a_negative_raises_cpython_valueerror`; updated GPU.md 6.3.

## Probes (`gcmp.sh` = `--gpu`, `AIL_GPU=0/emu/force` vs CPython; `cmp.sh` = default/general)
All matched stdout and exit status:
- `p24_catch3` — `caught ValueError` (was `caught ZeroDivisionError`) on all four paths; kernel note now says `kernel k0: SPIR-V ... 1282 words`, trace `gpu: k0 replay flags=0x40 (float-division)`.
- `p3_uncaught` — exit 1, stderr `ValueError: math domain error` on all paths.
- `p25_mixed`, `p26_nan_zero`, `p21_int_sqrt`, `p13_comp` (marked comprehension), `p28_expr`, `p29_intvar` (int list), `p30_dict` (value from a dict), `p27_div`, `p8_divzero`.
- `p13/p25/p29/p24/p3` also verified in the default and general builds (`cmp.sh`).
- A marked loop whose function has `try/except` is still refused by name, exit 3.

## Tests
- `test_ail_gpu_g5.py`: 9 OK (2 skipped: no Vulkan, no `spirv-val`; the four Program cases now actually launch a kernel — no longer skipped).
- `test_ail_gpu_g1.py` 42 OK, `test_ail_gpu_g2.py` 35 OK (12 skipped), `test_ail_gpu_smoke.py` 6 OK (2 skipped).
- `test_ail_safetynet`: 1 failure, `S4_generators_gc` — the same pre-existing failure the review confirmed on base.
- `test_ail_files` OK; `test_ail_corpus_findings3` OK.
- `tools/update_manifest.py` run; `--check` = 0.

Committed on `job-fdgpu2-11070727` as `1b34204` (no push, per the runner instruction). Working tree clean apart from the pre-existing untracked `.agent/pipeline.md`. Device bits/SPIR-V validation remain unverified here (no Vulkan device or `spirv-val`); the kernel/SPIR-V emitter code itself is unchanged.
[commandcode stop=end_turn turns=121 out_tokens=64835]

## review 0
[model commandcode/deepseek-v4.1-flash]
I've got enough. Let me summarize what I probed and verified.

## Review — fdgpu2 (fix of the G5 `math.sqrt` ValueError defect)

**What the diff really does:** replaces the `1.0/0.0` negative arm with a `math.sqrt` → `_ail_gpu_sqrt(float(x))` rewrite, injects a typed top-level helper `_ail_gpu_sqrt` (zero unchanged, negative → `ValueError("math domain error")`, else `x ** 0.5`), and makes the kernel builder lower *any call named* `_ail_gpu_sqrt` to its sqrt op (the old `SQRT_REWRITE` AST tag is deleted). Docs + one new g5 test.

**Probes** (HEAD = this commit; base = `/tmp/base` at `work`):

| probe | result |
|---|---|
| q1 catch negative in caller (`except ValueError/ZeroDivisionError`) | `caught ValueError`, all of CPython/`AIL_GPU=0`/`emu`/`force`; kernel k0 built, replay `flags=0x40` — review defect fixed |
| q2 uncaught `-2.5` | exit 1, `ValueError: math domain error`, all paths |
| q3 `+0,-0,2,1e300,5e-324,4` | identical incl. `-0.0` sign |
| q4/q7 sqrt of int list incl. `2**60+1` | identical |
| q5/q12/q13 NaN, +inf, -inf, negative int | identical (negatives → `ValueError`) |
| q17 temp, q18 module-level loop, q19 two sqrts, q21 empty list | identical |
| q8 sqrt in and out of the marked loop; q14 `from math import sqrt` | identical stdout (fallback where refused) |
| q9 dict value, q10 attribute, q11 hand-written `** 0.5` | named compile-time refusal, exit 3 |
| q6 non-sqrt marked `/` loop | `--debug-dir` C byte-identical to base; q1 default-build C also identical |
| **q25 user fn `_ail_gpu_sqrt` in a marked loop, no `math.sqrt`** | **base: `[9.0]` all paths; HEAD: `[3.0]` under `emu`/`force` while `AIL_GPU=0` gives `[9.0]`** |
| **q16 user fn `_ail_gpu_sqrt` + `math.sqrt` in loop** | **base: `[2.0]` all paths; HEAD: `AIL_GPU=0` gives `[8.0]`, `emu`/`force` give `[2.0]`** |
| q23/q24 local var / parameter with that name | fine (calls resolve statically) |

**Defect (caused by this change, absent on base).** The kernel builder matches the helper by name alone, and `prepare` deliberately skips injection when the user already defines that name (`not any(FunctionDef named GPU_SQRT)`), so a user function called `_ail_gpu_sqrt` is silently turned into sqrt on the device/emulation path while the CPU loop runs the user's function:
```python
def _ail_gpu_sqrt(x: float) -> float:
    return x * 2.0

def g(a: list[float]) -> list[float]:
    r = [0.0] * len(a)
    # ail: gpu
    for i in range(len(a)):
        r[i] = _ail_gpu_sqrt(a[i]) + 1.0
    return r

def main():
    print(g([4.0]))
main()
```
CPython/base: `[9.0]`; HEAD `--gpu` `AIL_GPU=emu`/`force`: `[3.0]`, `AIL_GPU=0`: `[9.0]`. The `math.sqrt` variant (q16) is wrong in the other direction (`[8.0]` vs `[2.0]`). The established behaviour for a colliding `_ail_math_sqrt` is a named "duplicate AIL name" refusal; this change has neither a refusal nor a tag, so it violates "a `--gpu` build prints exactly what `AIL_GPU=0` prints" for a program that need not use the feature at all. Fix: tag the rewritten call node (the old `SQRT_REWRITE` mechanism) or refuse a user definition of `_ail_gpu_sqrt` by name.

**Tests:** `test_ail_gpu_g5` 9 OK, 2 skipped (no Vulkan, no `spirv-val`), including the new `test_sqrt_of_a_negative_raises_cpython_valueerror`; `test_ail_safetynet` **5/5 OK** (the report's "1 failure `S4_generators_gc`" did not reproduce). `tools/update_manifest.py --check` = 0.

**Report claims:** defect-1 fix — verified; `1282 words`/`flags=0x40` — verified; `** 0.5` still refused — verified; 9 OK/2 skipped — verified; manifest 0 — verified; "1 safetynet failure pre-existing" — false here (passes); device bits/SPIR-V validation — unverified (no Vulkan/spirv-val). Diff scope is only the allowed files.

**Pre-existing:** none observed (q25/q16 match on base).

**Speed:** unaffected — non-GPU generated C is byte-identical; only `--gpu` builds change, no hot code. Not measured.

**Unverified:** SPIR-V validity, device bits, and g1/g2/smoke modules (not edited).

VERDICT: FIX
1. The kernel builder lowers *any* call named `_ail_gpu_sqrt` (and `prepare` skips injection when the user defines that name), so a user top-level function of that name is silently compiled as sqrt on `AIL_GPU=emu`/`force` while `AIL_GPU=0` runs the user's function. Probe `/tmp/rprobes/q25_userfn.py` (above): expected `[9.0]` (CPython and base, all paths), actual `[3.0]` with `AIL_GPU=emu`/`force`; variant `/tmp/rprobes/q16_userhelper.py`: expected `[2.0]`, actual `[8.0]` with `AIL_GPU=0`. Expected: a named refusal for the collision (as `_ail_math_sqrt` gets) or a node tag so only the rewritten call is lowered.
[commandcode stop=end_turn turns=41 out_tokens=30355]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed (`bf2f951`).

**Defect fixed:** the builder lowered *any* call named `_ail_gpu_sqrt`, and `prepare` skipped injection when the user defined that name. Now the rewrite tags the call node (`GPU_SQRT_CALL`) so only rewritten calls become sqrt ops, and the injected helper gets a name no function/local/param/import already uses (`_ail_gpu_sqrt_1`, …), so it can't be shadowed either.

**Probes** (`gcmp.sh`, CPython vs `AIL_GPU=0/emu/force`):
- q25/q16 (user `_ail_gpu_sqrt`, with and without `math.sqrt`): now `[9.0]` / `[2.0]` on all paths — both were wrong before.
- q1–q8, q12–q19, q21, q23, q24, plus my c1 (comprehension), c3 (local shadow), c4 (nested def shadow): all match.
- q9/q10/q11/q20: named compile-time refusals (exit 3), unchanged.

**Tests on HEAD:** `test_ail_gpu_g5` 10 tests OK (2 skips: no Vulkan/`spirv-val`), `g1`/`g2`/`smoke` OK, `test_ail_files` OK, `test_ail_corpus_findings3` OK. `update_manifest.py --check` = 0.

`test_ail_safetynet` passes 5/5 without the memory cap; under `ulimit -v 1500000` the pre-existing `S4_generators_gc` fails (the test contains no GPU marker, and the first review confirmed base fails identically).
[commandcode stop=end_turn turns=36 out_tokens=22650]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — fdgpu2 fix (sub-step 2)

**What the diff really does:** replaces the `(float(x) if … else 1.0/0.0 if … else x**0.5)` rewrite with a typed helper function that `prepare()` injects at module top and `_SqrtRewrite` calls (`ValueError("math domain error")` for negatives); tags the generated call node (`GPU_SQRT_CALL`) so the builder lowers only rewritten calls, and picks a helper name no user name binds (`_ail_gpu_sqrt_1`, …). The old `SQRT_REWRITE` tag path is deleted, so a hand-written `** 0.5` is refused exactly as before. Plus GPU.md, two tests, manifest. Matches the report.

**Probes** (`/tmp/rprobes`, `gcmp.sh` = `--gpu` × `AIL_GPU=0/emu/force`; `cmp.sh` = general+default):

| probe | result |
|---|---|
| r1 negative sqrt caught/uncaught, `-0.0` sign, NaN, inf, subnormal, 1e300 | `VE math domain error`; base printed `ZDE float division by zero`; all modes match CPython |
| r2 int list 2⁵³±1, negative int, bools | matches |
| r4 docstring + `from __future__` + sqrt inside/outside loop (general-path fallback) | matches |
| r6 module-level comprehension, negative caught | matches |
| r7 empty list, partial output state, caught ValueError | matches |
| r10 int64 max through the loop, conditional body | matches |
| r12 module-level var `_ail_gpu_sqrt` + two sqrt calls per item | matches (fresh name, both builds) |
| r5 marked loop without sqrt | generated `program.c` byte-identical to base |
| r3, r8, r9, r11 local/param/nested-def collisions, attribute/dict argument, output aliasing | **named refusals, byte-identical on base** → pre-existing |
| r7 with `-1e309` | C error `inf` undeclared — **identical on base** → pre-existing literal bug |

**Claims:** old-bug description verified from `1b34204`; ValueError fix verified (r1); collision handling verified (g5 `USER_HELPER*`, r12); "10 tests, 2 skips" verified; `g5`, `g1`, `g2`, `smoke`, `g1`+`smoke`, `test_ail_files`, `test_ail_corpus_findings3` all ok; `test_ail_safetynet` ok; `update_manifest.py --check` = 0. "0 mismatches on lavapipe" **unverified** (no Vulkan/spirv-val).

**Pre-existing:** `-1e309` → `inf` undeclared in C (base identical); safetynet `S4_generators_gc` under `ulimit -v` (prior review confirmed base identical).

**Speed:** non-feature C byte-identical; compile-time-only change, no hot path — not applicable.

**Unverified:** device bits, SPIR-V validity, lavapipe numbers.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=28 out_tokens=24766]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T00:39:09Z
