# job job-pre340-10272149  started 2026-10-27T12:50:22Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"05389a72-3ff6-4520-a4c7-d5c167236f43","session_id":"45f6acd9-9be9-4121-8186-40d9e660f28c"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"8602c134-909a-4529-8cba-c66fd63dd21a","session_id":"9537c041-7787-4eaf-ae22-f7a704dce77a"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre-existing item from pre333: `int(Box(1e300).v)` where `__init__` stores its parameter directly now refuses by name on both builds (`int() of a float outside int64: 1e+300 (CPython makes a big integer)`) instead of overflowing.

Probes in `/tmp/probes/pre340`, both builds:
- 13 refused by name: direct, negative, keyword argument, default, second positional, module constant/list-item argument, instance name, alias, list/dict item, function argument, nested wrapper.
- 7 match CPython: in-range, literal class attribute, later field store, dynamic value, in-range wrapper, non-conversion use, mutated default.
- Baseline second item unchanged: `p12` general matches, default build still fails; `p15` matches both.

Commit `0229017`. Final-commit tests: `test_ail_pre340`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 282s, 0 failed. `update_manifest.py --check` passes. DEVLOG/DIFFERENCES updated.
[cost $0.0000, opencode tokens {"total": 4352120, "input": 121222, "output": 14001, "reasoning": 25409, "cache.write": 0, "cache.read": 4191488}]
    tool time: bash 15.1 min
        409s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre340 test_ail_pre306 test_ail_safetynet test_a
        284s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre340 test_ail_safetynet test_ail_files test_ai
         63s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre302 test_ail_pre311 2>&1 | tail -20
         37s bash   cd /tmp/probes/pre340; for p in p16*.py; do echo "===== $p"; out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/
         36s bash   cd /tmp/probes/pre340; for p in p16*.py; do out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-ci 2>&
         32s bash   mkdir -p /tmp/probes/pre340; cat > /tmp/probes/pre340/p16_attr_route.py <<'EOF' class Box:     def __init__(se
         18s bash   for p in /tmp/probes/pre340/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E 'cpython 
         15s bash   cd /tmp/probes/pre340 cat > p16u_no_int.py <<'EOF' class Box:     def __init__(self, v):         self.v = v pr

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `0229017` (pre340)**

**What the diff really does:** In `ail_chatgpt.py` the class-attribute fold now binds a constructor call to `__init__` parameters (positional, keyword, default, kw-only, alias) and reads `self.attr = param` at the call site; `_parameter_source` also follows `Class(arg).attr`. Effect is confined to the `int()`/int64 static check (nil or named refusal); codegen is untouched. Report description matches.

**Claims**
- Direct `int(Box(1e300).v)` now refused on both builds — verified (`p01` on HEAD: named refusal; base: `integer overflow`).
- 13 refusal routes (keyword, default, second positional, module const/list item, instance name, alias, list/dict item, argument, nested wrapper) — verified: `test_ail_pre340` enumerates exactly these and passes; spot probes `p05`, `p06`, `p11` refuse by name.
- 7 in-range/dynamic/later-store routes match CPython — verified via test plus `p07`, `p08`, `p12`, `p14`, `p18`.
- p12/p15 baseline unchanged — verified: `p12` general matches, default fails on base and HEAD; `p15` matches both.
- Commit/tests/manifest — verified (reran `test_ail_pre340`+`safetynet` 136 s and `test_ail_files`+`test_ail_corpus_findings3` 228 s, 0 failed; `update_manifest.py --check` exit 0).

**Pre-existing (identical on `/tmp/base`, not blocking)**
- `p04_starargs.py` (`__init__(self, v, *rest)`, `Box(1e300, 2)`): CPython big int, both builds `integer overflow`.
- `p09_annassign.py` (`self.v: float = v`): both overflow.
- `p10_rebind_in_init.py` (`v = int(v)` before store): both overflow.
- `p17`/`p19` custom `__setattr__`: base overflowed; HEAD refuses by name (acceptable, no regression).

**C/speed:** `program.c` byte-identical between HEAD and base for `g00_000`, `g04_028`, `g12_028` (only `native_report.json` temp paths differ); compile-time-only change, no runtime cost.

**Unverified:** none material; worker's `/tmp/probes/pre340` were spot-checked rather than all rerun (equivalent cases covered by `test_ail_pre340`).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1032156, "input": 66127, "output": 4732, "reasoning": 14609, "cache.write": 0, "cache.read": 946688}]
    tool time: bash 8.6 min
        230s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
        139s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre340 t
         57s bash   cd /tmp/rprobes && for p in p*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1 | grep -E 'cpyt
         29s bash   cd /tmp/rprobes && for p in p*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-c
         17s bash   cd /tmp/probes/pre340 && for p in p12_dict_item_overwrite.py p15_dict_update.py; do for w in /home/runner/work
         15s bash   cd /tmp && rm -rf dbg_h dbg_b && for f in g00_000 g04_028 g12_028; do mkdir -p dbg_h/$f dbg_b/$f; for w in /ho
         14s bash   cd /tmp/rprobes && cat > p17_dictsetattr.py <<'EOF' class Box:     def __init__(self, v):         self.v = v  
          5s bash   cd /tmp/rprobes && cat > p13_setattr.py <<'EOF' class Box:     def __init__(self, v):         self.v = v      

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T14:40:06Z
