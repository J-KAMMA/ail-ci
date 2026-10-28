# job job-pre422-10281644  started 2026-10-28T07:44:41Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"2aeb813f-e7e1-411a-bb4c-b3c4d25eb891","session_id":"70e7a6a9-f6ce-439a-af2b-76440d657f83"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"55f9e842-3a53-46cc-9f41-1f44f51d4497","session_id":"5bb8c853-5a0e-44b2-bd89-c1e1d9c9a3b9"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the pre-existing slice-error name difference.

- Reproduced: `del MyErr()[0:1]` / `MyErr()[0:1] = []` printed `'exception' ...` on both builds; CPython prints `'MyErr' ...`.
- Cause: `safetyrt.py`'s `ail2s_setslice` used `ail_type_name(c.tag)`; now uses `ail__raise_item_tname`.
- Probes in `/tmp/probes/pre422` (6 programs, both builds via `cmp.sh`): all match CPython — direct/step/None/negative slices, subclass, long 210-char name, alias/argument/list-item/attribute/dict-value routes, builtin names, uncaught error.
- Added `test_ail_pre422.py`; registered in `ail_check.MODULES` and `tools/ci_shards.json`.
- Final commit `6965825`; manifest `--check` passes.
- Tests on final commit: `test_ail_pre422`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 375s (j=2).
- Left unrelated untracked `.agent/pipeline.md` alone; no push.
[cost $0.0000, opencode tokens {"total": 2632871, "input": 97009, "output": 9114, "reasoning": 10652, "cache.write": 0, "cache.read": 2516096}]
    tool time: bash 7.7 min, edit 0.0 min, write 0.0 min
        377s bash   python3 tools/par_check.py -j 2 test_ail_pre422 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
         24s bash   cd /tmp/probes/pre422 && cat > p_slice_builtins.py <<'EOF' def show(label, fn):     try:         fn()     exce
         14s bash   cd /tmp/probes/pre422 && cat > p_slice_del.py <<'EOF' class MyErr(Exception):     pass  class Sub(MyErr):     
         13s bash   AIL_NO_CACHE=1 PYTHONUTF8=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-types' python3 -B -m unittest -v te
         13s bash   cd /tmp/probes/pre422 && for p in p_slice_del.py p_slice_routes.py; do echo "=== $p ==="; bash ~/tools/cmp.sh 
          9s bash   cd /tmp/probes/pre422 && for p in p_slice_del.py p_slice_routes.py; do echo "=== $p ==="; bash ~/tools/cmp.sh 
          7s bash   cd /tmp/probes/pre422 && python3 - <<'PY' p='p_slice_more.py' s=open(p).read() s=s.replace("show('del_alias', 
          0s bash   git show --stat --oneline e4e1d6d; echo ====; git show --stat --oneline $(git log --format=%H -- AIL_CURRENT/t

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** `safetyrt.SLICE`'s non-list `ail2s_setslice` now formats its TypeError through `ail__raise_item_tname` instead of `ail_type_name`, so exception/ordinary class names replace the tag names in slice assignment/deletion errors. This matches the report.

**Probes** (written in `/tmp/rprobes`, both builds):
- p1 exception class through direct, alias, argument, list item, attribute, dict value, subclass, plain class; `None`/negative/step/empty slices: HEAD matches CPython; base prints `'exception'`/`'instance'`.
- p2 builtin non-list values (`int`, `float`, `NoneType`, `tuple`, `str`, `bytes`, `range`, `bool`) plus bounds: HEAD matches except the pre-existing `bytes` deletion wording.
- p3 class-name lengths 1/199/200/201/210/300: HEAD matches CPython including the 200-character cap; base differs.
- p4 actual `slice` objects, stepped/negative slices, and routes: HEAD matches; base differs.
- p5 valid list slice operations and aliases: unchanged and matches.
- p6 feature-free program (`--debug-dir`): `program.c` byte-identical to base; only temp paths in `native_report.json` differ.
- p7 builtin exception classes and p8 non-ASCII class name: named compile-time refusals on both builds, acceptable.

**Pre-existing:** `del b'ab'[0:1]` prints `'bytes' object doesn't support item deletion` on both HEAD and base where CPython prints `... does not ...`; identical on base, not caused here.

**Tests:** `test_ail_pre422`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed, 265s. `update_manifest.py --check` exits 0.

**Claims:** reproduction, cause, six worker probes (rerun: all match), registration/commit/manifest/tests: verified. Untracked `.agent/pipeline.md` left alone: verified. Minor false detail: DEVLOG says the test has “3 programs”; it has 2 source programs (each built on both paths). Cosmetic only.

Speed not measured: the edit is on an error-only path, not hot code.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 664702, "input": 38759, "output": 6252, "reasoning": 8235, "cache.write": 0, "cache.read": 611456}]
    tool time: bash 6.9 min
        267s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre422 t
         40s bash   cd /tmp/rprobes; for p in p1 p2 p3 p4 p5; do echo "===== BASE $p ====="; bash ~/tools/cmp.sh /tmp/rprobes/$p.p
         37s bash   cd /tmp/probes/pre422; for p in *.py; do echo "=== HEAD $p"; bash ~/tools/cmp.sh /tmp/probes/pre422/$p /home/r
         29s bash   cd /tmp/rprobes cat > p1.py <<'EOF' class MyErr(Exception):     pass class Sub(MyErr):     pass class Plain:  
         22s bash   cd /tmp/rprobes; for p in p1 p2 p4 p5; do echo "===== HEAD $p ====="; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /
          9s bash   cd /tmp/rprobes cat > p7.py <<'EOF' def show(label, fn):     try:         fn()     except Exception as e:     
          8s bash   cd /tmp/rprobes cat > p8.py <<'EOF' def show(label, fn):     try:         fn()     except Exception as e:     
          3s bash   rm -rf /tmp/dbg_head /tmp/dbg_base; cd /tmp/rprobes; AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AI

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T09:22:32Z
