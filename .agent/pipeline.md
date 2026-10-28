# job job-cov14-10290221  started 2026-10-28T17:31:22Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"228df496-01b0-43ae-ab75-88ab4c5b5992","session_id":"cd5f070c-4eb8-4354-87a5-51dca0e7654d"}
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"39f34e99-4d4a-4b2f-a753-06f587161823","session_id":"230c4def-979f-44fb-a81c-eeb4884d5d94"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed as `50814ca` on `job-cov14-10290221`.

- Profiled all 219 corpus programs in both builds. `lab/profile/run.py` is absent; used the `lab/corpus/check.py` compile loop instead.
- Supported construct: generator expression nested inside another when the inner one is eagerly/fully consumed (`sum`, `join`, `list`, `tuple`, `sorted`, `min`, `max`, unpacking). Lazy nestings stay refused by name.
- Refused programs: default **24 → 21**, `AIL_UNIFIED_FORCE=1` **24 → 21**; nested-genexpr refusals **3 → 0**.
- Recovered corpus programs `t172`, `t432`, `glm/t432` match CPython on all three inputs in both builds.
- Probes in `/tmp/probes/cov14`: `basic`, `p_sum`, `p_join`, `p_routes`, `p_alias`, `p_any`, `p_any_inner`, `p_nested_any`, `p_next_nested` match CPython; `p_unsafe`, `p_unsafe2`, `p_any_unsafe` are refused by name. Both builds covered.
- Tests passed: `test_ail_cov14` (4), `test_ail_pre116` (9), `test_ail_pre211` (2), `test_ail_unified` (14), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skipped), `test_ail_corpus_findings3` (2).
- `update_manifest --check` and `ci_shards --check` pass. Only untracked `.agent/pipeline.md` remains.
[cost $0.0597, opencode tokens {"total": 5345008, "input": 133515, "output": 18011, "reasoning": 22282, "cache.write": 0, "cache.read": 5171200}]
    tool time: bash 43.2 min
        819s bash   mkdir -p /tmp/prof && cat > /tmp/prof/run.py <<'PY' import json, os, re, subprocess, sys, tempfile, shutil, ti
        433s bash   cd /home/runner/work/ail-ci/ail-ci && for m in test_ail_pre116 test_ail_pre211 test_ail_unified test_ail_safet
        432s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 /tmp/prof/run.py
        335s bash   cd /home/runner/work/ail-ci/ail-ci && for m in test_ail_safetynet test_ail_files test_ail_corpus_findings3; do
        307s bash   cd /home/runner/work/ail-ci/ail-ci && for m in test_ail_cov14 test_ail_pre116 test_ail_pre211 test_ail_unified
         46s bash   cat > /tmp/probes/cov14/p_next_nested.py <<'PY' rows = [[1, 2], [3, 4]] print(next(sum(v * 2 for v in row) for
         34s bash   mkdir -p /tmp/probes/cov14 && cat > /tmp/probes/cov14/p_sum.py <<'PY' rows = [[1, 2, 3], [4, 5], [], [-2, -7]]
         24s bash   cd /home/runner/work/ail-ci/ail-ci && cat > AIL_CURRENT/test_ail_cov14.py <<'PY' """Branch cov14: a generator 

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Review — cov14 (commit 50814ca)**

Change really does: replaces the blanket refusal for any generator expression nested in another with `_nested_genexp_unsafe`, which permits the inner one when its immediate consumer is a call named like a consuming builtin (`sum`, `min`, `max`, `list`, …), a method named `join`/`extend`/`update`/`array`, a starred unpack, or tuple/list unpacking — matched by name/attribute only, and with no account of the receiver type or keyword arguments.

**Defects (base refuses all of these, HEAD accepts them with wrong output):**

1. Method-name heuristic accepts user-defined consumers. Probe `/tmp/rprobes/r_value_diff.py`:
```python
log = []
def f(x):
    log.append(x); return x
class C:
    def extend(self, it):
        v = next(iter(it))
        return (v, len(log))
c = C()
print(list(c.extend(f(x) for x in [1, 2, 3]) for _ in [0]))
```
Expected CPython: `[(1, 1)]`; actual HEAD (both builds): `[(1, 3)]` — the inner generator was materialised eagerly. Same wrong result with a user method named `update` (`r_custom_update.py`: expected `[1] (1, 1)`, got `[1, 2, 3] (1, 1)`) and `join` (`r_custom_join.py`: expected `[1]`, got `[1, 2, 3]`).

2. `min`/`max` with `key=` interleave element production and key calls; eager materialisation reorders them. Probe `/tmp/rprobes/r_max_key2.py`:
```python
log = []
def f(x):
    log.append(('f', x)); return x
def k(x):
    log.append(('k', x)); return -x
print(list(max((f(x) for x in [1, 2, 3]), key=k) for _ in [0]))
print(log)
```
Expected: `[('f', 1), ('k', 1), ('f', 2), ('k', 2), ('f', 3), ('k', 3)]`; actual HEAD: `[('f', 1), ('f', 2), ('f', 3), ('k', 1), ('k', 2), ('k', 3)]` on both builds.

Because the guard is syntactic, the fix needs to restrict the allowance to provably builtin receivers and to consumer paths with no interleaved callbacks (e.g. no `key=`), otherwise keep the named refusal.

**Claim checks**
- `lab/profile/run.py` absent: verified.
- Test module registration / manifest / ci_shards: verified (`--check` exit 0); only `.agent/pipeline.md` untracked.
- `test_ail_cov14` (4 tests) and `test_ail_safetynet` on HEAD: verified pass.
- Refusal counts 24→21 (both builds), nested-genexpr 3→0: unverified.
- `t172`/`t432` recovered and matching CPython on all three inputs both builds: unverified.
- Probes listed in the report match/refuse: own probes `r_basic` and no-feature program match; no-feature `--debug-dir` C source identical to base (only path fields differ).
- No runtime/hot-code path touched, so instruction counts not run.

Unverified: corpus profiling totals, recovered-program outputs, the report's other claimed test modules (`pre116`, `pre211`, `unified`, `files`, `corpus_findings3`).

VERDICT: FIX
[cost $0.0161, opencode tokens {"total": 483115, "input": 38883, "output": 3872, "reasoning": 11048, "cache.write": 0, "cache.read": 429312}]
    tool time: bash 2.0 min
         88s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_cov1
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r_*.py; do (bash ~/tools/cmp.sh "$p" "$PWD" > "${p
          7s bash   cat > /tmp/rprobes/r_max_key2.py <<'PY' log = [] def f(x):     log.append(('f', x))     return x def k(x):    
          4s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir dbg_head dbg_base && cd dbg_head && cp /tmp/rprobes/r_nofeature.p
          4s bash   cd /home/runner/work/ail-ci/ail-ci && find lab -name 't172*' -o -name 't432*' | head; cd /tmp/base && bash ~/t
          3s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r_max_key2.py /tmp/rprobes/r_custom_join.py; do (b
          2s bash   cat > /tmp/rprobes/r_value_diff.py <<'PY' log = [] def f(x):     log.append(x)     return x class C:     def e
          0s bash   git worktree add /tmp/base work 2>&1 | tail -2; cd /tmp/base && git log --oneline -1

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `5ff126f`.

**Fix:** `_nested_genexp_unsafe` now accepts a nested generator only when its sole-argument, keyword-free consumer is an unshadowed builtin (`sum`, `min`, `max`, `list`, `tuple`, `set`, `frozenset`, `dict`, `sorted`, `bytes`, `bytearray`) or `join` on a provably exact `str` (literal, f-string, unshadowed `str(...)`). User methods, rebound builtin names, extra arguments, and `key=`/`start=`/`default=`/`reverse=` keep the named refusal. Starred/unpacking consumers unchanged.

**Corpus (219 programs, both builds):** refusals 24 → 21 before the original cov14 change; still 21 after this review fix (24/24 base). Nested-generator refusals 3 → 0. `t172` and both `t432` variants match CPython on all 3 inputs in both builds.

**Probes** (`/tmp/probes/cov14fix`, both builds):
- Match CPython: `p_sum_gen`, `p_minmax_gen`, `p_join_gen`; also `p_sum`, `p_minmax`, `p_join`, `p_join_var`.
- Refused by name: `p_custom_extend`, `p_custom_update`, `p_custom_join`, `p_max_key`, `p_shadowed_sum`, `p_sum_start`, `p_join_var_gen`, `p_lazy`; `p_star_gen` remains refused (different named reason on HEAD).

**Tests on final commit:** `test_ail_cov14`, `pre116`, `pre166`, `pre211`, `unified`, `safetynet`, `files`, `corpus_findings3` — 8 modules, 0 failed (392s). `update_manifest.py --check` exits 0.
[cost $0.0350, opencode tokens {"total": 2085777, "input": 81785, "output": 11656, "reasoning": 16400, "cache.write": 0, "cache.read": 1975936}]
    tool time: bash 32.0 min
        807s bash   sed "s#ROOT=Path('/home/runner/work/ail-ci/ail-ci')#ROOT=Path('/tmp/base')#; s#/tmp/profile_corpus.json#/tmp/p
        624s bash   cd /home/runner/work/ail-ci/ail-ci && ls lab/corpus/programs/*/t*.py | wc -l && cat > /tmp/profile_corpus.py <
        393s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_cov
         32s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_cov
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/cov14fix/*.py; do echo "===== $(basename $p)"; bash
         16s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/check_recovered.py <<'PY' import os,subprocess,sys,tempfile f
         15s bash   cd /tmp/probes/cov14fix && cat > p_sum_gen.py <<'PY' rows = [[1, 2, 3], [4, 5], [], [-2, -7]] print(sum(sum(v 
          4s bash   cd /tmp/base && git log --oneline -1 && bash ~/tools/cmp.sh /tmp/probes/cov14fix/p_star_gen.py /tmp/base 2>&1 

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review of `work..HEAD` (5ff126f)

**What the change really does:** replaces the blanket nested-generator-expression refusal with `_nested_genexp_unsafe`, which allows an inner genexp only when its *immediate* consumer is an unshadowed full-consuming builtin or `join` on a literal/f-string/`str()`; the *outer* generator's eagerness is still decided by the pre-existing, name-based `_genexp_consumed_in_place`.

### Probes (HEAD unless noted; `bash ~/tools/cmp.sh …`)
- `p_ok_nested_routes` (arg / list item / attribute / dict value, empty, negative, aliasing, `sum/min/max/list/join` routes): **same** both builds; base refuses by name.
- `p_nextbreak` (`next(join(...) for ...)`): **same**; base refuses.
- `p_outer_extend`, `p_outer_join` (user method consumes the *outer* generator): **DIFF** on both builds; base refuses by name.
- `p_forbreak_sum`, `p_forbreak_join`, `p_unpack_outer`: **DIFF** on both builds; base refuses by name.
- `p_strsub` (`str(x)` returning a str subclass whose `join` is overridden): refused earlier because `class S(str)` is unsupported, so this hole is not reachable.
- No-feature C comparison (`--debug-dir`, p_ok_more): `program.c` identical to base (only temp paths in report).
- Corpus targets: `t172` and both `t432` compile and match CPython on all 3 inputs in both builds; base (general path) refuses all three for the nested genexp.

### Defects (all newly accepted by this change; base refused them by name)
1. **User method as the outer generator's consumer is treated as an eager consumer.**
```python
log = []
def f(v): log.append(v); return v
class C:
    def extend(self, it): return next(iter(it))
row = [1, 2, 3]; c = C()
print(c.extend(f(v) * 10 + sum(x * 100 for x in row) for v in row))
print(log)
```
Expected (CPython): `610` then `[1]`; actual HEAD: `610` then `[1, 2, 3]`. Same with `join`. This falsifies the report's “User methods … keep the named refusal”.

2. **A `for` loop with `break` over the outer generator evaluates every element.**
```python
rows = [[1, 2], ["x"]]
for total in (sum(v for v in row) for row in rows):
    print(total); break
```
Expected: `3`, exit 0; actual: no stdout, `TypeError`, exit 1 (all rows were summed before the loop). `p_forbreak_join` shows the same over-consumption with side effects.

3. **Fixed-length unpacking consumes the whole outer generator.**
```python
log = []
def f(v): log.append(v); return v
rows = [[1], [2], [3], ["x"]]
try:
    a, b = (sum(f(v) for v in row) for row in rows)
except Exception as e:
    print(type(e).__name__)
print(log)
```
Expected: `ValueError` then `[1, 2, 3]`; actual: `TypeError` then `[1, 2, 3, 'x']`.

### Pre-existing (identical on base)
- `set` repr order in `p_ok_routes`: `[{1, 2}, set(), {4, -3}]` vs `{-3, 4}` on base too.
- The eager outer-generator lowering itself (`_genexp_consumed_in_place`) already miscompiles the non-nested analogues on base; this change extends it to previously-refused nested programs.

### Claims
- Code description of `_nested_genexp_unsafe` / unshadowed builtin + `join`: **verified**.
- “User methods … keep the named refusal”: **false** for an outer consumer (defect 1).
- Extra args / `key=`/`start=`/`default=`/`reverse=` refusals: **verified** (test module + code).
- Starred/unpacking “unchanged”: branch is unchanged, but fixed-length unpacking is not fully consuming (defect 3).
- Nested refusals 3 → 0 and t172/t432 results: **verified** (general path).
- Global corpus counts 24 → 21 and full 8-module test run: **unverified** (only targeted runs).
- Tests: `test_ail_cov14` 38.5s ok, `test_ail_safetynet` 97.9s ok; `update_manifest.py --check` rc 0.

VERDICT: FIX
1. Outer generator passed to a user method named `extend`/`join`/`update`/`array` is materialised eagerly: `p_outer_extend` expected `[1]`, got `[1, 2, 3]`; `p_outer_join` same.
2. Outer generator used as a `for`/comprehension source is materialised eagerly even when the loop breaks: `p_forbreak_sum` expected `3`/rc0, got `TypeError`/rc1; `p_forbreak_join` expected `['a', 'b']`, got `['a', 'b', 'c', 'd']`.
3. Outer generator used as the RHS of fixed-length unpacking consumes every element: `p_unpack_outer` expected `ValueError` + `[1, 2, 3]`, got `TypeError` + `[1, 2, 3, 'x']`.
[cost $0.0454, opencode tokens {"total": 2127632, "input": 88463, "output": 8272, "reasoning": 35249, "cache.write": 0, "cache.read": 1995648}]
    tool time: bash 4.4 min
         99s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         49s bash   cat > /tmp/check_corpus.sh <<'SH' set -u wt=$1; shift for prog in "$@"; do   tid=$(basename "$prog" .py); mode
         26s bash   cd /tmp/base && date && for p in p_forbreak_sum p_forbreak_join p_ok_routes p_ok_more; do echo "########## $p 
         25s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p_forbreak_sum p_forbreak_join p_nextbreak p_ok_routes 
         12s bash   cd /tmp && rm -rf dbgA dbgB && mkdir dbgA dbgB && cp /tmp/rprobes/p_ok_more.py /tmp/dbgA/p.ail && cp /tmp/rpro
         10s bash   cd /tmp/rprobes && cat > p_ok_nested_routes.py <<'PY' log = [] def f(v):     log.append(v)     return v class 
          7s bash   cd /tmp/rprobes && cat > p_outer_extend.py <<'PY' log = [] def f(v):     log.append(v)     return v class C:  
          7s bash   cd /tmp/base && date && for p in p_outer_extend p_outer_join; do echo "########## $p BASE"; bash ~/tools/cmp.s

FINAL VERDICT: FIX  2026-10-28T19:22:40Z
