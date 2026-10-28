# job job-cov28-10290512  started 2026-10-28T20:17:38Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"9dfcf428-651a-4772-b7de-e7045726de2e","session_id":"681c0c5c-04fa-4469-9b50-205c204a9909"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"14f0ac9a-bd8b-4328-b163-6280932ddafe","session_id":"1eaf6474-28d0-4063-a457-f18ace0bceb0"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

- Commit `dd37461` on `job-cov28-10290512`.
- Corpus of 219 programs: refusals **24 → 21** on both the default build and `AIL_UNIFIED_FORCE=1`.
- Top non-import blocker was nested generator expressions (3 programs: deepseek t172/t432, glm t432). All three now match CPython on all 3 inputs on both builds.
- Change: an inner generator expression consumed whole as the sole argument of an unbound fully-consuming builtin, or `str.join` on a string literal, no longer refuses. Loop/comprehension sources, `next`, `any`/`all`, shadowed builtins and user methods remain named refusals.
- Probes: `cov28_core`, `cov28_empty_negative`, `cov28_effects`, `cov28_routes` match CPython on both builds; `cov28_refuse_list_source`, `cov28_refuse_next`, `cov28_refuse_comp_source`, `cov28_refuse_star`, `cov28_refuse_shadow_sum`, `cov28_refuse_user_join` are refused by name on both.
- Added and registered `AIL_CURRENT/test_ail_cov28.py`; passed `test_ail_cov28`, `test_ail_pre41`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (7/7).
- DEVLOG/DIFFERENCES updated; `update_manifest.py --check` exits 0.
[cost $0.0652, opencode tokens {"total": 6087538, "input": 145877, "output": 17016, "reasoning": 25765, "cache.write": 0, "cache.read": 5898880}]
    tool time: bash 50.9 min
        767s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/cov28/count.py default /tmp/cov28/final-default.json 2>&1 |
        443s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/cov28/count.py default /tmp/cov28/after-default.json 2>&1 |
        387s bash   mkdir -p /tmp/cov28 && cat > /tmp/cov28/count.py <<'PY' import os, re, subprocess, sys, tempfile, json, shutil
        381s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/cov28/count.py unified /tmp/cov28/after-unified.json 2>&1 |
        380s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/cov28/count.py unified /tmp/cov28/before-unified.json 2>&1 
        334s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov28 test_ail_p
        238s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/cov28_core.py /tmp/probes/cov28_empty_negative.py /

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `cov28` nested generator expressions

**What the change really does:** in `pyboxed2.py:12462` it replaces the blanket refusal of a generator expression nested inside another with an allow-list: an inner genexp is accepted iff it is the sole, keyword-free argument of an unbound `list/tuple/set/frozenset/dict/sorted/sum/min/max/bytes/bytearray`, or of `str.join` on a string literal (`pyboxed2.py:12468-12492`). Everything else keeps the old named refusal.

**Claims checked**
- Commit/message/counts/test registration/manifest: verified (`dd37461`; counts in message; `test_ail_cov28` in `MODULES`; `update_manifest.py --check` = 0).
- Three corpus programs now build and match CPython on both builds: verified for one input each (t172, deepseek/t432, glm/t432). "All three inputs" unverified.
- Corpus 24→21 on both builds: **unverified** (not reran; worker's counter script unavailable).
- "consumed whole … exact": **false** — several allowed builtins do not read the argument to the end before they can raise (see defect).
- Tests: `test_ail_cov28`, `test_ail_safetynet` pass (2/2). The other five modules listed by the worker were not rerun.
- Programs without the feature: `program.c` for `p8_nofeature`, `g00_000`, `g00_010` byte-identical to base. Good.
- Refusal cases still refused by name: covered by the passing test module.

**Defect 1 (silent difference, both builds):** the allow-list includes consumers that can raise before exhausting the inner generator. The eager lowering builds the whole inner list first, so later elements' side effects run where CPython would have stopped. This is the same eager-lowering limitation that already exists for non-nested genexps (pre-existing), but here it is newly exposed by accepting programs that the base refused by name, violating "never a silent difference".

Probes in `/tmp/rprobes/` (all refused by name on base, both builds; accepted and diverging on HEAD, both builds):

| probe | source core | CPython | HEAD |
|---|---|---|---|
| `p1_sum_typeerr.py` | `sum(f(v) for v in row)` where `f` returns `str` | `f 1` / `TypeError` | `f 1` / `f 2` / `f 3` / `TypeError` |
| `p2_min_typeerr.py` | `min(f(v) for v in [1,"a",2])` | `f 1` / `f a` / `TypeError` | adds `f 2` |
| `p3_bytes_range.py` | `bytes(f(v) for v in [65,300,66])` | `f 65` / `f 300` / `ValueError` | adds `f 66` |
| `p4_set_unhashable.py` | `set(f(v) for v in [1,[2],3])` | `f 1` / `f [2]` / `TypeError` | adds `f 3` |

Fix direction: restrict the safe set to consumers that materialise fully before any element-based failure — `list`, `tuple`, `sorted`, and `str.join` on a literal (`p5_join_typeerr.py` and `p6_basic_routes.py` already match). `sum`, `min`, `max`, `bytes`, `bytearray`, `set`, `frozenset` and `dict` can raise mid-iteration and must keep the named refusal.

No speed impact (compile-time-only change).

VERDICT: FIX
[cost $0.0195, opencode tokens {"total": 723980, "input": 40207, "output": 5972, "reasoning": 13097, "cache.write": 0, "cache.read": 664704}]
    tool time: bash 3.0 min, write 0.0 min
         93s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_cov28 te
         26s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_sum_typeerr p2_min_typeerr p3_bytes_range p4_set_unhashable 
         20s bash   cd /tmp && rm -rf hc bc && mkdir hc bc && cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/p8_nofea
         14s bash   cd /tmp/base && for p in p1_sum_typeerr p2_min_typeerr p3_bytes_range p4_set_unhashable; do echo "######## $p 
         13s bash   cd /tmp && rm -rf corp && mkdir corp && cd corp && printf 'north,q1,10\nnorth,q2,20\nsouth,q1,5\n' > in172.txt
          6s bash   cd /tmp/corp && src=/home/runner/work/ail-ci/ail-ci/lab/corpus/programs/glm-5.3-flash-free/t432.py; for m in g
          6s bash   cat > /tmp/rprobes/p9_plain_sum.py <<'EOF' def f(x):     print("f", x)     return str(x)  def main():     try:
          1s bash   rm -rf /tmp/base && cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -2 && cd

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `7007ad6` on `job-cov28-10290512`.

**Fix:** nested generator expressions are now accepted only as the sole argument of unbound `list`, `tuple`, `sorted`, or `str.join` on a string literal. `sum`, `min`, `max`, `bytes`, `bytearray`, `set`, `frozenset`, `dict` keep the named refusal because they can raise mid-iteration.

**Corpus:** 24/219 refusals before, 22/219 after, on both builds. `deepseek/t432` and `glm/t432` match CPython on all 3 inputs on both builds; `deepseek/t172` still needs `sum` and remains refused by name.

**Probes** (`/tmp/probes`, via `cmp.sh`, both builds):
- Matched CPython: `cov28_core`, `cov28_types`, `cov28_empty_negative`, `cov28_effects`, `cov28_join_typeerr`, `cov28_routes`
- Refused by name: `cov28_refuse_sum`, `cov28_refuse_min`, `cov28_refuse_set`, `cov28_refuse_dict`, `cov28_refuse_bytes`, `cov28_refuse_list_source`, `cov28_refuse_next`, `cov28_refuse_shadow_sorted`, `cov28_refuse_user_join`
- Legacy probes also refused by name: `cov28_refuse_comp_source`, `cov28_refuse_star`, `cov28_refuse_shadow_sum`

**Tests:** `test_ail_cov28`, `test_ail_pre41`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7/7 passed, 0 failed. `update_manifest.py --check` = 0.
[cost $0.0314, opencode tokens {"total": 1913876, "input": 67316, "output": 12601, "reasoning": 13799, "cache.write": 0, "cache.read": 1820160}]
    tool time: bash 22.6 min, edit 0.0 min, write 0.0 min
        813s bash   cd /tmp && python3 /tmp/count_corpus.py > /tmp/count_corpus.out 2>&1; tail -40 /tmp/count_corpus.out
        186s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov28 test_ail_p
        186s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov28 test_ail_p
        120s bash   cd /tmp && nohup python3 /tmp/count_corpus.py > /tmp/count_corpus.out 2>&1 & echo $!
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/cov28_*.py; do echo "######## $(basename $p)"; bash
         10s bash   cat > /tmp/run_t432.py <<'EOF' import os, subprocess, sys, tempfile from pathlib import Path ROOT = Path('/hom
          9s bash   cd /tmp && for p in cov28_refuse_shadow_list cov28_refuse_user_join cov28_refuse_sum cov28_refuse_bytes; do fo
          2s bash   cd /tmp && for name in sorted tuple; do d=$(mktemp -d); cat > $d/p.ail <<EOF def $name(x):     return x   def 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** replaces the blanket nested-generator refusal with `_unsafe_nested_genexp()` (`pyboxed2.py:12483`), which only judges the *inner* generator expressions: an inner one is safe iff it is the sole argument of an unbound `list`/`tuple`/`sorted` or of `str.join` on a string literal. The *containing* generator's consumer is not re-checked.

**Claims**
- Inner consumers `sum`/`min`/`bytes`/`set`/`dict`/`next`/`any`/`all` stay refused: verified (all refuse by name on both builds; `next`/`any`/`all` have their own guards).
- `deepseek/t432`, `glm/t432` match CPython on all 3 inputs, both builds: verified.
- `deepseek/t172` still refused by name: verified (its top refusal is the `collections` import; the general-path reason is still the nested-genexp refusal, not specifically `sum`).
- Corpus 24→22 refusals: unverified (did not rerun the 219-program count).
- Tests: `test_ail_cov28`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass (2+2 modules, 0 failed); `pre41`/`pre116`/`pre211` not rerun.
- `update_manifest.py --check`: verified (0).
- Programs not using the feature have identical C: verified (`p8_nofeature.py`, `--debug-dir` program.c byte-identical to `/tmp/base`).
- "Accepted only as the sole argument of list/tuple/sorted/join": true only of the *inner* node; false in effect, because the containing generator may be consumed by a `for`/comprehension source or by `sum`/`min`/`max`/`set`/`dict`/`bytes` — defects 1–2.

**Pre-existing (same on `/tmp/base`)** — the same eager-lowering ordering for *non-nested* generators: `s1_plain_for` (`for a in (tick(x) for x in [1,2,3]): print("body", a)`) and `s2_plain_sum` (`sum(f(v) for v in [1,2,3])`) differ identically before/after. Not blockers, but they are the root cause the new acceptance exposes.

**Unverified:** corpus refusal counts; the three `pre` modules.

**Defects**
1. A containing generator used as a `for`/comprehension source is accepted, but the eager outer materialisation reorders body side effects and over-runs early exits. Base refuses these by name; HEAD silently differs on both builds.
   - Probe `/tmp/rprobes/q6_for_all.py`:
     ```python
     def tick(v):
         print("tick", v)
         return v
     for a in (list(tick(x) for x in row) for row in [[1], [2], [3]]):
         print("body", a)
     ```
     Expected (CPython): `tick 1, body [1], tick 2, body [2], tick 3, body [3]`; actual HEAD: `tick 1, tick 2, tick 3, body [1], body [2], body [3]` (exit 0 both).
   - Probe `/tmp/rprobes/r1_break_crash.py`:
     ```python
     for a in (list(int(x) for x in row) for row in [["1"], ["x"]]):
         print("body", a)
         break
     print("done")
     ```
     Expected: `body [1]`, `done`, exit 0; actual HEAD: no output, exit 1 `ValueError: invalid literal for int() ... 'x'`. Same with a comprehension body (`q8_comp_body_effects.py`: expected `tick 1, row [1], tick 2, row [2]`; actual `tick 1, tick 2, row [1], row [2]`).
2. A containing generator consumed by a raising builtin is accepted; the eager outer materialisation runs later elements' side effects before the consumer raises (base refuses these by name).
   - `/tmp/rprobes/q1_sum_outer.py`: `print(sum(list(tick(x) for x in row) for row in [[1],[2],[3]]))` — expected `tick 1` then `TypeError`; actual `tick 1, tick 2, tick 3` then `TypeError` (both builds, exit 1).
   - Same for `set` (`q3`: extra `tick 2/3`), `dict` (`q4`: extra `tick 2/3`) and `min` (`q2b`: extra `tick 3` before the comparison `TypeError`).

The fix should apply the “safe consumer” test to the *outermost* generator expression relative to its own consumer (and still refuse `for`/comprehension sources because they interleave body execution, and `sum`/`min`/`max`/`set`/`dict`/`bytes` because they can stop/raise mid-iteration). `test_ail_cov28.py` misses this because every allowed case has the containing generator as the sole `list`/`tuple`/`sorted` argument.

VERDICT: FIX
1. Containing generator as a `for`/comprehension source: accepted and reorders/re-runs effects; `q6` expected `tick 1, body [1], tick 2, body [2], tick 3, body [3]`, got all `tick`s first; `r1` expected `body [1]`/`done` exit 0, got exit 1 `ValueError`.
2. Containing generator consumed by `sum`/`min`/`max`/`set`/`dict`/`bytes`: accepted and runs later elements' effects before the exception; `q1` expected `tick 1` then `TypeError`, got `tick 1, tick 2, tick 3` then `TypeError`; `q3`/`q4`/`q2b` likewise.
[cost $0.0354, opencode tokens {"total": 1184759, "input": 94389, "output": 7140, "reasoning": 23006, "cache.write": 0, "cache.read": 1060224}]
    tool time: bash 5.5 min
        145s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_files test_
         82s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_cov28 test_
         29s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p[1-9]_*.py; do echo "######## $(basename $p)"; ba
         20s bash   cd /tmp/base && for p in /tmp/rprobes/p6_forbreak_list.py /tmp/rprobes/q1_sum_outer.py /tmp/rprobes/q6_for_all
         16s bash   cd /tmp/rprobes && cat > r1_break_crash.py <<'EOF' for a in (list(int(x) for x in row) for row in [["1"], ["x"
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q[1-7]_*.py; do echo "######## $(basename $p)"; ba
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for prog in lab/corpus/programs/deepseek-v4.1-flash-free/t432.py lab/cor
          7s bash   cd /tmp/rprobes && cat > q8_comp_body_effects.py <<'EOF' def tick(v):     print("tick", v)     return v  def m

FINAL VERDICT: FIX  2026-10-28T22:27:49Z
