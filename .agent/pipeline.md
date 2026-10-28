# job job-pre392-10280857  started 2026-10-27T23:57:42Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"cbfe9ec8-58f2-4191-b422-345d042f24cb","context_usage_ratio":0.019625},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16193914417142855}},"permission_denials":[],"fast_mode_state":"off","uuid":"f4f61e8c-fcdd-4cfc-9022-9e27b1a7a877","session_id":"aeef5308-df90-4ce1-a72b-0a1c2d4f3f10"}

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Committed as `e74f83e` on `job-pre392-10280857`.

**Difference reproduced (both builds, before the change):** `show(d["k"])` / `show(items[0])` with text read from a bound container (`d = {"k": "9223372036854775808"}`, `items = ["9223372036854775808"]`) and converted by the helper's `int(v)` printed the bignum in CPython but stopped with `integer overflow` on both builds.

**Cause / fix:** the wrapper-int branch in `_Int64CallChecker.visit_Call` applied only `_outside_int64_float`, while the direct `int(...)` branch also applies `_int_conversion_outside_int64` (text/bytes). Both branches now share `_check_conversion` / `_refuse_out_of_range` (AIL_CURRENT/ail_chatgpt.py:1139).

**Probes** (`/tmp/probes/pre392`, each via `cmp.sh`, both builds):
- Refused by name (`int64 constant expression out of range`): r01 dict value, r02 list item, r03 negative, r04 whitespace/underscore/plus, r05 bytes, r06 class+instance attribute, r07 wrapper/passthrough chain, r08 alias, r09 dict.get + default, r10 tuple negative index, r11 int key, r21 function-local container, r23 keyword multi-parameter.
- Match CPython: r12 in-range/boundaries, r13 invalid-text ValueError, r16 float in-range, r22 container mutated to in-range, r25 print-only, r26 reassigned binding, r27 dynamic in-range, r29 printing a container.
- r15 float control still refused (`int() of a float outside int64`). r24 refused by the pre-existing `int`-shadowing subset rule.
- Unchanged pre-existing differences (disclosed, not caused by this change): r17/r28 nested container (`int(v[0])`), r18 container mutated to an out-of-int64 value (run-time `integer overflow`), r30 `int(list)` TypeError wording.

**Tests on the committed tree** (`-j 2`): test_ail_pre392, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 4 modules, 231 s, 0 failed.

**Records:** new `test_ail_pre392.py` (3 tests, 14 refused + 7 matching programs + float control) registered in `ail_check.MODULES` and `tools/ci_shards.json`; DIFFERENCES row `C?-job-pre392-10280857-1`; DEVLOG entry at top; `update_manifest.py` run and `--check` passes.

The case where the item is itself a list/dict (`d = {"k": [1e300]}; show(d["k"])` with `int(v[0])`) is not fixed: it keeps the nested/mutable-container limitation pre322 already documented, and I did not claim it works.

## review 0
[model qoder/DeepSeek-Flash]
All checks are done (started 00:19, finished 00:26 UTC; no new probes needed).

## Review: pre392 wrapper-int text range check

**What the change really does (one line):** in `_Int64CallChecker.visit_Call` (AIL_CURRENT/ail_chatgpt.py:1139), the wrapper-`int(<param>)` branch now runs the same `_check_conversion` as the direct `int(...)` branch — float refusal plus `_int_conversion_outside_int64` (text/bytes) — factored into `_check_conversion`/`_refuse_out_of_range`; nothing else changes.

**Probes** (all via `bash ~/tools/cmp.sh`, both general and default builds, on HEAD and `/tmp/base` = `work`):

| probe | content | HEAD | base |
|---|---|---|---|
| r15_exact | task repro `d["k"]`, `items[0]` (positive big text) | refused by name | `integer overflow` |
| r02 | negative `-9223372036854775809` via dict | refused by name | `integer overflow` |
| r05 | inline container literal `show({...}["k"])` | refused by name | `integer overflow` |
| r07 | big text via function-return chain / `outer("big")` | refused by name (direct literal) | `integer overflow` |
| r01 | int64 min/max, `+000…`, underscores, whitespace, bytes, class attr | matches CPython | matches |
| r03 | alias mutated to in-range **before** the call | matches (no spurious refusal) | matches |
| r04 | no-conversion helper / other param / rebound param | matches | matches |
| r10 | for-target, walrus, item-store rebinding to in-range | matches (no spurious refusal) | matches |
| r08/r12 | wrapper in-range / no feature: generated `.c` via `--debug-dir` | byte-identical to base | — |

**Pre-existing (identical on base, do not block):**
- r06/r09 `bytearray` text (direct and via wrapper) → runtime `integer overflow` on both; CPython prints the bignum.
- r11 dict built by item stores (`d["k"] = big`) → runtime trap on both.
- r13/r14 nested container (`int(v[0])`, float and text) → runtime `integer overflow` on both, which the report explicitly discloses.

No new false refusals or crashes found; every new refusal is an out-of-int64 constant expression, which the task explicitly permits ("refuse the construct by name at compile time").

**Report claims:**
- Reproduced on both builds pre-change — *verified* (r15/r02/r05 base).
- Cause/fix (wrapper branch only had float check; shared `_check_conversion`) — *verified* from the diff, matches description.
- Probe results r01–r30 — *corroborated* by my independent probes; their `/tmp/probes/pre392` files were not inspected.
- Tests: I ran on HEAD `test_ail_pre392` (36.8s) and `test_ail_safetynet` (103.3s) with `-j 2` — both **ok**; `files`/`corpus_findings3` not rerun (per review scope).
- New test has 14 refused + 7 matching + 1 float control, registered in `ail_check.MODULES` and `ci_shards.json`; DIFFERENCES row `C?-job-pre392-10280857-1`; DEVLOG entry dated 2026-10-28; `update_manifest.py --check` rc=0 — *verified*.

**Speed:** compile-time-only change; accepted programs emit byte-identical C, so no runtime/icount impact. No gdev run needed.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T01:40:57Z
