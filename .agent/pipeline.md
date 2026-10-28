# job job-rbpre409-10281622  started 2026-10-28T07:27:53Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"0bd5b42a-830b-43d5-b8fd-45b312b52543","session_id":"a236ee3b-7639-4d7a-835f-e58af749c54c"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"e3f2bd1d-c8ee-4fb1-8874-77383c359df0","session_id":"197c7a77-c8dc-4751-876f-8eccce659930"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied pre409 on top of the current tree and committed as `497a19a`.

- Adapted the class-subscript error helper to the current `ail__raise_item_tname` runtime, including dynamic buffer and 200-character cap.
- Added `test_ail_pre409.py`, registered it in `ail_check.MODULES`, updated DEVLOG/DIFFERENCES.
- `tools/diff_ids.py` does not exist in this tree, so it could not be run.
- `python3 tools/update_manifest.py` and `--check`: pass.
- Tests on final commit: `test_ail_pre409`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass.
- Probes `/tmp/probes/p409_short_routes.py` and `/tmp/probes/p409_long_names.py`: both builds match CPython exactly.
[cost $0.0000, opencode tokens {"total": 1044613, "input": 41950, "output": 6887, "reasoning": 2752, "cache.write": 0, "cache.read": 993024}]
    tool time: bash 7.8 min, edit 0.0 min, write 0.0 min
        269s bash   python3 tools/par_check.py -j 2 test_ail_pre409 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
        184s bash   python3 tools/par_check.py -j 2 test_ail_pre409 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
          9s bash   for p in /tmp/probes/p409_short_routes.py /tmp/probes/p409_long_names.py; do echo "=== $p"; bash ~/tools/cmp.s
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre409-10281141 2>&1 | tail -5
          1s bash   git status && git log --oneline -5 && ls
          0s bash   git add AIL_CURRENT/test_ail_pre409.py AIL_CURRENT/DEVLOG.md AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v
          0s bash   git status --short; echo ===; python3 tools/update_manifest.py --check; echo "CHECK:$?"; echo ===; git diff --
          0s bash   git diff AIL_CURRENT/MANIFEST.json; python3 tools/update_manifest.py --check 2>&1 | tail -20; echo "EXIT:${PIP

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds `ail__class_subscript_error` to the v2 runtime and routes `AIL_T_CLASS` reads in `ail_op_getitem` / `ail_op_getslice` through it, so `A[1]` / `A[1:2]` say `type 'A' is not subscriptable` (name capped at CPython's 200 characters). This matches the fetched pre409 diff; the worker adapted the helper's raise/format calls to the current tree without changing semantics.

**Probes** (`bash ~/tools/cmp.sh <probe> $PWD`, both `g` and `d` builds; results identical on both):

| probe | result |
|---|---|
| p1_long: names 95,96,100,199,200,201,300; index+slice | matches CPython |
| p2_routes: plain, subclass, `_AilDeque_Foo`, alias, arg, list, tuple, attribute, dict item/get; index+slice | matches CPython |
| p4_controls: store, del, instance `__getitem__` | store/instance match; `del` differs (see Pre-existing) |
| p6_nofeature: ordinary program | matches CPython; `--debug-dir` C differs from base only by the added runtime helper |
| p7b_aug: store, slice-store, `A[0] += 1` | matches CPython; base differed on the augmented read (improvement) |
| p3/p3b builtin classes, p5 unicode name, p8 nested class, p9 `__name__` assignment | refused by name, identical on base |
| worker's `/tmp/probes/p409_long_names.py`, `p409_short_routes.py` | both match CPython |

**Pre-existing.** `del A[1]`: AIL says `'type' object doesn't support item deletion`, CPython says `does not`; byte-identical on `/tmp/base`, unchanged by this diff.

**Report claims.** All verified: commit `497a19a`; helper uses a dynamic buffer with a 200-char cap; test registered; DEVLOG/DIFFERENCES/manifest updated (`--check` passes); `tools/diff_ids.py` absent from work, FETCH_HEAD and HEAD; tests pass on final commit — `test_ail_pre409`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (4/4, 179s, `-j 2`). Not checked: speed (error-only path, no hot code).

Minor note: the new DIFFERENCES row keeps the original `C?-job-pre409-10281141-1` id rather than the current branch id; consistent with "apply the same change", so not a defect.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 994143, "input": 45383, "output": 7235, "reasoning": 13397, "cache.write": 0, "cache.read": 928128}]
    tool time: bash 4.4 min
        181s bash   cd AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre409 test_ail_safetynet te
         14s bash   date; for p in /tmp/rprobes/p1_long.py /tmp/rprobes/p2_routes.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p"
         11s bash   date; echo "=== BASE p4"; bash ~/tools/cmp.sh /tmp/rprobes/p4_controls.py /tmp/base; for p in /tmp/rprobes/p5_
          9s bash   date; for p in /tmp/probes/p409_long_names.py /tmp/probes/p409_short_routes.py; do echo "===== $p"; bash ~/too
          8s bash   cat > /tmp/rprobes/p7b_aug.py <<'PY' class A:     def __init__(self):         self.x = 1   def main():     try
          7s bash   date; for p in /tmp/rprobes/p3_builtin.py /tmp/rprobes/p4_controls.py; do echo "===== $p"; bash ~/tools/cmp.sh
          6s bash   cat > /tmp/rprobes/p3b_exc.py <<'PY' class MyError(Exception):     pass   def main():     try:         Excepti
          6s bash   cat > /tmp/rprobes/p3_builtin.py <<'PY' def main():     try:         int[1]     except TypeError as e:        

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T09:02:51Z
