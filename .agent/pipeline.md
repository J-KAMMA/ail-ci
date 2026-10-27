# job job-pre366-10280408  started 2026-10-27T19:09:44Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"3b217dbf-6504-44f8-abe1-236e874eadc2","session_id":"cd7fa955-e3dd-4573-b646-0cf248b01b5d"}
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"2ff069fe-9d2e-4c26-ba8d-4fcdf13b40fc","session_id":"8c52c0f0-d465-4d33-9549-3de5df618575"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed `r12` on branch `job-pre366-10280408`, commit `09f2517`.

**Change:** the constant checks now follow module-level `q = power` aliases (and alias chains). This covers power wrappers (`base ** exponent`, `pow(base, exponent)`) and `int()` wrappers. Out-of-int64 constant calls are refused by name; aliased power wrappers with non-static operands are refused by name. Safe constants still match CPython; direct wrappers keep their prior runtime behaviour.

**Probes** (`bash ~/tools/cmp.sh`, both builds, 31 total):
- Match CPython (9): `p01`, `p05`, `p07`, `p09`, `p15`, `p16`, `p22`, `p23`, `p24`.
- Refused by name (22): `a_pow_wrapper_alias`, `a_pow_wrapper_direct`, `b_exp_wrapper_alias`, `b_exp_wrapper_direct`, `c_int_wrapper_alias`, `c_int_wrapper_direct`, `p02`, `p03`, `p04`, `p06`, `p08`, `p10`, `p11`, `p12`, `p13`, `p14`, `p17`, `p18`, `p19`, `p20`, `p21`, `p25`.

**Final tests on commit:** 16 modules, 420 s, 0 failed (`test_ail_pre366`, related power/wrapper modules, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`). `tools/update_manifest.py --check` passes.

**Unverified:** local aliases of `int()` wrappers; loop/conditional wrapper-call shapes beyond the direct function-argument route; full suite.
[cost $0.0000, opencode tokens {"total": 6033141, "input": 148933, "output": 15600, "reasoning": 30016, "cache.write": 0, "cache.read": 5838592}]
    tool time: bash 14.5 min
        422s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre366 test_ail_pre290 test_ail_pre294 test_ail_
        146s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre290 test_ail_pre294 test_ail_pre299 test_ail_
        139s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre366 test_ail_safetynet 2>&1 | tail -60
         49s bash   cd /home/runner/work/ail-ci/ail-ci for f in /tmp/probes/pre366/*.py; do printf '%-38s ' "$(basename $f)"; out=
         38s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre366 2>&1 | tail -20
         36s bash   mkdir -p /tmp/probes/pre366 && cd /tmp/probes/pre366 && cat > p01_pow_alias_safe_static.py <<'EOF' def power(b
         24s bash   mkdir -p /tmp/probes/pre366 && cat > /tmp/probes/pre366/a_pow_wrapper_direct.py <<'EOF' def power(base, expone
         11s bash   cat > /tmp/probes/pre366/p23_pow_alias_boundaries_safe.py <<'EOF' def power(base, exponent):     return base *

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Adds AST-only constant-check support for module-level `q = wrapper` aliases (and chains) of `int()` wrappers and of one-return `**`/`pow()` wrappers; out-of-int64 constants are refused with the existing messages, and aliased power wrappers with non-static operands get a new by-name refusal. No emitted code/runtime change.

**Claims**
- Verified: r12 shape (`q = power`) now reproduces as a named refusal on both builds instead of the runtime `integer overflow`; module and function-scope aliases, chains, int aliases, attribute/list/dict/argument routes behave as reported; safe constants match CPython; local int aliases remain unhandled (pre-existing); tests/manifest as stated.
- Minor inaccuracy: “direct wrappers keep their prior run-time behaviour” holds only for run-time operands; direct calls with constant out-of-int64 operands are now refused by name (the report also lists `a_pow_wrapper_direct` as refused, so the summary is loose, not wrong in effect).
- Unverified by me: full suite, other pre330 modules, compile-time cost.

**Probes** (`/tmp/rprobes`, both builds; base compared where relevant)
- Match CPython: `q01` non-feature alias, `q02` direct wrapper dynamic, `q03` safe bases/`q(-2,63)`, `q08` dynamic in-range int, `q11` global-base wrapper, `q15` function-scope alias chain safe, `q19` base −1 dynamic.
- Refused by name: `q04` `(-2,64)` (`int64 constant expression out of range`; base overflowed), `q05` static base/dynamic exponent (base matched; refusal allowed), `q07` `int(2**63 float)` (`int() of a float outside int64`), `q09` float operands, `q10` defaulted wrapper (base already refused), `q12` keyword call through function value (base already refused), `q13`/`q14`/`q17` function/conditional alias cases, `q18` loop alias (base matched; refusal allowed).
- Pre-existing: `q06`/`q16` local `int()` alias still stop with runtime `integer overflow`, identical on base.

**Tests:** `test_ail_pre366`, `test_ail_safetynet` (137 s), plus `test_ail_pre290`, `test_ail_pre305` (36 s): 0 failed. `tools/update_manifest.py --check` passes. Records (`DEVLOG`, `DIFFERENCES`, `MANIFEST`, shards) present.

**Unverified:** full suite, compile-time cost, and local int aliases (still overflow, but unchanged from base).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1084943, "input": 57734, "output": 4361, "reasoning": 18560, "cache.write": 0, "cache.read": 1004288}]
    tool time: bash 4.7 min
        139s bash   cd AIL_CURRENT && timeout 500 python3 ../tools/par_check.py -j 2 test_ail_pre366 test_ail_safetynet 2>&1 | tai
         55s bash   cd /tmp/rprobes && for f in q*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" /tmp/base 2>&1 | grep -E "cpyt
         38s bash   date; cd AIL_CURRENT && timeout 300 python3 ../tools/par_check.py -j 2 test_ail_pre290 test_ail_pre305 2>&1 | 
         34s bash   cd /tmp/rprobes && for f in q*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-c
         15s bash   cd /tmp/rprobes && cat > q13_fn_alias_dynamic.py <<'EOF' def power(base, exponent):     return base ** exponen
          1s bash   cd /tmp/rprobes && for f in q04_alias_over.py q07_int_boundary.py; do echo "== $f"; out=$(bash ~/tools/cmp.sh 
          0s bash   git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/base | head
          0s bash   python3 tools/update_manifest.py --check 2>&1 | tail -5

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T20:57:47Z
