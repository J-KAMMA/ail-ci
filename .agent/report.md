# job job-pre52-10270920  started 2026-10-27T00:21:18Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"6a4d217f-3cab-47db-b47a-45280b866411","session_id":"4cdf7020-2981-4ee5-ad54-99c2ab5e4afc"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"221f9d39-c28e-4c1b-aa73-fe8cda7c306d","session_id":"80cd4a65-98a5-4668-a9af-416e717f0ca6"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Merged the current integration snapshots into the pre52 branch so its delta is only the pre52 fix; the old base was several integrated candidates behind, so applying the branch reverted them and caused the 136-module failure list.

- Final commit: `8d76aad` (not pushed)
- Required/targeted tests on final commit: 21 modules, 20 ok. `test_ail_pre52`, `pre27`, `pre270`, `multifile`, `safetynet`, `files`, `corpus_findings3` all pass.
- `test_ail_pre59` fails, but it already fails on clean `cand-1027092746` (verified separately); it conflicts with `test_ail_pre75` over negative literal `r`, not caused by pre52.
- Probes (`/tmp/probes/pre52_*`, both builds): 12 total. 10 refused by name with `line:col` (`body_import`, `from_import`, `handler_only`, `else_only`, `finally_only`, `nested_body`, `tuple_handler`, `handler_and_body`, `import_value`, `shadowed`); 2 match CPython (`exception_ok`, `plain_try`).
- `python3 tools/update_manifest.py --check`: exit 0.
- Working tree clean except untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 9743663, "input": 110654, "output": 17143, "reasoning": 36218, "cache.write": 0, "cache.read": 9579648}]
    tool time: bash 36.9 min, edit 0.0 min, write 0.0 min
        371s bash   cd /tmp/integtest && timeout 2400 python3 tools/par_check.py -j 2 test_ail_callable_values test_ail_crypto tes
        364s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3600 python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_pre
        322s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_pre
        320s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_multifile test_ail
        276s bash   cd /tmp/integ2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_pre100 test_ail_fuzz42 
        173s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_pre1
        159s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_pre2 test_ail_pre1
         84s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/integ3 && git worktree add --detach /tmp/integ3 origin/cand-

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** It merges two integration snapshots (cand-1027073603 / `5a17d1d` and cand-1027092746 / `1f21ed3`) into the pre52 branch. Net result: `HEAD` equals the newer integration content (`5a17d1d`, which contains every test file and source feature of `1f21ed3`) plus only the pre52 delta (`pyboxed2` try-body import scan + column, and the `test_ail_pre52` registration). No new compiler work beyond that.

**Probes (`/tmp/rprobes`, both builds, vs CPython; base `/tmp/base` = `work`):**
- pre52: `p1_guard_handler` (import in body + handler) refused `p.ail:2:5`; `p2_handler_only` refused `p.ail:1:1`; `p3_nested_try` refused `p.ail:3:9`; `p4_column` refused `p.ail:3:5`; `p5_exception_handler` matches.
- merged features: `p6_comp_alias`, `p7_comp_raise`, `p8_comp_routes`, `p9_iadd`, `p10_iadd_fallback`, `p11_with_beside_yield` match.
- `p12_with_yield` / `p12b_with_open` (read-only `with open` around yield) are not refused and match CPython (the skipped `__exit__` is unobservable); `p12c_with_open_close` (write + close) is refused by name (`with` around a `yield`), while base compiles and matches — a named refusal, acceptable.
- Plain program (no try/import feature): `--debug-dir` `program.c` is byte-identical between HEAD and `5a17d1d`; only `native_report.json` differs.

**Tests (HEAD, `-j 2`):** 18 added/edited+safetynet/files/corpus modules: 17 ok, `test_ail_pre59` fails. Plus sampled originally-failing modules `test_ail_callable_values`, `crypto`, `gcstress`, `hostile_input`, `typed_inherit`, `pre100`: all ok. `pre27`, `pre270`, `multifile`: ok. `tools/update_manifest.py --check` exit 0; tree clean except untracked `.agent/pipeline.md`.

**Claims:** delta-only-pre52 verified; commit `8d76aad` verified; the named passing modules verified; `pre59` fails identically on clean `1f21ed3` (verified) — pre-existing pre75/pre59 negative-literal-`r` conflict; 12 probes claim not reproduced exactly but independent probes agree; manifest/clean-tree claims verified.

**Pre-existing:** `test_ail_pre59` fails because pre75 refuses a negative `r` literal while pre59 expects a runtime `ValueError`; identical on `5a17d1d` and `1f21ed3`, not caused by this change. Also the merged DEVLOG's claim that `with open(...)` around a yield is always refused is false for read-only literal opens, but that path has no observable difference.

**Unverified:** the exact 12 worker probes; the remaining ~125 originally-failing modules; speed (worker delta is compile-time only, so not relevant).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2239068, "input": 88069, "output": 8839, "reasoning": 22608, "cache.write": 0, "cache.read": 2119552}]
    tool time: bash 11.5 min
        309s bash   date; timeout 1500 python3 tools/par_check.py -j 2 test_ail_fuzz28 test_ail_fuzz4 test_ail_fuzz49 test_ail_mod
        260s bash   date; timeout 900 python3 tools/par_check.py -j 2 test_ail_callable_values test_ail_crypto test_ail_gcstress t
         53s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre27 test_ail_pre2
         35s bash   date; cd /tmp/rprobes; for p in p*.py; do echo "######## $p"; bash ~/tools/cmp.sh $p /home/runner/work/ail-ci/
         13s bash   git worktree add --detach /tmp/cand 1f21ed3 2>&1 | tail -2; cd /tmp/cand && timeout 300 python3 tools/par_chec
          8s bash   cd /tmp/rprobes && rm -f /tmp/ailw.txt && cat > p12c_with_open_close.py <<'EOF' import os p = '/tmp/ailw.txt' 
          5s bash   cd /tmp/rprobes && cat > p12b_with_open.py <<'EOF' def g():     with open('/dev/null') as f:         f.read() 
          2s bash   rm -rf /tmp/dbgx; mkdir -p /tmp/dbgx; cd /tmp/rprobes; for wt in /tmp/base2 /home/runner/work/ail-ci/ail-ci; d

## full suite
test_ail_pre59

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed `test_ail_pre59` by routing direct/keyword negative `r` through a computed value, matching pre75's accepted compile-time literal refusal while preserving pre59's runtime-`ValueError` coverage.

Verified `test_ail_pre59`, `pre52`, `pre75`, `pre126`, `pre137` all pass; `update_manifest.py --check` is clean. Committed as `63c4dd1`.
[cost $0.0000, opencode tokens {"total": 587962, "input": 34458, "output": 2513, "reasoning": 6479, "cache.write": 0, "cache.read": 544512}]
    tool time: bash 1.3 min, edit 0.0 min
         55s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest -q test_ail_pre75 test_ail_
         12s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && cd AIL_CURRENT && timeout 900 python
          8s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_pre59 2>&1 | tail -80
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat 8d76aad | head -40 && git show --stat e8527c3 | head -60
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git diff --stat && git diff -- AIL_CURRENT/test_ail_pre59.py | head -120
          0s bash   pwd && ls -la && git status && git log --oneline -10
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_pre59.py AIL_CURRENT/MANIFEST.json && git c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T03:17:28Z
