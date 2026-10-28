# job job-rbrbpre409-10282004  started 2026-10-28T11:05:25Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"c1ecaa94-946c-444c-ad32-fd3498e1ba16","session_id":"2ca597ab-d805-4fe4-9396-96fc5160b11f"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"9441a369-1f98-4b0c-8abe-d4b263c5e93d","session_id":"fe94111d-e4d5-42fd-ab53-7cdebca49f49"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

- Re-applied pre409 behavior; the code fix was already present via pre419 (`ail__raise_class_subscript` + early `AIL_T_CLASS` checks), so kept that instead of adding the older unreachable helper.
- Added `AIL_CURRENT/test_ail_pre409.py` (4 tests), registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
- Updated `DEVLOG.md`, `DIFFERENCES.md`, and `AIL_CURRENT/MANIFEST.json`.
- `tools/diff_ids.py` is not present on this tree.
- Probes: `p409_index`, `p409_slice`, `p409_routes`, `p409_names`, `p409_controls` — all match CPython on both builds.
- Final commit `92ce6b3`; tests on it: `test_ail_pre409`, `test_ail_pre419`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed.
- `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0000, opencode tokens {"total": 1132856, "input": 48374, "output": 6304, "reasoning": 7330, "cache.write": 0, "cache.read": 1070848}]
    tool time: bash 13.3 min
        407s bash   python3 tools/par_check.py -j 2 test_ail_pre409 test_ail_pre419 test_ail_safetynet test_ail_files test_ail_cor
        298s bash   python3 tools/par_check.py -j 2 test_ail_pre409 test_ail_pre419 test_ail_safetynet test_ail_files test_ail_cor
         32s bash   for p in /tmp/probes/p409_*.py; do printf '%s: ' "$(basename "$p")"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | gr
         24s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_check.py') s=p.read_text() old="    'test_ai
         20s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes'); p.mkdir(exist_ok=True) p.joinpath('p409_index
         14s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes') widths=[1, 95, 96, 100, 199, 200, 201, 300, 10
          3s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-rbpre409-10281622 && git diff cd8ecf6d260729665aedb24a811e
          0s bash   python3 tools/ci_shards.py --update && python3 tools/ci_shards.py --check; python3 tools/update_manifest.py &&

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** Adds `AIL_CURRENT/test_ail_pre409.py`, registers it in `ail_check.MODULES` and `tools/ci_shards.json`, and records DEVLOG/DIFFERENCES/MANIFEST. No runtime or codegen change: the class-subscript behaviour already exists on this tree via pre419 (`ail__raise_class_subscript` + early `AIL_T_CLASS` checks in `ail_op_getitem`/`ail_op_getslice`), which is equivalent for the pre409 feature. The report says this accurately.

**Probes** (`/tmp/rprobes`, both builds, HEAD vs base `/tmp/base`):
- `p1_index`: class index via int/0/-1/str/None/float, subclass, alias, argument, list item, attribute, dict value/dict.get, and 95/96/100/199/200/201/300-char names — HEAD = CPython = base.
- `p2_slice`: basic/empty/negative/None/step/all/neg-step slices plus alias/argument/list/attribute/dict routes — HEAD = CPython = base.
- `p3_unicode`: non-ASCII class name refused by name (`v2 runtime is ASCII-only`) on base too.
- `p4_nofeature`: lists/dicts/strings/`__getitem__` instances/assignment/IndexError/KeyError — HEAD = CPython = base; no codegen changed, so feature-free C is unchanged by construction.
- `p5_del`: `del A[1]` differs (`doesn't` vs CPython `does not`) identically on HEAD and base.
- Worker's own `p409_{index,slice,routes,names,controls}` re-run: all match CPython on both builds.

**Tests on HEAD** (`par_check.py -j 2`): `test_ail_pre409`, `test_ail_pre419`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.

**Claims:** all verified; `tools/diff_ids.py` indeed absent. Root `DEVLOG.md` is the current cumulative log (superset of `AIL_CURRENT/DEVLOG.md`), so the entry location is correct.

**Pre-existing (identical on base, non-blocking):** `del A[1]` says `doesn't support item deletion` instead of CPython's `does not`; non-ASCII class-name source is refused by name.

**Unverified:** speed — not applicable, the diff touches no runtime/codegen.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 587235, "input": 33717, "output": 6762, "reasoning": 8260, "cache.write": 0, "cache.read": 538496}]
    tool time: bash 7.0 min, write 0.0 min
        302s bash   date; python3 ../tools/par_check.py -j 2 test_ail_pre409 test_ail_pre419 test_ail_safetynet test_ail_files tes
         46s bash   date; for p in /tmp/rprobes/p*.py; do b=$(basename "$p" .py); for t in HEAD BASE; do if [ $t = HEAD ]; then wt
         33s bash   for p in /tmp/probes/p409_*.py; do echo "== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E 's
         17s bash   date; for p in /tmp/rprobes/p*.py; do b=$(basename "$p"); echo "===== $b HEAD"; bash ~/tools/cmp.sh "$p" "$PWD
         10s bash   python3 - <<'PY' from pathlib import Path names=['A'*95,'A'*96,'A'*100,'A'*199,'A'*200,'A'*201,'B'*300] lines=
          9s bash   ls DIFFERENCES.md AIL_CURRENT/DIFFERENCES.md 2>&1; cat > /tmp/rprobes/p5_del.py <<'EOF' class A:     pass   tr
          0s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-rbpre409-10281622 2>&1 | tail -3; echo ----; git diff cd8e
          0s bash   cat ~/tools/cmp.sh; echo ====; git rev-parse work; git worktree add /tmp/base work 2>&1 | tail -3

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T12:46:35Z
