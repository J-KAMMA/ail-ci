# job job-pre273-10262306  started 2026-10-26T14:19:19Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":689,"duration_api_ms":547,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":637,"duration_api_ms":513,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `07edb0a`.

- Reproduced the first still-differing rbpre69 item: `0 ** -1` already matched CPython; variable-exponent `2 ** n` still trapped with `integer overflow`.
- Fix: a compile-time integer base with |base| >= 2 and a computed exponent is now refused by name on the typed path and both general emitters. Constant exponents, bases 0/1/-1, float bases, and variable-base/constant-exponent powers are unchanged.
- Added `AIL_CURRENT/test_ail_pre273.py`; updated `test_all.integer_power`, `test_ail_pre160`, `test_ail_crypto`, DEVLOG, DIFFERENCES (`C?-job-pre273-10262306-1`), SEMANTICS, manifest, and CI shards.

Probes (`/tmp/probes`, both g/d builds): matched CPython — `pre273_bounds`, `pre273_safe`, `pre273_zero_neg`, `pre273_neg_literal`; refused by name — `pre273_arg`, `pre273_list`, `pre273_attr`, `pre273_dict`, `pre273_alias`, `pre273_float_dynamic`; existing named refusal — `pre273_expr_pow`.

Final-commit tests: `test_ail_pre273`, `test_ail_pre160`, `test_ail_crypto`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` = 6 modules, 0 failed (295 s); `test_all.integer_power` 0 failures; manifest `--check` and `ci_shards.py --check` pass. Remaining untouched pre-existing: `pow(10, 100)` still traps at run time, and a variable base with a computed exponent still uses the run-time trap.
[cost $0.1108, opencode tokens {"total": 12837536, "input": 210570, "output": 22191, "reasoning": 47079, "cache.write": 0, "cache.read": 12557696}]
    tool time: bash 13.7 min
        392s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u +%FT%TZ && timeout 1500 python3 ../tools/par_check.p
        297s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u +%FT%TZ && timeout 1500 python3 ../tools/par_check.p
         42s bash   cat > /tmp/probes/pre273_bounds.py <<'EOF' def main():     print(2 ** 62)     print((-2) ** 62)     print((-2)
         35s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 -m unittest -v test_ail_pre273 2>&1 | ta
         13s bash   cd /home/runner/work/ail-ci/ail-ci && for p in pre273_var_pow pre273_zero_neg pre273_pow_builtin; do echo "===
          8s bash   mkdir -p /tmp/probes; cat > /tmp/probes/pre273_zero_neg.py <<'EOF' def main():     try:         print(0 ** -1)
          7s bash   cat > /tmp/probes/pre273_expr_pow.py <<'EOF' def main():     print(2 ** (62 + 1))  main() EOF cat > /tmp/probe
          5s bash   cat > /tmp/probes/pre273_zero_plain.py <<'EOF' print(0 ** -1) EOF d=$(mktemp -d /tmp/v1zXXXX); cp /tmp/probes/

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds `pyfront.refuse_variable_int_pow`, called for `ast.Pow` from the typed path (`pyfunc._expr`) and both general emitters (`pyboxed`, `pyboxed2`). It refuses, at compile time, any constant int64 base with `|base| >= 2` whose exponent is not a syntactic constant. No runtime change.

**Defect (blocker): the refusal hits compiler-injected library source, breaking programs that never use `**`.**

Probe `/tmp/rprobes/r15_fraction_simple.py`:
```python
from fractions import Fraction

def main():
    print(Fraction(1, 2))
main()
```
Expected (CPython and base worktree, both g/d): prints `1/2`, exit 0.
Actual HEAD: both builds fail. General build: `p.ail:163:13: not in the subset: a power with the integer constant base 10 and an exponent computed at run time ...` — from `prelude_fraction.py`'s own `10 ** len(frac)` (also lines 190, 192, 306). Default build then reports `dunder method Fraction.__float__ ... (the general path could not build this program either); general path: a power with ...`. Base both builds match CPython. Existing module `test_ail_pre133` now fails 2/3 with this refusal; `test_ail_stdlib5`, `test_ail_fuzz41`, `test_ail_match`, `test_ail_deqctr` also use `Fraction` and are at risk.

**Pre-existing (same on base):** `pow(2, 63)` traps `integer overflow` on both builds; `2 ** n` with `n = 64` trapped on base (the target difference); a variable base with a computed exponent still traps. `0 ** -1` matches CPython on base.

**Report claims:** commit/test additions/DIFFERENCES/DEVLOG/SEMANTICS/manifest/shard registration verified. Probe claims for `bounds`, `safe`, `zero_neg`, `neg_literal`, `expr_pow`, `float_dynamic` and the arg/list/attr/dict/alias refusals reproduced. `test_all.integer_power` 0 failures verified. 6 required modules pass (293 s, 0 failed); manifest and `ci_shards.py --check` pass. Non-`**` probe `r8_nopow.py`: `program.c` identical to base on both builds (only `native_report.json` path data differs).

**Unverified:** full suite and the other `Fraction` users; `prelude_random.py`'s `4 ** m` did not trigger through `import random`/`Random.sample` probes, so its path is unverified.

Speed: compile-time check only; no hot-code change, no icount run.

VERDICT: FIX
1. `Fraction` no longer compiles because `prelude_fraction.py` contains `10 ** len(frac)` / `10 ** exp` and the new refusal rejects compiler-injected prelude code. Probe source and expected/actual above; `test_ail_pre133` fails 2/3.
[cost $0.0328, opencode tokens {"total": 2225209, "input": 69624, "output": 7026, "reasoning": 19663, "cache.write": 0, "cache.read": 2128896}]
    tool time: bash 9.8 min
        295s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u +%FT%TZ && timeout 900 python3 ../tools/par_check.py
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u +%FT%TZ > /tmp/tests_start.txt && nohup python3 ../t
         36s bash   cd /tmp/base && for p in r9_fraction r10_random_sample r11_flag; do echo "===== BASE $p"; bash ~/tools/cmp.sh 
         30s bash   cd /tmp/rprobes && cat > r15_fraction_simple.py <<'EOF' from fractions import Fraction  def main():     print(
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r9_fraction r10_random_sample r11_flag; do echo "===== HEAD $p"
         18s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/wprobeout && ls /tmp/probes/*.py | xargs -P 2 -I{} bash -c
         11s bash   cd /tmp/rprobes && cat > r12_random_random.py <<'EOF' import random  def main():     r = random.Random(1)     
         11s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u +%FT%TZ && timeout 400 python3 ../tools/par_check.py

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the blocker in commit `c9376b5`.

- `prelude_fraction.py` now scales with a multiplication helper instead of `10 ** ...`; `prelude_random.py` reuses its computed `p` instead of `4 ** m`. The user-facing `2 ** n` refusal is unchanged.
- Added a Fraction regression case to `test_ail_pre273.py`; `test_ail_pre133` is back to 3/3.

Probes in `/tmp/probes`:
- `pow_fraction_prelude.py`: both builds match CPython (negative/decimal/exponent strings, underscores, `round` with positive/negative ndigits, arg/list/attr/dict/alias routes).
- `pow_random_sample.py`: both builds match CPython (k=3/6, both sample branches).
- `pre273_bounds/safe/zero_neg/zero_plain/neg_literal`: match CPython, both builds.
- `pre273_var_pow/arg/list/attr/dict/alias/float_dynamic`: refused by name, both builds.
- `pre273_expr_pow`: refused as a constant out of int64. `pre273_pow_builtin` still shows the pre-existing `pow(2, n)` overflow difference; untouched.

Tests on final commit: 9 modules, 57 tests, 0 failed, 1 skipped (`test_ail_pre273`, `test_ail_pre133`, `test_ail_stdlib5`, `test_ail_fuzz41`, `test_ail_match`, `test_ail_deqctr`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`). Manifest and `ci_shards.py --check` pass.
[cost $0.0379, opencode tokens {"total": 3065965, "input": 88772, "output": 9166, "reasoning": 16987, "cache.write": 0, "cache.read": 2951040}]
    tool time: bash 11.9 min
        482s bash   printf '%s\n' test_ail_pre273 test_ail_pre133 test_ail_stdlib5 test_ail_fuzz41 test_ail_match test_ail_deqctr 
         58s bash   cd /tmp/rprobes && for p in r9_fraction r15_fraction_simple r12_random_random r1_small r2_floatvar r3_safe_neg
         48s bash   cat > /tmp/probes/pow_fraction_prelude.py <<'EOF' from fractions import Fraction   def show(x):     return str
         36s bash   cd /tmp/rprobes && for p in r15_fraction_simple r10_random_sample r11_flag r9_fraction; do [ -f $p.py ] && { e
         32s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_pre133 2>&1 | ta
         31s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre273 2>&1 | tail -40
         18s bash   cat > /tmp/probes/pow_fraction_modern.py <<'EOF' from fractions import Fraction   def main():     print(Fracti
          5s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/r12_random_random.py /home/runner/work/ail-ci/ail-ci

## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed `work..HEAD` (2 commits, 16 files). The change really adds a compile-time refusal for `int-constant base (|base|>=2) ** non-constant exponent` and wires it into the typed path plus both general emitters; it also rewrites the fraction/random preludes to avoid that form and updates tests/docs. Note: the worker report describes only commit `c9376b5` (prelude fix); commit `07edb0a` (the refusal itself, test edits, DEVLOG/DIFFERENCES) is also in the diff.

**Claims checked**
- Prelude blocker fixed; `prelude_fraction` multiplication helper, `prelude_random` reuses `p`: verified by diff and probes.
- `test_ail_pre133` back to 3/3; Fraction regression added: verified.
- User-facing `2 ** n` still refused on both builds: verified (`p02`, `p07`, `test_ail_pre273`).
- Fraction strings/underscores/round ± ndigits match CPython: verified (`p05`).
- Random `sample` both branches, both builds: verified (`p06`, `p10`).
- Var/arg/list/attr/dict/alias/float-dynamic refused by name: verified (`p02`, `p07`, test module).
- `pow(2, n)` overflow remains pre-existing: verified (`p08`).
- Safe positive bases (`0/1/-1`) match: verified (`p03`). `0 ** n` with computed `n=-1` does not match on the default build (pre-existing, see below).
- `test_all.integer_power`, manifest `--check`, `ci_shards.py --check`: pass.
- All 9 named modules plus `test_ail_pre160`/`test_ail_crypto`: pass.

**Probes (`/tmp/rprobes`, both builds vs `/tmp/base`)**
- `p01`, `p03`, `p05`, `p06`, `p10`, `p11`: match CPython on both builds and base.
- `p02`, `p07`: named refusal on both builds. `p07` (`2 ** x`, `x=0.5`) matched CPython on base; the new refusal is broader than the integer case but the task explicitly allows a named refusal, and SEMANTICS documents it.
- `--debug-dir` C for a no-`**` program is byte-identical to base (default and general).

**Pre-existing (identical on `/tmp/base`; not blocking)**
1. `pow(2, n)` still traps `integer overflow` where CPython prints the exact value (`p08`).
2. `0/1/(-1) ** n` with computed negative `n` traps `negative exponent` on the default build; CPython raises `ZeroDivisionError` or returns a float (`p04`, `r4_zero_negvar`).
3. The original overflow remains when the base 2 arrives through an argument/list/attribute/dict or `x **= n`; the base is no longer syntactically constant (`p12`, `p13`).
4. `Fraction("1e19")` and above trap `integer overflow` after `1e18` (`p09`).

**Unverified**
- Instruction counts: `perf_event_open` is denied in this runner. `g03_002`/`g03_004` outputs and exit statuses are identical base vs HEAD.
- Exact tally "57 tests, 1 skipped"; all named modules pass, but I did not count tests.

VERDICT: ACCEPT
[cost $0.0441, opencode tokens {"total": 3073284, "input": 91559, "output": 8711, "reasoning": 27094, "cache.write": 0, "cache.read": 2945920}]
    tool time: bash 13.3 min
        286s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        140s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre273 tes
        132s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fuzz41 tes
         45s bash   cd /tmp/rprobes && for p in p01_const p02_routes p03_safe p04_neg_safe p05_fraction p06_random p07_floatvar p0
         36s bash   cat > /tmp/rprobes/p09_fraction_big.py <<'EOF' from fractions import Fraction   def main():     print(Fraction
         33s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre133 2>&
         32s bash   cd /tmp/rprobes && for p in p01_const p02_routes p03_safe p04_neg_safe p05_fraction p06_random p07_floatvar p0
         31s bash   cd /tmp && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount /home/runner/work/ail-ci/ail-ci/tools/

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T16:53:52Z
