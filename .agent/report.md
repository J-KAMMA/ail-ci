# job job-pre380-10280705  started 2026-10-27T22:12:54Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"75e25348-90aa-4eaf-ba68-fcbef286cf2f","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16194866845714284}},"permission_denials":[],"fast_mode_state":"off","uuid":"17d413d9-3b7b-4826-b730-9902c96eb0b3","session_id":"69b4bdbb-1055-41c0-a928-53150ea7bcc0"}

## worker report 0
[model qoder/DeepSeek-Flash]
Committed as `df27248`.

**Reproduced:** the module-level `[(lambda: x)() for x in range(3)]` body-read case still differed on both builds (`[99, 99, 99]` vs CPython `[0, 1, 2]`). The gdev instruction counts could not be re-measured (`perf_event_paranoid` is 4).

**Cause/fix:** `compscope.rename` renamed a clashing comprehension target but never rewrote a nested lambda body, so the lambda kept reading the enclosing `x`. It now resolves the body's free loads (parameters, walrus targets and nested-comprehension targets excluded) against the enclosing comprehension stack: function scope matches CPython; module scope is refused by name (`not in the subset: closures nested too deeply...`) instead of printing the wrong value.

**Probes** (`/tmp/probes/pre380`, both builds via `cmp.sh`):
- `r01`–`r14`: argument, list item, attribute, dict value, set/dict comp, consumed generator, if condition, nested same-name comps, two targets, empty/negative/string, outer value after, shadowed inner target — all match CPython.
- `q01`–`q08`: same routes at module scope — refused by name.
- `c01`–`c04`, `n01`–`n03`: defaults, outer reads, target passed as argument, class-body default, parameter shadowing, assignment after the comp, nested comps without an outer use — all match CPython.
- Earlier `p`/`m`/`f` probes: function cases match; module cases refused; walrus case refused by name.

**Tests on final commit:** test_ail_pre380, test_ail_pre363, test_ail_quirks, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 6 modules, 607 s, 0 failed. `update_manifest.py --check` passes. `ci_shards.py --check` still exits 1 on four duplicate entries present on HEAD; pre380 is mapped.

## review 0
[model qoder/DeepSeek-Flash]
Review complete. All probes and required tests are done; here is the report.

## Review: pre380 `df27248` (lambda body follows a renamed comprehension target)

**What the diff really does (one line):** `compscope._Scope.visit_Lambda` now resolves a lambda body's free loads (excluding its params, walrus targets and nested-comprehension targets) against the enclosing comprehension stack, so when `rename` renames a clashing target the lambda body token is rewritten too; at module scope the construct then hits the existing boxclosure refusal. Plus test `test_ail_pre380.py` (16 match / 6 refuse programs), records and manifest/shard registration. It matches the report.

**Probes** (28 in `/tmp/rprobes`, both builds via `cmp.sh`, HEAD):
- **Matched CPython (21):** p03 escape `(99,[2,2,2])`, p04 walrus, p05 inner comp, p06 nested lambda, p07 default, p09 outer read, p10 two reads, p11 param shadow, p12 module walrus, p13 dict values, p14 nested same-name, p15 tuple target, p16/p18 no-clash, p17 dict comp, p19 f-string, p20 `lambda x=x`, p21 param shadow, p22 two comps, p25 (CPython TypeError, exit 1 both), p27 mutation after slice.
- **Refused by name:** p02 (the reported case), p01, p08, p24, p26, p28.
- **p02 base vs HEAD:** base prints `99 [0, 1, 2]`? No — base prints `99 [99, 99, 99]` (wrong); HEAD refuses `not in the subset: closures nested too deeply to settle their shared names`. Fix verified.
- **p28 note:** `x=99; fs=[(lambda: x) for x in range(3)]; print(x, len(fs))` compiled correctly on base (`99 3`) and is now refused by name — the same module-scope construct, a refusal the task explicitly permits.

**C unchanged for non-feature programs:** `--debug-dir` `program.c` byte-identical HEAD vs base for p16 (function comp, no lambda) and p23 (comprehension clash without a lambda), both builds.

**Pre-existing (also fail on `/tmp/base`):** p01 module-level no-clash lambda refusal, p08 class-body refusal, p26 posonly-lambda refusal; `tools/ci_shards.py --check` exits 1 with the same four duplicated entries on base; `perf_event_paranoid` is 4, so gdev counts are unmeasurable as reported.

**Report claims:** reproduced case — verified; cause/fix description — verified; function-scope capture / module refusal — verified; `update_manifest.py --check` passes — verified (rc 0); pre380 mapped in shards — verified; "walrus case refused by name" — false for my function-scope walrus probe (p04 matched CPython); worker's own probe files r/q/c/n — not inspected (my equivalent probes are consistent); the four extra test modules — unverified (not required). 

**Tests on HEAD:** `test_ail_pre380` 113.4 s and `test_ail_safetynet` 145.0 s, 2 modules, 0 failed. Commit carries the co-author trailer; DIFFERENCES row uses the `C?-job-pre380-10280705-1` placeholder.

**Not checked (time/scope):** gdev instruction counts; the worker's extra four test modules; speed (compile-time only, emitted C identical).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T23:56:33Z
