# job job-pre391-10280854  started 2026-10-27T23:55:51Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> vice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"1d64e0e0-aa77-4a2d-a3f4-ff45972d6f8f","context_usage_ratio":0.019625},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.1625106013142857}},"permission_denials":[],"fast_mode_state":"off","uuid":"4fb75568-ead6-494b-9516-0b419d498c6f","session_id":"266bb4d3-6bd1-4580-ba48-be7aac56bc9b"}

## worker report 0
[model qoder/DeepSeek-Flash]
Fixed the first still-differing item and committed it as `5638bc1` (branch `job-pre391-10280854`).

**What changed**
- `AIL_CURRENT/ail_chatgpt.py`: new `_check_int64_augmented_pow_constants`. The constant-power checks only resolve a name stored once, and `x **= 40` is itself a store, so `x = 10` was invisible. When the target's only other binding is one plain module/function-level assignment with a known int value, and nothing in the program can rebind it (second store, `global`/`nonlocal`, parameter, import, def, handler, match capture), a constant exponent whose exact result leaves int64 is refused by name. Program-wide store counting makes an intervening call safe: no code assigns the name, so no call can change it.
- Added `test_ail_pre391.py` (8 refused, 7 matching programs, both builds), DIFFERENCES row `C?-job-pre391-10280854-1`, DEVLOG entry; registered in `ail_check.MODULES` and `tools/ci_shards.json` (38.8).

**Probes (both builds, `cmp.sh`; `/tmp/probes/pre391`)**
- Refused by name (`int64 constant expression out of range`): `a01` recorded call case, `a02` no call, `a03` function-local, `a04` negative base, `a05` known-name exponent, `a06` alias binding, `a07` annotated binding, `a12` 2**63, `a15` unrelated parameter.
- Match CPython: `a08` `global` rebind then in-range power, `a09` `x **= 0` then plain power, `a10` boundaries (2**62, (-2)**63, 1/-1/0 huge exponents, float, negative exponent), `a11` later rebinding, `a13` INT64_MIN, `a14` loop.
- Unchanged pre-existing items: `b1_unpack` still traps `integer overflow` on both; `c1`/`c3` still "not in the subset" on both; `c2` default build refuses, general build matches. Values reached through a list item, attribute, dict value or function argument (`r01`–`r04`) still trap on both — the plain `x ** 40` form traps identically there (`q01`–`q04`), so that is a separate pre-existing folding limit, not this cause.

**Tests** (`par_check.py -j 2`, final tree): test_ail_pre391, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3, test_ail_pre351, test_ail_globals — 6 modules, 238 s, 0 failed. `tools/update_manifest.py` run; `--check` exits 0.

## review 0
[model qoder/DeepSeek-Flash]
Review complete. All probes and the two targeted modules are done (started 00:09, finished 00:14).

## What the change really does

`_check_int64_augmented_pow_constants` (ail_chatgpt.py:2032) runs at compile time only. For a `**=` on a plain name whose only other Store/Del is one plain module/function-level assignment with a statically known int base (and no rebinding construct: second store, `global`/`nonlocal`, import, def/class, handler, match capture, or an own-scope parameter), it evaluates `base ** const_exponent` exactly and raises `int64 constant expression out of range: …` when the result leaves int64. Program-wide store counting is what makes an intervening call safe. Matches the report.

## Claims

- Fixed the recorded case: **verified** — `p1` (`x = 10; print("hello"); x **= 40`) and `p2` (function-local with call) now fail on both builds with `int64 constant expression out of range`, where base compiled and trapped `integer overflow`.
- 8 refused + 7 matching programs, both builds: **verified** by reading `test_ail_pre391.py` and running it (ok, 17.6 s).
- Registered in `ail_check.MODULES`, `ci_shards.json` (38.8), DIFFERENCES row `C?-job-pre391-10280854-1`, DEVLOG at top: **verified**; `update_manifest.py --check` exits 0.
- Tests (6 modules, 238 s): only pre391 + safetynet re-run per scope (2 modules, 84 s, 0 failed); the other four are **unverified**.
- Other two recorded items unchanged: **verified** for the unpacking target (`b, = [10]; b **= 40` → `integer overflow` on HEAD and base) and for `globals()`/`exec` (both refuse "not in the subset" on base).
- No runtime/hot-code impact: **verified** — generated C for a non-feature program is byte-identical (sha256 `d3cc50c3…`, 84640 B) between HEAD and base; compile time on g12_036.py 4.27 s vs 4.33 s base.

## Probes (`/tmp/rprobes`, both builds via `cmp.sh`)

| probe | HEAD | base |
|---|---|---|
| p1 call-between | refused by name | trap (this is the fix) |
| p2 function-local | refused by name | trap |
| p3 no feature | same stdout, identical C | — |
| p4 `exec` rebind | refused | "not in the subset" |
| p5 `if False: x **= 40` | **refused** | matches CPython (prints 10) |
| p6 global rebind, in-range | matches CPython | — |
| p7 (-2)**63 = INT64_MIN | matches | — |
| p8 `True **= 40` | matches | — |
| p9 `2 **= -1` | matches | — |
| p10 dict-value base | trap | trap (pre-existing) |
| r_float_exp `**= 40.0` | matches | — |
| r_min INT64_MIN base | refused by name | trap |
| r_globals mutation | refused | "not in the subset" |
| b1 unpack target | trap | trap |
| q_dead_plain `if False: print(x ** 40)` | refused by name | **already refused on base** |

## Observations

- `p5`: the aug form is now refused even in unreachable code, where base and CPython both print 10. This is a new refusal, but it is exactly the pre-existing static policy: the *plain* `x ** 40` in the same dead branch is already refused on base (`q_dead_plain`). The file contains no reachability analysis anywhere, so this is consistent, not a new class of defect.
- p4/r_globals are programs base already rejects; only the diagnostic differs.

## Pre-existing (identical or already failing on base)

- dict/list/argument-held base (`p10`) still traps `integer overflow`; unpacking target still traps; `exec`/`globals()` remain outside the subset.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T01:25:23Z
