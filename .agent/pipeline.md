# job job-pre426-10281803  started 2026-10-28T09:03:54Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"90917acf-1976-4841-a39d-2e566bc899ab","session_id":"23f6eb80-4a6f-42ee-b7db-2132b1f887c2"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"393f9914-d028-4542-807f-c9ec82f4b949","session_id":"7017bf46-62bf-42ab-94e7-26b4fe208b15"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Reproduced the first still-differing item, `r14` (function body mutates `d`, function never called): both builds trapped `integer overflow`.

Fix: function-body effects now apply at the statement that names the function (direct/alias/callback/nested), so a never-used function cannot affect a container. `r14` is refused by name at compile time on both builds. `r16` (`.keys()` before read) and `r21` (instance attribute) remain unchanged pre-existing traps.

Probes in `/tmp/probes/pre426` (both builds via `cmp.sh`):
- Refused by name: p01 uncalled, p03 called after read, p06 alias uncalled, p07 alias called after read, p09 nested uncalled, p11 read through argument.
- Match CPython: p02 in-range uncalled, p04 called before read, p05 callback, p08 alias called before read, p10 nested called.

Tests on final code state: `test_ail_pre426`, `test_ail_pre417`, `test_ail_pre388`, `test_ail_pre322`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7 modules, 0 failed, 355s. Manifest and shard checks pass.

Committed as `8e2779d` on `job-pre426-10281803`; not pushed.
[cost $0.0000, opencode tokens {"total": 1637109, "input": 105043, "output": 8276, "reasoning": 19534, "cache.write": 0, "cache.read": 1504256}]
    tool time: bash 6.7 min
        356s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre426 test_ail_pre417 test_ail_pre388 test_ail_
         20s bash   cd /tmp/probes/pre426 && cat > p01_uncalled.py <<'EOF' d = {"k": 1e300} def mutate():     d["k"] = 1.5 print(i
         15s bash   for p in r14 r16 r16b r21; do echo "=== $p ==="; bash ~/tools/cmp.sh /tmp/probes/pre426/$p.py /home/runner/wor
         11s bash   for p in r14 r16 r16b r21; do echo "=== $p ==="; bash ~/tools/cmp.sh /tmp/probes/pre426/$p.py /home/runner/wor
          0s bash   mkdir -p /tmp/probes/pre426 && cd /tmp/probes/pre426 && cat > r14.py <<'EOF' d = {"k": 1e300} def mutate():   
          0s bash   python3 tools/update_manifest.py --check && python3 tools/ci_shards.py --check && git diff --check && git add 
          0s bash   ls AIL_CURRENT/test_ail_pre*.py | sed 's/.*test_ail_pre//' | sort -n | tr '\n' ' '; echo; git show --stat HEAD
          0s bash   python3 tools/ci_shards.py --update && python3 tools/ci_shards.py --check; echo exit=$?; git diff --stat

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** `_escaped_constant_statements` no longer attributes a function body's names to its definition statement; it stores effects per function *name* and applies them at statements that load that name. Functions under a `ClassDef` keep the old treatment.

**Report claims verified**
- r14 / p01: refused by name on both builds (`int() of a float outside int64...`), base traps. Verified.
- p02, p04, p05, p15(argument mutation), p08, p10: match CPython. Verified subsets.
- p06, p07, p09, p11: refused by name on HEAD. Verified messages.
- r16, r21: still `integer overflow` on HEAD **and** base. Verified.
- `test_ail_pre426` + `test_ail_safetynet`: 2 modules, 0 failed, 105 s. Manifest and shard checks pass. Verified.
- Non-feature C unchanged: `g00_000.py` `--debug-dir` `program.c` identical base vs HEAD (only temp paths differ in `native_report.json`).

**Defect (caused by the change)**
Function effects are keyed only by identifier, ignoring shadowing. A variable used before a later same-named mutating `def` now inherits that function's effects, dropping a still-constant container and turning a named refusal into a runtime trap:

```python
d = {"k": 1e300}
mutate = 0
x = mutate + 1
print(int(d.get("k")))
def mutate():
    d["k"] = 1.5
```
- CPython: exit 0, prints the exact big integer.
- base: `p.ail:4:7: int() of a float outside int64: 1e+300 (CPython makes a big integer)` (exit 0 build refusal).
- HEAD (g and d): compiles, then `integer overflow`, exit 1.

**Pre-existing (identical on base, not blocking)**
- q02 nested same-name collision, q04 method never called, q05 instance attribute, q10 bare `mutate` reference: all trap `integer overflow` on base and HEAD.

**Unverified:** instruction counts (generated C is unchanged for non-feature programs); wider test suite (not run by design).

VERDICT: FIX
1. `q13_shadow_then_def.py` — effect table keyed by name makes a pre-`def` variable reference apply a later function's mutation. Expected a by-name refusal (base) or CPython output; actual runtime `integer overflow`, exit 1 on both builds. Fix by resolving effects per binding (or falling back to refusal) instead of a global name-keyed map.
[cost $0.0000, opencode tokens {"total": 1042693, "input": 48024, "output": 5652, "reasoning": 25689, "cache.write": 0, "cache.read": 963328}]
    tool time: bash 3.7 min, write 0.0 min
        107s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre426 test_ail_safetynet 2>&1 | tail -25;
         26s bash   cd /tmp && for p in /tmp/rprobes/q*.py; do echo "##### HEAD $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/ru
         22s bash   cd /tmp && for p in q01_param_collision q11_tuple_ref_uncalled q12_is_ref_uncalled; do for wt in /home/runner/
         15s bash   cd /tmp && for p in p06_alias_uncalled p07_alias_called_after p09_nested_uncalled p11_read_via_argument; do ec
         14s bash   cd /tmp && for p in q02_nested_name_collision q04_method_uncalled q05_attr_uncalled q10_bare_ref_uncalled; do 
         12s bash   cd /tmp && for p in /tmp/probes/pre426/r14.py /tmp/probes/pre426/p01_uncalled.py /tmp/probes/pre426/p02_in_ran
          6s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/q14_redef_branch.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -8
          6s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "##### $(basename $wt) q14"; bash ~/to

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `79fe4d3`.

- Change: function effects and aliases are now resolved against each name's binding at that statement; definitely rebound names no longer inherit a later same-named `def`'s effects.
- Probes `/tmp/probes/pre426fix/p01-p12` on both builds: p01-p09, p11 refused by name on HEAD (p05, p08, p09 were base traps); p10 `duplicate AIL name` on both; p12 matches CPython.
- Reviewer q01-q15: q13 now matches base's by-name refusal; q03, q07, q09 also improve to refusals; q06, q08, q15 match; q01, q02, q04, q05, q10-q12, q14 unchanged.
- Final-commit tests: `test_ail_pre426`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 211 s, 0 failed.
- `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0000, opencode tokens {"total": 1970983, "input": 150761, "output": 10098, "reasoning": 28364, "cache.write": 0, "cache.read": 1781760}]
    tool time: bash 6.5 min
        213s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre426 test_ail_safetynet test_ail_files test_ai
         89s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $(basename $wt)"; for p in
         28s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $(basename $wt)"; for p in
         24s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $(basename $wt)"; for p in
         23s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre426 2>&1 | tail -30
          6s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "##### $(basename $wt) q14"; bash ~/to
          4s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "##### $(basename $wt)"; bash ~/tools/
          0s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "##### $(basename $wt) q13"; bash ~/to

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** In `_escaped_constant_statements`, function-body effects are now attributed to the statement that names the function instead of its `def`, and both effects and alias edges are resolved against the name's binding at that statement (`AIL_CURRENT/ail_chatgpt.py:1129`).

**Defects (new, caused by this change):** the "unsettled binding keeps the union" fallback makes a variable whose value is a call/subscript/attribute/`IfExp` inherit a later same-named `def`'s mutation, dropping the container before the read. Base refused these by name; HEAD now compiles and traps at runtime.

1. `/tmp/rprobes/r02.py`:
```python
d = {"k": 1e300}
lst = [0]
mutate = lst[0]
x = mutate + 1
print(int(d.get("k")))
def mutate():
    d["k"] = 1.5
```
CPython: prints the 1e300 big integer. Base (both builds): named refusal `int() of a float outside int64: 1e+300`. HEAD (both builds): exit 1, stderr `integer overflow`, no stdout.

2. `/tmp/rprobes/r03.py`:
```python
d = {"k": 1e300}
mutate = 0 if True else 1
x = mutate + 1
print(int(d.get("k")))
def mutate():
    d["k"] = 1.5
```
CPython: prints the big integer. Base: named refusal (line 4). HEAD: exit 1, stderr `integer overflow`, no stdout.

The report's "definitely rebound names no longer inherit..." is true, but it omits that unknown-valued rebindings (`Call`, `Subscript`, `Attribute`, `IfExp`) still inherit the later `def`, which is the new trap.

**Pre-existing (identical on base and HEAD, non-blocking):** r01, r04, r05, r06, r10; p03, p04, p07, p08, p09, p12, p15, p17 (`.keys()`, instance attr, method, branch/passing/bare-read traps); q01, q02, q04, q05, q10-q12, q14. r16/r21 still trap as stated.

**Verified claims:** r14 shape (p01/p02, q03, q07, q09, q13) now refused by name on HEAD where base trapped; q06, q08, q15 match both; q01/q02/q04/q05/q10-q12/q14 unchanged; unaffected programs n01/n02 have identical `program.c` under `--debug-dir`; `test_ail_pre426` + `test_ail_safetynet` pass (0 failed); `update_manifest.py --check` and `ci_shards.py --check` exit 0. Report's description of the mechanism matches the diff.

**Unverified:** worker's `/tmp/probes/pre426fix` p-suite not re-run; no speed check (compile-time pass, not hot runtime).

VERDICT: FIX

1. `mutate = lst[0]` then a later same-named `def` traps at runtime (`integer overflow`) instead of the base's named refusal — see `/tmp/rprobes/r02.py`; expected (CPython) the big integer, actual exit 1 with `integer overflow`.
2. `mutate = 0 if True else 1` then a later same-named `def` likewise traps instead of refusing — see `/tmp/rprobes/r03.py`; expected the big integer, actual exit 1 with `integer overflow`.
[cost $0.0000, opencode tokens {"total": 653396, "input": 36109, "output": 5108, "reasoning": 8019, "cache.write": 0, "cache.read": 604160}]
    tool time: bash 6.2 min
        107s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre426 t
         97s bash   cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $(basename $wt)"; for p in
         88s bash   date && cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $(basename $wt)"; 
         73s bash   date && cd /tmp && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $(basename $wt)"; 
          4s bash   cd /tmp && rm -rf /tmp/dbg_ail-ci_n01 /tmp/dbg_ail-ci_n02 /tmp/dbg_base_n01 /tmp/dbg_base_n02 /tmp/out_ail-ci_
          2s bash   cd /tmp && rm -rf /tmp/dbg_head_* /tmp/dbg_base_* /tmp/dbg_head /tmp/dbg_base; for wt in /home/runner/work/ail
          0s bash   cd /tmp && rm -rf /tmp/dbg_head /tmp/dbg_base && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check >/tmp/man.log 2>&1; echo "manif

FINAL VERDICT: FIX  2026-10-28T09:48:22Z
