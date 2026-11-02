# job job-prog21-11021237  started 2026-11-02T03:37:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed as `af553b6` on `job-prog21-11021237` (not pushed).

- Profiled all 8 programs; hot-function shares and first refusals are in `lab/progfix/prog21.md`.
- 6/8 compile as whole typed modules. `g25_016` remains blocked by the enum member table; `t419` by Decimal printing.
- Hybrid fix: `abs` of numeric arguments, `str(<number>)` and `int(<int/bool>)` are now safe calls. `g22_022.shift_and_add_multiply` is newly accelerated; `abs(INT64_MIN)` falls back to CPython, never wraps.
- Remaining follow-ups: `g25_016` enum module table, `t419` Decimal, `t139.fmt` `int(float)`, `g21_038.encode_rounded_floats` `json.dumps`/`round`.
- All 8 hybrid builds match CPython stdout/exit on supplied inputs. Probes `/tmp/probes/p21_*` match on both builds; `p21_abs_bound.py` matches under the hybrid.
- Generated C for all 10 `lab/compare` tasks is byte-identical (10/10 SHA-256).
- Tests pass: `test_ail_prog21` 6, `test_ail_cpython_hybrid` 7, `test_ail_prog2` 9, `test_ail_safetynet` 5, `test_ail_files` 18 (1 skipped), `test_ail_corpus_findings3` 2.
[cost $0.1984, opencode tokens {"total": 29704914, "input": 329086, "output": 45696, "reasoning": 56276, "cache.write": 0, "cache.read": 29273856}]
    tool time: bash 30.0 min
        606s bash   cd /home/runner/work/ail-ci/ail-ci && for t in test_ail_safetynet test_ail_files test_ail_corpus_findings3; do
        511s bash   cd /home/runner/work/ail-ci/ail-ci && for t in test_ail_safetynet test_ail_files test_ail_corpus_findings3; do
         71s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/base21 && mkdir /tmp/base21 && git archive HEAD | tar -x -C 
         49s bash   cd /home/runner/work/ail-ci/ail-ci && ROOT=$PWD && cat > /tmp/hyb21/jobs6.txt <<EOF g22_014|$ROOT/lab/census/p
         45s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/build21/jobs2.txt <<'EOF' lab/census/programs/gdev/g22_014.py
         42s bash   cd /home/runner/work/ail-ci/ail-ci && ROOT=$PWD && cat > /tmp/hyb21/jobs5.txt <<EOF t078|$ROOT/lab/census/prog
         38s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/hyb21/one.sh <<'SH' #!/bin/bash k=$1; src=$2; shift 2 d=/tmp/
         37s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 AIL_SERVER=0 timeout 1800 python3 -B AIL_CURRENT/test_ail

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review — prog21 (af553b6)

**What the change really does.** Only `AIL_CURRENT/ail_cpython_hybrid.py` changes behaviour: `_safe_call` now accepts `abs(<float/int>)`, `str(<number/str>)`, `int(<int/bool>)` in hybrid clones, and `_unsafe_body` learns the result kind and numeric parameter kinds. Everything else is tests/docs/manifest.

**Probes** (hybrid built with `build --cpython`, compared to CPython; defect also run on `/tmp/base`):
- `p_floatstr.py`, `p_floatfuzz2.py` (537 finite/inf/nan/denormal floats), `p_bigstr.py`: `str(int/float)` all match.
- `p_absfuzz.py` (304 floats), `p_abs_float.py`: float `abs` matches.
- `p_abs_simple.py`, `p_abs_int.py`, `p_shift.py`, `p_shift_over*`: int `abs`, incl. `INT64_MIN`, falls back and matches (`mag` accelerated).
- `p_abs_bool.py`, `p_ia_simple.py`, `p_ib_simple.py`, `p_neg_int.py`, `p_boolstr_simple.py`: match.
- `p_str_neg_min.py`: **fails** (below); base hybrid refuses `f` and matches.
- `p_empty.py`: `str(-x)` float matches; `int()`/`str()` no-arg not selected.
- `bash ~/tools/cmp.sh /tmp/rprobes/p_str_neg_min.py $PWD`: general/default typed builds trap; identical on base (pre-existing for those builds).

**Tests:** `test_ail_prog21` 7/7, `test_ail_safetynet` 5/5 pass. `update_manifest.py --check` clean. `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_prog2`, `test_ail_cpython_hybrid` not re-run.

**Claims:** profile table and 6/8 whole-typed verified; g25 enum and t419 Decimal messages verified byte-for-byte; `g22_022.shift_and_add_multiply` newly accelerated verified; `abs(INT64_MIN)` fallback verified; 10 compare C files not re-hashed but no codegen file changed, so unchanged. The test-file docstring (`test_ail_prog21.py:26-30`) falsely says pymix now proves `json.dumps` returns str — `encode_rounded_floats` is still not a mix unit (same as base); the worker report itself correctly says `unresolved-return`. Non-blocking.

**Pre-existing:** default/general typed builds exit 1 on `str(-x)` with `INT64_MIN` (same on base).

**Defect (caused by this change):** `_provably_number` accepts unary `-` of an int parameter, so `str(-x)` is now allowed in a **str-returning** clone. Str results have no overflow wrapper (`integer_ret` false), so `INT64_MIN` takes the typed `ail_die`, whereas the hybrid contract is to fall back to CPython. Base refused the function and matched.

VERDICT: FIX
1. `str(-x)` on `INT64_MIN` in a str-returning hybrid clone exits 1 instead of falling back.
   Probe `/tmp/rprobes/p_str_neg_min.py`:
   ```python
   def f(x: int) -> str:
       return str(-x)

   def main() -> None:
       print(f(-(2**63)))

   if __name__ == "__main__":
       main()
   ```
   Expected (CPython and base hybrid): stdout `9223372036854775808`, exit 0.
   Actual (HEAD `build --cpython`): stdout empty, stderr `OverflowError: integer overflow in unary - or abs() (ints are 64-bit; --exact-int gives exact ints)`, exit 1. `f` is reported accelerated. Fix: refuse unary `-` of an int in `str()` unless `ret` is int/bool, or add an overflow wrapper for str results; add this probe to `test_ail_prog21`.
[cost $0.0446, opencode tokens {"total": 2906758, "input": 76094, "output": 13030, "reasoning": 28258, "cache.write": 0, "cache.read": 2789376}]
    tool time: bash 6.5 min
        180s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && AIL_NO_CACHE=1 AIL_SERVER=0 timeout 1500 python3 -B 
         95s bash   cat > /tmp/rprobes/run8.py <<'PY' import json, os, subprocess, sys, tempfile, shutil from pathlib import Path 
         12s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 /tmp/rprobes/runhy.py "$PWD/AIL_CURRENT/ail_chatgpt.py" 
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for CL in /tmp/base/AIL_CURRENT/ail_chatgpt.py "$PWD/AIL_CURRENT/ail_cha
          9s bash   python3 - <<'PY' import struct, random random.seed(4242) vals=[] for _ in range(300):     v=struct.unpack('<d'
          8s bash   cat > /tmp/rprobes/p_abs_bool.py <<'PY' def big(x: int) -> bool:     return abs(x) > 3  def main() -> None:   
          8s bash   python3 - <<'PY' import struct, random random.seed(999) vals=[] for _ in range(300):     v=struct.unpack('<d',
          6s bash   cat > /tmp/rprobes/p_abs_simple.py <<'PY' def mag(x: int) -> int:     return abs(x)  def main() -> None:     p

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed as `ba63377`.

**Root cause/fix:** `str(-x)`/`int(-x)` on an int could overflow at `INT64_MIN`, but str-returning clones have no overflow wrapper. `_provably_number`/`_provably_int` now accept an int unary `-` only when the clone returns `int`/`bool`; otherwise the function is refused by name and falls back to CPython. Float `str(-x)` remains accelerated.

**Hybrid probes** (`build --cpython`, all stdout/exit match CPython):
- `p21_str_neg_min`, `p21_str_neg_int`, `p21_int_neg_str`: refused by name, fall back
- `p21_str_neg_float`, `p21_str_pos_int`, `p21_plain_str_int`, `p21_abs_int`, `p21_abs_bool`, `p21_str_neg_intret2`: match
- `cmp.sh` general/default builds still stop loudly on `INT64_MIN` (pre-existing declared int64 behavior); float/positive/plain probes match both builds.

**Tests:** `test_ail_prog21` 7/7, `test_ail_cpython_hybrid` 7/7, `test_ail_safetynet` 5/5, `test_ail_files` 18/18 (1 skip), `test_ail_corpus_findings3` 2/2. `update_manifest.py --check` clean. Generated `program.c` for all 10 `lab/compare` tasks is SHA-256 identical to `HEAD`.

Also corrected the test docstring's false claim: `g21_038.encode_rounded_floats` remains at pymix `unresolved-return`.
[cost $0.0252, opencode tokens {"total": 1686952, "input": 52673, "output": 10676, "reasoning": 10163, "cache.write": 0, "cache.read": 1613440}]
    tool time: bash 13.0 min
        570s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for t in test_ail_cpython_hybrid test_ail_safetynet test_ail
         84s bash   cd /home/runner/work/ail-ci/ail-ci && fail=0; for t in berth_sim chain_relax echo_pack ledger_bin rail_transfe
         43s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 AIL_SERVER=0 python3 -B test_ail_prog21.py -v
         29s bash   cat > /tmp/probes/run_hybrid.py <<'PY' import json, os, subprocess, sys, tempfile from pathlib import Path rep
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p21_str_neg_min p21_str_neg_int p21_str_neg_float p21_str_pos_i
          7s bash   cd /tmp/probes && python3 - <<'PY' from pathlib import Path p = Path('p21_str_neg_int.py') s = p.read_text().r
          5s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import json, os, subprocess, sys, tempfile from pathlib
          5s bash   cd /tmp/probes && python3 - <<'PY' from pathlib import Path p = Path('p21_str_neg_int.py') s = p.read_text() i

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Only the CPython-hybrid safety analysis changes (`AIL_CURRENT/ail_cpython_hybrid.py`): it now accepts `abs` of provable float/int, `int(<int/bool>)`, `str(<number>)`, and int unary `-` only for int/bool-returning clones. Tests/docs were added; code generation is untouched.

**Defect found (caused by this change)**

Probe `/tmp/rprobes/rv21_abs_bool.py`:
```python
def f(x: bool) -> int:
    return abs(x)

def main() -> None:
    print(f(True))
    print(f(False))

if __name__ == "__main__":
    main()
```
- CPython: `1\n0\n`
- HEAD hybrid (`build --cpython`): `True\nFalse\n` — `f` is reported accelerated.
- Base hybrid: `f` is refused (`a call can raise or have side effects`) and output is correct.

Same failure with `rv21_abs_bool_assign.py` (`y = abs(x); return y`). Cause: `_safe_call` accepts `abs` via `_provably_int(..., int_names, True)`, and `int_names` includes `bool` parameters (`ail_cpython_hybrid.py:296`); the accelerated clone returns the bool unchanged instead of `int`. The worker’s probes only call `abs` on an `int` parameter with a bool argument (`mag(True)`), which falls back at the wrapper, so the gap was missed.

**Pre-existing (not caused by the change):** general/default builds stop loudly on `abs(INT64_MIN)` with `OverflowError: integer overflow in unary - or abs()`; identical on base (`rv21_abs_min.py`).

**Claims checked**
- `ba63377` exists; `str(-x)`/`int(-x)` on an int in a str-returning clone are refused again: verified (`rv21_strneg_strret.py`).
- Float `str(-x)` remains accelerated and matches CPython: verified (`rv21_str_neg_float.py`).
- `str(int/float/bool)`, `int(bool)`, `abs(int)` boundaries: verified except the bool-operand `abs` case above.
- `g22_022.shift_and_add_multiply` accelerated; `t139.fmt` and `g21_038.encode_rounded_floats` not: verified.
- All eight programs’ hybrid stdout/exit match CPython on the inputs I ran: verified (no-input runs; the added test covers more inputs).
- `test_ail_prog21`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass (`-j 2`).
- `update_manifest.py --check`: clean.
- 10/10 `lab/compare` `program.c` byte-identical between HEAD and base via `--debug-dir`: verified.
- Speed: not measured (unverified); the change only enables more hybrid acceleration.

VERDICT: FIX
1. `abs(<bool parameter>)` is accepted as an int/bool-result call but produces `True`/`False` instead of CPython’s `1`/`0` when returned as an int. Probe: `/tmp/rprobes/rv21_abs_bool.py` (above); expected `1\n0\n`, actual `True\nFalse\n`. Also `/tmp/rprobes/rv21_abs_bool_assign.py`. Exclude bool parameters from the `abs` int proof (or convert the result to int) and add a regression test.
[cost $0.0282, opencode tokens {"total": 2234722, "input": 32714, "output": 9938, "reasoning": 17990, "cache.write": 0, "cache.read": 2174080}]
    tool time: bash 13.1 min
        239s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3
        181s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog21 test_ail_cpython_hybrid 
         81s bash   find / -name 'pymix.py' 2>/dev/null | head; grep -n "sys.path" AIL_CURRENT/ail_chatgpt.py | head
         80s bash   cd /tmp && rm -rf cmpcs; mkdir cmpcs; fail=0; for d in /home/runner/work/ail-ci/ail-ci/lab/compare/src/*/; do 
         32s bash   cd /tmp/rprobes && python3 run_hy.py /home/runner/work/ail-ci/ail-ci /home/runner/work/ail-ci/ail-ci/lab/corpu
         24s bash   cd /home/runner/work/ail-ci/ail-ci && ls lab/census/programs/gdev/g22_014.py lab/census/programs/gdev/g22_022.
         22s bash   cat > /tmp/rprobes/run_hy.py <<'PY' import json, os, shutil, subprocess, sys, tempfile from pathlib import Pat
         19s bash   cd /tmp/rprobes cat > rv21_abs_int_boolann.py <<'PY' def f(x: int) -> bool:     return abs(x)  def main() -> N

FINAL VERDICT: FIX  2026-11-02T05:37:32Z
