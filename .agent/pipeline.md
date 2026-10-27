# job job-pre337-10272138  started 2026-10-27T12:40:55Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"7bb63821-6816-4659-a092-b6dd02c385f1","session_id":"640b4026-51bb-4317-a31d-30f1f3687e85"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"a24af25f-1e49-454a-88cc-5b3a8d532939","session_id":"f3839b8f-a266-459a-88bf-fbbb48db3de8"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented on branch `job-pre337-10272138`.

- Reproduced the first recorded difference: `int(items[0])` with `items` a parameter overflowed on both builds.
- Fixed it by following a parameter’s constant subscript and short wrapper chain to a known argument and refusing the conversion by name: `int() of a float outside int64: ... (CPython makes a big integer)`.
- The other recorded items were not changed.

Probes in `/tmp/probes/pre337` (both builds):
- Refused by name: `p1`-`p1m` (literal, dict, negative, parameter index, wrapper, module container/alias, attribute, dict-value route, list-item route, keyword, nested item, upper bound, call inside a function).
- CPython-identical controls: `p1e`, `p1n`-`p1s`, `p2`, `p5`, `p6`.
- Unchanged other items: `p3` still differs, `p4` is already refused.

Tests on final commit `39afe07`:
- `test_ail_pre337`: 14 refused + 12 matching, pass
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: pass
- Also ran `test_ail_pre31/39/253/263/290/306/311`: pass
- `tools/update_manifest.py --check`: passes

Commits: `5b0d282` (fix + tests/records), `39afe07` (manifest pin).
[cost $0.0000, opencode tokens {"total": 3425215, "input": 87288, "output": 13859, "reasoning": 23588, "cache.write": 0, "cache.read": 3300480}]
    tool time: bash 17.9 min, edit 0.0 min
        370s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && : > /tmp/pre337_final.log; for pair in "test_ail_pre337.py t
        192s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && : > /tmp/pre337_final2.log; for pair in "test_ail_pre337.py 
        191s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for pair in "test_ail_pre31.py test_ail_pre290.py" "test_ail
         63s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_pre337.py 2>&1 | tail -20
         53s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_pre337.py 2>&1 | tail -20
         44s bash   cd /tmp/probes/pre337 && cat > p1j.py <<'EOF' def f(items):     return int(items[0]) print(f([[1e300]][0])) EO
         43s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_pre337.py 2>&1 | tail -30
         38s bash   mkdir -p /tmp/probes/pre337 && cd /tmp/probes/pre337 && cat > p1b.py <<'EOF' def f(items):     return int(item

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change:** adds a second AST pass (`_check_parameter_index_int_calls`) that resolves a parameter's constant subscripts back to literal call arguments/containers and refuses `int()` of an out-of-int64 float. Report's description matches the code.

**Verified**
- Target case: `p1` (`int(items[0])` with `items` a parameter) refuses by name on HEAD; base still prints `integer overflow` on both builds.
- Other recorded items: `p3` (subclass attribute) still overflows on HEAD and base; `p4` (class alias) is already refused by name on both.
- In-range controls `r4` (negative/bool/str index) and `r5` (wrapper) match CPython on HEAD; `r6` (direct mutation) matches.
- C unchanged for a program not using the feature: `--debug-dir` `program.c` is byte-identical to base (only report paths differ).
- `test_ail_pre337`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass; `update_manifest.py --check` passes.

**False claims / defects:** the report says "a container mutated before the call" and "a same-named local in an enclosing function" still match CPython. Both are false: HEAD refuses programs that base runs identically to CPython.

1. Mutation through a function call is missed (root: `_passable_module_containers` doesn't mark a container passed as an argument unsafe).
```
def bump(xs):
    xs[0] = 1.5
a = [1e300]
bump(a)
def f(items):
    return int(items[0])
print(f(a))
```
Expected `1`; HEAD refuses: `int() of a float outside int64: 1e+300 ...`.

2. Mutation through an alias is missed (only the alias name is marked unsafe).
```
a = [1e300]
b = a
b[0] = 1.5
def f(items):
    return int(items[0])
print(f(a))
```
Expected `1`; HEAD refuses with the same message.

3. A locally shadowed function name is not skipped in the final check (`_check_parameter_index_int_calls` ignores `call.func.id in local` there).
```
def f(items):
    return int(items[0])
def other():
    def f(x):
        return 1.5
    return f([1e300])
print(other())
```
Expected `1.5`; HEAD refuses with the same message.

**Pre-existing:** `p3` subclass class-attribute overflow (identical on base). **Unverified:** individual worker probes `p1b`–`p1m`, `p2`, `p5`, `p6`; compile speed (change is compile-time only).

VERDICT: FIX
1. `r1` mutation via a called function: expected `1`, actual compile refusal.
2. `r2` mutation via a container alias: expected `1`, actual compile refusal.
3. `r3` call to a locally shadowed function of the same name: expected `1.5`, actual compile refusal.
[cost $0.0000, opencode tokens {"total": 667268, "input": 21648, "output": 3832, "reasoning": 13052, "cache.write": 0, "cache.read": 628736}]
    tool time: bash 6.8 min
        227s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_c
        136s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre337 t
         15s bash   cd /tmp/rprobes; R=/home/runner/work/ail-ci/ail-ci; date; for p in r1 r2 r3 r4 r5 r6; do echo "########## $p H
         14s bash   cd /tmp/rprobes; date; for p in r1 r2 r3; do echo "########## $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py
         13s bash   cd /tmp/probes/pre337; R=/home/runner/work/ail-ci/ail-ci; date; for p in p1 p3 p4; do echo "=== $p HEAD"; bash
          2s bash   cd /tmp; rm -rf dbgH dbgB plainH plainB; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/ail-ci/
          0s bash   cd /tmp/rprobes && for p in r1 r2 r3; do echo -n "$p cpython: "; python3 $p.py; done; echo; cd /home/runner/wo
          0s bash   cd /tmp/rprobes && cat > r4.py <<'EOF' def f(items, i):     return int(items[i]) print(f([1e300, 1.5], -1)) pr

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three reviewer defects:

1. Mutation via called function (`bump(a)`): parameter-mutation analysis incl. method stores, `del`, augmented assignment, inner aliases and transitive calls (`ail_chatgpt.py:870`).
2. Mutation via alias (`b=a; b[0]=1.5`): alias unsafety now propagates across the whole alias group.
3. Locally shadowed function name in final check (`ail_chatgpt.py:1139`).

Compile-time analysis was also made monotone and skipped when no module containers exist; the previous version hung `test_ail_corpus_findings3` (600 s timeout) and now that case compiles in ~14 s.

Probes run with `cmp.sh` on both builds:
- `r1`-`r3` (reviewer failures): match CPython, expected `1`, `1`, `1.5`.
- `r4`-`r6`, `a2`-`a9`, `a11`: match CPython (call, alias, alias-chain, wrapper, keyword, inner-alias mutation; method mutation; shadowed function).
- Refusal controls `p1`, `p1c` remain refused by name; `p1q`, `p1r` match CPython.
- Pre-existing `p3` (subclass class attribute) still differs on both builds, untouched.
- Known limitation: mutation that leaves the indexed item unchanged (e.g. augmented append) still reaches the pre-existing runtime overflow; not covered by the fixed claim.

Final commit `7a6ab69` (plus `0cbbf5d`): `test_ail_pre337`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`4 modules in 341s, 0 failed`); `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2882163, "input": 105497, "output": 14437, "reasoning": 26485, "cache.write": 0, "cache.read": 2735744}]
    tool time: bash 50.5 min
       1399s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre337 test_ail_safetynet test_ail_files test_ai
        700s bash   cd /tmp && python3 - <<'PY' import sys,ast sys.path.insert(0,'/home/runner/work/ail-ci/ail-ci/AIL_CURRENT') im
        343s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre337 test_ail_safetynet test_ail_files test_ai
        110s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre337 2>&1 | tail -30
         89s bash   for p in /tmp/rprobes/r1.py /tmp/rprobes/r2.py /tmp/rprobes/r3.py /tmp/rprobes/r4.py /tmp/rprobes/r5.py /tmp/r
         60s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd /tmp/probes/pre337fix && fo
         57s bash   cd /tmp/probes/pre337 && for f in p1 p1b p1c p1d p1e p1f p1g p1h p1i p1j p1k p1l p1m p1n p1o p1p p1q p1r p1s p
         40s bash   cd /tmp && AIL_IR=0 AIL_NO_CACHE=1 timeout 40 python3 - <<'PY' >/tmp/date_dbg2.log 2>&1 import sys, time, ast 

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Change:** Adds a compile-time AST pass that traces `int(x)` / `int(x[i])` through module-function parameters to statically known call arguments, plus a module-container mutation/alias scan to decide when to refuse with the named out-of-int64-float error. Test module/DIFFERENCES/DEVLOG/manifest updated.

**Verified**
- Target case: `/tmp/rprobes/t1.py` (`f([1e300])`) is now refused by name on both builds; base overflows. `t2` (exactly 2^63 float) refused; `t3` (-2^63) and `t4` (largest float below 2^63) match CPython.
- Earlier review fixes `r1`-`r3` match CPython on HEAD; `p1`/`p1c` refused, `p1q`/`p1r` match.
- `test_ail_pre337` (114.6s) and `test_ail_safetynet` (141.0s) pass with `-j 2`; `update_manifest.py --check` passes.
- Non-feature program: `program.c` identical base vs HEAD via `--debug-dir` (only temp paths differ in JSON).
- Compile times comparable: `g00_000` 1.32s vs base 1.33s; `g00_010` 10.57s vs 10.30s.
- Report claim “container mutated before the call … still match CPython” is **false** (see defects). `p3` is identical on both (pre-existing overflow).

**Defects (over-refusal: base matches CPython, HEAD rejects)**
1. Mutation inside a nested function is not tracked. `/tmp/rprobes/fp_nested_closure.py`:
```python
def bump(xs):
    def inner(): xs[0] = 1.5
    inner()
a = [1e300]; bump(a)
def f(items): return int(items[0])
print(f(a))
```
Expected `1`; HEAD both builds fail `int() of a float outside int64: 1e+300`; base prints `1`.
2. Mutation via a class method or function alias is not tracked. `/tmp/rprobes/fp_method.py` (`C().bump(a)`) and `/tmp/rprobes/fp_function_alias.py` (`fn = bump; fn(a)`, where `bump` does `xs[0] = 1.5`): expected `1`; HEAD refuses on both builds; base prints `1`.
3. Mutation of a nested item / dict value / class attribute is not tracked. `/tmp/rprobes/fp_nested_item.py`:
```python
a = [[1e300]]; a[0][0] = 1.5
def f(items): return int(items[0][0])
print(f(a))
```
Expected `1`; HEAD refuses; base prints `1`. Same for `/tmp/rprobes/fp_inner_alias.py`, `fp_subscript_arg.py`, `fp_dict_value.py`, `fp_class_attr.py`.

Root cause: `_passable_module_containers` only tracks direct stores, method calls on the container itself, and `Name = Name` aliases; `_parameter_mutations` skips nested defs/methods and only keys module `FunctionDef`s; nested subscript stores do not mark the outer container. Suggest treating an unprovable container as unsafe (do not refuse) or extending these routes.

**Pre-existing:** `bump = lambda xs: xs.__setitem__(0, 1.5)` fails on base too; `p3` subclass-attribute case identical on both.

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3` not re-run; the “corpus ~14s” claim and `r4`-`r6`/`a2`-`a9`/`a11` not individually re-run; runtime icount not relevant (compile-time only).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 916490, "input": 44325, "output": 5275, "reasoning": 20554, "cache.write": 0, "cache.read": 846336}]
    tool time: bash 5.2 min
        143s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre3
         39s bash   cd /tmp/rprobes && for p in t1 fp_nested_closure fp_method fp_function_alias fp_lambda fp_inner_alias fp_subsc
         36s bash   for p in p1 p1c p1q p1r p3; do echo "== $p HEAD"; bash ~/tools/cmp.sh /tmp/probes/pre337/$p.py /home/runner/wo
         24s bash   cd /tmp && for f in g00_000 g00_010 g00_050; do src=~/corpus/gdev/$f.py; [ -f "$src" ] || continue; for side i
         19s bash   cd /tmp/rprobes && for p in r1 r2 r3; do echo "== $p HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /home/runne
         18s bash   cd /tmp/rprobes && for p in t1 t2 t3 t4 fp_nested_closure fp_method fp_function_alias fp_lambda fp_inner_alias
         15s bash   cd /tmp/rprobes && cat > fp_nested_item.py <<'EOF' a = [[1e300]] a[0][0] = 1.5  def f(items):     return int(i
         10s bash   cd /tmp/rprobes && cat > fp_slice_store.py <<'EOF' a = [1e300] a[:] = [1.5]  def f(items):     return int(item

FINAL VERDICT: FIX  2026-10-27T14:19:10Z
