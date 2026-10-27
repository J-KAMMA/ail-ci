# job job-pre339-10272146  started 2026-10-27T12:48:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"d164ce00-7e34-4821-93d9-fed3ee3c41e7","session_id":"f1312371-5095-46e5-bcec-4eda8680f32d"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"4fb5a170-5e46-464d-a0ec-1a2e62dabed5","session_id":"d4268656-d016-4f5b-8438-9e631e4fd35b"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Result:** Fixed the first still-differing pre314 pre-existing item, `class_alias` (`Alias = C; Alias().f()` with a bound-method field). Both builds now refuse it by name instead of stopping later with `AttributeError`.

**Change:** `refuse_field_method_call` resolves class aliases and alias chains in their Python scope (`AIL_CURRENT/python/pkg-v12/pyfront.py:716`). Added `test_ail_pre339.py`, registered it in `ail_check.MODULES` and `ci_shards.json`, and added DEVLOG/DIFFERENCES records.

**Commit:** `6f19675` (`pre339: refuse a class alias to a bound-method field by name`)

**Probes** (`cmp.sh`, both builds):
- Refused by name: `class_alias`, `class_alias_assigned`, `alias_chain`, `alias_tuple_unpack`, `alias_local_direct`, `alias_arg`, `alias_list`, `alias_attr`, `alias_dict`.
- Match CPython: `class_alias_lambda`, `alias_param_shadow`, `alias_local_shadow`, `alias_unrelated`, `alias_no_feature`.

**Tests:** final tree `test_ail_pre339`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 366 s, 0 failed. `test_ail_pre278` and `test_ail_pre279` also passed (209 s, 0 failed). `tools/update_manifest.py --check` passes. `ci_shards.py --check` only reports its pre-existing duplicate entries.
[cost $0.0000, opencode tokens {"total": 4360570, "input": 137167, "output": 13664, "reasoning": 25803, "cache.write": 0, "cache.read": 4183936}]
    tool time: bash 12.8 min
        368s bash   cd AIL_CURRENT && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre339 test_ail_safetynet test_ail_
        155s bash   git add AIL_CURRENT/test_ail_pre339.py AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/pyfront.py AIL_CURR
         79s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfront.py') s=p.read_text() old=
         47s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfront.py') s=p.read_text() old=
         44s bash   cd /tmp/probes/pre339 cat > alias_chain.py <<'EOF' class C:     def __init__(self):         self.f = self.g   
         28s bash   mkdir -p /tmp/probes/pre339 && cd /tmp/probes/pre339 cat > class_alias.py <<'EOF' class C:     def __init__(se
         13s bash   cd /tmp/probes/pre339 cat > class_alias_lambda.py <<'EOF' class C:     def __init__(self):         self.f = la
         13s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfront.py') s=p.read_text() old=

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of pre339 (`6f19675`)**

**What the diff really does:** `refuse_field_method_call` now resolves a receiver name to any class bound to it by assignment (following `Name` alias chains) and refuses `.f()` when one of those classes has an `f` method/field collision. It also lets the receiver-name shortcut treat aliases like direct class names. This matches the report.

**Probes (`bash ~/tools/cmp.sh`, HEAD then base):**

| probe | HEAD | base | CPython |
|---|---|---|---|
| p1_basic `Alias = C; Alias().f()` | refused by name (both builds) | exit 1, `AttributeError` (the pre314 item) | 55 |
| p5_param_shadow / p6_lambda_field / p7_no_feature | match | match | match |
| **p2_reassign_other** | **refused by name (both builds)** | **7, match** | 7 |
| **p3_cond_false** | **refused by name (both builds)** | **7, match** | 7 |
| **p4_for_rebind** | **refused by name (both builds)** | **7, match** | 7 |

`p7_no_feature` has identical generated `program.c` on base and HEAD (only paths in `native_report.json` differ), so the no-feature C is unchanged. `update_manifest.py --check` and `ci_shards.py --check` behave as reported.

**Claims:** refusal of the listed alias routes — verified by the new test and p1. Shadow/lambda/unrelated routes — verified by p5/p6. `test_ail_pre339` + `test_ail_safetynet` — verified, 2 modules, 135 s, 0 failed. `test_ail_files`/`test_ail_corpus_findings3` not re-run (worker claims pass) — **unverified**. Instruction counts not run (compile-time-only change).

**Defects (introduced by this change):**

1. Flow-insensitive alias resolution refuses programs where the alias no longer denotes the colliding class.
```python
class C:
    def __init__(self): self.f = self.g
    def g(self): return 55
    def f(self): return 102
class D:
    def f(self): return 7
Alias = C
Alias = D
print(Alias().f())
```
Expected (CPython and base): `7`, exit 0. Actual HEAD: compile refused, `not in the subset: the method .f() on an instance whose class also stores an instance field named f (CPython calls the field)`, both builds.

2. Same cause, conditional reassignment:
```python
Alias = D
if False:
    Alias = C
print(Alias().f())
```
Expected: `7`, exit 0. Actual: same compile-time refusal on both builds. (Base matches CPython.)

3. Same cause, loop rebinding:
```python
Alias = C
for Alias in [D]:
    print(Alias().f())
```
Expected: `7`, exit 0. Actual: same compile-time refusal on both builds. (Base matches CPython.)

Root cause: `_class_alias_classes` unions *all* assignments to a name in a scope, ignoring order/branch/loop rebinding; `_classes_of` then intersects any one colliding class with the refusal set. The new test only covers a single alias binding, so it misses these.

**Pre-existing:** none observed beyond the pre314 `class_alias` difference itself, which HEAD fixes (p1).

VERDICT: FIX
1. p2: expected `7` exit 0, actual compile-time refusal.
2. p3: expected `7` exit 0, actual compile-time refusal.
3. p4: expected `7` exit 0, actual compile-time refusal.
[cost $0.0000, opencode tokens {"total": 387533, "input": 14324, "output": 3252, "reasoning": 7589, "cache.write": 0, "cache.read": 362368}]
    tool time: bash 3.6 min
        137s bash   date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre339 test_ail_safetynet 2>&
         32s bash   cd /tmp/rprobes && for p in p1_basic p2_reassign_other p3_cond_false p4_for_rebind p5_param_shadow p6_lambda_f
         30s bash   cd /tmp/rprobes && for p in p1_basic p2_reassign_other p3_cond_false p4_for_rebind p5_param_shadow p6_lambda_f
         12s bash   cd /tmp && rm -rf dbg_h dbg_b && mkdir dbg_h dbg_b && cp /tmp/rprobes/p7_no_feature.py /tmp/dbg_h/p.py && cp /
          2s bash   cd /tmp && d=$(mktemp -d) && cp /tmp/rprobes/p2_reassign_other.py $d/p.py && cd $d && (unset AIL_UNIFIED_FORCE
          0s bash   git worktree add /tmp/base work >/tmp/wt.log 2>&1; tail -3 /tmp/wt.log; git -C /tmp/base log --oneline -1; ls 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "rc=$?"; c
          0s bash   cd AIL_CURRENT && python3 ail_chatgpt.py compile --help 2>&1 | grep -iE "debug|emit|output" | head -20

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three false refusals and committed as `34af6c2`.

**Change:** alias resolution now follows execution order in the name's own scope — later assignment overwrites, constant-false branches are skipped, and `for` targets bind before the body. Alias chains keep their captured class; ancestor scopes resolve at scope end.

**Probes** (`/tmp/probes/pre339fix`, both builds): 12 total — 9 match CPython (`01`–`04`, `06`–`09`, `12`), 3 refused by name (`05`, `10`, `11`). `10` is a pre-existing unrelated refusal also present on base.

**Tests on final commit:** `test_ail_pre339`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 327 s, 0 failed. `update_manifest.py` run; `--check` passes. `ci_shards.py --check` still reports pre-existing duplicate entries.
[cost $0.0000, opencode tokens {"total": 1889805, "input": 80511, "output": 11382, "reasoning": 35736, "cache.write": 0, "cache.read": 1762176}]
    tool time: bash 8.7 min, write 0.0 min, edit 0.0 min, read 0.0 min
        329s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre339 test_ail_sa
         54s bash   cd /tmp/probes/pre339fix && for p in *.py; do echo "########## $p"; bash ~/tools/cmp.sh "$PWD/$p" /home/runner
         53s bash   cd /tmp/probes/pre339fix && out=$(for p in *.py; do bash ~/tools/cmp.sh "$PWD/$p" /home/runner/work/ail-ci/ail
         36s bash   cd /tmp/rprobes && for p in p1_basic p2_reassign_other p3_cond_false p4_for_rebind p5_param_shadow p6_lambda_f
         36s bash   cd /tmp/rprobes && for p in p1_basic p2_reassign_other p3_cond_false p4_for_rebind p5_param_shadow p6_lambda_f
          9s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/wt619 /tmp/wtbase && git worktree add --detach /tmp/wt619 6f
          0s write  /tmp/probes/pre339fix/04_for_after.py
          0s write  /tmp/probes/pre339fix/06_chain_other.py

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds a flow-sensitive abstract interpreter to `refuse_field_method_call` so names bound to a class (alias chains included) resolve to that class in execution order, and `_classes_of(Call)` now resolves the callee name. The alias-constructed receiver then reaches the existing field/method refusal. Broadly as reported, but the resolver is over-eager.

**Verified:** original case fixed (`Alias = C; Alias().f()`: base 55→AttributeError, HEAD named refusal). Reassignment (rv14) and dead `while False` (rv11) match CPython; chain keeps its captured class (rv15 refuses, base differs). Non-feature `program.c` identical HEAD vs base (rv10). `test_ail_pre339` + `test_ail_safetynet` pass (134 s, 0 failed); manifest `--check` passes.

**Defects (all new false refusals: base matches CPython, HEAD refuses):**

1. Alias RHS ignores a shadowed class name. `_value_classes` returns `{C}` for any `Name` whose text is a class, before looking at the flow env.
```python
class C:  # self.f = self.g; def g: 55; def f: 102
class D:  # def f: 7
def f():
    C = D
    Alias = C
    return Alias().f()
print(f())
```
Expected `7`; actual both builds: refusal `the method .f() ... field named f`. Base: `7`. Same bug via a parameter (`def f(C): Alias = C`, rv05) and a module rebinding (`C = D` rv06), expected `7` in both.

2. Keyword-only parameter shadow not recognized: `_param_names` omits `kwonlyargs`.
```python
Alias = C
def call(*, Alias=D):
    return Alias().f()
print(call())
```
Expected `7`; actual HEAD: named refusal; base: `7`. Contradicts "a parameter ... binding shadows the alias".

3. Runtime-conditional rebinding is unioned with the old class (`_merge_env`), so a name that does not denote the collision at the call is still refused:
```python
Alias = D
flag = len([]) == 1
if flag:
    Alias = C
print(Alias().f())
```
Expected `7`; actual HEAD: named refusal; base: `7` (same locally, rv17). Contradicts "a name no longer denoting it matches CPython".

**Pre-existing (identical on base, not blocking):** `try: Alias = C` still prints `AttributeError: 'C' object has no attribute 'g'` on both builds vs CPython `55` (rv08); function use before a later `Alias = D` likewise (rv09, ancestor end-of-scope resolution).

**Unverified:** `test_ail_files` / `test_ail_corpus_findings3` (not re-run per reviewer scope); instruction counts (front-end only, generated C unchanged); `ci_shards --check` duplicates compared against base.

VERDICT: FIX

1. **Shadowed class name on the alias RHS** (rv04): expected `7`, actual named refusal; also via parameter (rv05) and module rebinding (rv06).
2. **Keyword-only parameter shadow** (rv13): expected `7`, actual named refusal; `_param_names` omits `kwonlyargs`.
3. **Runtime-conditional rebinding union** (rv03/rv17): expected `7`, actual named refusal; `_merge_env` unions with the earlier colliding class.
[cost $0.0000, opencode tokens {"total": 901844, "input": 52502, "output": 5934, "reasoning": 21136, "cache.write": 0, "cache.read": 822272}]
    tool time: bash 4.8 min, write 0.0 min
        136s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         52s bash   cd /tmp/rprobes && date && for p in rv13_kwonly_default rv14_reassign_basic rv15_chain_use rv16_cond_true_rebi
         52s bash   cd /tmp/rprobes && date && for p in rv*.py; do echo "########## $p"; bash ~/tools/cmp.sh "$PWD/$p" /home/runne
         31s bash   cd /tmp/rprobes && date && for p in rv02_kwonly_param rv03_cond_runtime_false rv04_local_shadow_rhs rv05_param
          5s bash   cd /tmp && rm -rf dbgA dbgB p10h p10b p10h.log p10b.log && for v in A B; do if [ $v = A ]; then wt=/home/runne
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh "$PWD/rv01_alias_basic.py" /tmp/base 2>&1 | tail -12
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh "$PWD/rv02_kwonly_param.py" /tmp/base 2>&1 | tail -30
          0s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir -p dbg_head dbg_base && cp /tmp/rprobes/rv10_nonfeature.py /tmp/p

FINAL VERDICT: FIX  2026-10-27T13:36:33Z
