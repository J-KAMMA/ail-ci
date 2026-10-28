# job job-rbpre411-10281757  started 2026-10-28T08:57:46Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"701bf6d4-e4c6-4a48-afc2-d67d3ad3a059","session_id":"ea23e473-6412-459c-8585-8332ffb003c7"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"c3a4cc5c-1823-4f92-b5cc-dc6c4690e845","session_id":"a6909bdf-51ac-45b6-9f96-15228ffbc08b"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied pre411 on top of the integ tree, preserving pre412's float/str IntEnum normalisation.

- Commit: `3fd7394` (8 files, +393/−15)
- Changes: non-int `__index__` validation, member-value index path, reserved `_AilIntEnum` refusal, new `test_ail_pre411`, records.
- Tests on final commit: `test_ail_pre411`, `test_ail_pre412`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 29 tests, OK (1 skipped).
- Manifest: `update_manifest.py` pinned the new test, `--check` exit 0.
- Probes: `p1_nonint`, `p2_enum_direct`, `p3_pre412_values`, `p5_es` matched CPython on both builds; `p4_reserved_{direct,index,chain,routes,nested}` were refused by name on both builds.
- `tools/diff_ids.py` does not exist in this tree, so it could not be run. No push.
[cost $0.0000, opencode tokens {"total": 2253447, "input": 90453, "output": 12077, "reasoning": 11269, "cache.write": 0, "cache.read": 2139648}]
    tool time: bash 16.1 min
        585s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -X utf8 -B -m unittest -q test_ail_pre411 test_ail_p
        272s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -X utf8 -B -m unittest -q test_ail_pre411 test_ail_p
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_nonint p2_enum_direct p3_pre412_values; do echo "===== $p ==
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p3_pre412_
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p3_pre412_
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p3_pre412_
         11s bash   cat >/tmp/probes/p5_es.py <<'EOF' from enum import IntEnum class ES(IntEnum):     ONE = "1"     TWO = "2" prin
          7s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p3_pre412_

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Re-applies pre411: `ail_syntax` refuses a user `ClassDef` named `_AilIntEnum`; `dunderrt` validates a non-int `__index__` result and adds an IntEnum/IntFlag member fast path that indexes by the stored `value` (ignoring an overridden `__index__`); new `test_ail_pre411`, records, manifest. Beyond the original diff, the member fast path also normalises float/str/nested member values through `int()` — the intended merge with this tree's pre412 (`__index__` is `int(self.value)`). Report describes this correctly.

**Probes** (`/tmp/rprobes`, `cmp.sh` HEAD vs base, both builds):
- `p1_index_results` — str/float/None/list `__index__`, bool, negative, direct IntEnum/IntFlag with overridden `__index__`, member chain, via arg/attr/item/dict: HEAD both builds = CPython. Base differed.
- `p2_pre412_values` — float/str/negative/zero member values through all routes: both = CPython.
- `p3_reserved` / `p8_reserved_legal_mention` — name only mentioned, or different class: both = CPython; `p6`/`p7` reserved class direct/nested: refused by name on both builds (base misindexed / used generic refusal).
- `p4_sideeffects` — `__index__` call count, raising `__index__`, slices, no-feature: both = CPython.
- `p5_unrelated` — no feature: both = CPython. Default-build `--debug-dir` C differs from base only by the added helper and the getitem instance-key body; user program code unchanged.
- `p11_composite` — IntFlag composite and routes: both = CPython (base differed).
- `p12_setitem` — identical failure on base and HEAD (pre-existing).
- `p13_nested_negative` — identical failure on base and HEAD (pre-existing enumlib limitation).
- `p9_strvals` / `p10_floatrange` — see pre-existing.

**Pre-existing / out of scope.**
- `p9`: CPython rejects `IntEnum` member `"0x10"` at class creation; both HEAD and base accept the class. HEAD's index error changes from base's `ValueError` to a generic `TypeError`; root divergence (class accepted) is pre-existing.
- `p10`: out-of-int64 float member (`2^63`) base traps `integer overflow`; HEAD gives `TypeError`, CPython gives `IndexError cannot fit ...`. pre412 explicitly leaves out-of-int64 uncovered; HEAD no longer crashes, so not a regression in severity.
- `p12`/`p13`/`p14`: identical on base (pre-existing setitem divergence, nested-enum-value limitation, and one unrelated compile refusal).

**Claims.** Commit `3fd7394`, 8 files, +393/−15 verified. Code changes verified. Tests on final commit: ran `test_ail_pre411 test_ail_pre412 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 5 modules, 0 failed (412s); exact 29/1-skipped count not checked. `update_manifest.py --check` exit 0. `tools/diff_ids.py` absent from the tree, so the worker's note is true. The worker's own `/tmp/probes` are not present, so those named results are unverified, but equivalent probes pass.

**Unverified.** Speed/icount (the new branch is guarded by `key.tag == AIL_T_INST`, so int-key hot paths are untouched); wider suite.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1864840, "input": 109705, "output": 8446, "reasoning": 16129, "cache.write": 0, "cache.read": 1730560}]
    tool time: bash 10.4 min
        414s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre
         55s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "########## $p"; bash ~/tools/cmp.s
         53s bash   cd /tmp/rprobes && cat > p11_composite.py <<'EOF' from enum import IntEnum, IntFlag  class F(IntFlag):     A =
         43s bash   cd /tmp/rprobes && cat > p9_strvals.py <<'EOF' from enum import IntEnum class E(IntEnum):     SP = " 2"     PL
         21s bash   cd /tmp/rprobes && cat > p13_nested_negative.py <<'EOF' from enum import IntEnum class Inner(IntEnum):     X =
         20s bash   cd /tmp/rprobes && cat > p6_reserved_class.py <<'EOF' class _AilIntEnum:     def __init__(self):         self.
         11s bash   cd /tmp/rprobes && cat > p14_mutate_value.py <<'EOF' from enum import IntEnum class E(IntEnum):     A = 1 xs =
          3s bash   cd /tmp/dbg_h && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_c

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T10:50:02Z
