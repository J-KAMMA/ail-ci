# job job-prog4-11020446  started 2026-11-01T19:48:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Report

- Profiled all 8 programs with CPython 3.12 `cProfile`; table and follow-ups are in `lab/progfix/prog4.md`.
- Fixed the hybrid body gate in `AIL_CURRENT/ail_cpython_hybrid.py`: division/modulo are allowed when `pymix` already proves the trap cannot reach a boxed handler, and slices are allowed only with a constant non-zero step. The analysis now also seeds annotated result kinds and `str`-slice kinds.
- Newly typed hot function: `is_prime` in `lab/census/programs/dev/t024.py` (now `accelerated: ["is_prime"]`; all 3 inputs match CPython). The other hot functions are void `main`, `t237`'s heterogeneous `list[float]`, `t434`'s dataclass/`Optional`, and `g15`'s recursion-limit control; these are recorded as big-feature follow-ups.
- Added `AIL_CURRENT/test_ail_prog4.py` (3 tests), registered via `tests.d/test_ail_prog4.txt`.
- Probes: `/tmp/probes/p4_divmod.py` and `/tmp/probes/p4_slice.py` match CPython on both `cmp.sh` builds and under `--cpython`; zero/variable slice steps stay on CPython. Hybrid builds of all 8 programs match CPython on every available input.
- `lab/compare`: 5 tasks build with byte-identical C to base; the other 5 refuse identically.
- Manifest `--check` passes. Final commit `4957411`; targeted tests all pass: `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (5 modules, 0 failed).
[cost $0.1182, opencode tokens {"total": 15171533, "input": 227551, "output": 30592, "reasoning": 35054, "cache.write": 0, "cache.read": 14878336}]
    tool time: bash 16.0 min, edit 0.0 min, write 0.0 min
        249s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog4 test_ail_cpython_hybrid t
        241s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/p4base /tmp/cidcur /tmp/cidbase && git worktree add -f /tmp/
        226s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && python3 tools/update_manifest.py --check && python
         63s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cid2cur /tmp/cid2base && mkdir -p /tmp/cid2cur /tmp/cid2base
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for t in tree_fold rail_transfer scar_life tally_lang chain_relax; do f=
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for f in lab/corpus/programs/deepseek-v4.1-flash-free/t237.py lab/census
         16s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/hyb && mkdir -p /tmp/hyb && for f in lab/corpus/programs/dee
         13s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/perfn.py <<'PY' import sys, ast, json, io, contextlib sys.pat

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `4957411 typed reach batch 4`

**What the change really does:** loosens the CPython-hybrid body gate so division/modulo and constant-step slices reach the typed clone, seeds annotated return kinds and a `str`-slice kind in the hybrid-only `pymix` analysis, and updates docs/tests. The general-path compiler and runtime are untouched.

**Probes (hybrid `build --cpython`, HEAD unless noted):**

| probe | result |
| --- | --- |
| `p1_div_zero.py` (mod by 0, uncaught, after prints) | accelerated `fdiv,mod,tdiv`; **stdout lost** |
| `p1b_float_zero.py` (float `/0.0`, uncaught) | accelerated `tdiv`; **stdout lost** |
| `p2_div_try.py` (mod under `try`) | not accelerated; stdout/exit same as CPython |
| `p3_div_edge.py` (`INT64_MIN//-1`, negatives) | accelerated; stdout same (falls back correctly) |
| `p4b_slice_mix.py` (float slice bound) | `ok` typed, `bad` not; same output/exit |
| `p5b_str_slice.py` (UTF-8 str slices) | `head,back` typed; byte-identical |
| `p6_str_index.py`, `p9_step.py`, `p8b_float_slice.py` | not accelerated; match CPython |
| no-feature `berth_sim` `--debug-dir` | `program.c` byte-identical to base |
| all 10 `lab/compare` tasks | 5 build (C identical), 5 refuse identically — verified |

Tests on HEAD: `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` passes.

**Claims:** verified — `is_prime` accelerated and all 3 inputs match; test registration; slice-step and `try` protection; compare-task C; manifest; tests. **False** — the implicit claim that pymix's rule makes accelerated division/modulo harmless: it only protects a boxed `try`, not an uncaught trap. The new tests exercise zero only under `try`, where the function is *not* accelerated, so they miss this path. **Unverified** — exact cProfile percentages and the four follow-up refusal messages.

**Pre-existing:** none material (stderr traceback paths differ on both builds).

### Defect

1. **Accelerated division/modulo by zero loses prior stdout.** `p1_div_zero.py`:
```python
def mod(x: int, y: int) -> int:
    return x % y
print('start')
print(mod(3, 2))
print(mod(3, 0))
```
Expected (CPython and base hybrid): stdout `start\n1\n`, exit 1. Actual (HEAD hybrid): stdout empty, exit 1, stderr `integer modulo by zero` — the typed clone calls `ail_die` → `_Exit`, bypassing Python's buffered stdout. Same for `p1b_float_zero.py` (`x / 0.0`). Base reports `accelerated: []` and matches CPython, so the change caused it. Gate division on a provably non-zero divisor, or make the clone raise/fall back instead of exiting.

VERDICT: FIX
1. Accelerated division/modulo can trap via `ail_die` and drop Python's buffered stdout (`p1_div_zero.py`, `p1b_float_zero.py`); base matches CPython, HEAD does not.
[cost $0.0352, opencode tokens {"total": 2387028, "input": 82681, "output": 7941, "reasoning": 18646, "cache.write": 0, "cache.read": 2277760}]
    tool time: bash 11.4 min
        303s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
        170s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_f
        147s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_prog4 test_ail_cpython_
         28s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbgcur /tmp/dbgbase && AIL_NO_CACHE=1 python3 AIL_CURRENT/ai
         16s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbgcur /tmp/dbgbase && AIL_NO_CACHE=1 python3 AIL_CURRENT/ai
          5s bash   cat > /tmp/rprobes/p5b_str_slice.py <<'PY' def head(s: str) -> str:     return s[:2]  def back(s: str) -> str:
          3s bash   cd /tmp/rprobes && date && (bash runhyb.sh p3_div_edge.py /home/runner/work/ail-ci/ail-ci > r3.txt 2>&1 & bash
          3s bash   cd /tmp/rprobes && date && (bash runhyb.sh p4_slice_bound.py /home/runner/work/ail-ci/ail-ci > r4.txt 2>&1 & b

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `de11848`.

- Accelerated int/bool clones now route zero-division/modulo traps through the existing overflow `setjmp` fallback; CPython raises the real `ZeroDivisionError` after flushing buffered stdout. Float/str clones keep a possibly-zero divisor in CPython; non-zero literal divisors remain eligible.
- Probes: 13/13 match CPython under hybrid (including `p1_div_zero.py`, `p1c_fdiv_zero.py`, `p3b_no_try.py`, `p6b_zero_paths.py`, `p6c_zero_attr.py`, `p7_types.py`); all match on both `cmp.sh` builds. `p1b_float_zero.py` now reports `accelerated: []` and matches.
- All ten `lab/compare` tasks: generated `program.c` byte-identical where built; refusals identical otherwise.
- Final-commit tests: `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` passes.
[cost $0.0531, opencode tokens {"total": 4663361, "input": 125771, "output": 14180, "reasoning": 20370, "cache.write": 0, "cache.read": 4503040}]
    tool time: bash 20.6 min, edit 0.0 min
        432s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_prog4 test_ail_cpython_
        403s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_file
        248s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/cmpc/run.sh <<'SH' #!/bin/bash set -u root=$1; tag=$2; task=$
         42s bash   cd /tmp/probes && for p in p1_div_zero.py p1b_float_zero.py p1c_fdiv_zero.py p1d_tdiv_int.py p2_div_try.py p3_
         41s bash   cd /tmp/probes && for p in p1_div_zero.py p1b_float_zero.py p1c_fdiv_zero.py p1d_tdiv_int.py p2_div_try.py p3_
         16s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_prog4 test_ail_cpython_
         13s bash   cd /tmp/probes && cat > p1c_fdiv_zero.py <<'PY' def fdiv(x: int, y: int) -> int:     return x // y print('star
         13s bash   cd /tmp/probes && cat > p3_div_edge.py <<'PY' def fdiv(x: int, y: int) -> int:     return x // y def mod(x: in

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** It relaxes the hybrid body gate (division/modulo, constant-step slices), seeds return annotations and a `str`-slice kind, and routes int/bool clone division traps through the existing int64-overflow `setjmp`; the general-build C is untouched.

**Probes (hybrid `build --cpython`, HEAD unless noted):**
- `p_div2.py` (int `%`,`//` literal; int/int `/` → float; float `%`,`//` literal): all accelerated, stdout/exit match.
- `p_div3.py` (variable/negative int divisors, INT64_MIN edges, bool/attr/list/dict routes): all accelerated, match.
- `p_zero_uncaught.py`, `p_boolzero.py`, `p_boolzero2.py` (uncaught `% 0`, `// False`, bool return): accelerated, stdout before trap preserved, exit 1 and traceback match.
- `p_slice.py`, `p_slice2.py` (empty/negative/far bounds, `[::-1]`, `[::-2]`, variable bounds, str/unicode, refused variable/zero steps): accelerated ones match.
- `p_neglit.py`, `p_mixed_bad.py` (float function with a **signed literal divisor**): fails (defect 1).
- `p_augdiv.py` / `p_augdiv_int.py` (aug-assignment): int path now fixed vs base; float path identical on base (pre-existing).
- C-identity: all 10 `lab/compare` tasks compiled HEAD vs `/tmp/base --debug-dir`; 7 `program.c` byte-identical, 3 refused identically on both.
- Tests: `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet` pass; `update_manifest.py --check` passes.

**Report claims:**
- int/bool zero-division → fallback and stdout flush: **verified**.
- float/str with possibly-zero divisor stays CPython: verified for BinOp; **false for `x /= y` aug-assign** (pre-existing hole, see below).
- "non-zero literal divisors remain eligible" incl. optional sign: **false** (defect 1).
- all ten `lab/compare` identical: **verified** (7 C-identical, 3 identical refusals).
- tests/manifest: first three modules and manifest verified; `test_ail_files` / `test_ail_corpus_findings3` not re-run (reviewer scope).

**Pre-existing (identical on `/tmp/base`, no block):** `def fdiv(x: float, y: float) -> float: x /= y; return x` with `fdiv(3.0, 0.0)` is accelerated and loses pre-trap stdout on **both** HEAD and base (`_unsafe_body` only scans `BinOp`, never `AugAssign`). Probe `p_augdiv.py`: CPython prints `start...`/`before-zero` then raises; both hybrids print nothing and stderr `division by zero`.

**Unverified:** instruction counts (`perf_event_open: Permission denied`), the worker's exact 13 probes, and `test_ail_files`/`test_ail_corpus_findings3`.

VERDICT: FIX
1. `AIL_CURRENT/ail_cpython_hybrid.py:80-88` `_provably_nonzero` rebinds `node = node.operand` and then evaluates `isinstance(node.op, ast.USub)`, raising `AttributeError: 'Constant' object has no attribute 'op'`. It is reached at line 111 exactly when the result is **not** int/bool and the divisor is a signed literal, and the exception aborts the whole hybrid analysis, so **every** function in the module loses acceleration (the program still runs correctly in CPython). Probe:
   ```python
   def add1(x: int) -> int: return x + 1
   def modp(x: int) -> int: return x % 7
   def head(s: str) -> str: return s[:2]
   def fdivneg(x: float) -> float: return x / -2.0
   print(add1(2), modp(20), head('hello'), fdivneg(7.0))
   ```
   Expected: `accelerated: ["add1","head","modp","fdivneg"]` (7.0/-2.0 cannot trap), stdout matches CPython.
   Actual: `accelerated: []`, build note `no extension: 'Constant' object has no attribute 'op'`; removing `fdivneg` restores `["add1","head","modp"]`. Same failure with `x % -2.0` / `x // -2.0`. Fix: keep the `UnaryOp` in a separate variable or test `step.op` before reassigning `node`.
[cost $0.0680, opencode tokens {"total": 5840351, "input": 142586, "output": 15167, "reasoning": 34214, "cache.write": 0, "cache.read": 5648384}]
    tool time: bash 15.6 min
        352s bash   cd /home/runner/work/ail-ci/ail-ci && date && for t in berth_sim echo_pack ledger_bin rail_transfer scar_life 
        262s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_prog4 test_ail_cpython_
        206s bash   cd /home/runner/work/ail-ci/ail-ci && date && for t in chain_relax tree_fold ticket_audit; do for w in new bas
         14s bash   cd /tmp/rprobes && date && bash hcmp.sh p_slice.py /home/runner/work/ail-ci/ail-ci 2>&1 | head -100
         14s bash   cd /tmp/rprobes && cat > p_slice2.py <<'PY' def vstep(xs: list[int], k: int) -> int:     s = 0     for v in xs
         13s bash   cd /tmp/rprobes && date && for p in p_zero_uncaught p_zero_after p_zero_try p_bad_slice; do echo "=== $p"; bas
          9s bash   cd /tmp/rprobes && cat > p_mixed_ok.py <<'PY' def add1(x: int) -> int:     return x + 1  def modp(x: int) -> i
          7s bash   cd /tmp/rprobes && cat > p_augdiv.py <<'PY' def fdiv(x: float, y: float) -> float:     x /= y     return x  de

FINAL VERDICT: FIX  2026-11-01T21:29:04Z
