# job job-cov44-10291433  started 2026-10-29T05:46:37Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"81cbd6b9-0fe5-49c9-9ac7-d918215bc3ce","session_id":"2a510249-e7a5-494a-9aeb-409f475f8e8e"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"30b87cb7-91be-4d08-bd4f-166bdcc37eeb","session_id":"ea4d9daf-8e05-4596-ac99-6d498d75c440"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `05021ad`.

**Result**
- Corpus refusal census over 219 programs: **24 → 21** on default and **24 → 21** with `AIL_UNIFIED_FORCE=1`.
- Supported the most frequent non-import refusal: nested generator expressions consumed in place (`join`, `sum`, `list`, `sorted`, etc.).
- The 3 affected corpus programs (`glm/deepseek t432`, `deepseek t172`) now build and match CPython on all three corpus inputs, both builds.
- Unsafe nesting remains a named refusal: saved inner generators, `for` iterables, `next()`, `any()`, `all()`.

**Tests** (final commit): `test_ail_cov44`, `test_ail_pre42`, `test_ail_pre41`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 31 run, OK (1 skipped: no zig). Manifest `--check` passes.

**Probes** in `/tmp/probes/p44_*.py` (14): 9 consumed-in-place probes match CPython on both builds (`nested_join`, `nested_sum_join`, `nested_sum`, `nested_sorted`, `nested_list`, `nested_sideeffects`, `nested_routes`, `nested_three`, `nested_inner_cond`); 5 unsafe probes are refused by name on both builds (`saved_inner`, `saved_outer`, `for_outer`, `next_outer`, `any_outer`).
[cost $0.0559, opencode tokens {"total": 4985515, "input": 143866, "output": 16003, "reasoning": 17198, "cache.write": 0, "cache.read": 4808448}]
    tool time: bash 30.7 min
        725s bash   cd /tmp/cov44 && ls src/*.ail | xargs -P2 -I{} /tmp/cov44/compile_one.sh {} d && ls src/*.ail | xargs -P2 -I{}
        614s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_cov44 test_ail_pre42 test_ai
        224s bash   cat > /tmp/cov44/compile_one.sh <<'EOF' #!/bin/bash f=$1; mode=$2; out=/tmp/cov44/out b=$(basename "$f" .ail) 
         72s bash   cd /tmp/cov44 && ls src/*.ail | xargs -P2 -I{} /tmp/cov44/compile_one.sh {} g python3 - <<'PY' import pathlib,
         57s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p44_*.py; do echo "===== $(basename $p)"; bash ~/to
         56s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p44_*.py; do echo "===== $(basename $p)"; bash ~/to
         52s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_cov44
         19s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg

## review 0 skipped: only -1 minutes left

FINAL VERDICT: ERROR  2026-10-29T10:43:11Z
