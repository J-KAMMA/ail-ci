# job job-cov26-10290509  started 2026-10-28T20:17:44Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"d0a18719-1c9c-4bf6-9e39-87616c9c69e4","session_id":"4541bc74-cd33-4243-bf58-a4e7c12a61d7"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"f95e14e0-2b6a-4577-ab64-35f45ec01549","session_id":"6487c8ee-816c-41f5-acf9-1eec4a700d77"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done on branch `job-cov26-10290509` (final commit `0787843`).

**Change:** accepted nested generator expressions when the outer generator and every inner one are fully consumed at once (`join`, `sum`, `list`, `tuple`, `sorted`, ...). Saved/lazy, `next()`, `any()`/`all()` and handed-on inner generators remain named compile-time refusals.

**Corpus profile (219 programs):**
- Before: `24/219` refused on both builds; general-path nested-genexp refusals: `3`.
- After: `21/219` refused on both builds; nested-genexp refusals: `0`.
- The 3 newly accepted programs (`t172` deepseek, `t432` deepseek/glm) match CPython 3.12 on all 3 corpus inputs on default and `AIL_UNIFIED_FORCE=1`.

**Tests:** `test_ail_cov26`, `test_ail_pre42`, `test_ail_pre116`, `test_ail_pre166`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 39 tests, OK (1 skipped). `tools/update_manifest.py --check` passes.

**Probes (19, both builds):** `p_join_join`, `p_join_sum_empty`, `p_sum_inner_negative`, `p_arg_route`, `p_list_item_route`, `p_attribute_route`, `p_dict_value_route`, `p_alias_route`, `p_side_effects`, `p_exception`, `p_types`, `p_nested_containers`, `p_widths`, `p_deep_nested` match CPython; `p_saved_outer_refused`, `p_next_refused`, `p_any_refused`, `p_inner_handed_on_refused` are refused by name.
[cost $0.0797, opencode tokens {"total": 8482918, "input": 178346, "output": 20826, "reasoning": 26082, "cache.write": 0, "cache.read": 8257664}]
    tool time: bash 35.6 min
        638s bash   mkdir -p /tmp/probes /tmp/cov26prof && cat > /tmp/cov26prof/profile.py <<'PY' import os, re, subprocess, sys, 
        464s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_cov26 test_ail_pre42 test_ai
        252s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_cov26 test_ail_pre42 test_ai
        250s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_cov26 test_ail_pre42 test_ai
        120s bash   cd /home/runner/work/ail-ci/ail-ci && sed 's/env.pop(.AIL_IR., None)/env.pop("AIL_IR", None); env["AIL_UNIFIED
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup setsid python3 /tmp/cov26prof/profile_u.py > /tmp/cov26prof/raw_u.
         59s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pre116 test_ail_pre166 2>&1 
         42s bash   mkdir -p /tmp/probes/cov26 && cd /tmp/probes/cov26 && cat > p_join_join.py <<'PY' rows = [[1, 2], [], [3], [-4

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: cov26 nested generator expressions

**What the diff does.** Adds `_genexp_consumed_fully` / `_nested_genexps_safe` in `pyboxed2.py` and exempts a nested generator expression from the by-name refusal when its parent is a call whose callee is a name in `{list,tuple,set,frozenset,dict,sorted,sum,min,max,bytes,bytearray,Counter,array}` or an attribute whose *name* is in `{join,extend,update,array}`, and every nested genexp inside it passes the same test. It reuses the existing eager list lowering.

**Claims checked**
- "Outer and every inner fully consumed => same elements at same point/order": **false** in general (defects below); the static test only inspects names and immediate parents.
- t172 / t432 now compile and match: **partially verified** — all three files compile on both builds and match CPython with empty stdin; the three generated corpus inputs were not rerun.
- Profile 24→21 refusals, nested refusals 3→0: **unverified** (profiler not rerun; `lab/corpus/results/results.jsonl` contains no such message).
- Tests: `test_ail_cov26` and `test_ail_safetynet` **pass**; the other five modules were not rerun.
- 19 probes: **unverified** (not present in the worktree).
- `update_manifest.py --check`: **passes**.
- No-feature program: `--debug-dir` output vs base differs only in temp paths/cwd; generated C is identical.

**Probes that matched** (both builds): `p_starred`, `p_order_sorted_key`, `p_no_nested`, `p_mutation`.

### Defects (each refused by name on base, so caused by this change)
1. **Extra call arguments are evaluated after the generator body instead of before it.**
   `/tmp/rprobes/p_order_sum_extra.py`
   ```python
   def note(tag, v):
       print("arg", tag); return v
   def val(x):
       print("elem", x); return x
   print(sum((sum(val(y) for y in [x]) for x in [1, 2]), note("start", 10)))
   ```
   Expected: `arg start`, `elem 1`, `elem 2`, `13`. Actual: `elem 1`, `elem 2`, `arg start`, `13`.

2. **A "fully consuming" consumer that aborts early leaves later elements unevaluated in CPython, but the eager lowering evaluates them.**
   `/tmp/rprobes/p_set_unhashable.py` (set on unhashable element)
   Expected: `elem 1`, `caught TypeError`. Actual: `elem 1`, `elem 2`, `caught TypeError`.
   `/tmp/rprobes/p_dict_unhashable.py` (same for `dict`)
   Expected: `elem 1`, `ValueError: ...#0 has length 1...`. Actual: `elem 1`, `elem 2`, `ValueError: ...`.

3. **The method whitelist matches any attribute with that name, including user methods that do not consume the argument.**
   `/tmp/rprobes/p_shadow_update.py` — `Acc.update` breaks after the first element.
   Expected: `elem 1`, `[1]`. Actual: `elem 1`, `elem 2`, `[1]`.

**Pre-existing.** The non-nested analogue of defect 2 (`set(val(x) for x in [[1],[2]])`) already differs on base; the nested probes above are nevertheless refused on base and newly wrong on HEAD.

**Unverified.** Corpus refusal counts; generated corpus inputs for t172/t432; the five other test modules; speed (compile-time-only change).

VERDICT: FIX
[cost $0.0185, opencode tokens {"total": 669851, "input": 42018, "output": 4543, "reasoning": 12730, "cache.write": 0, "cache.read": 610560}]
    tool time: bash 2.9 min
         87s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         23s bash   cd /tmp/rprobes && for p in p_order_sum_extra p_order_sorted_key p_set_unhashable p_join_nonstr p_shadow_list 
         17s bash   cd /tmp/rprobes && cat > p_order_sum_extra.py <<'PY' def note(tag, v):     print("arg", tag)     return v  def
         15s bash   cd /tmp/rprobes && for f in /home/runner/work/ail-ci/ail-ci/lab/corpus/programs/deepseek-v4.1-flash-free/t172.
         13s bash   cd /tmp/rprobes && for p in p_order_sum_extra p_set_unhashable p_shadow_update p_dict_unhashable; do echo "===
          6s bash   cd /tmp/rprobes && cat > p_set_unhashable_non_nested.py <<'PY' def val(x):     print("elem", x)     return x  
          5s bash   cd /tmp/rprobes && cat > p_shadow_sum.py <<'PY' def sum(g):     for x in g:         return x     return 0  def
          4s bash   cd /tmp && mkdir -p ddh ddb && printf 'xs=[1,2,3]\nprint(sum(x*2 for x in xs))\nprint([x for x in xs if x>1])\

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects and committed as `93626a7`.

- Defect 1: extra call arguments now make a nested generator refuse by name (no evaluation-order mismatch); `sum(genexp)` also consumes element-by-element.
- Defect 2: `set`/`dict`/`min`/`max`/`bytes`/`Counter`/`array` removed from the safe consumer set; aborting consumers refuse by name.
- Defect 3: no method-name whitelist remains; `.join` only on a string-literal receiver with a provably-str element.

Verification:
- Profile: **24 → 21 refusals** on both builds (baseline from prior profile, after-count rerun here); nested-generator refusals **3 → 0**.
- Corpus t172/t432 (deepseek) and t432 (glm): all 3 inputs match CPython on both builds.
- 30 probes: **17 match CPython**, **13 refused by name** (including the three reviewer probes and `p_types`, now refused because its element is a method call with no proven str receiver).
- `update_manifest.py --check`: passes.
- Final-commit tests: `test_ail_cov26`, `test_ail_pre42`, `test_ail_pre116`, `test_ail_pre166`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **7/7 pass**.
[cost $0.0816, opencode tokens {"total": 6540694, "input": 247546, "output": 16211, "reasoning": 26569, "cache.write": 0, "cache.read": 6250368}]
    tool time: bash 47.2 min, write 0.0 min
        838s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
        803s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 /tmp/profile_cov26.py | grep -E '^(d|g) total|NESTE
        727s bash   cat > /tmp/profile_cov26.py <<'PY' import concurrent.futures, os, re, subprocess, sys, tempfile, shutil from p
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov
         69s bash   mkdir -p /tmp/probe_results && cd /tmp/probes/cov26 && for f in p_*.py; do echo "########## $f" | tee /tmp/pro
         69s bash   rm -rf /tmp/probe_results && mkdir -p /tmp/probe_results && cd /tmp/probes/cov26 && for f in p_*.py; do bash ~
         45s bash   cat > /tmp/run_corpus3.py <<'PY' import os, subprocess, sys, tempfile, shutil from pathlib import Path ROOT=Pa
         44s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode-go/deepseek-v4.1-flash]
Read the diff, ran 27 probes on HEAD and base, re-ran the 7 required test modules (7/7 pass), and checked the 3 corpus programs (9/9 inputs match on both builds).

**What the change really does:** narrows nested-generator acceptance to `list`/`tuple`/`sorted`/`sum` (unshadowed, sole positional arg) and literal-receiver `str.join` with a syntactically-str element, and adds a fused element-by-element `sum(genexp)` emitter. This matches the report; it does not mention the class-body interaction below.

**Claims checked:** defect fixes 1–3 verified (probes + `test_ail_cov26`); 30 worker probes re-run = 17 match / 13 refused by name (verified); corpus t172/t432 9/9 same (verified); `update_manifest.py --check` exit 0 (verified); 7/7 target modules pass (verified). Full 24→21 profile count and speed were not re-run (unverified).

**Defect (caused by the change):** the new fused `sum(genexp)` branch calls `_emit_comp_generators` directly (`pyboxed2.py:9453`); that sets `ctx.class_locals = None` (`:6485`) and never restores it (only `_emit_comp` saves/restores at `:6467-6471`). In a class-body attribute expression, names after the sum then resolve as globals.

```
# /tmp/rprobes/p_class_nested_sum_wrong.py
xs = [[9, 9], [9, 9]]
class C:
    xs = [[1, 2]]
    t = sum(sum(v for v in row) for row in xs) + len(xs)
    pair = (sum(sum(v for v in row) for row in xs), xs)
print(C.t, C.pair)
```
Expected (CPython, both builds): `4 (3, [[1, 2]])`
Actual HEAD (both builds): `5 (3, [[9, 9], [9, 9]])`
Base: refused by name (nested genexp), so HEAD newly accepts and silently miscomputes.

Non-nested regression on a program base compiled correctly (`/tmp/rprobes/p_class_after_sum_wrong.py`): `xs=[9,9]; class C: xs=[1,2,3]; t=sum(v for v in xs)+len(xs); pair=(sum(v for v in xs),xs); print(C.t,C.pair)` → CPython/base `9 (6, [1, 2, 3])`, HEAD `8 (6, [9, 9])`. Fix: save/restore `ctx.class_locals` around the fused emission (or route through `_emit_comp`).

**Pre-existing** (identical on base, do not block):
- `set(val(y) for y in [[1],[2]])`: HEAD and base print `elem [2]`; CPython stops after `[1]` (non-nested eager consumer abort order).
- `any(genexp)` followed by a class-name read in the same class attribute fails on both HEAD and base (same class-locals pattern).

VERDICT: FIX
1. Fused `sum(genexp)` leaks `ctx.class_locals = None` into the rest of a class-body attribute expression, so later class names silently read module globals. Probe `/tmp/rprobes/p_class_nested_sum_wrong.py`: expected `4 (3, [[1, 2]])`, actual `5 (3, [[9, 9], [9, 9]])` on both HEAD builds (base refused by name). Non-nested variant `/tmp/rprobes/p_class_after_sum_wrong.py`: expected `9 (6, [1, 2, 3])`, actual `8 (6, [9, 9])`; base matches CPython.
[cost $0.0424, opencode tokens {"total": 1983402, "input": 81541, "output": 8568, "reasoning": 32429, "cache.write": 0, "cache.read": 1860864}]
    tool time: bash 7.7 min
        218s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_cov2
         73s bash   cd /tmp/probes/cov26 && for f in p_*.py; do out=$(bash ~/tools/cmp.sh "$PWD/$f" /home/runner/work/ail-ci/ail-c
         46s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 550 python3 /tmp/run_corpus3.py 2>&1; date
         21s bash   cd /tmp/rprobes && cat > p_class_after_sum.py <<'PY' class C:     xs = [1, 2, 3]     t = sum(v for v in xs) + 
         21s bash   cd /tmp/rprobes && for f in p_sum_float p_sum_in_loop p_sum_filter p_dict_mutate p_set_non_nested p_no_nested_
         16s bash   cd /tmp/rprobes && cat > p_class_after_sum_wrong.py <<'PY' xs = [9, 9]  class C:     xs = [1, 2, 3]     t = su
         13s bash   cd /tmp/rprobes && for f in p_nonliteral_join p_nonstr_join p_sum_start_nested p_sorted_key p_fstring_conv p_n
         13s bash   cd /tmp/rprobes && for f in p_sum_classbody p_sum_classbody2 p_any_classbody; do echo "########## $f HEAD"; ba

FINAL VERDICT: FIX  2026-10-28T22:50:17Z
