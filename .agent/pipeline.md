# job job-pre346-10280033  started 2026-10-27T15:34:05Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"25d63f74-6329-4fdf-a9da-efdc2c162086","session_id":"885cabf2-53b3-4134-bcdc-69f96c5983db"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"64260ce2-b668-4b26-8720-7611a4cd2485","session_id":"11782df1-89a0-4035-ad7f-17f96b71a4aa"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed `d522979` on `job-pre346-10280033`.

**What was wrong:** the pre346 branch was written on an older integ. Ported it onto today's integ (kept the newer compiler files/test modules), deduplicated `ail_check.MODULES`, registered `test_ail_pre346`, added stale-placement dedupe in `build()` (including rebalance), and regenerated `ci_shards.json`/`MANIFEST.json`.

**Tests on final commit** (`par_check.py -j 2`, 0 failed, 279s):
- test_ail_pre346, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3
- Earlier on the same code: pre334/pre335/pre338/pre340/pre9 also passed.
- `tools/ci_shards.py --check` and `tools/update_manifest.py --check` exit 0.

**Probes** (`/tmp/probes/`):
- `p346_shards_build.py`: duplicate modules, stale/duplicate placements, empty input, rebalance — all pass, one placement each.
- `p346_repo_state.py`: module/json duplicates empty, sets exact, pre346 registered — pass.
- `p346_no_feature.py` via `cmp.sh`: both builds match CPython stdout/exit.

`test_ail_safetynet` could not be made to fail even on the pre-fix branch here, so I could not reproduce that part; the port removes the reverts of today's compiler changes, and it passes on the integrated result.
[cost $0.0000, opencode tokens {"total": 6248595, "input": 124096, "output": 14456, "reasoning": 28123, "cache.write": 0, "cache.read": 6081920}]
    tool time: bash 31.7 min
        385s bash   cd AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre346 test_ail_safetynet test_ail_
        281s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo manifest_check=$?; cd AIL
        234s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 2>&
        140s bash   cd /tmp/inttest5/AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_safetynet 2>&1 | tail -60
        139s bash   cd /tmp/inttest3/AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_safetynet 2>&1 | tail -100
        138s bash   cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre346 test_ail_safetynet 2>&1 | ta
        136s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_safetynet 2>&1 | tail -80
        136s bash   cd /tmp/inttest2/AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_safetynet 2>&1 | tail -60

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does** (net of today's integration `f47df17`): `AIL_CURRENT` compiler files are byte-identical to the integration; the only deltas are `ail_check.MODULES` losing its 4 duplicates (`test_ail_fuzz4`, `test_ail_pre126`, `test_ail_pre59`, `test_ail_pre61`), `test_ail_pre346` registered, `ci_shards.build()` deduplicating its input and stale placements, regenerated `ci_shards.json`/`MANIFEST.json`, plus DEVLOG/DIFFERENCES. This matches the report. The large `work..HEAD` diff is the old-lineage base; it does not revert anything.

**Probes**
- `/tmp/rprobes/probe_shards.py`: empty input, duplicate input, stale dup in same/cross shard, unknown stale name, more old shards than `n`, rebalance with dup – every case places each module once, none lost.
- `/tmp/rprobes/shard_union.py`: 20 shards, 497 modules, 497 distinct, 0 missing, 0 duplicated.
- `/tmp/rprobes/sets2.py`: old→new MODULES loses nothing, gains only `test_ail_pre346`.
- `cmp.sh` p1_plain / p2_intconv / p3_excargs on HEAD and `/tmp/base`: both builds match CPython stdout+exit.
- `--debug-dir` C for those three: identical HEAD vs integration (only `native_report.json` paths differ).
- Integration base `tools/ci_shards.py --check` exits 1 with the four duplicates; HEAD exits 0. `build(prev=data)` exactly reproduces `ci_shards.json`; `update_manifest.py --check` exits 0.

**Tests on HEAD** (`par_check.py -j 2`): test_ail_pre346 ok (0.1s), test_ail_safetynet ok (140.4s), 0 failed. Safetynet also passes on the integration base (5 tests, OK, 139s), so the reported failure is not reproducible, as the report says.

**Claims**: ported-onto-integ verified; MODULES deduplicated verified; pre346 registered verified; stale-placement dedupe (incl. rebalance) verified; regenerated json/manifest verified; safetynet-not-reproducible verified. Unverified: pre334/335/338/340/pre9 and test_ail_files/test_ail_corpus_findings3 (not re-run; compiler identical to integ). No icount: nothing on a hot path changed (CI metadata only).

**Pre-existing**: none attributable; the duplicate MODULES entries the change removes were the integration's actual failure.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T17:42:16Z
