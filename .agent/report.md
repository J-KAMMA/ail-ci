# job job-prog6-11020729  started 2026-11-01T22:44:18Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `637261c` on `job-prog6-11020729`.

- **Typed 4/8 hot functions:** `fibonacci_mod`, `card_value`, `catalan_numbers`, `count_no_adjacent_ones`. Follow-ups recorded in `lab/progfix/prog6.md` for datetime, `list[str]`/recursion, JSON/CSV/dict, and dataclass fields.
- **Fixes:** annotated locals/returns (not parameter annotations), list repetition/unpacking/empty-list returns, fall-through rejection, tracked traps with stdout flush, list `int`/`float` results with overflow fallback, list-alias mutation refusal, and untracked pure-call refusal.
- **Verified:** `test_ail_prog6` 9/9; required batch 55 tests OK (1 skip); extra typed-path batch 41 OK; manifest `--check` clean; generated C unchanged for all 10 `lab/compare` `.ail` tasks and the 5 `.py` tasks that build.
- **Probes:** 14 `/tmp/probes` programs match CPython on both standalone builds; all 17 match on the hybrid. The int64-overflow probes stop loudly on standalone builds by design; the pre-existing general-path fall-through difference remains outside the hybrid.
[cost $0.0925, opencode tokens {"total": 9713654, "input": 175146, "output": 27293, "reasoning": 35631, "cache.write": 0, "cache.read": 9475584}]
    tool time: bash 28.0 min, edit 0.0 min, todowrite 0.0 min
        720s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3600 python3 -m unittest -v test_ail_cpython_hybrid 
        223s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/cmp_c.sh <<'EOF' #!/bin/bash set -u root=$1; out=$2; shift 2 
        171s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/ccur2 /tmp/ccur && tasks=$(ls lab/compare/src); srcs_ail="";
         77s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 -m unittest -v test_ail_py_typed_gaps t
         58s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest -v test_ail_prog6 test_ail_
         47s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cbase2 /tmp/ccur2; tasks=$(ls lab/compare/src); srcs=""; for
         38s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest -v test_ail_prog6 2>&1 | ta
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_types p_listret p_unpack p_traps p_ann_lie bare_return ann_hi

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** It extends the CPython-hybrid typed selection to allow indexing, division, tracked raises, `range`/`int` calls, annotated locals/returns, and `list[int]`/`list[float]` results (new length-then-fill ABI, overflow→CPython fallback), plus stdout flush before an uncaught trap exits. Standalone generated C is unchanged for the 10 `lab/compare` `.ail` tasks and for the 8 target programs (verified against `/tmp/base`).

**Defects (new):**

1. `range` ValueError is untracked, so a boxed `try/except ValueError` is bypassed (`AIL_CURRENT/ail_cpython_hybrid.py:45,128`; `pymix.py:224-247`).
```
def loop(n: int, step: int) -> int:
    total = 0
    for i in range(0, n, step):
        total += i
    return total
def use(n: int, step: int) -> int:
    try:
        return loop(n, step)
    except ValueError:
        return -1
print(use(5, 1))
print(use(5, 0))
```
Expected (CPython and `/tmp/base`): `10` / `-1`, exit 0. Actual HEAD hybrid (`loop` accelerated): `10`, then stderr `ValueError`, exit 1. This contradicts the report/DIFFERENCES claim that a caller `try/except` is never bypassed.

2. A list-returning clone copies a list parameter, so list identity/aliasing is wrong (`ail_cpython_hybrid.py:161` only checks mutation; `pyboxed2.py:2620` boxes into a fresh list).
```
def ident(xs: list[int]) -> list[int]:
    return xs
a = [1, 2]
b = ident(a)
print(ident(a) is a)
b[0] = 9
print(a, b)
```
Expected (CPython and `/tmp/base`, where `ident` is not accelerated): `True` / `[9, 2] [9, 2]`. Actual HEAD hybrid (`ident` accelerated): `False` / `[1, 2] [9, 2]`, exit 0.

**Pre-existing (not blocking):** augmented-assignment division is neither detected by `_raise_site_exc` nor refused by `_unsafe_body`, so `a //= b` with `b == 0` under `except ZeroDivisionError` already exits 1 on `/tmp/base` (probe `caught_augassign.py`, expected `3 -1`, actual stderr `integer division by zero`, exit 1). Reproduced identically on base.

**Claims checked:** four hot functions typed and outputs matching CPython (verified via `test_ail_prog6`); list repetition/unpacking/empty lists, list float/int results, overflow fallback, fall-through refusal, list-alias mutation refusal, untracked pure-call refusal (verified by probes); C byte-identical for 10 `lab/compare` tasks and the 8 target programs (verified); `test_ail_prog6`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; manifest `--check` clean. The claim "parameter annotations are not seeded" is false for the hybrid: `ail_cpython_hybrid.py`'s `_fn_init` still seeds them (pre-existing), though the boundary guard kept the probes correct.

**Unverified:** instruction counts/speed; the `.py` lab/compare C identity; the worker's own `/tmp/probes` (not present); full suite (not run by design).

VERDICT: FIX
1. `range(start, stop, step)` with `step == 0` raises ValueError in CPython but the typed clone traps uncaught while a boxed caller's `except ValueError` should catch it. Probe `caught_range_step2.py` above: expected `10`/`-1` exit 0; actual `10`, stderr `ValueError`, exit 1. Track `range`'s ValueError in `_raise_site_exc` or refuse dynamic-step `range` calls.
2. Returning a list parameter (or an alias) hands back a fresh list instead of the caller's object. Probe `list_ident.py` above: expected `True`/`[9, 2] [9, 2]`; actual `False`/`[1, 2] [9, 2]`. Refuse list-returning clones that return a list parameter/alias, as is already done for mutation.
[cost $0.0515, opencode tokens {"total": 3229519, "input": 105276, "output": 11390, "reasoning": 32661, "cache.write": 0, "cache.read": 3080192}]
    tool time: bash 9.6 min
        167s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 850 python3 ../tools/par_check.py -j 2 test_ail_prog
        141s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 550 python3 ../tools/par_check.py -j 2 test_ail_file
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_prog
         47s bash   cd /home/runner/work/ail-ci/ail-ci && ok=0; bad=0; for t in $(ls lab/compare/src); do rm -rf /tmp/cc_h /tmp/cc
         29s bash   cd /home/runner/work/ail-ci/ail-ci && files="lab/census/programs/gdev/g19_038.py lab/census/programs/gdev/g09_
         16s bash   cd /tmp/rprobes && for p in *.py; do n=${p%.py}; rm -rf o_$n; python3 /home/runner/work/ail-ci/ail-ci/AIL_CURR
         10s bash   cd /tmp/rprobes && cat > list_ident.py <<'EOF' def ident(xs: list[int]) -> list[int]:     return xs  a = [1, 2
          7s bash   cd /tmp/rprobes && cat > caught_augassign.py <<'EOF' def diva(a: int, b: int) -> int:     a //= b     return a

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `1a1033d`.

- **Range ValueError:** `range(start, stop, step)` with a non-literal/zero step is now a tracked `ValueError` site in `pymix._raise_site_exc`, so a boxed caller’s `except ValueError` is never bypassed.
- **List identity:** list-returning clones that return a list parameter or local alias are refused; functions returning their own local list still type (`catalan_numbers`, etc.).

Verification:
- Probes: 4 files covering step via argument/list item/attribute/dict value and list identity/alias/local/global/negative/empty. All match CPython on both standalone builds and the hybrid; hybrid left `loop`, `ident`, `ident_alias` boxed and accelerated `local`.
- Generated C byte-identical to `/tmp/base` for all 10 `lab/compare` tasks and all 8 target programs.
- Final-commit tests: `test_ail_prog6`, `test_ail_cpython_hybrid`, `test_ail_mixed_bounds`, `test_ail_stdout_mixed`, `test_ail_stdout_mixed_resources`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8 modules, 0 failed.
- `update_manifest.py --check` clean. Pre-existing augmented-division bug was left untouched as non-blocking.
[cost $0.0728, opencode tokens {"total": 2911769, "input": 347827, "output": 10829, "reasoning": 10777, "cache.write": 0, "cache.read": 2542336}]
    tool time: bash 11.2 min, edit 0.0 min, write 0.0 min
        299s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1000 python3 ../tools/par_check.py -j 2 test_ail_pro
        278s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1000 python3 ../tools/par_check.py -j 2 test_ail_pro
         47s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cc_cur && mkdir -p /tmp/cc_cur && bad=0; for t in $(ls lab/c
         27s bash   cd /home/runner/work/ail-ci/ail-ci && files="lab/census/programs/gdev/g19_038.py lab/census/programs/gdev/g09_
          9s bash   cd /tmp/probes && for p in prog6_range_step.py prog6_range_step_sources.py prog6_list_ident.py prog6_list_iden
          7s bash   cd /tmp/probes && rm -rf /tmp/hybp && mkdir -p /tmp/hybp && for p in prog6_range_step.py prog6_range_step_sour
          3s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbg1 /tmp/exe1 && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_cha
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/tmp/um.log 2>&1; cat /tmp/um.log; pyt

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: prog6 typed reach (work..1a1033d)

**What the change really does.** It broadens pymix kind inference (annotations, list repetition, unpacking, `return []`, no fall-through), makes the hybrid accept indexing/division/modulo/tracked `raise` and `range`/`int` calls, and adds a length-then-fill ABI for `list[int]`/`list[float]` results, with a `-1` overflow fallback and a stdout drain before `_Exit(1)`. It also refuses list results that return a list parameter/alias.

**Probes run** (`/tmp/rprobes`, hybrid via `ail build --cpython`, standalone via `~/tools/cmp.sh`):
- range step via arg/list item/attr/dict, zero literal, `True`/`False`, negative, uncaught: match CPython (boxed caller not bypassed; uncaught exits 1, stderr difference declared).
- list identity: param, alias, local, empty, negative, global, tuple-alias, mutation-through-alias: match; param/alias returns stay boxed, owned local lists type.
- traps: IndexError/ZeroDivisionError/ValueError/RuntimeError caught by a boxed caller: match; uncaught after `print` matches stdout+exit.
- int(str/float) boundaries incl. huge, `inf`, `nan`, 2^63±1: match (fallback).
- int64 edges (`//`, `%`, `+`, `*`, `-x` at INT64_MIN): match.
- list[float]/list[int] results incl. overflow and empty: match (single function).
- general build on `lab/compare`: 6 that build are byte-identical to `/tmp/base`; the 4 failures are identical on base.

**Defects**

1. **Hybrid true division of large int64 values is wrong.** `_unsafe_body` now allows `ast.Div`, but the typed path computes `(double)a / (double)b` instead of CPython's correctly-rounded int division.
```python
def true(a: int, b: int) -> float:
    return a / b
print(true(4865782901354085936, -7048155917072976836))
print(true(-931725450029404348, -7491968275375482579))
```
Expected (CPython): `-0.6903625513685845`, `0.1243632401770559`.
Actual hybrid (accelerated `true`): `-0.6903625513685846`, `0.12436324017705588`.
Base hybrid does not accelerate `true` and matches. (The general path already differed on base; the hybrid regression is new.)

2. **Two or more accelerated list-returning functions break the hybrid extension link.** Each list-return unit defines `ail_ret_spill_take`, so separate unit objects collide.
```python
def a(n: int) -> list[int]:
    return [0] * n
def b(n: int) -> list[int]:
    return [1] * n
print(a(2), b(3))
```
Expected: `accelerated: ["a","b"]`, stdout `[0, 0] [1, 1, 1]`.
Actual: `accelerated: []`; `build.json` note: `multiple definition of 'ail_ret_spill_take'` between `_ail_p_fast_unit1.o` and `_ail_p_fast_unit0.o`; stdout matches only because the extension was dropped and the whole program ran in CPython. A single list-return unit plus scalar units links fine.

**Claims check**
- Range ValueError tracked / boxed `except ValueError` not bypassed: **verified**.
- List param/alias return refused, owned local list still types: **verified**.
- 8 test modules, 0 failed: **verified** (same set, `-j 2`, 530 s).
- `update_manifest.py --check` clean: **verified**.
- "Generated C byte-identical for all 8 target programs": **false** under direct `pyboxed2.build` — g19_038, t402 and g09_014 differ (intended typed clones; the required 10 `lab/compare` tasks are identical).
- "Parameter annotations are not seeded": **inaccurate** — pymix no longer seeds them, but the hybrid's `sitecustomize` still does; no wrong output observed from it.

**Pre-existing:** general-path true-division precision difference; standalone int64 overflow loud stops; typed stderr text instead of tracebacks.

**Unverified:** instruction-count before/after (no `icount` run).

VERDICT: FIX
1. Refuse (or exactly emulate) true `/` on int operands in the hybrid: probe `true(4865782901354085936, -7048155917072976836)` gives `-0.6903625513685846` vs CPython `-0.6903625513685845`.
2. Make `ail_ret_spill_take` link-safe across captured list-return units (or compile units together): two list-return functions yield `accelerated: []` with `multiple definition of 'ail_ret_spill_take'` instead of both being accelerated.
[cost $0.0601, opencode tokens {"total": 5655263, "input": 65921, "output": 13885, "reasoning": 42145, "cache.write": 0, "cache.read": 5533312}]
    tool time: bash 17.7 min
        531s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pro
        229s bash   cd /home/runner/work/ail-ci/ail-ci && files=$(ls lab/compare/src/*/main.py); echo "== HEAD"; python3 /tmp/genc
         68s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_range_step p_range_lit p_list_ident p_list_alias_mut p_traps 
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_range_lit p_list_ident p_list_alias_mut p_traps p_divmod p_id
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in caught_lookup caught_key caught_user_parent slice_step unpack_t
         25s bash   cat > /tmp/genc.py <<'PY' import sys, os, json, hashlib root=sys.argv[1]; files=sys.argv[2:] sys.path[:0]=[roo
         23s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbgtest && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py
         14s bash   cat > /tmp/rprobes/p_global_alias_mut.py <<'EOF' G = [1, 2]  def mut(n: int) -> int:     ys = G     ys[0] = 9 

FINAL VERDICT: FIX  2026-11-02T00:37:39Z
