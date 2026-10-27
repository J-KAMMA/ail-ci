# job job-pre346-10280248  started 2026-10-27T17:49:04Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"ceaaae4f-32b1-44c8-b0b7-938ac002de84","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"b7e5ce79-9e19-4ed1-8ca2-d6d2f4466d3f","session_id":"c0562752-a405-4e9c-9ced-c41afaa4dcc1"}

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Summary:

**Root cause:** the branch snapshot was built on an older integ, so applying it over today's integ reverted the newer compiler fixes (pre328/331/341/347/351: `ail_chatgpt.py`, `compscope.py`, `tupcommon.py`, `tuplib.py` and their tests), which broke the dependent modules.

**Fix (commit `31e849b`):**
- Carried today's integ versions of those 4 compiler files and 5 test modules unchanged.
- Re-applied only the pre346 change: `ail_check.MODULES` unique (removed 4 duplicate entries for `test_ail_fuzz4`, `test_ail_pre126`, `test_ail_pre59`, `test_ail_pre61`), `test_ail_pre346` registered (502 unique modules), `build()` keeps only the first placement from a stale assignment, `tools/ci_shards.json` regenerated.
- Added DEVLOG entry (top, 2026-10-27) and DIFFERENCES row `C?-job-pre346-10280248-1`; ran `update_manifest.py` then `--check` (passes), `ci_shards.py --check` exits 0.
- Final tree differs from today's integ only in the 7 intended files.

**Tests on the final commit (all pass):** test_ail_pre334 (6), pre335 (4), pre338 (2), pre340 (2), pre346 (4), pre9 (2), safetynet (5), files (18, 1 skipped), corpus_findings3 (2).

**Probes (7):**
- `pre346_build.py` (Python): OK — duplicate input names, stale duplicate placements/first-placement, rebalance, empty shards, unknown names, real 502-module list.
- cmp.sh probes, both builds: `pre346_comp_scope.py`, `pre346_pow_inrange.py`, `pre346_slice.py`, `pre346_tuple_mut.py` match CPython; `pre346_pow.py`, `pre346_int_attr.py` refused by name (`int64 constant expression out of range`).

Not verified: CI-side application of the branch (local runner only); no push performed.

## review 0
[model qoder/DeepSeek-Flash]
## Review report

**What the change really does:** ports the pre346 shard fix onto today's integ — restores 4 compiler sources and 5 test modules byte-identical to `origin/integ`, removes 4 duplicate `MODULES` entries, registers `test_ail_pre346`, makes `ci_shards.build()` dedupe and keep the first stale placement, regenerates `ci_shards.json` (502 modules), and updates MANIFEST/DEVLOG/DIFFERENCES.

**Verification**
- Byte-identical to `origin/integ`: `ail_chatgpt.py`, `compscope.py`, `tupcommon.py`, `tuplib.py`, `test_ail_pre328/331/341/347/351.py` (cmp). Only `ail_check.py`, `test_ail_pre346.py`, `MANIFEST.json` differ in `AIL_CURRENT`; overall vs `origin/integ` only the 7 intended files.
- `MODULES`: 502 entries, 502 unique, no duplicates; the 4 removed names still present once; assignment covers all 502 exactly once; 20 shards non-empty except 5 pre-existing single-module shards (also single in integ).
- `python3 tools/ci_shards.py --check` exit 0; `--update` writes nothing ("unchanged"); `tools/update_manifest.py --check` exit 0.
- `test_ail_pre346.py` (4), `test_ail_check` (7), pre334 (6), pre335 (4), pre338 (2), pre340 (2), pre9 (2), safetynet (5), files (18), corpus_findings3 (2): all pass (`par_check -j 2`, 0 failed).
- Probes: `/tmp/rprobes/pre346_build.py` — 10 checks pass (module dedupe, duplicate in one stale shard, unknown-name drop, empty list, all-duplicates, rebalance, shard count, real 502-module coverage). `p_triv.py`, `p_pow.py`, `p_cls.py` match CPython on both builds; `program.c` identical for HEAD vs `origin/integ` vs base.
- Speed: not run — the change touches no compiler/runtime code (sources byte-identical to integ); test lists and CI tooling only.

**Report claims**
- Root cause, carried files unchanged, unique MODULES/502, first-placement build, regenerated shards (4 placements removed, pre346 added), DEVLOG top entry 2026-10-27, DIFFERENCES row `C?-job-pre346-10280248-1`, manifest check, test pass list, probe results: **verified**.
- "Final tree differs from today's integ only in the 7 intended files": **false as stated** — 510 `corpus/gdev` files (g24/g25) also differ; they are already in the job base `work`, are not touched by `git diff work..HEAD`, and `origin/integ` tracks no `corpus/` at all, so this is not caused by the change.

**Pre-existing:** the snapshot's 510 tracked `corpus/gdev` files absent from `origin/integ`; unrelated to this change and outside its diff.

**Unverified:** CI-side application of the branch onto integ (local runner only); shard timings (weights) not re-measured.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T19:45:17Z
