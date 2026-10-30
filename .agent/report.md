# job job-fz203-10300647  started 2026-10-29T22:18:54Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"83db6edc-8d56-45cb-8334-736474d05b9c","context_usage_ratio":0.019628},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"8582e2dd-57c8-4a15-9630-c6e802b1aec9","session_id":"010d3b5f-92dc-46c9-82f6-b380fe50d159"}

## worker report 0
[model qoder/DeepSeek-Flash]
**No reproduction on this tree — changed nothing, as instructed for step 1.**

**Confirmation (reproducer saved at /tmp/probes/fz203.py; `python3 lab/fuzz/gen.py 2075517896 -o` is byte-identical to the supplied program):**

| configuration | result |
|---|---|
| `bash ~/tools/cmp.sh /tmp/probes/fz203.py $PWD` (build `g` = `AIL_UNIFIED_FORCE=1`, `d` = default) | `same stdout`, exit 7, empty stderr (both) |
| `python3 lab/fuzz/run.py --start 2075517896 --count 1 --modes default,ir` (exact daily-fuzz harness/env) | `same` in both modes, no findings dir |
| `AIL_IR=0`, `AIL_IR=0 AIL_UNIFIED_FORCE=1`, `AIL_UNIFIED=1`, `AIL_IR=1 AIL_UNIFIED=1`, fuzzer env (`PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0`, exe run with `AIL_IR=1`), `bash ~/tools/cmpu.sh` | identical stdout and exit 7 in every case; all builds produced the same exe sha256 |
| 20 executions of each of the 7 builds | 16 `-29` lines every time, never 32 |

**Cause signature:** the finding's AIL output had **32** `-29` lines vs CPython's **16** (exactly double, moving `'3.5'` from line 19 to line 35). That is the `except IndexError: print(-29)` inside `h0` running twice per call — the doubling does not occur on this tree; `h0` is called 16 times and prints once per call in all builds. Since `AIL_IR` defaults to `1` (`pyc.py:859`), the fuzzer's "default" and "ir" modes are the same build, so no mode is untested.

**Self-check probes** (all via `cmp.sh`, both builds): `fz203` (full program), `fz203_p1` (printing handler in a callee under a multi-type `try`, nested loops), `fz203_p2` (out-of-range list-item write reached through a dataclass attribute, `%`/`join` formatting), `fz203_p3` (callee raises `IndexError`, caller handler catches) — all match CPython stdout and exit code on both builds.

**Other differences seen:** none. No new `DIFFERENCES` row, no DEVLOG entry, no `test_ail_fz203.py`, no manifest run and no commit, because nothing was changed; the working tree is untouched (only the pre-existing untracked `.agent/pipeline.md` is present).

FINAL VERDICT: NOCHANGE  2026-10-29T22:24:22Z  (the worker changed nothing; no review was run)
