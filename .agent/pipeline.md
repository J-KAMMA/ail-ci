# job job-pre363-10280258  started 2026-10-27T17:59:19Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"4f312347-3a28-45fc-8538-a6bbc8cfb5c3","context_usage_ratio":0.019625},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"fafb4680-2b11-4a72-8ef8-e83581f69108","session_id":"cdb6a1ad-d1f8-42ff-a5da-91dc8bea26a2"}

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Final state: two commits on `job-pre363-10280258`, working tree clean except the harness log `.agent/pipeline.md`.

**What differed.** The pre347 reviewer's first recorded pre-existing item was the uncaught `RecursionError` for a class-body comprehension whose lambda uses a default (`[(lambda v=x: v)() for x in range(3)]`) or a shadowing parameter (`[(lambda x: x)(i) ...]`), where CPython runs the program. Cause: `call_value` expanded a class-construction branch for every call through a value; `_call_class` → `_class_attr_value` then re-evaluated the class attribute still being compiled, so `_init_class_attrs` recursed.

**Fix.** While a class-attribute value is being compiled, a literal-lambda callee skips the class branch (elsewhere emitted C is unchanged); a re-entrant class-attribute read is refused by name. `compscope`'s class-body guard now ignores lambda argument defaults (evaluated in the comprehension scope, so they follow the target's rename) and lambda-bound names, so the default/param forms match CPython instead of clobbering the enclosing name.

**Probes** (`/tmp/probes/pre363`, both builds, `cmp.sh`):
- Match CPython: p02–p08, p14, p15, p17–p21 (defaults, shadowed params, arg target, all comprehension kinds, nested defaults, empty/negative ranges, later class attribute, module-level control).
- Refused by name: p09–p12 (`not in the subset: closures nested too deeply ...`), p13 (`name 'x' is not defined`), p16.
- p01 (module-level `[(lambda: x)() ...]`) is the separate body-read difference from pre347's first review round; unchanged by this work and not in the final review's first item.

**Tests on final commit `f8d20e7`:** 6 modules (pre363, pre347, pre304, safetynet, files, corpus_findings3), 0 failed in 449s; `update_manifest.py --check` rc=0.

**Unverified:** speed/instruction counts (compile-time-only change; not measured).

## review 0
[model qoder/DeepSeek-Flash]
All checks done; writing the report.

**Review: job `pre363` (`f8d20e7`, `55e2a5c` on `work`)**

**What the change actually does.** Adds a `class_dispatch` flag: while a class-attribute value is being compiled (`evaluating_class_attrs`), a call whose callee is a literal `ast.Lambda` skips the construct-a-class branch of `call_value`; `_class_attr_value` refuses a re-entrant read of the same slot by name. Separately, `compscope._lambda_loads`/`_free_body` no longer let a lambda's *argument defaults* or its own bound names suppress a class-body comprehension-target rename. This matches the report's mechanism; its headline ("class-body comprehension lambda") is narrower than the real blast radius — the same crash also hit plain lambda calls in class attributes (my p09).

**Probes** (24 programs, `/tmp/rprobes`, `cmp.sh` on HEAD and `/tmp/base`, both builds):

| group | probes | HEAD | base |
|---|---|---|---|
| defaults/scalars/wide ints/negative/strings/conditional/walrus/default calls a function | p01–p05, p14–p19 | match CPython | `RecursionError` |
| set/dict comps, shadowed param | p05, p20 | match | `RecursionError` |
| nested comps, nested lambda default, lambda body containing its own comp, function-local class body, lambda call in class attribute | p09, p12, p17, p22 | match | `RecursionError` |
| module-level control, class comp w/o lambda | p08, p23 | match (unchanged) | match |
| pre-existing refusals | p06 genexp-as-value, p07 nested class, p10 class attr via class, p11/p22 target read in lambda body, p13 duplicate class, p21 class-scope name, p24 `C.a` in body | refused by name | same message |

No wrong output, crash, or exit-status difference attributable to the change.

**Generated C unchanged for non-feature programs.** `--debug-dir` on a program with a class, comprehension and a module-level lambda: `program.c` byte-identical between `/tmp/base` and HEAD; only `native_report.json` temp paths differ.

**Tests.** `par_check.py -j 2 test_ail_pre363 test_ail_safetynet` on HEAD: `ok` 49.0 s / 130.8 s, 0 failed. `tools/update_manifest.py --check` rc=0. Commit trailers present; tree clean apart from `.agent/pipeline.md`.

**Claim checks.** RecursionError cause/fix: verified. "Elsewhere emitted C unchanged": verified. Default/shadow/arg-target/all comp kinds/empty/negative/nested/attribute dict value match CPython: verified. Refusals by name instead of RecursionError: verified. Report's p-numbering could not be mapped exactly, but no claim contradicted what I observed.

**Pre-existing (identical on base).** p06, p07, p10, p11, p13, p21, p22, p24 refusals; module-level lambda-body-read difference was not probed.

**Unverified.** gdev instruction counts (not run: compile-time-only change, emitted C identical); module-level `[(lambda: x)() ...]` body-read case.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T20:46:37Z
