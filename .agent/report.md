# job job-pre241-10260355  started 2026-10-25T19:00:37Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":390,"duration_api_ms":272,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":395,"duration_api_ms":279,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `7955625`.

- **First still-differing case:** `True << 64` trapped with `integer overflow` on both builds. The target `(True << 64) >> 64` also trapped on this tree. Both now: out-of-int64 results are refused by name with the existing `integer constant expression ... signed 64-bit range` wording; the target prints `1`.
- **Change:** `pyfunc` constant folders now accept bool constants exactly like ints. `&`, `|`, `^` of two bools still return a bool at run time, so `True & False` keeps printing `False`; negative shift counts still raise `ValueError`.
- **Probes:** 53 files in `/tmp/probes/pre241/`. 45 match CPython or are refused by name on both builds, covering shift widths 0/1/62/63/64/4096/100000, `False`, bool arithmetic/bitwise, maxsplit, dead code, module constants, arguments, list items, attributes and dict values. The other 8 pass a non-constant bool through a name/parameter/list/attribute/dict and keep the pre-existing int64 runtime trap, exactly as the int counterpart does.
- **Final-state tests:** `test_ail_pre241` 3 OK; `test_ail_safetynet` 5 OK; `test_ail_files` 18 OK (1 skipped); `test_ail_corpus_findings3` 2 OK. Manifest `--check`: exit 0.
- **Note:** I also ran `test_ail_pre121`; 4/6 pass, and the 2 failures are pre-existing message mismatches for int `10**30`, untouched by this bool-only change.
[cost $0.0000, opencode tokens {"total": 4603568, "input": 93038, "output": 15026, "reasoning": 22160, "cache.write": 0, "cache.read": 4473344}]
    tool time: bash 13.8 min, edit 0.0 min, write 0.0 min
        132s bash   (cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-point
        128s bash   (cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-point
        124s bash   cd /tmp/probes/pre241 && for f in p*.py; do out=$(bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-ci 2>&
         81s bash   (cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-point
         77s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointe
         57s bash   mkdir -p /tmp/probes/pre241 cd /tmp/probes/pre241 cat > p01_true64.py <<'EOF' print(True << 64) EOF cat > p02_
         43s bash   cd /tmp/probes/pre241 && for f in p01_true64.py p02_true4096.py p03_truebig.py p04_dead.py p05_target.py p08_t
         31s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointe

## review 0
[model opencode/deepseek-v4.1-flash-free]
# Review: job-pre241 (bool constant folding)

**What the change really does:** `pyfunc._const_int_expr` and `_maxsplit_const` now accept `bool` constants (`type in (int, bool)`), unary `+` on a bool is coerced to `int`, and `fold_int_constant` skips booleans so `& | ^` results stay runtime bools. One commit, `7955625`; no runtime changes. This matches the report, though it covers all constant ops/maxsplit, not just shifts.

**Probes** (`/tmp/rprobes/q*.py`, HEAD general + default vs CPython; base compared where relevant)

| probe | HEAD | base |
|---|---|---|
| q01 `(True << 64) >> 64` | matches (1) | both builds trap → pre-existing, fixed |
| q02 `(True << 100000) >> 100000` | matches (1) | both trap → fixed |
| q03 `True << 63` | refused by name | both trap |
| q04 `& \| ^ ~ + -` on bools | matches | same |
| q05 maxsplit `True`, `+True`, `(True<<64)>>64`, `True&True` | matches | same |
| q06/q16 non-constant bool through arg | trap both builds | identical → pre-existing |
| q07 module const/list/attr/dict in-range | matches | pre-existing fix |
| q08 negative shift counts | matches (`ValueError`) | same |
| q09 bool arithmetic shifts | in-range matches; out-of-range refused | base traps |
| q10 dead-code refusal + live target | refused by name (accepted policy) | base traps |
| q11 int-only program | matches | same |
| q12/q18 bool-valued `& \| ^`, `type()` | matches (still `bool`) | same |
| q13 `False`/`True` shift boundaries | matches | same |
| q14 q15 mixed bool bitwise, module constants | matches | q15 traps on base |
| q17 exact cap/overflow | refused by name (CPython errors on 4300-digit print) | refusal policy |

**Other checks:** `program.c` for `corpus/gdev/g00_000.py` byte-identical HEAD vs `/tmp/base` (only `native_report.json` temp paths differ); manifest `--check` exit 0; `test_ail_pre241` + `test_ail_safetynet`: 2 modules, 0 failed; commit trailer present; DIFFERENCES placeholder/deVLOG date correct.

**Claims:** first-differing `True << 64`/target trap on base — verified; target prints 1 — verified; named refusals — verified; non-constant bools keep pre-existing trap — verified; C unchanged for non-feature program — verified; reports' 53-probe count, `test_ail_files` and `test_ail_corpus_findings3` runs — unverified (out of reviewer scope).

**Pre-existing (not blocking):** non-constant bool shifts (`True` through a name/parameter/list/attribute/dict) still trap with `integer overflow` on both HEAD and base, exactly like non-constant ints; q17 base/CPython differ for huge-int printing/limits.

**Unverified:** worker's exact probe set and the two extra test modules; speed not measured (fold is compile-time only, generated C identical for the int-only probe).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 532342, "input": 37480, "output": 4791, "reasoning": 11991, "cache.write": 0, "cache.read": 478080}]
    tool time: bash 2.4 min
         69s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         24s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && \ cat > q01_target.py <<'EOF' print((True << 64) >> 64) EOF cat > 
         22s bash   cd /tmp/rprobes && cat > q12_bool_context.py <<'EOF' print(True & True) print(True | True) print(True ^ False)
         12s bash   cd /tmp/rprobes && for f in q02_big_roundtrip.py q03_63.py q09_arith.py q10_dead_bool.py q06_nonconst_arg.py; 
          9s bash   cd /tmp/rprobes && cat > q17_edge.py <<'EOF' print(True << 1048575 >> 1048575) print(True << 1048576) EOF cat 
          4s bash   cd /tmp/rprobes && echo "=== q01 target base"; timeout 300 bash ~/tools/cmp.sh q01_target.py /tmp/base 2>&1 | 
          1s bash   cd /tmp && rm -rf cdiff && mkdir -p cdiff/h cdiff/b && cp /home/runner/work/ail-ci/ail-ci/corpus/gdev/g00_000.
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12 && python3 - <<'EOF' import ast, pyfunc for s in

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T20:12:18Z
