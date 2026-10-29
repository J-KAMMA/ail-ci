# job job-cov36-10291014  started 2026-10-29T01:36:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"43876ebe-d669-4775-80ae-70d4314a33a1","session_id":"3b944f11-21dc-4b16-a0ed-b8b26a757fd2"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"dc493c22-2a92-488e-a58d-11b943ceb0dc","session_id":"75d5e0a7-3d09-47af-ac3f-5478d313fb7b"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0726, opencode tokens {"total": 8908872, "input": 99321, "output": 20220, "reasoning": 32211, "cache.write": 0, "cache.read": 8757120}]
    tool time: bash 84.6 min, edit 0.0 min
       1715s bash   sed 's#HERE = Path(.*#HERE = Path("/tmp/base")#' /tmp/cov36/scan.py > /tmp/cov36/scan_base.py; sed -i "s#/tmp/
       1490s bash   mkdir -p /tmp/cov36 /tmp/probes && cat > /tmp/cov36/scan.py <<'PY' import collections, json, os, re, subproces
       1082s bash   cd /tmp/cov36 && python3 run3.py | grep -v ' OK ' ; echo "--- scan current ---"; timeout 3000 python3 scan.py 
        426s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_cov36 test_ail_pre42 test_ail_p
         93s bash   cd /tmp/probes && cat > cov36_p3_eager_calls.py <<'PY' def main():     rows = [[3, 1], [2], []]     print(sort
         72s bash   cd /tmp/probes && for f in cov36_p*.py; do echo "===== $f ====="; bash ~/tools/cmp.sh /tmp/probes/$f /home/run
         67s bash   cd /tmp/probes && cat > cov36_p3_eager_calls.py <<'PY' def main():     rows = [[3, 1], [2], []]     print(sort
         32s bash   cat > /tmp/cov36/run3.py <<'PY' import os, subprocess, sys, tempfile from pathlib import Path HERE=Path('/home
(cut off after 100 minutes)

## review 0 skipped: only 42 minutes left

FINAL VERDICT: ERROR  2026-10-29T05:49:24Z
