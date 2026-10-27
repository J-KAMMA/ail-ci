# job job-rbrbpre278-10271620  started 2026-10-27T07:23:18Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"0a587bcc-3516-4a8c-8f73-e91d0bf0a9b2","session_id":"f848b83f-d366-4be1-bf3a-75f7b19f12b5"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"8da82a6b-d5f8-4fb7-84ff-153100dd44bb","session_id":"c2be9303-769b-4b00-a268-868bd8c8023b"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `e47a896` on `job-rbrbpre278-10271620`.

Re-applied the accepted pre278 change: added `refuse_field_method_call` (with scoped name resolution and bound-method refusal) to `pyfront.py`, wired it into both typed entries and the general emitter, added `test_ail_pre278.py`, registered it, and updated DEVLOG/DIFFERENCES/manifest. Existing pre279 behaviour was preserved.

Verification:
- Probes (both builds via `cmp.sh`): 6 matched CPython — `p_direct`, `p_routes`, `p_inherited_self`, `p_noncallable`, `p_unrelated`, `p_shadow_scopes`; 6 refused by the pre278 name — `p_base_refusal`, `p_bound_self`, `p_bound_routes`, `p_bound_dict_alias`, `p_bound_builtin`, `p_shadow_branch`.
- Tests: `test_ail_pre278` 8 OK; `test_ail_pre279` 7 OK; `test_ail_safetynet` 5 OK; `test_ail_files` 18 OK (1 skipped); `test_ail_corpus_findings3` 2 OK.
- `tools/diff_ids.py` is absent on this tree. `tools/update_manifest.py` was run; `--check` exits 0.
[cost $0.0000, opencode tokens {"total": 1016780, "input": 46993, "output": 7637, "reasoning": 6630, "cache.write": 0, "cache.read": 955520}]
    tool time: bash 5.6 min, write 0.0 min, edit 0.0 min
        219s bash   printf '%s\n' test_ail_pre279 test_ail_safetynet test_ail_files test_ail_corpus_findings3 | xargs -P2 -I{} bas
         74s bash   python3 AIL_CURRENT/test_ail_pre278.py 2>&1 | tail -30
         18s bash   cd /tmp/probes && ls p_*.py | xargs -P2 -I{} bash -c 'echo "=== {} ==="; bash ~/tools/cmp.sh /tmp/probes/{} /h
         18s bash   cd /tmp/probes && rm -f out_*.txt && ls p_*.py | xargs -P2 -I{} bash -c 'bash ~/tools/cmp.sh /tmp/probes/{} /h
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-rbpre278-10270752 2>&1 | tail -5
          0s bash   grep -n "test_ail_pre278" AIL_CURRENT/MANIFEST.json | head; python3 -m py_compile AIL_CURRENT/python/pkg-v12/p
          0s bash   git add AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_CURRENT/python/pkg-v12/pyc.py AIL_
          0s bash   python3 tools/update_manifest.py; python3 tools/update_manifest.py --check; echo "check:$?"; git status --shor

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: job-rbrbpre278 re-apply

**What the change really does (one line):** adds `refuse_field_method_call` (`python/pkg-v12/pyfront.py:548`) and calls it from both typed entries (`pyc.py:531`, `pyfunc.py:34816`) and the general emitter (`pyboxed2.py:11734`, `allow_owners=True`), plus the test module/registration/docs/manifest. The 401-line function and 401-line test are byte-identical to the accepted `job-rbpre278-10270752` diff; only import context and DEVLOG/DIFFERENCES text differ.

**Probes** (`/tmp/rprobes`, both builds, `~/tools/cmp.sh`, HEAD vs `/tmp/base`):

| probe | HEAD | base |
|---|---|---|
| direct, routes (arg/list/dict/attr/alias), inherited, self, unrelated, shadow, global alias, lambda arg, plain func, nested field, only-method, only-field, classcall, empty, edges 1–5 | same stdout / exit as CPython | same |
| base method + subclass field; bound self/arg/dict/builtin | named refusal (`also stores an instance field named`) | wrong output/exit, or unrelated refusal name |
| noncallable field | same stdout / exit as CPython (exit 1) | default build wrong exit/output |

No case on HEAD differs while base matches, so the refusal pass introduces no false refusal in these shapes. `--debug-dir` of a no-feature program (`p_empty`) is byte-identical (`sha256` of `program.c` equal); only temp paths differ. No runtime/codegen change, so icount is not applicable.

**Tests (HEAD e47a896):** `test_ail_pre278` ok, `test_ail_pre279` ok, `test_ail_safetynet` ok (3 modules, 0 failed). `tools/update_manifest.py --check` exits 0; `tools/diff_ids.py` is absent. Pre279 behaviour preserved.

**Claims:** probes-verified; tests-verified (the 3 run); `diff_ids` absent verified; manifest `--check` verified. Not verified: the worker's exact probe filenames, `test_ail_files` and `test_ail_corpus_findings3` counts (not re-run, per reviewer scope).

Pre-existing differences: none remaining in the probes run.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 678441, "input": 40960, "output": 4785, "reasoning": 8056, "cache.write": 0, "cache.read": 624640}]
    tool time: bash 3.2 min
        114s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date +%H:%M && python3 ../tools/par_check.py -j 2 test_ail_p
         28s bash   cd /tmp/rprobes && date +%H:%M && ls p_*.py | xargs -P2 -I{} bash -c 'bash ~/tools/cmp.sh /tmp/rprobes/{} /tmp
         20s bash   cd /tmp/rprobes && date +%H:%M && ls p_*.py | xargs -P2 -I{} bash -c 'bash ~/tools/cmp.sh /tmp/rprobes/{} /hom
         19s bash   cd /tmp/rprobes && date +%H:%M && ls p_*.py | xargs -P2 -I{} bash -c 'echo "=== {} ==="; bash ~/tools/cmp.sh /
         11s bash   cd /tmp/rprobes cat > p_edge1.py <<'EOF' d = {"z": 1} class C:     def __init__(self):         self.f = {"a": 
          1s bash   cd /tmp && rm -rf ddbase ddhead && mkdir ddbase ddhead && cp /tmp/rprobes/p_empty.py ddbase/p.ail && cp /tmp/r
          0s bash   cd /home/runner/work/ail-ci/ail-ci && cat ~/tools/cmp.sh; echo ---; ls tools/ | head; git worktree add /tmp/ba
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git fetch https://github.com/J-KAMMA/ail-ci.git job-rbpre278-10270752 2>

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T08:32:42Z
