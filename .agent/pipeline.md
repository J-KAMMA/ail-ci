# job job-fz197-10282231  started 2026-10-28T13:33:01Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"da4ce8c6-1ebf-4c3a-a66f-ca7af2690411","session_id":"e602d266-bfab-4081-b503-d615dd62fd16"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"6384659f-d6a9-407e-8008-668ffaf52544","session_id":"8fbd4415-4ba0-4077-9020-b5161a23eee1"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
No change made — the difference does not reproduce on this tree.

- Regenerated with `python3 lab/fuzz/gen.py 2075412095`; it is byte-identical to the attached program.
- CPython 3.12: exit 1, stdout ends at `125` (`IndexError: string index out of range`).
- AIL default and `AIL_IR=1`: both exit 1 with identical stdout and the same `IndexError`; `cmp.sh` also reports `g`/`d` same stdout.
- Cause was the try/`else` exception-routing bug already fixed on this tree by the `fz1` job (`DEVLOG.md` top entry, 2026-10-28), covered by `AIL_CURRENT/test_ail_fz1.py`.
- Probes on both builds: `fz197`, `else_idx`, `else_val`, `else_zero`, `else_ok` — all match CPython (stdout and exit code).
- No other differences seen. Working tree unchanged (only pre-existing untracked `.agent/pipeline.md`); nothing committed.
[cost $0.0000, opencode tokens {"total": 367506, "input": 35066, "output": 4023, "reasoning": 4577, "cache.write": 0, "cache.read": 323840}]
    tool time: bash 1.7 min
         39s bash   WT=/home/runner/work/ail-ci/ail-ci; for p in fz197.py else_idx.py else_val.py else_zero.py else_ok.py; do echo
         34s bash   WT=/home/runner/work/ail-ci/ail-ci; for p in fz197 else_idx else_val else_zero else_ok; do d=$(mktemp -d /tmp/
         25s bash   cd /home/runner/work/ail-ci/ail-ci && ls lab/fuzz && d=/tmp/fz197gen && rm -rf $d && mkdir -p $d && python3 la
          1s bash   cd /tmp/probes && for p in fz197.py else_idx.py else_val.py else_zero.py else_ok.py; do echo "===== $p"; bash 
          0s bash   pwd && ls && git status --short && git branch --show-current && ls ~/tools 2>/dev/null
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "AIL_IR\|AIL_UNIFIED_FORCE" lab tools .github | head -40
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && git diff --stat
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -n "else" DEVLOG.md | head -20; grep -rn "else clause\|else block\|

FINAL VERDICT: NOCHANGE  2026-10-28T13:36:38Z  (the worker changed nothing; no review was run)
