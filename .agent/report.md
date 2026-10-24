# job job-pre121-10242314  started 2026-10-24T14:28:41Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":501,"duration_api_ms":386,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":523,"duration_api_ms":405,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Commit:** `b545672` — pre121: constant int expressions are exact or refused by name

**What changed**
- Added exact compile-time folding for all-constant int expressions: in-range values (`2**63 - 1`, `-(2**63)`, `-1 << 63`, `~(-2**63)`, `2**100 // 2**80`) are emitted as literals; out-of-int64 values (`10**30`, `1 << 63`, `(-2)**64`) are refused by name.
- Hooked into typed `_expr`, general `Compiler.expr`, unified `nexpr`, and IR lowering, since module-level statements can reach any of them.
- Added `AIL_CURRENT/test_ail_pre121.py` covering boundaries, dynamic/non-int expressions, and the recorded p6/p7/p13 shapes.

**Probes** (`bash ~/tools/cmp.sh`, both builds): 23 total
- 7 matched CPython: `c_inrange`, `c_intermediate_inrange`, `c_dynamic`, `c_bool_float`, `p7_inrange`, `p13_inrange`, `test_inrange`.
- 15 refused by name: p5 unbound (2), p6 user-split, p7 plain, p13 variable, plus pow/shift/mod cases via argument, list, dict, attribute, return and module scope.
- 1 still differs: `p12_none.py` (runtime `sep=None`, pre-existing different cause, not fixed).

**Tests on final commit (`-j 2`):** `test_ail_pre121`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 201 s, 0 failed. Earlier targeted runs also passed: overflow/modconst/cov2/range/bugs7, numeric/IR/fuzz-findings, unified/sets-general/native-diagnostics.

Manifest `--check` rc 0. p5 was already refused by name, so p6 was the first actionable difference; p12 was left as a separate pre-existing cause.
[cost $0.0000, opencode tokens {"total": 12738335, "input": 336318, "output": 27086, "reasoning": 40211, "cache.write": 0, "cache.read": 12334720}]
    tool time: bash 17.5 min, edit 0.0 min, write 0.0 min
        204s bash   python3 ../tools/par_check.py -j 2 test_ail_numeric_binding_boundaries test_ail_numeric_bindings test_ail_nume
        203s bash   python3 ../tools/par_check.py -j 2 test_ail_pre121 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        193s bash   python3 ../tools/par_check.py -j 2 test_ail_overflow_error test_ail_modconst test_ail_cov2 test_ail_range_chec
        168s bash   python3 ../tools/par_check.py -j 2 test_ail_unified test_ail_sets_general test_ail_native_diagnostics
         58s bash   for p in /tmp/probes/c_inrange.py /tmp/probes/c_intermediate.py /tmp/probes/c_intermediate_inrange.py /tmp/pro
         41s bash   python3 ../tools/par_check.py -j 2 test_ail_pre121
         39s bash   python3 ../tools/par_check.py -j 2 test_ail_pre121
         31s bash   for p in /tmp/probes/c_inrange.py /tmp/probes/c_intermediate.py /tmp/probes/c_dynamic.py /tmp/probes/c_bool_fl

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre121 — constant int expressions folded / refused

**What the diff really does:** adds `_const_int_expr`/`fold_int_constant` in `pyfunc.py` (exact Python-int evaluation with 4096-bit guards; out-of-int64 → `Unsupported`) and calls it at the top of typed `_expr`, general `Compiler.expr`, unified `nexpr` and IR `_expr`. This matches the report.

**Probes** (`cmp.sh`, HEAD vs /tmp/base): ~35 programs.
- Match CPython both builds: boundaries `2**63-1`, `-(2**63)`, `-1<<63`, `(-2)**63`, `~(-2**63)`, `~(2**63-1)`; `//`,`%`,`>>`,`&`,`|`,`^` with negatives; through arg/list/dict/attr/tuple/set/default/kwarg/return; f-string, float assignment, comparisons/truthiness, in-range via `2**63//2`, `2**64//2**64`, `(2**63)-(2**63)`; non-int `2**-1`, float mixes; `1<<-1` still ValueError. (`r1,r2,r3,r6,r9,r10,s1,s3,s4,s5,s6,t3,u1,u2,u3,v1`)
- Refused by name: `10**30`, `1<<63`, `(-2)**64`, `(-2**63)//-1`, `2**63/2`, `float(10**30)`, `2**63*1.0`, `(2**5000)//(2**5000)`; containers/kwargs covered (`r4,r5,r8,s2,t1,t2,t4,w1–w6`). Base on these: runtime `integer overflow` (pre-existing).
- No-feature C via `--debug-dir`: identical to base. A program using only `-1` changes C only by dropping the now-unneeded `ck_neg` helper; semantics unchanged.

**Claim checks**
- In-range folding: **verified** (listed values); caveat: in-range *results* through >4096-bit intermediates are refused, not emitted — named refusal, as pre97 noted.
- Out-of-int64 refused by name: **verified** (`pre121` test + probes).
- Four hooks / both builds: **verified**; no wrong-value case found (emitted values are Python-exact).
- `test_ail_pre121` added and passing: **verified** (`test_ail_pre121` 40.8s, `test_ail_safetynet` 75.9s, 0 failed). Also ran `test_ail_cov2` + `test_ail_overflow_error`: 0 failed.
- Manifest `--check` rc 0, DEVLOG/DIFFERENCES row, commit trailer: **verified**.
- p5 already refused, p6 first actionable: **verified** (p5 `name 'str' is not defined` on both; p6 refused by name now).
- Worker's exact 23-probe tally and `test_ail_files`/`test_ail_corpus_findings3`: **unverified** (outside targeted scope).

**Pre-existing (identical on base):** p12 `sep=None` still `ValueError: empty separator`; p5 refusal; huge dead-code literal refusal. Dead-branch `10**30` is now refused by name (base compiled it) — consistent with the existing literal policy and allowed by the task. No speed check: compile-time only, runtime untouched.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2300875, "input": 87820, "output": 9200, "reasoning": 38863, "cache.write": 0, "cache.read": 2164992}]
    tool time: bash 5.7 min
        147s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov2 test_
         77s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre121 tes
         24s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/r*.py; do echo "===== $(basename $p) HEAD"; bash ~/t
         15s bash   cd /tmp/rprobes cat > w1_tuple_set.py <<'EOF' print((10**30,)) EOF cat > w2_set.py <<'EOF' print({10**30}) EOF
         14s bash   cd /tmp/rprobes; for p in s*.py; do echo "===== $p HEAD"; bash ~/tools/cmp.sh "$PWD/$p" "/home/runner/work/ail
         13s bash   cd /home/runner/work/ail-ci/ail-ci for f in p5_unbound p6_user_split p7_plain p13_variable p12_none; do   echo
          9s bash   cd /tmp/rprobes cat > t1_mixbig.py <<'EOF' print(2**63 * 1.0) print(2**63 + 0.0) print(float(2**63)) print(2**
          8s bash   for p in t1_mixbig.py t2_mixbig2.py t4_minover.py; do echo "===== $p BASE"; bash ~/tools/cmp.sh "/tmp/rprobes/

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T15:54:41Z
