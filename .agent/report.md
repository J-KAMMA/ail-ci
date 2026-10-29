# job job-ex32-10291111  started 2026-10-29T02:40:42Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"35c5847a-be99-470a-b0ea-8fd3fc6507ac","session_id":"fb394203-1d89-4ac5-bae2-6241933f42d4"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"337f0cb1-a532-4f29-97fb-9d3b5b52e18b","session_id":"38b221d6-b09f-4850-ae77-16fcb2505d72"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report — job-ex32-10291111 (commit `17b53e4`)**

- **Refused set:** six Python-syntax `.ail` examples under `language_examples` (hello, integer_series, math, stdin_sum, sum, use_math). All build on general/default; on the typed path `hello.ail` was refused with `a script that is only print(<expression>) needs general object semantics`. `use_math` builds with its documented `--module math.ail`.
- **Fix:** typed-path print gate now accepts non-bool Constants and proven integer constant expressions; out-of-int64 values are left to the big-int check. Bare bool/float/text/container arguments keep the old fallback. `hello.ail` now prints `42`/exits 0 on general, default and typed-only builds.
- **Probes:** 19 in `/tmp/probes` via `cmp.sh`; all match CPython on g/d. Typed-only: 14 integer-expression probes (including hello) match; `bool_direct`, `float`, `str`, `list` keep the named print refusal; `big` (`2 ** 100`) is refused by the big-int check.
- **Tests:** `test_ail_ex32` (3 tests, added/registered), `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed, 723s. Updated `test_ail_build_cache` general-note case (`print(True)`), passed in 79s.
- **Records:** DEVLOG entry added; `update_manifest.py --check` passes; `ci_shards.py --update/--check` done.
[cost $0.0000, opencode tokens {"total": 10385087, "input": 155291, "output": 18175, "reasoning": 30501, "cache.write": 0, "cache.read": 10181120}]
    tool time: bash 19.6 min
        727s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex32 test_ail_py
         94s bash   rm -rf /tmp/probes && mkdir -p /tmp/probes && cd /tmp/probes cat > p_ex32_add.py <<'EOF' print(40 + 2) EOF cat
         83s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/test_ail_build_cache.py' s=open(p).read(
         39s bash   cd /tmp/probes && rm -rf /tmp/typedout && mkdir -p /tmp/typedout && for p in p_ex32_*.py; do b=${p%.py}; if AI
         29s bash   mkdir -p /tmp/probes && cd /home/runner/work/ail-ci/ail-ci && for f in hello math sum; do cp AIL_CURRENT/langu
         17s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for src in 'print([1, 2])' 'print((1, 2))' 'print({1, 2})' '
         16s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for src in 'print(not False)' 'print(1 == 1)' 'print(1 < 2)'
         16s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for src in 'print(1.5 + 2.5)' 'print("a" + "b")' 'print(40 -

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Review — job-ex32-10291111 (17b53e4)**

**What the change really does:** adds `_print_scalar_constant` to the typed-print gate in `pyc.py`: beside the already-accepted non-bool `Constant`s, a print argument is now accepted if `_int_const_value` proves it an integer constant expression; bool results, non-int expressions and unprovable expressions still take the general print fallback. Nothing else in codegen changed.

**Probes (all in /tmp/rprobes, run with cmp.sh on HEAD and /tmp/base):**
- g/d match CPython: add, neg, boolmix (`True+True`, `~True`, `+True`), boolop, big (`2**100`), bound (`2**63-1`, `-(2**63)`, `(1<<63)//2`), over, zerodiv, negshift, divneg, floatx, strx, sep, multi; boundary set `-2**63`, `INT64_MAX+1`, `1<<63`, `10**19`, `2**64//2**64`, `0<<1000`, `0*(2**100)`, `(2**100)**0`, `big_literal**0`, `True<<63`, `True&True`.
- All 19 worker probes in /tmp/probes: g/d match; typed-only exactly as reported (14 match, bool/float/str/list refused by the print message, `2**100` refused by big-int check).
- Non-feature programs: `program.c` byte-identical base vs HEAD for a def/loop script, `print(True)`, a list-comprehension print, and `print("a"+"b")`.

**Claims:** refused six = the only 6 `.ail` files that parse as Python (confirmed); hello refused on base typed with the quoted message and prints `42`/0 on g, d and typed HEAD (verified); use_math builds on g/d only with `--module math.ail` (same on base); `test_ail_build_cache` change to `print(True)` is sound; manifest/ci_shards `--check` exit 0. Claim that out-of-int64 is “left to the big-int check to name” is imprecise: `2**63` is named, but on `AIL_NO_GENERAL` `print(1<<63)` and `print(INT64_MAX+1)` reach the typed/legacy int64 emitter and stop with `integer overflow` (exit 1). That is the documented typed-path loud-stop (cf. test_ail_bigint `b6_overflow`), identical to the base's def-program equivalent, and g/d match CPython — not blocking. Minor wording: non-bool `Constant`s were already accepted before this diff.

**Tests:** `test_ail_ex32`, `test_ail_build_cache`, `test_ail_safetynet` → 3 modules, 0 failed. Also re-ran likely-affected boundary modules: `pre121`, `pre201`, `pre236`, `pre285`, `pre113`, `pre109`, `pre204`, `pre273`, `pre33` → 0 failed.

**Speed:** not measured; no runtime/codegen change for non-print-only programs, generated C unchanged.

**Unverified:** full suite; `test_ail_python_syntax`, `test_ail_files`, `test_ail_corpus_findings3` (reported by worker, not re-run).

VERDICT: ACCEPT
[cost $0.0542, opencode tokens {"total": 3578972, "input": 105166, "output": 13038, "reasoning": 33952, "cache.write": 0, "cache.read": 3426816}]
    tool time: bash 21.6 min
        262s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        218s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 700 python3 ../tools/par_check.py -j 2 test_ai
        102s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ai
         80s bash   cd /tmp/rprobes/typed && i=0; for src in 'print((-2) ** 3)' 'print((-2) ** 62)' 'print(- -5)' 'print(+-+5)' 'p
         73s bash   cd /tmp/probes && for p in p_ex32_*.py; do r=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ail-ci/ail
         65s bash   cd /tmp/rprobes && for p in add neg boolmix boolop big bound over zerodiv negshift divneg floatx strx sep mult
         60s bash   cd /tmp/rprobes/ex && for tag in base head; do wt=/tmp/base; [ $tag = head ] && wt=/home/runner/work/ail-ci/ai
         57s bash   cd /tmp/rprobes && for p in add neg boolmix boolop big bound over zerodiv negshift divneg floatx strx sep mult

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-29T05:43:52Z
