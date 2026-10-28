# job job-pre393-10280904  started 2026-10-28T00:05:19Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> vice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"9eee66ac-51f1-4d81-9766-6a343e00ce4c","context_usage_ratio":0.019628},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.1619677170285714}},"permission_denials":[],"fast_mode_state":"off","uuid":"3c933a1d-2f6a-4f76-9de2-e6595bb2d45a","session_id":"753ac524-4aab-4025-bf8a-bf6e7b52c287"}

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Fixed the first still-differing case from the pre370 review (its `r09`, the default-argument route) by name at compile time.

**Change** (`AIL_CURRENT/ail_chatgpt.py`): `_Int64CallChecker` now receives `_wrapper_int_defaults` (positional defaults aligned from the tail, plus keyword-only defaults) and falls back to the default expression when a call omits the argument. The direct-`int()` and wrapper routes now share `_check_int_value`, so a constant string outside int64 through a wrapper also gets the named conversion refusal instead of a runtime stop.

**Probes** (`/tmp/probes/pre393`, both builds via `cmp.sh`):
- Refused by name (12): `r09_default` (recorded case), `d01_kwonly`, `d02_positional`, `d06_negative`, `d07_module_const`, `d08_list_item`, `d09_dict_value`, `d10_attr`, `d11_str`, `d14_chain`, `d17_arg_str_out`, `d19_direct_str`.
- Match CPython (7): `d03_inrange_arg`, `d04_not_called`, `d05_inrange_default`, `d12_boundary` (9.2e18), `d13_nonint_use`, `d16_inrange_str`, `d18_starred`.
- Reproduced but unchanged (the other recorded routes, left alone per the one-cause instruction): `r10_computed_index`, `r22_list_arg`, `r23_returned_list`, `p08_container_item`, `p09_dict_value` — both builds still compile and stop with `integer overflow`.

**Records/tests**: added `AIL_CURRENT/test_ail_pre393.py` (11 refused + 7 matching programs), DIFFERENCES row `C?-job-pre393-10280904-1`, DEVLOG entry, registered in `ail_check.MODULES` and `tools/ci_shards.json`; `update_manifest.py` run and `--check` passes.
Final-state tests (`par_check.py -j 2`): test_ail_pre393, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 4 modules, 297 s, 0 failed.

Committed as `9ab8a88` on `job-pre393-10280904`; not pushed.

## review 0
[model qoder/DeepSeek-Flash]
All required checks are done. Here is my review.

## What the change does

`_wrapper_int_defaults` (ail_chatgpt.py:978) maps each wrapper parameter that flows into `int()` to its default expression; `visit_Call` (ail_chatgpt.py:1174-1176) falls back to that default when the call omits the argument and runs the shared `_check_int_value`. Compile-time check only; generated C is unchanged (verified: `program.c` byte-identical to base for two no-default programs).

## Defect (caused by this change)

The default expression is evaluated with `self._value(...)`, which looks up names in **the call-site's local scope** (`value_scopes[-1]`), but a default is evaluated at def time in the **module** scope. A call from a function/method that locally binds a name used by the default refuses a program that CPython and the base both run correctly.

Probe `/tmp/rprobes/p01_shadow_scalar.py`:
```python
BIG = 5
def f(x=BIG):
    return int(x)
def g():
    BIG = 1e300
    return f()
print(g())
```
Expected (CPython and base, both builds): builds succeed, prints `5`, exit 0.
Actual (HEAD, both builds): compile fails with `p.ail:10:12: int() of a float outside int64: 1e+300` — a value that never reaches `int()`.
Same failure for `/tmp/rprobes/p04_shadow_container.py` (`M = [5]` module default, `M = [1e300]` local in caller) and `/tmp/rprobes/p08_default_and_call_in_method.py` (identical inside a method body). Root cause is at ail_chatgpt.py:1176: defaults must be evaluated in the module scope (`value_scopes[0]`/`known`), e.g. by precomputing their constant value in `_wrapper_int_defaults`.

## Claims check

- Refusal of `r09_default` (the recorded first case) via defaults: **verified** (worker's `r09_default.py` refused by name on both builds).
- 13 of the worker's probes refused, 7 match: verified by running all 26; report says 12 refused, it is 13 (`d15_float_boundary` is also refused, unmentioned).
- "Constant string outside int64 through a wrapper is refused": verified (`d11`, `d17`, `d19`).
- "Other recorded routes unchanged (`r10`, `r22`, `r23`, `p08`, `p09`)": verified — base also exits 1 with `integer overflow`, so pre-existing.
- "No exit-status regression attributable to the change": **false** — see defect.
- Manifest `--check`, DEVLOG top entry, DIFFERENCES row, Co-Authored-By: verified. `test_ail_pre393` + `test_ail_safetynet`: `2 modules, 0 failed`.

## Pre-existing (do not block)

- `p07_explicit_shadow_arg.py` (explicit argument resolved in call-site scope) refuses on base too.
- `p05_attr_mutated.py` (class attribute reassigned after def) fails to build on base too.
- `r10`, `r22`, `r23`, `p08_container_item`, `p09_dict_value` stop at runtime with `integer overflow` on both base and HEAD.

## Unverified

- Speed/icount: not applicable — change is compile-time only and touches no generated C.

VERDICT: FIX

1. Default expressions are resolved in the call-site scope, so a local name shadowing a name used by a default yields a false refusal: `/tmp/rprobes/p01_shadow_scalar.py` (also `p04_shadow_container.py`, `p08_default_and_call_in_method.py`) — expected: builds, prints `5`, exit 0 (as CPython and the base); actual: compile fails, `int() of a float outside int64: 1e+300`. Fix: evaluate defaults in the defining/module scope at ail_chatgpt.py:1176.

## worker report 1
[model qoder/DeepSeek-Flash]
Fixed the reviewer's defect and committed as `8b2ca62` on `job-pre393-10280904`.

**Root cause:** `_wrapper_int_defaults` returned default AST nodes that `visit_Call` evaluated via `_value` in the call-site's local scope. Defaults are evaluated at def time in module scope, so a caller-local shadow (`BIG = 1e300` inside `g()` while the module has `BIG = 5`) produced a false refusal.

**Fix:** `_wrapper_int_defaults` now takes the module `known` map, `passthrough` and `attributes` and stores each default's constant value resolved with module-scope lookup; `visit_Call` checks that stored value when the argument is omitted. No generated-C changes.

**Probes** (`/tmp/probes`, both builds via `cmp.sh`, 13 total):
- Match CPython (exit 0, same stdout): `s01_shadow_scalar`, `s02_shadow_list_item`, `s03_shadow_in_method`, `s04_shadow_kwonly`, `s05_shadow_dict_value`, `s06_shadow_attribute`, `s07_shadow_explicit_argument`, `s08_shadow_in_range_default`, `s12_shadow_nonconstant_default`, `s13_default_and_call_same_scope`.
- Refused by name on both builds (CPython prints the big integer): `s09_shadow_out_of_range_default`, `s10_shadow_negative_default`, `s11_shadow_string_default`.

**Tests on final commit:** `test_ail_pre393 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 27 tests, 0 failed, 1 skipped. `update_manifest.py` run, `--check` passes. DEVLOG entry added (no new DIFFERENCES row needed; existing `C?-job-pre393-10280904-1` remains accurate). `.agent/pipeline.md` left untracked as found.

## review 1
[model qoder/DeepSeek-Flash]
Review complete. Timing: started 00:33, finished 00:39 UTC (well inside the 35-minute box).

## What the change really does

`_wrapper_int_defaults` (AIL_CURRENT/ail_chatgpt.py:978) now resolves each `int()`-wrapper parameter default to a constant with the module-scope `known` map instead of returning the AST node for call-site evaluation; `visit_Call` (ail_chatgpt.py:1173) checks that constant when the argument is omitted. The direct `int()` and wrapper checks were merged into `_check_int_value`. It only raises or leaves codegen alone; it does not emit C.

## Probes (`/tmp/rprobes`, both builds via `cmp.sh`, base `/tmp/base` = `work`)

Refused by name on HEAD where base overflowed at run time (the fix): `p03_neg_index` (`M[-1]`), `p07_dict_get_default` (`D.get("k",0)`), `p09_alias_list`, `p10_attr_instance` (`c.v`), `p12_posonly`, `p15_kwonly_pos_default` — CPython prints the big integer, so refusal is the intended outcome.

Match CPython on HEAD: `p05_rebind_after_def` (`BIG=5; def f(x=BIG); BIG=1e300; print(f())` → 5; the name has two stores so it is not folded), `p16_param_shadow` (callee-local name shadowed by a parameter), `p17_local_lambda_shadow`, `p19_inrange_bool_minint` (bool/INT64_MIN defaults), `p20_inrange_kwonly_string`.

Pre-existing (identical on base, not caused by the change): `p04_mutate_after_def` (list escapes, both overflow), `p06_class_attr_mutated` and `p11`/`p01`/`p02` (`C.v = ...` / `**kwargs` are "not in the subset"), `p08_int_default_literal` (already refused by the int-literal check), `p18_default_calls_int_direct` (direct check).

One new but acceptable refusal: `p13_dead_branch` (`return 0` before `return int(x)`) prints 0 on base and is refused now — a named, compile-time refusal of unreachable `int()`, consistent with the documented dead-code refusal family and the brief's "named refusal is acceptable" rule.

No feature use: `p14_no_feature` compiled on HEAD and base; `program.c` in both `--debug-dir` trees is byte-identical (only temp paths in `native_report.json` differ).

## Report claims

- Root cause / fix description: verified against the diff and the shadowing tests (`s01`–`s13` cases are in `MATCH`/`REFUSED` and pass).
- "No generated-C changes": verified (`p14`).
- r09 default now refused by name: verified.
- `update_manifest.py --check`: passes (silent, exit 0). DIFFERENCES row and DEVLOG match observed behaviour.
- Tests on HEAD: `test_ail_pre393` 54.4s ok, `test_ail_safetynet` 103.3s ok. Unverified: the worker's "27 tests, 1 skipped" figure (I did not run `test_ail_files`/`test_ail_corpus_findings3` per the review rule).
- Not re-probed: the other recorded routes (r10/r22/r23/p08/p09) — they are the argument route, untouched by this diff; the report only claims them as still differing.

Speed: not applicable; the change is compile-time only and accepted programs emit identical C.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T01:54:12Z
