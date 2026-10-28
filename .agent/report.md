# job job-pre425-10281802  started 2026-10-28T09:03:04Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"7f74b818-4960-48de-8abf-5a087e6fdfc3","session_id":"061692ca-65eb-4111-afb6-bec715e98419"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"34ea285e-7980-4193-b702-aecb6bf1982f","session_id":"6df49bbe-3d66-4126-b89b-71c3d0ca7746"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed r16, the first still-differing item. r04/r05 are already named refusals and r11 is the existing named subset refusal.

Commit `9be619e` on `job-pre425-10281802`:
- Added routed augmented-power folding for parameters bound through module calls (nested, positional/keyword) plus list/dict/attribute and local-container routes.
- Added `test_ail_pre425.py` (9 refused cases, safe controls).
- Updated DEVLOG, DIFFERENCES (`C?-job-pre425-10281802-1`), manifest and CI shards.

Probes in `/tmp/probes/pre425` on both builds: 16 refused by name (direct, nested, keyword, list/dict arguments, module list/dict/attribute, function-local list; plus r04/r05/r11) and 8 matched CPython (in-range, safe bases, negative exponent, float/bool, dynamic, store-before, mutated list/dict). No probe differed. r17 loop-mutated exponent was checked separately and remains the unchanged run-time trap.

Final tests on the commit: 6 modules (`pre425`, `pre372`, `pre364`, `safetynet`, `files`, `corpus_findings3`), 319 s, 0 failed. Manifest and shard checks pass. Speed not measured; change is compile-time only.
[cost $0.0000, opencode tokens {"total": 6539416, "input": 322092, "output": 18703, "reasoning": 31197, "cache.write": 0, "cache.read": 6167424}]
    tool time: bash 8.6 min
        321s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre425 test_ail_pre372 test_ail_pre364 test_ail_
         41s bash   for p in /tmp/probes/pre425/*.py; do b=$(basename "$p"); case "$b" in loop_*|r17_loop.py) continue;; esac; ech
         28s bash   for p in /tmp/probes/pre425/aug_*.py /tmp/probes/pre425/r16_*.py /tmp/probes/pre425/r04_default.py /tmp/probes
         25s bash   mkdir -p /tmp/probes/pre425 cat > /tmp/probes/pre425/aug_list.py <<'EOF' values = [2, (3**100)>>150] b = value
         20s bash   cat > /tmp/probes/pre425/r16_list_mutated_before.py <<'EOF' def power(b, e):     b **= e     return b  values 
         19s bash   mkdir -p /tmp/probes/pre425 cat > /tmp/probes/pre425/r04_default.py <<'EOF' def power(b, e=(3**100)>>150):    
         18s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre425 test_ail_pre372 test_ail_pre364 2>&1 | ta
         15s bash   cat > /tmp/probes/pre425/r16_wrapper.py <<'EOF' def power(b, e):     b **= e     return b  def apply(a, b):   

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre425 (`9be619e`)

**What the change really does:** adds `_check_int64_routed_augmented_powers`, which follows module-scope calls into plain functions, binds positional/keyword int arguments (including through module containers/attributes and nested wrappers), and raises a named compile-time refusal when the exact `b **= e` result leaves int64. It also extends the straight-line folder with `assigned`/`seen` so list/dict/attribute routes resolve, and invalidates them on stores. Matches the report; compile-time only.

**Probes** (27 in `/tmp/rprobes`, both builds via `cmp.sh`, base at `/tmp/base`):
- r16 direct/list/dict-int-key/negative-index/tuple/loop-body → now refused by name on HEAD (base: runtime `integer overflow`). Fix confirmed.
- Safe routes → CPython-matching: in-range (arg/attr/posonly/kwonly-default/local tuple), safe bases 0/±1 with huge exponent, negative exponent, dynamic args, store-before, rebind-after, guarded `if b == 1`, list/dict/alias mutation before & after, attribute overwrite, helper local containers, recursion, comprehensions, unused big route, `**kwargs`/`*args`, float/bool controls.
- No new false refusal of a safe program found; no crash.
- C unchanged: `--debug-dir/program.c` identical to base for a feature-free program and for an in-range augmented-power program.

**Pre-existing (identical on base, not blocking):** augmented power with default argument (`default_big`), `.get()` route, method call route, helper-return exponent, nested container, loop-mutated (`r17_loop`, `loop_mut`, `loop_mut2`), required keyword-only subset refusal, wrong-arity subset refusal.

**Report claims:** r16 fixed — verified; r04/r05 named pow refusals and r11 class-attribute subset refusal — verified on both builds; safe controls match — verified; r17 unchanged trap — verified. "6 modules, 0 failed" — verified 4/6 (`pre425`, `safetynet`, `files`, `corpus_findings3`, 0 failed); `pre372`/`pre364` unverified (unedited by this change). Manifest/shard `--check` exit 0; DEVLOG date, DIFFERENCES id, commit co-author all correct.

**Speed:** not measured; generated C is identical, so no runtime instruction-count impact.

**Unverified:** `test_ail_pre372`, `test_ail_pre364`; large-program compile-time cost of the new scan.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1017544, "input": 77189, "output": 6573, "reasoning": 14230, "cache.write": 0, "cache.read": 919552}]
    tool time: bash 9.4 min
        206s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        110s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre425 tes
         51s bash   date; cd /tmp/rprobes; for p in *.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1 | grep -E "cpy
         41s bash   date; cd /tmp/rprobes; for p in *.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-
         41s bash   date; cd /tmp/rprobes; for p in attr_inrange.py dict_int_keys.py negative_index.py get_route.py star_args.py k
         33s bash   date; for p in r16_dynamic r16_safe r16_store_before r16_list_mutated_before r16_list_mutated_after r16_dict_m
         26s bash   cd /tmp/rprobes && cat > kwargs.py <<'EOF' def power(b, e):     b **= e     return b   opts = {"b": 2, "e": 10
         22s bash   date; cd /tmp/rprobes; for p in get_route.py default_big.py method_route.py helper_return.py loop_body.py kwon

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T10:50:06Z
