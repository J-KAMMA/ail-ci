# job job-pre252-10260447  started 2026-10-25T19:52:01Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":550,"duration_api_ms":428,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":529,"duration_api_ms":407,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-pre252-10260447` as `97ce780`.

- Cause: builtins outside `_BUILTIN_VALUE_ARITY` were refused as values. Added variadic `max`/`min` adapters, `callable`/`hash` fixed-arity values, builtin-aware `type(x).__name__`, and source-direction max/min comparison errors.
- Probes: 12 match CPython on both builds (`maxmin`, `maxmin_shapes`, `direct_badcmp`, `fixed_values`, `nan`, `setargs`, `module_rebind`, `rebind_max`, `tuple_wrapper*`, test candidates); 2 are named refusals (`maxmin_attr`, `builtin_values`).
- Tests on final commit: `test_ail_pre252` (2), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skipped), `test_ail_corpus_findings3` (2) — all pass.
- Records updated: `DIFFERENCES.md`, both `DEVLOG.md` files, `ail_check.MODULES`, `ci_shards.json`, `MANIFEST.json` (`--check` passes).
[cost $0.0000, opencode tokens {"total": 9010229, "input": 322350, "output": 27605, "reasoning": 43058, "cache.write": 0, "cache.read": 8617216}]
    tool time: bash 14.0 min, edit 0.0 min, write 0.0 min
        378s bash   for t in test_ail_pre252 test_ail_safetynet test_ail_files test_ail_corpus_findings3; do echo "=== $t"; python
        101s bash   python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -20
         93s bash   cat > /tmp/probes/gen_pre252.py <<'PY' from pathlib import Path cases = {  'max': 'f = max\nprint(f(3, 1))',  
         59s bash   for p in /tmp/probes/pre252_*.py; do echo "=== $(basename "$p")"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep 
         41s bash   for p in /tmp/probes/pre252_*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | tail -5; done
         24s bash   cat > /tmp/probes/pre252_maxmin.py <<'PY' class Box:     pass  box = Box() box.f = max xs = [min] d = {"m": ma
         21s bash   cat > /tmp/probes/pre252_maxmin_shapes.py <<'PY' class Box:     pass  def use_default(g=max) -> int:     retur
         13s bash   for p in /tmp/probes/pre252_maxmin.py /tmp/probes/pre252_direct_badcmp.py /tmp/probes/pre252_fixed_values.py; 

## review 0 failed to run: [cost $0.0000, opencode tokens {}]     tool time:  (cut off after 60 minutes) 

## review 0
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-25T22:37:11Z
