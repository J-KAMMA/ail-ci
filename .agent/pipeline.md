# job job-pre324-10271601  started 2026-10-27T07:03:45Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"d2071c03-fe68-4fcf-b164-b75cbf6a7aa2","session_id":"7e73e74d-4bc6-425f-9f1a-6fc9d3bc787c"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"af509044-7d71-430a-9f57-416e7880aa16","session_id":"e69c97a0-fa48-45d0-beea-1a818046bec1"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Reproduced the first pre304 pre-existing item (p18): a method default reading an earlier class-body name (`x = 3; def m(self, a=x)`) used the module global (`100`) on both builds instead of CPython’s `3`. `_hoist_defaults` now refuses that construct by name; unaffected defaults still match CPython.

Commit `3b4ab10`. Probes in `/tmp/probes/pre324` (both builds, 18 total): 13 refused by name — `p18_default_class_attr`, `default_expr`, `with_init`, `init_before_attr`, `kwonly`, `method_earlier`, `alias_attr`, `class_attr_route`, `negative_attr`, `empty_attr`, `builtin_shadow`, `comp_outer_class`, `lambda_default_class`; 5 matched CPython — `default_later`, `no_class_attr`, `lambda_global`, `comp_body_global`, `module_func`.

Final commit tests: `test_ail_pre324`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 245 s, 0 failed; manifest `--check` passes. Relevant `test_ail_fuzz1` default test passes; the full fuzz1 module has unrelated missing-`difffuzz` failures. Speed not measured.
[cost $0.0000, opencode tokens {"total": 5129426, "input": 137216, "output": 11576, "reasoning": 15386, "cache.write": 0, "cache.read": 4965248}]
    tool time: bash 12.7 min
        343s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre324 test_ail_fuzz1 test_ail_safetynet test_ai
        247s bash   python3 tools/update_manifest.py --check && echo manifest-ok; cd AIL_CURRENT && python3 ../tools/par_check.py 
         71s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre324 2>&1 | tail -30
         58s bash   cat > /tmp/probes/pre324/p18_class_attr_route.py <<'PY' data = {"v": 3} class C:     x = data["v"]     def __i
         15s bash   mkdir -p /tmp/probes/pre324; cat > /tmp/probes/pre324/p18_default_class_attr.py <<'PY' x = 100 class C:     x 
         14s bash   cat > /tmp/probes/pre324/p18_with_init.py <<'PY' x = 100 class C:     x = 3     def __init__(self):         pa
          4s bash   d=$(mktemp -d /tmp/pre324dbgXXXX); cp /tmp/probes/pre324/p18_default_class_attr.py $d/p.py; cd $d; python3 "$P
          3s bash   cd AIL_CURRENT && python3 -m unittest test_ail_fuzz1.NonLiteralDefaults.test_class_attribute_default_refused_o

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed HEAD (`3b4ab10`) against `/tmp/base` (worktree of `work`). The change adds `_default_scope_loads` and makes `_hoist_defaults` reject a method default that loads any name bound with a smaller line number in the same class body. It fixes the recorded p18 sample (`x = 100; class C: x = 3; def m(self, a=x)` now refused by name on both builds; base printed `100`). Non-feature generated C is unchanged (diffed `--debug-dir` C for a plain program), tests `test_ail_pre324` and `test_ail_safetynet` pass, manifest `--check` passes.

But the refusal is broader than the constructed difference, because `_store_linenos` (pyboxed2.py:1285) counts things that are not class-body bindings:

- annotation-only `x: int` is recorded as binding `x`, though CPython only records `__annotations__`;
- comprehension targets are recorded, though `_default_scope_loads` correctly treats the comprehension as a separate scope.

Both programs compiled and matched CPython on the base; HEAD now refuses them.

Probes (CPython and base vs HEAD):
- `p18_orig` → base `100`/DIFF, HEAD refused by name (`reads the class-body name x`) — intended fix.
- `same_line*` → invalid Python (`SyntaxError`), no issue.
- `same_line_later`, `dict_value` → unchanged / intended.
- `ann_only`, `comp_target` → base matched (`100`), HEAD refused (defects below).

Claims: p18 reproduction and both-build refusal verified; "unaffected defaults still match CPython" is false (`ann_only`, `comp_target`); test and manifest claims for the modules I re-ran verified. Unverified: the other 4 test modules, worker's full 18-probe set, fuzz1, speed (compile-time-only, not needed).

VERDICT: FIX

1. Annotation with no value is wrongly treated as an earlier class-body binding.
```python
x = 100
class C:
    x: int
    def m(self, a=x):
        return a
print(C().m())
```
Expected (CPython and base): `100`
Actual (both HEAD builds): compile refusal `not in the subset: a default in method C.m reads the class-body name x; ...` — a new false refusal for a program that matched on the base.

2. A comprehension target is wrongly treated as an earlier class-body binding.
```python
x = 100
class C:
    y = [x for x in range(3)]
    def m(self, a=x):
        return a
print(C().m())
```
Expected (CPython and base): `100`
Actual (both HEAD builds): compile refusal `not in the subset: a default in method C.m reads the class-body name x; ...` — a new false refusal; `x` here is local to the comprehension, not a class attribute.
[cost $0.0000, opencode tokens {"total": 648416, "input": 39598, "output": 3753, "reasoning": 23305, "cache.write": 0, "cache.read": 581760}]
    tool time: bash 3.1 min
        103s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre324 test_ail_safetynet 2>&1
         28s bash   cat > /tmp/rprobes/match_capture.py <<'PY' x = 100 class C:     match 3:         case x:             pass     
         14s bash   date; for p in same_line same_line2 same_line_later ann_only async_local dict_value; do echo "===== $p BASE"; 
         13s bash   date; for p in same_line same_line2 same_line_later ann_only async_local dict_value; do echo "===== $p HEAD"; 
         13s bash   date; for p in comp_target ann_value with_bind arg_route; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /tmp/rp
          7s bash   echo "== p18 HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/p18_orig.py /home/runner/work/ail-ci/ail-ci 2>&1 | grep -
          4s bash   rm -rf /tmp/dbgrootH /tmp/dbgrootB; mkdir -p /tmp/dbgrootH /tmp/dbgrootB AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 p
          4s bash   cd /tmp/rprobes && python3 ann_only.py; python3 comp_target.py; echo ---; cat > /tmp/rprobes/p18_orig.py <<'PY

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `_store_linenos` (`AIL_CURRENT/python/pkg-v12/pyboxed2.py:1285`): annotation-only `x: int` no longer counts as a class binding, and comprehension generator targets are no longer treated as class-body bindings. Annotations with a value still bind and are refused when read by an earlier method default.

Probes (`/tmp/probes/pre324`, both builds):
- Match CPython: `p18_ann_only`, `p18_ann_only_alias`, `p18_ann_only_arg`, `p18_ann_only_multi`, `p18_comp_target`, `p18_comp_target_arg`, `p18_comp_target_dict`, `p18_comp_target_gen`, `p18_comp_target_nested`, `p18_comp_target_tuple`.
- Refused by name as intended: `p18_ann_value`, `p18_ann_only_then_attr`, `p18_comp_target_with_attr`, `p18_comp_target_then_attr`.
- Earlier 18 probes: 5 match, 13 refused by name.
- Total: 15 match, 17 refused by name, 0 unexplained differences.

Tests: `test_ail_pre324`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 263s, 0 failed. `test_ail_fuzz1.NonLiteralDefaults` + `ForwardLambdaDefaults` — 16 tests, OK. Manifest `--check` passes.

Committed as `36784a0`.
[cost $0.0000, opencode tokens {"total": 954342, "input": 49476, "output": 6904, "reasoning": 10410, "cache.write": 0, "cache.read": 887552}]
    tool time: bash 8.4 min, write 0.0 min, edit 0.0 min
        265s bash   cd /home/runner/work/ail-ci/ail-ci && date; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 
        109s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre324/*.py; do echo "===== $(basename $p)"; bash ~
         79s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest test_ail_fuzz1.NonLiteralDef
         49s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre324/p18_ann_only.py /tmp/probes/pre324/p18_comp_
          3s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/pre324/p18_alias_attr.py "$PWD" 2>&1 | t
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && python3 -m py_compile AIL_CU
          0s bash   cd /home/runner/work/ail-ci/ail-ci && date; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed HEAD `36784a0` against `/tmp/base` (worktree of `work`).

**What the change really does:** `_hoist_defaults` refuses, by name, a method default that loads a name bound earlier in the same class body; `_store_linenos` no longer treats annotation-only targets or comprehension generator targets as class-body bindings. This matches the report.

**Probes:**
- p18 original: base printed `100` (DIFF), HEAD refuses by name on both builds — intended.
- All 32 `/tmp/probes/pre324` probes: 15 match, 17 named refusals, 0 unexplained (matches report exactly).
- My probes (`/tmp/rprobes`): annotation-only, comprehension target, nested/tuple/dict/gen comps, lambda/comprehension bodies, module functions, later attrs, args/list/attr/dict routes, `del`, `if False`, `except as`, `global`, for/with targets, async, nested class — all match CPython or are named refusals.
- `r29`–`r33` (`x if False else 7`, `0 and x`, `[x][0:0]`, etc.): base matched, HEAD now conservatively refuses. This is a named refusal of a default that syntactically loads an earlier class-body name, so it is acceptable under the task; however, the claim “loads the `def` statement evaluates now are counted” is overbroad — dead/short-circuited loads are counted too. No wrong output, crash, or wrong exit status found.
- Non-feature C identical: `--debug-dir` `program.c` unchanged for `plain.py`, `p18_ann_only`, `p18_comp_target`.

**Pre-existing (same on base):** nested class inside a function refused; async method in a class body refused; class-body `for`/`with`/`try`/`global` refused.

**Tests:** `test_ail_pre324` and `test_ail_safetynet` — 2 modules, 100s, 0 failed. `test_ail_fuzz1.NonLiteralDefaults` + `ForwardLambdaDefaults` — 16 tests, OK. `update_manifest.py --check` passes. `test_ail_files`/`test_ail_corpus_findings3` runs not re-verified.

**Speed:** compile-time-only change; not measured.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1722615, "input": 106470, "output": 7661, "reasoning": 38692, "cache.write": 0, "cache.read": 1569792}]
    tool time: bash 9.0 min
        111s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/probes/pre324/*.py; do n=$(basename $p .py); out=$
        101s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         75s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 -m unittest test_ail_fuzz1.NonLi
         46s bash   cd /home/runner/work/ail-ci/ail-ci && for n in p18_ann_only p18_ann_only_alias p18_ann_only_arg p18_ann_only_m
         42s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/r*.py; do echo "===== $(basename $p)"; tim
         28s bash   cd /tmp/base && for p in /tmp/rprobes/r1[5-9]_*.py /tmp/rprobes/r2[0-2]_*.py; do echo "===== BASE $(basename $
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r1[5-9]_*.py /tmp/rprobes/r2[0-2]_*.py; do echo "=
         20s bash   cd /tmp/base && for p in /tmp/rprobes/r04_cond_false.py /tmp/rprobes/r08_comp_outer_attr.py /tmp/rprobes/r13_d

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T09:14:43Z
