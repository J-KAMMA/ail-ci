# job job-rbpre304-10271604  started 2026-10-27T07:09:51Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"510d9ba3-89b9-4a5f-b4b1-f4d96d6e01e7","session_id":"32f414ba-85d2-42a8-a12a-afb0598771f4"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"c0d68304-91d9-4556-adf7-c94abccdc96f","session_id":"be3f8c71-9089-4f98-93f2-7d5ee738cf0c"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `23fbeba` on `job-rbpre304-10271604` (7 files, +445/−24).

- Re-applied pre304, merging its class-body name map with the tree's newer class-attribute refusal path; both existing fixes kept.
- `tools/diff_ids.py` is absent on this tree; `tools/update_manifest.py` ran and `--check` passes.
- Probes (12, both builds): 9 match CPython — `attr_types`, `comp_body_global`, `comp_outer`, `duplicate_later_global`, `inherit_override`, `method_then_attribute`, `negative_zero_bool_empty`, `routes_instance`, `widths`; 3 refused by name — `comp_body_noglobal`, `method_rebind`, `property_rebind`.
- Final-commit tests all OK: `test_ail_pre304`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; also `test_ail_pre279`, `test_ail_pre283`, `test_ail_fuzz29`, `test_ail_dunders`, `test_ail_typed_inherit`, `test_ail_virtual_dispatch`.
- `tools/ci_shards.py --check` still reports the pre-existing duplicate entries (`test_ail_fuzz4`, `pre126`, `pre61`); pre304 was added with weight 19.1.
[cost $0.0000, opencode tokens {"total": 3500875, "input": 78855, "output": 12098, "reasoning": 10114, "cache.write": 0, "cache.read": 3399808}]
    tool time: bash 19.9 min, write 0.0 min, edit 0.0 min
        224s bash   cd /home/runner/work/ail-ci/ail-ci; (python3 AIL_CURRENT/test_ail_corpus_findings3.py > /tmp/probes/out/cf3.lo
        163s bash   cd /home/runner/work/ail-ci/ail-ci; (python3 AIL_CURRENT/test_ail_dunders.py > /tmp/probes/out/dunders.log 2>&
        141s bash   cd /home/runner/work/ail-ci/ail-ci; (python3 AIL_CURRENT/test_ail_safetynet.py > /tmp/probes/out/safetynet.log
        130s bash   cd /home/runner/work/ail-ci/ail-ci; (python3 AIL_CURRENT/test_ail_pre304.py > /tmp/probes/out/final_pre304.log
        101s bash   cd /home/runner/work/ail-ci/ail-ci; for a in test_ail_pre283 test_ail_fuzz29 test_ail_dunders; do :; done; (py
        100s bash   time python3 AIL_CURRENT/test_ail_pre304.py -v 2>&1 | tail -25
         79s bash   time python3 AIL_CURRENT/test_ail_pre304.py -v 2>&1 | tail -25
         60s bash   cd /tmp/probes; for p in pre304r_*.py; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/wor

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete.

**What the change really does:** re-applies pre304's class-body name map (`ctx.class_locals`, `_class_attr_locals`, `_class_attr_value`/`_cached_class_attr` owner plumbing, comprehension outer-iterable scoping) on top of the newer `_class_attr_through_class_refusal` path, keeping both. It also re-adds `test_ail_pre304.py`, registry/manifest/shard entries, DEVLOG and one DIFFERENCES row.

**Claims checked**
- Verified: commit `23fbeba`, 7 files, +445/−24; only the intended files changed.
- Verified: both fixes coexist — the name map is present and the tree's newer class-attribute refusal path is retained in `_init_class_attrs` and `expr_Attribute` (pyboxed2.py:5757, 6780).
- Verified: `tools/diff_ids.py` does not exist anywhere in the tree; `update_manifest.py --check` exits 0.
- Verified: pre304 probe results (12 files in `/tmp/probes`) reproduced exactly — 9 match CPython on both builds; `comp_body_noglobal`, `method_rebind`, `property_rebind` refuse with `name 'x' is not defined`.
- Verified: `ci_shards.py --check` reports the same duplicate warning (`test_ail_fuzz4`, `pre126`, `pre61`) on base and HEAD; pre304 weight is 19.1.
- Unverified: the extra 6 test modules the report mentions (pre279, pre283, fuzz29, dunders, typed_inherit, virtual_dispatch) were not re-run, per the instruction to run only targeted modules.
- No false claims found.

**My probes (28, both builds unless noted):** `r1` inherited-base name (CPython NameError, refused on both), `r2` class read, `r3` duplicate/reassign, `r4` forward global, `r5` containers, `r6` strings, `r7` negative/bool, `r8` method-after, `r9` method rebind (CPython TypeError, refused both), `r10` comp body global, `r11` shared list mutation, `r14` mixed reads, `r15` arg/list/dict/attr routes, `r25` multi-generator scoping, `r26` nested comprehension, `r27` comprehension conditions, `r28` class redefinition, `r29` class alias, `r30` reassignment order — all match CPython or are refused by name. `r12/r13` nested class, `r17/r20` lambda/method-default class reads, and `r28` redefinition are refused identically on base (pre-existing).

**C unchanged:** `--debug-dir` `program.c` is byte-identical to base for `corpus/gdev/g00_000.py` and a plain class/function probe.

**Tests on HEAD (`-j 2`):** `test_ail_pre304`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (350 s). Manifest check passes.

**Speed:** no runtime hot path changed; generated C is unchanged for programs that do not use the feature.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1332802, "input": 36690, "output": 7621, "reasoning": 15403, "cache.write": 0, "cache.read": 1273088}]
    tool time: bash 9.9 min
        352s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 AIL_CURRENT/../tools/par_check.py -j 2 test_ail_pre304 test_
         70s bash   cd /tmp/rprobes; date; for p in r*.py; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p /home/runner/wo
         59s bash   cd /tmp/probes; date; for p in pre304r_*.py; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runn
         17s bash   cd /tmp/rprobes; for p in r12_nested_func_class.py r13_nested_func_class_outer.py; do echo "===== $p HEAD"; ba
         17s bash   cd /tmp/rprobes; for p in r1_inherit_base_name.py r9_method_rebind_read.py; do echo "===== $p HEAD"; bash ~/to
         16s bash   cd /tmp/rprobes; cat > r21_lambda_instance_global.py <<'EOF' x = 100 class C:     x = 3     f = lambda: x o = 
         16s bash   cd /tmp/rprobes; cat > r17_lambda_global.py <<'EOF' x = 100 class C:     x = 3     f = lambda: x     y = f() p
         14s bash   cd /tmp/rprobes; cat > r25_multigen.py <<'EOF' x = 2 class C:     x = 3     a = [i for i in range(2) for j in 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T09:06:42Z
