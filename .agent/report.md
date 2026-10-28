# job job-stdlib10-10290221  started 2026-10-28T17:32:22Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"f63fcb17-c548-4d3f-b697-a7f77bdc6fbd","context_usage_ratio":0.019633},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"8d46009c-8601-462a-bd32-de115d5bc49c","session_id":"06d184fb-476c-45f3-bfd6-3ecc1fd0bc50"}

## worker report 0
[model qoder/DeepSeek-Flash]
{"type":"result","subtype":"error_during_execution","duration_ms":5995366,"duration_api_ms":5356067,"is_error":true,"num_turns":109,"stop_reason":"tool_use","total_cost_usd":0,"total_credits":6.182172712228572,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"032f7bf8-1fc8-4360-91c3-89acb4883537","context_usage_ratio":0.030128},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":6.182172712228572}},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_tools","fast_mode_state":"off","uuid":"213bdc1a-e333-4787-ba99-c4402d500bac","session_id":"5073d197-bbf9-4a07-9ef6-9394170b48d9"}

(cut off after 100 minutes)

## review 0 failed to run: [model qoder/DeepSeek-Flash] {"type":"result","subtype":"error_during_execution","duration_ms":529515,"duration_api_ms":200097,"is_error":true,"num_turns":24,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":2.0518302054285713,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"536e948c-706e-42c5-a19a-5bdf7e9cb88c","context_usage_ratio":0.085688},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":2.0518302054285713},"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"fa8c3637-fc4d-461f-b322-cec28707d730","session_id":"3f408855-0a51-4548-9d75-36928d9e9b39"} 

## review 0
[model qoder/DeepSeek-Flash]
{"type":"result","subtype":"error_during_execution","duration_ms":343,"duration_api_ms":223,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"cd395fb0-f04f-44ab-aac3-2af7abbd8519","session_id":"f6b7d08d-ae38-41ee-aa50-8e3b87e898d4"}

FINAL VERDICT: ERROR  2026-10-28T19:23:40Z
