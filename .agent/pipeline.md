# job job-cov52-10292235  started 2026-10-29T14:34:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"cef73807-f4f7-48a2-8def-6871fc9c6fa9","session_id":"98769529-d83d-4c36-9eda-8d50932b0f5d"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"831a0c3a-2b78-4dc9-ac7e-a3481053c235","session_id":"1aee447b-a823-419e-b2b1-6c43ab7050c4"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

**Change:** Nested generator expressions are now supported when the outer and every inner generator are passed directly to a consumer that drains the whole iterable (`sum/list/tuple/sorted/min/max/set/dict` or a literal `str`/`bytes` `.join`). Unsafe shapes keep the named refusal.

**Census:** 219 programs × both builds → compile refusals **48 records / 24 programs**, now **42 / 21**. The chosen construct was the most frequent non-import refusal: **3 programs** (deepseek t172/t432, glm t432), all now matching CPython on all three inputs on both builds.

**Probes (`cmp.sh`, both builds):**
- Match: `p01_join`, `p02_sum`, `p03_reductions`, `p04_routes` (argument/list item/attribute/dict value), `p05_triple`
- Refused by name: `p06_inner_iter_refused`, `p07_unconsumed_refused`, `p08_list_later_refused`, `p09_shadow_refused`

**Tests on final commit:** `test_ail_cov52`, `test_ail_pre41`, `test_ail_pre42`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → **31 run, 0 failed, 1 skipped** (no zig). `update_manifest.py --check` passes.

Commits: `83530f5` (fix) and `faa0c78` (manifest pin). Not pushed.
[cost $0.1065, opencode tokens {"total": 8589701, "input": 349451, "output": 20625, "reasoning": 28521, "cache.write": 0, "cache.read": 8191104}]
    tool time: bash 60.1 min, write 0.0 min
        900s bash   mkdir -p /tmp/census && cat > /tmp/census/census.py <<'EOF' import json, os, re, subprocess, tempfile, shutil,
        456s bash   python3 -m unittest -v test_ail_safetynet test_ail_files test_ail_corpus_findings3
        357s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "##### $(basename $p)"; bash ~/tools/
        300s bash   sleep 300; wc -l /tmp/census/out2.jsonl; tail -2 /tmp/census/log2.txt
        300s bash   sleep 300; wc -l /tmp/census/out2.jsonl; tail -2 /tmp/census/log2.txt
        300s bash   sleep 300; wc -l /tmp/census/out2.jsonl; tail -2 /tmp/census/log2.txt
        240s bash   sleep 240; wc -l /tmp/census/out2.jsonl; tail -3 /tmp/census/log2.txt
        236s bash   python3 -m unittest -v test_ail_cov52 test_ail_pre41 test_ail_pre42 test_ail_safetynet test_ail_files test_ail

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Change:** `pyfront.safe_generator_expressions` now lets a nested generator expression through when the outer expression and every inner one are direct arguments of an eager consumer (`sum/list/tuple/sorted/min/max/set/dict` or literal `str`/`bytes`.join`); both emitters consult the resulting id set. This matches the report.

**Claims**
- Verified: common shapes match CPython on both builds (`join`, `sum`, reductions, triple nesting, bytes, `sum(gen, start)`, inner in an `if`, routes through arg/list/attr/dict); `for`-iterable / `any` / `all` / assigned-generator / user-defined-`sum` stay refused; `test_ail_cov52`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass (0 failed); `update_manifest.py --check` exits 0; C is byte-identical to base for a feature-free program (`--debug-dir`, general path).
- False: “a shadowed builtin stays refused.” Two shadowing forms bypass `_bound_names` and are now silently miscompiled.
- Unverified: census 48/24→42/21, the three corpus programs, exact test counts, speed (front-end-only change, not measured).

**Defects**
1. Lambda parameter shadows a consumer. `pyfront.py:1282` collects args for `FunctionDef`/`AsyncFunctionDef` but not `ast.Lambda`, so `sum` in a lambda parameter counts as the builtin.
   Probe: `f = lambda sum: list(sum(v for v in row) for row in [[1, 2], [3]])` / `print(f(lambda g: g[0]))`
   CPython: `TypeError: 'generator' object is not subscriptable`, exit 1 (base refuses by name). HEAD: prints `[1, 3]`, exit 0, both builds.
2. `except ... as sum` shadows a consumer. `_bound_names` ignores `ast.ExceptHandler.name`.
   Probe: `try: raise ValueError("boom")` / `except ValueError as sum:` / `rows=[[1,2],[3]]` / `print("\n".join(str(sum(v for v in row)) for row in rows))`
   CPython: `TypeError: 'ValueError' object is not callable`, exit 1 (base refuses by name). HEAD: prints `3\n3`, exit 0, both builds. (The non-nested counterpart is already wrong on base; the new gate turns a named refusal into a silent difference.)

**Pre-existing:** sorting/min/max of sets hits the same runtime “AIL limit” on base and HEAD (`sorted(set(row) for row in rows)`); except-as name resolution without nesting is equally wrong on base.

**Probes:** p01–p19 in `/tmp/rprobes` run via `cmp.sh` on HEAD; p07/p08/p09/p16/p17/p18 also on `/tmp/base`.

VERDICT: FIX — 1) lambda-parameter shadow (p16: expected TypeError/exit 1, got `[1, 3]`/exit 0), 2) except-as shadow (p08: expected TypeError/exit 1, got `3\n3`/exit 0).
[cost $0.0245, opencode tokens {"total": 718279, "input": 51246, "output": 4535, "reasoning": 20322, "cache.write": 0, "cache.read": 642176}]
    tool time: bash 7.7 min
        350s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_cov5
         72s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p*.py; do echo "##### $(basename $p)"; bash ~/tools/
         26s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p16_lambda_shadow2.py /tmp/rprobes/p17_sorted_set_pl
          5s bash   cd /tmp/rprobes && cat > p19_consumers2.py <<'EOF' rows = [[3, 1, 2], [], [-1, 5]] print(sorted(sorted(v for v
          4s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh /tmp/rprobes/p08_except_shadow.py /tmp/base 2>&1 | tai
          1s bash   rm -rf /tmp/base && git worktree add /tmp/base work >/tmp/baseadd.log 2>&1; tail -2 /tmp/baseadd.log; git -C /
          0s bash   cd /home/runner/work/ail-ci/ail-ci; python3 AIL_CURRENT/ail_chatgpt.py compile --help 2>&1 | grep -n "debug-di
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "exit $?"

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `fb3717f`.

- `_bound_names` now collects `ast.Lambda` parameters and `ast.ExceptHandler.name`; also `match` captures (`MatchAs`, `MatchStar`, `MatchMapping.rest`) which had the same bypass.
- Added lambda/except shadow refusal cases to `test_ail_cov52.py`.
- Probes on both builds via `cmp.sh`: `p01_lambda_sum`, `p02_lambda_list`, `p03_except_sum`, `p04_except_join`, `p05_match_sum`, `p06_match_rest`, `p07_lambda_vararg`, `p08_lambda_kwonly`, `p12_lambda_default_sum` refused by name; `p09_lambda_other_name_ok`, `p10_except_other_name_ok`, `p11_match_other_name_ok` match CPython.
- Final-commit tests: test_ail_cov52, test_ail_pre41, test_ail_pre42, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 6 modules, 0 failed (362s).
- `update_manifest.py --check` exits 0.
- Census: 42 records / 21 programs after the feature, 48 / 24 on base. I did not rerun the full 219-program census; an AST scan shows no corpus program binds a consumer name via lambda/except/match, so those counts are unchanged by this fix.
[cost $0.0169, opencode tokens {"total": 1134856, "input": 35021, "output": 6705, "reasoning": 7306, "cache.write": 0, "cache.read": 1085824}]
    tool time: bash 12.3 min, edit 0.0 min
        363s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && cd AIL_CURRENT && timeout 24
        344s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
         26s bash   cd /tmp/probes && cat > p11_match_other_name_ok.py <<'EOF' value = [[1, 2], [3]] match value:     case rows:  
          1s bash   cd /tmp/probes && cat > p02_lambda_list.py <<'EOF' f = lambda list: tuple(list(v for v in row) for row in [[1,
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   git -C /tmp/base log --oneline -2 2>/dev/null; git -C /tmp/base status --short 2>/dev/null | head
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && python3 tools/update_manifest.py && python3 tools/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import ast, pathlib cons={'sum','list','tuple','sorted'

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** It adds `pyfront.safe_generator_expressions()` (`pyfront.py:1355`), which whitelists a nested `GeneratorExp` when the outer and every inner one are the first positional argument of an unshadowed `sum/list/tuple/sorted/min/max/set/dict` or a literal `str/bytes.join`; both emitters (`pyboxed.py`, `pyboxed2.py`) then skip the blanket nested-genexpr refusal for those ids. The review commit additionally collects `Lambda` parameters, `ExceptHandler.name` and match captures in `_bound_names`. This matches the report.

**Verified**
- Intended shape works: `test_ail_cov52` + `test_ail_safetynet` pass (2 modules, 0 failed, 162 s). All 18 runs of the three corpus programs (deepseek t172/t432, glm t432 × 3 inputs × 2 builds) match CPython. No-feature program's generated `program.c` is identical base vs HEAD.
- Lambda/except/match binding bypasses are closed: `r04` (MatchAs), `r05` (MatchStar), `r06` (MatchMapping.rest), `r09` (keyword-only lambda param), plus the module's `lambda_parameter_shadow`/`except_as_shadow` cases are refused by name.
- `update_manifest.py --check` exits 0; MANIFEST change is consistent.

**Pre-existing** (identical on base and HEAD; single-level analogues):
- `sum(f(x) for x in ["a","b"])` prints an extra `f b` before `TypeError`.
- `sum((p(v) for v in row), start())` prints `start` after the elements.
- `min((v for v in row), [9])` prints `[1, 2, 3]` instead of raising.

**Defects** (base `/tmp/base` refuses these, HEAD on both builds silently differs):
1. `min`/`max` are misclassified as eager consumers when they have a second positional argument. `pyfront.py:1315-1323` only checks `call.args[0] is node`; CPython never iterates arg 0 when `min`/`max` has more than one positional arg.
   - `rows = [[1, 2], [3]]; print(min((sum(v for v in row) for row in rows), [9]))`
   - expected: exit 1, no stdout, `TypeError: '<' not supported between instances of 'generator' and 'list'`
   - actual: exit 0, stdout `[3, 3]` (both builds). `max(...)` prints `[9]` and exits 0.
2. Additional evaluated arguments are drained in the wrong order.
   - `def start(): print("start"); return 100` / `def p(v): print("p", v); return v` / `rows=[[1,2],[3]]` / `print(sum((sum(p(v) for v in row) for row in rows), start()))`
   - expected stdout: `start`, `p 1`, `p 2`, `p 3`, `106`
   - actual: `p 1`, `p 2`, `p 3`, `start`, `106` (exit 0 both builds).
3. "Drains before returning" fails when a consumer rejects an element (sum/dict/join validate as they go).
   - `def f(x): print("f", x); return x` / `rows=[["a","b"],["c"]]` / `print(sum(sum(f(y) for y in row) for row in rows))`
   - expected stdout: `f a` (then `TypeError`); actual: `f a` + `f b` (both exit 1).
   - `rows=[[1],[2]]; print(dict(f(sum(y for y in row)) for row in rows))`
   - expected stdout: `f 1`; actual: `f 1` + `f 2`. (Same eager-materialisation flaw as the pre-existing single-level case, but these nested programs are newly accepted.)

**Unverified:** the 42 records/21 programs vs 48/24 census (worker did not rerun it); the worker's `p01`–`p12` probes (I re-ran analogues only); `test_ail_pre41`, `test_ail_pre42`, `test_ail_files`, `test_ail_corpus_findings3` (not re-run per review scope).

VERDICT: FIX
1. `min`/`max` with more than one positional argument must not count as an eager consumer (`pyfront.py:1315`), otherwise `r11`/`r12` return a value where CPython raises.
2. The whitelist must not ignore additional evaluated arguments (sum `start`, min/max extra values), otherwise `r16` reorders side effects.
3. Sum/dict/join are not drain-before-validate consumers; the nested forms `r02`/`r08` leak side effects that CPython never performs before the error.
[cost $0.0378, opencode tokens {"total": 1189436, "input": 86952, "output": 6439, "reasoning": 29421, "cache.write": 0, "cache.read": 1066624}]
    tool time: bash 5.6 min
        164s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_cov5
         32s bash   cd /tmp/base && for p in /tmp/rprobes/r02*.py /tmp/rprobes/r08*.py /tmp/rprobes/r11*.py /tmp/rprobes/r12*.py /
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r0*.py /tmp/rprobes/r10*.py; do echo "##### $(base
         28s bash   cd /tmp/rprobes && cat > s01_single_sum_string.py <<'EOF' def f(x):     print("f", x)     return x print(sum(f
         26s bash   cd /tmp/rprobes && cat > r11_min_two_args.py <<'EOF' rows = [[1, 2], [3]] print(min((sum(v for v in row) for r
         22s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/check_corpus.sh <<'EOF' set -u WT=$PWD for pair in "deepseek-
         17s bash   cd /tmp/rprobes && cat > r16_sum_start_order.py <<'EOF' def start():     print("start")     return 100 def p(v
          9s bash   cd /tmp/rprobes && cat > s03_single_min_two.py <<'EOF' row = [1, 2, 3] print(min((v for v in row), [9])) EOF e

FINAL VERDICT: FIX  2026-10-29T16:59:45Z
