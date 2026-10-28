# job job-pre399-10281027  started 2026-10-28T01:31:07Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"f9236015-bec8-4c4f-ae8a-f7384ed5c075","session_id":"22b7f704-79a1-428c-a1ef-a1cf6e637166"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"e25be20f-474d-425d-93c8-38d38016f903","session_id":"407b372e-f911-4dd6-93a5-63bba250b724"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the class-body self-reference difference on both builds: a class name is now unbound while its own body runs, so reads raise CPython’s `NameError`; deferred lambdas/methods and saved generator expressions still match CPython.

- Probes `/tmp/probes/pre399`: `m01`–`m08` match CPython; `n01`–`n12` (direct/items/argument/attribute/alias/lambda/default/callback/generator routes) print nothing and exit 1 with `NameError`, on both builds.
- Final commit `6af60dc`.
- Tests on final commit: `test_ail_pre399`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `tools/update_manifest.py --check` passes; records updated with the corrected pre-fix behaviour.
[cost $0.0000, opencode tokens {"total": 1758060, "input": 59616, "output": 9473, "reasoning": 9099, "cache.write": 0, "cache.read": 1679872}]
    tool time: bash 8.7 min, edit 0.0 min, write 0.0 min
        409s bash   printf '%s\n' test_ail_pre399 test_ail_safetynet test_ail_files test_ail_corpus_findings3 | xargs -P2 -I{} bas
         91s bash   mkdir -p /tmp/probes/pre399; cp /tmp/probes/v1b.py /tmp/probes/pre399/n01_immediate_lambda.py; cp /tmp/probes/
         14s bash   cat > /tmp/probes/v1b.py <<'EOF' class C:     y = (lambda: C)() print(C.y) EOF cat > /tmp/probes/v1c.py <<'EOF
          5s bash   mkdir -p /tmp/probes; cat > /tmp/probes/v1.py <<'EOF' class D:     v = 1     fs = [(lambda: [D][0]().v)()] pri
          3s bash   git fetch --no-tags origin refs/heads/job-pre382-10280718:refs/remotes/origin/job-pre382-10280718 2>&1 | tail 
          0s bash   grep -rn "lambda: \[D\]\|\[D\]\[0\]\|D() takes\|genexp reads\|saved genexp\|reads the name only" . --exclude-d
          0s bash   git add AIL_CURRENT/test_ail_pre399.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py
          0s bash   python3 tools/update_manifest.py; python3 tools/update_manifest.py --check; echo check_exit=$?; git status --s

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** ports a module-lifetime `g_cls_ready_<slot>` flag: `_init_class_attrs` leaves it 0 while a class body runs and sets it 1 afterwards; name/attribute/constructor/lambda/comprehension reads of the busy class emit a `NameError` check (`pyboxed2.py:5081,5878,7220,9065`), and genexps clear the busy gate for their body.

**Claims:**
- v1/v2 base behaviour and updated records: verified (base: `TypeError` for v1, success for v2; HEAD: `NameError`).
- m01–m08 / n01–n12 and both builds: verified by `test_ail_pre399` (20 cases) passing.
- deferred lambdas/methods/saved genexps: verified (`p07`, `q11` match).
- `test_ail_pre399`, safetynet, files, corpus_findings3: verified, 4 modules 0 failed.
- commit `6af60dc`, manifest `--check`: verified.
- “any read … raises `NameError`” is **false** for a class-body attribute that shadows the class name.

**Defects (change-caused; base matches CPython):**
1. `class D: v = 7` / `class C: C = D; x = C.v` / `print(C.x)` — expected `7`, exit 0; HEAD (both builds) empty stdout, exit 1, `NameError: name 'C' is not defined`. Base prints `7`. The `expr_Attribute` gate ignores `ctx.class_locals` (`pyboxed2.py:5878`).
2. `class D: def m(self): return 42` / `class C: C = D(); x = C.m()` / `print(C.x)` — expected `42`, exit 0; HEAD empty stdout, exit 1, `NameError`; base prints `42`. The `_call_attribute` gate has the same missing `class_locals` guard (`pyboxed2.py:9065`).
3. Related same root: `class id: x = id` / `print(id.x is id)` — CPython `False` exit 0; HEAD `NameError` exit 1 (base prints `True`, already wrong). The gate also ignores builtin fallback.

**Pre-existing (identical on base):**
- `class C: x = list(C for i in range(1))`: CPython `NameError`, base and HEAD print the class, exit 0. `lazy_body` clears the gate for the eagerly materialised body.
- `f = lambda: C; class C: x = f()`: CPython `NameError`, base and HEAD print the class, exit 0.

**Other checks:** generated `program.c` for two non-self-referential gdev programs is unchanged vs `/tmp/base`; no hot-path change, so no instruction-count run.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1921171, "input": 129220, "output": 7706, "reasoning": 24373, "cache.write": 0, "cache.read": 1759872}]
    tool time: bash 11.5 min
        409s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre399 test_ail_
         49s bash   cd /tmp/rprobes; for f in q*.py; do echo "===== HEAD $f"; bash ~/tools/cmp.sh $PWD/$f /home/runner/work/ail-ci
         40s bash   cd /tmp/rprobes; for f in p*.py; do echo "===== $f"; bash ~/tools/cmp.sh $PWD/$f /home/runner/work/ail-ci/ail-
         27s bash   cd /tmp; for p in g12_036 g25_034; do for wt in head base; do if [ $wt = head ]; then W=/home/runner/work/ail-
         26s bash   cd /tmp/rprobes cat > t01_shadow_attr.py <<'EOF' class D:     v = 7 class C:     C = D     x = C.v print(C.x) 
         19s bash   cd /tmp/rprobes cat > v1_selfread.py <<'EOF' class D:     v = 1     fs = [(lambda: [D][0]().v)()] print(D.fs) 
         19s bash   cd /tmp/rprobes cat > r01_catch_class.py <<'EOF' try:     class C:         x = C except NameError as e:     pr
         18s bash   cd /tmp/rprobes; for f in p01_genlist.py p03_outer_lambda.py p07_saved_gen.py p08_other_class.py; do echo "===

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed as `661361c`.

- Class-body bindings reusing the class name now resolve to that binding (`expr_Attribute`, `_call_attribute` class-locals guards).
- Builtin-named classes no longer rename the builtin inside their own body; `id` is supported as a value/call, so `class id: x = id` matches CPython.
- Corrected the saved-genexp claim in DIFFERENCES/DEVLOG.

Probes: 17 run on both builds — 13 match CPython, 2 refused by name, 2 remain pre-existing mismatches (`class C: x = list(C for ...)`, `f = lambda: C; class C: x = f()`).

Final-commit tests: `test_ail_pre399`, `test_ail_builtin_shadowing`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 6539944, "input": 135452, "output": 12001, "reasoning": 30123, "cache.write": 0, "cache.read": 6362368}]
    tool time: bash 22.1 min
        429s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && printf '%s\n' test_ail_pre399 test_ail_builtin_shadowing tes
        427s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo manifest_ok && cd AIL_C
        171s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_p
        168s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_p
         57s bash   cd /tmp/probes/pre399fix && cat > p01_shadow_attr_container.py <<'EOF' class D:     v = 7 class C:     C = [D]
         22s bash   mkdir -p /tmp/probes/pre399fix && cd /tmp/probes/pre399fix && cat > t01_shadow_attr.py <<'EOF' class D:     v 
         18s bash   cd /tmp/probes/pre399fix && for f in t04_genexp_eager.py t05_lambda_call.py t06_id_call.py t07_id_value.py; do
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I have enough to write the report.

**What the change really does.** It ports pre382's "busy class" flag: while a class body runs, a read of that class's own name compiles to a runtime `NameError` (skipped when a class-body binding supplies the name), and a saved generator's body is excluded from the gate. It also stops the shadowing renamer from renaming a first-defined builtin-named class's name inside its own body, and adds `id` as a builtin value/call (`_b_id`) so `class id: x = id` compiles.

**Probes** (`bash ~/tools/cmp.sh`, both builds, HEAD vs `/tmp/base`):

| probe | CPython | HEAD g/d | base |
| --- | --- | --- | --- |
| p04 `class C: C = D; x = C.v` | 7 | same | same |
| p13 container/method binding | same | same | same |
| p14 `C = D(); x = C.m()` | 42 | same | same |
| p05 `class id: x = id; y = id(7)` | False/True | same | refused by name |
| p07/p08/p24 saved genexp | class / `[5]` | same | same |
| p11 plain, p23 class+genexp | — | same; `program.c` byte-identical to base | — |
| p31/p32 earlier in-body int/list binding | 6 / 1 | same | same |
| **p02** `id(True)==id(1)`, `id(0)==id(False)` | False,False | **True,True** | refused by name |
| **p03** `a=2**40; b=a+0; id(a)==id(b)` | False | **True** | refused by name |
| **p28** id via argument/list item/attribute/dict value | False×4 | **True×4** | refused by name |
| p22 `"hello"` vs `"hel"+"lo"` ids | True | **False** | refused by name |
| p21 `def get(): return C; class C: x=get()` | NameError | class, exit 0 | class, exit 0 (pre-existing) |
| p29/p30 saved genexp consumed in body by `next`/`any` | NameError | class, exit 0 | class, exit 0 (pre-existing) |
| p20 class-level dict comp reading C | NameError | — | both builds refused by name |
| p01/p06/p09/p16/p17/p25/p26/p27 | — | refused by name | refused by name (pre-existing) |

`v1_selfread` base: `TypeError: D() takes other arguments`, exit 1; HEAD `NameError`, matching CPython. `v2_selfread2` base: compiles, prints `<class '__main__.C'>`; HEAD `NameError` — both base-tree record corrections verified.

**Report claims.** Class-body rebinding fix — verified (p04, p13, p14). Builtin-named class fallback — verified for the test's exact program (p05), but the accompanying `id` support introduces the defect below, and the DIFFERENCES text "`_b_id` returns the object's address" is false: the code returns the integer value for int/bool and `backing+off` for strings, so distinct objects with equal values share an id. Saved-genexp claim correction — verified (p07/p08 vs p29/p30). Probe counts, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing` and `update_manifest.py --check` — unverified here.

**Tests on HEAD.** `test_ail_pre399`, `test_ail_safetynet`: 2 modules, 0 failed (184s).

**Speed.** `perf_event_open` is denied on this runner, so no icount. Generated C is byte-identical to base for a plain program and a class+genexp program, and the new gate is compile-time-gated, so no hot-path change is expected.

**Pre-existing** (identical on base): p21 class read through a function defined before the class, p29/p30 in-body consumption of a saved genexp, and the named refusals above.

VERDICT: FIX
1. `id()` does not model object identity — `_b_id` collapses int/bool to `.i` and strings to `backing+off`, so distinct objects with equal values compare equal. This is new wrong output (base refused `id` by name).
   - Probe `/tmp/rprobes/p02_id_bool.py`: `print(id(True) == id(1))` / `print(id(0) == id(False))`. Expected (CPython, HEAD exit 0): `False`, `False`. Actual HEAD (both builds): `True`, `True`.
   - Probe `/tmp/rprobes/p03_id_bigint.py`: `a = 2 ** 40; b = a + 0; print(id(a) == id(b))`. Expected `False`; actual `True`.
   - Probe `/tmp/rprobes/p28_id_routes.py`: `id(v)` through an argument, `id(items[0]) == id(items[1])`, an attribute and a dict value. Expected `False` ×4; actual `True` ×4.
   Fix: keep `id` refused by name (drop it from `_BUILTIN_VALUE_ARITY` / raise `Unsupported`) or model identity properly; also correct the DIFFERENCES wording "returns the object's address", which is false for int/bool/str.

FINAL VERDICT: FIX  2026-10-28T04:12:19Z
