# job job-pre190-10251806  started 2026-10-25T09:12:18Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":389,"duration_api_ms":264,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":419,"duration_api_ms":293,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-pre190-10251806` as `278fd01`.

**Change:** constant folding now decides zero operands and power bases `0/1/-1` before the size guard, and permits a bounded larger intermediate (`2**20` bits; `2**24` for such exponents). Same rules in `_maxsplit_const`; oversized maxsplit is still refused by name.

**Probes** (all matched CPython on both `cmp.sh` builds):
- `p_basecase`, `p_bigshift`, `p_bigsplit`, `p_powbig`
- `p_boundary` (4095/4096/4097-bit cases)
- `p_routes` (argument, list item, attribute, dict value)

**Tests on final commit:** `test_ail_pre190`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes. Not pushed.
[cost $0.0000, opencode tokens {"total": 6171047, "input": 152734, "output": 14619, "reasoning": 53102, "cache.write": 0, "cache.read": 5950592}]
    tool time: bash 6.3 min
        293s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre190 test_ail_safetynet test_ail_files test_ai
         22s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre190 2>&1 | tail -50
         16s bash   for p in /tmp/probes/p_basecase.py /tmp/probes/p_bigshift.py /tmp/probes/p_bigsplit.py /tmp/probes/p_powbig.py
         12s bash   for p in /tmp/probes/p_basecase.py /tmp/probes/p_bigshift.py /tmp/probes/p_bigsplit.py; do echo "===== $p"; ba
         10s bash   for p in /tmp/probes/p_basecase.py /tmp/probes/p_bigshift.py /tmp/probes/p_bigsplit.py /tmp/probes/p_powbig.py
          6s bash   cat > /tmp/probes/p_intbase.py <<'EOF' def show(label, fn):     try:         print(label, fn())     except Exc
          6s bash   cat > /tmp/probes/p_boundary.py <<'EOF' def main():     for n in (4095, 4096, 4097):         print(n, (1 << n)
          3s bash   cat > /tmp/probes/p_powbig.py <<'EOF' def main():     print(0 ** (1 << 5000))     print(1 ** (1 << 5000))     

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of `278fd01` (pre190)

**What the change really does:** `pyfront.int_constant` now short-circuits zero operands and power bases `0/1/-1` before the size guard, retries large exponents at `2**24` bits, and raises the fold limit from 4096 to `2**20` bits; `pyfunc._maxsplit_const` gets the same rules. This matches the report, but the short-circuit is applied even when the other operand is not a constant int, which the report does not mention.

**Target fix works:** `p_basecase`, `p_routes`, `p_boundary`, `p_bigsplit`, `p_bigshift`, `p_powbig` all match CPython on both builds. `test_ail_pre190` and `test_ail_safetynet` pass; `update_manifest.py --check` passes.

**New defects (all reproduce on HEAD, not on base):**

1. `x ** 0` is folded without checking `x`. Probe `p_pow_float.py`: `print(1.5 ** 0)` expected `1.0`, general build prints `1`; `p_sideeffect.py`: `print(f() ** 0)` expected `called` then `1`, HEAD prints only `1`; `p_zero_errors.py`: `print((1 // 0) ** 0)` expected `ZeroDivisionError`/exit 1, HEAD prints `1`/exit 0.

2. `0 * x` / `x * 0` folds to int `0` without checking `x`. Probe `p_mul_str.py`: `print(0 * "ab")` expected an empty line, unified build prints `0`; `print(len(0 * "ab"))` expected `0`, unified build raises `TypeError: object of type 'int' has no len()`. Also `p_sideeffect.py` `print(f() * 0)` / `print(0 * f())` drop the `called` side effect, and `p_zero_errors.py` `print(0 * (1 // 0))` prints `0` instead of raising.

3. `0 & x` / `x & 0` folds to `0` without checking `x`. Probe `p_bitand_float.py`: `print(0 & 1.5)` expected `TypeError`, exit 1; HEAD prints `0`/`0.0`, exit 0 on both builds. `p_zero_errors.py` `print(0 & (1 // 0))` expected `ZeroDivisionError`, HEAD prints `0`.

4. `_maxsplit_const` has the same bug. Probe `p_maxsplit_special.py`: `"a,b,c".split(",", f() ** 0)` / `0 * f()` skip `called`; `"a,b,c".split(",", 2.0 ** 0)` expected `TypeError: 'float' object cannot be interpreted as an integer` (exit 1), HEAD prints extra `['a','b,c']` and `['a,b,c']` (exit 0).

**Pre-existing:** none blocking. (`p_mul_float` fails on base but matches on HEAD, so not a regression.)

**Unverified:** C output for programs not using the feature, speed/icount, `test_ail_files`, `test_ail_corpus_findings3` (only the reviewer-required modules were rerun).

VERDICT: FIX
1. Power base is not validated before returning `1` for exponent 0; float/effectful/erroring bases are silently folded.
2. Multiplication zero short-circuit ignores the other operand's type and evaluation, producing int `0` for strings/floats and hiding errors/side effects.
3. BitAnd zero short-circuit ignores the other operand's type, printing `0` where CPython raises `TypeError`.
4. `_maxsplit_const` repeats the same zero/base short-circuit without requiring the other operand to be a constant int, so non-int maxsplit expressions are folded and their evaluation is skipped.
[cost $0.0000, opencode tokens {"total": 662723, "input": 31722, "output": 3824, "reasoning": 9065, "cache.write": 0, "cache.read": 618112}]
    tool time: bash 3.2 min
        113s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ai
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "##### $(basename $p) BASE"; timeout
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_basecase p_routes p_boundary p_bigsplit p_bigshift p_powbig; 
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $p"; timeout 120 bash ~/tools
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_mul_float p_pow_float p_sideeffect p_mul_str; do echo "##### 
          8s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 120 bash ~/tools/cmp.sh /tmp/rprobes/p_pow_float.py /tmp/base 2>
          7s bash   cat > /tmp/rprobes/p_maxsplit_special.py <<'EOF' def f():     print("called")     return 2  def main():     pr
          0s bash   ls -d /tmp/base 2>/dev/null || git worktree add /tmp/base work >/dev/null 2>&1; ls /tmp/base/AIL_CURRENT/ail_c

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all four review defects in `aab127e`: zero/base shortcuts now require the other operand to be a constant integer expression.

Probes (both `cmp.sh` builds matched CPython):
- `/tmp/rprobes/p_{pow_float,mul_float,mul_str,bitand_float,sideeffect,zero_errors,maxsplit_special}.py`
- `/tmp/probes/p_pre190_{pow,mul,bitand,maxsplit}.py` — literals, both operand orders, floats, strings, list multiplication, calls/errors, beyond-fold-limit values, and argument/list-item/attribute/dict routes
- Original large-intermediate probes `p_{basecase,bigshift,bigsplit,boundary,powbig,routes}.py`

Tests on final commit: `test_ail_pre190` (4 tests, all modes), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 1006718, "input": 44540, "output": 7846, "reasoning": 11100, "cache.write": 0, "cache.read": 943232}]
    tool time: bash 6.5 min, edit 0.0 min, write 0.0 min
        268s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre190 test_ail_sa
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py /tmp/probes/p_pre190_*.py; do echo "===== $(b
         48s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -B -m unittest -v test_ail_pre190 2>&1 |
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_basecase.py /tmp/probes/p_bigshift.py /tmp/probes
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('DEVLOG.md') s=p.read_t
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo check=$?; git status --sh
          0s edit   /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12/pyfunc.py
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && git diff --stat && git diff --check

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Raises the compile-time int-fold limit 4096→2^20 bits (2^24 for a power exponent), folds zero/±1-base powers, zero mult/bit-and/shift before the size guard, and takes those shortcuts only when the other operand is a *constant int* (commit `aab127e` fixes this after `278fd01`); `_maxsplit_const` gets the same rules/limits. It is not just the one guard fix: it also repairs shortcuts introduced by the first commit.

**Probes (both `cmp.sh` builds unless noted):**
- `r1_pow_mul_and.py` – powers/mult/and with large ints, floats, strings, calls, errors, arg/list/attr/dict routes: HEAD matches CPython (g,d).
- `r2_maxsplit.py` – same via `split`/`rsplit`, float/call/error maxsplit: HEAD matches.
- `r6_zero_orders.py` – `0<<`, `0*`, `0&`, `0**(10**500000)`, `1**`, `(-1)**` at 2M-bit intermediates, negative exponents/shifts: HEAD matches; base refuses.
- `r5_limits_split.py`, `r8b_split.py` – `(1<<k)>>k`, I64_MAX/I64_MIN/2^62 maxsplit: HEAD matches; base refuses by name.
- `r8a_arith.py`, `r3_limits.py`, `r4_limits_int.py`, `r4b_zero_ops.py`, `r7_pre_existing.py` – see Pre-existing.
- Plain no-feature program: `--debug-dir` C (`program.c`, `program_mix0.c`) byte-identical to `/tmp/base` in both builds (only temp paths in `native_report.json` differ).
- Existing `/tmp/rprobes/p_*`, `/tmp/probes/p_*`: all match on HEAD except `p_intbase.py`, identical overflow on base.
- Tests on HEAD: `test_ail_pre190`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`); `update_manifest.py --check` passes; `git diff --check` clean.

**Worker claims:** verified: four shortcut defects fixed; all four named test modules pass; manifest check; probe claims. No false claims found.

**Pre-existing (identical on `/tmp/base`, do not block):**
- Negative INT64_MIN values still fail at run time: `print(-(1 << 63))`, `print(-((1 << 5000) >> 4937))` → `integer overflow` vs `-9223372036854775808`.
- Other unhandled reductions still overflow: `0 >> (1 << 5000)`, `2 ** ((1<<2000000)-(1<<2000000))`, `0 ** (-(1<<5000))`, `(1<<2000000)>>2000000`.
- `int("1"*5000, 2)` (`p_intbase.py`) overflows (noted by worker).

**Unverified:** runtime instruction counts/icount (change is compile-time folding; no-feature C is identical, so no hot-path effect expected).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2030016, "input": 80402, "output": 8788, "reasoning": 39642, "cache.write": 0, "cache.read": 1901184}]
    tool time: bash 13.7 min
        240s bash   cat > /tmp/fuzzfold2.py <<'PY' import ast, random, sys sys.path.insert(0, '/home/runner/work/ail-ci/ail-ci/AIL
        217s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_finding
        126s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre190 test_ail_safetynet 2>&
         78s bash   date; for p in /tmp/rprobes/p_*.py /tmp/probes/p_*.py; do out=$(bash ~/tools/cmp.sh "$p" $PWD 2>&1); if echo "
         52s bash   for e in '-((1 << 5000) >> 4937)' '((1 << 5000) >> 4937) - 1' '(1 << 5000) >> 4938' '-((1 << 5000) >> 4938)' '
         18s bash   cat > /tmp/rprobes/r4b_zero_ops.py <<'PY' def show(label, fn):     try:         print(label, fn())     except 
         15s bash   cat > /tmp/rprobes/r8a_arith.py <<'PY' def main():     print(-((1 << 5000) >> 4937))     print(((1 << 5000) >>
         13s bash   date; for p in /tmp/rprobes/r1_pow_mul_and.py /tmp/rprobes/r2_maxsplit.py; do echo "===== $p"; bash ~/tools/cm

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T11:19:50Z
