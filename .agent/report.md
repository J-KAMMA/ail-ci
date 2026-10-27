# job job-pre316-10271448  started 2026-10-27T05:58:58Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"801fd7f7-36e8-4cd0-9c58-18911b1657ca","session_id":"01633c8b-01e7-4a42-9349-271edfb312b1"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"495e984d-289e-49d6-83d2-66dc81cb03a7","session_id":"367cfe85-2d54-4ad1-bac1-911bd85118f2"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first pre-existing difference from the `rbrbpre61` review.

**Change:** `c.f = partial(add, 3); c.f(4)` was refused by name because the general path only checked instance attributes when a class method of the same name existed. It now consults the instance table when the class has no such method, for known receivers and receivers arriving through arguments/wrappers. Keyword/starred calls remain named refusals.

**Commit:** `bf8332e` (7 files, +308/−8). Added `AIL_CURRENT/test_ail_pre316.py`, registered it, added DEVLOG/DIFFERENCES rows.

**Probes** in `/tmp/probes` (both builds):
- Match CPython (10): `pre316_inst_attr_plain`, `pre316_attr_partial_basic`, `pre316_attr_routes`, `pre316_attr_alias`, `pre316_attr_plain_func`, `pre316_attr_errors`, `pre316_attr_shadow_method`, `pre316_attr_receiver_arg`, `pre316_attr_receiver_routes`, `pre316_attr_builtin_names`.
- Refused by name (5): `pre316_attr_kwargs`, `pre316_attr_star`, `pre316_attr_bound_method`, `pre316_cls_bound_method`, `pre316_class_attr_partial`.

**Final-commit tests:** `test_ail_pre316`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 209 s, 0 failed. `update_manifest.py --check` passes.

The second pre-existing item (`map` over a zero-argument partial) was not changed.
[cost $0.0000, opencode tokens {"total": 3885935, "input": 100762, "output": 12445, "reasoning": 15544, "cache.write": 0, "cache.read": 3757184}]
    tool time: bash 7.3 min
        210s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre316 test_ail_safetynet test_
         81s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre316 test_ail_safetynet 2>&1 
         49s bash   cd /tmp/probes && for p in pre316_*.py; do echo "===== ${p%.py}"; bash ~/tools/cmp.sh /tmp/probes/$p /home/run
         47s bash   cd /tmp/probes && for p in pre316_*.py; do echo "===== ${p%.py}"; bash ~/tools/cmp.sh /tmp/probes/$p /home/run
         12s bash   cd /tmp/probes && for p in pre316_attr_bound_method pre316_inst_attr_plain pre316_class_attr_partial pre316_cl
         11s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s = p.read_text()
          7s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s = p.read_text()
          6s bash   cd /tmp/probes && cat > pre316_attr_errors.py <<'EOF' from functools import partial   def add(a, b):     retur

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Diff (one line):** The general path now performs an instance-attribute lookup before method dispatch whenever the attribute name is assigned somewhere, even when no user class defines a method of that name; if found it calls the field with no receiver, otherwise it emits an AttributeError (or the method fallback).

**Probes** (`bash ~/tools/cmp.sh`, general + default, HEAD):
- Match CPython: basic partial, reassignment, negative/large ints, arg receiver, wrappers, list item, dict value, attribute chain, `__init__` assignment, inheritance, alias, plain function/lambda, class value, callable instance, non-callable (int/None/bytes), arity/TypeError, mutation loop, missing field, other class.
- Refused by name: keyword/starred call, partial of a bound method, class-attribute assignment, `del` attribute.
- Newly accepted but wrong: attribute-assigned **bound method** (user and builtin), see defect.
- No-feature programs: `--debug-dir` generated `program.c` byte-identical to `/tmp/base` for two representative programs.
- Unchanged/pre-existing: property called with `()` (both print `5`, CPython `TypeError`); attribute names colliding with builtin methods (`c.items = partial(...)`) still refused on both.
- Tests: `test_ail_pre316`, `test_ail_safetynet` — 0 failed (79 s). `update_manifest.py --check` passes.

**Report claims:** fixed first difference (verified: base refuses, HEAD matches); instance lookup for known and argument/wrapper receivers (verified); keyword/starred still refused (verified); commit contents (verified); 10 probes match / 5 refused (verified by re-running all 15); `test_ail_files` and `test_ail_corpus_findings3` (not re-run, unverified); map-over-zero-arg-partial unchanged (unverified).

**Defect 1 — attribute-assigned bound method now compiles to a wrong result.** Base refused these by name (acceptable); the new branch accepts them and fails at run time, so the change caused it.
```python
class Other:
    def __init__(self, n): self.n = n
    def add(self, x): return self.n + x
class C: pass
o = Other(10); c = C(); c.f = o.add
print(c.f(5))
```
Expected `15` (CPython); actual `AttributeError: 'Other' object has no attribute 'add'`, exit 1, both builds. Same for a builtin bound method: `xs=[1,2]; c=C(); c.f=xs.append; c.f(3); print(xs)` expected `[1, 2, 3]`, actual `AttributeError: 'list' object has no attribute 'append'`. The argument-receiver variant (`def call(c): return c.f(5)`) fails identically. Fix: either call bound-method field values correctly or refuse non-def/lambda field values by name in these branches.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, map-over-zero-argument-partial, and speed (not needed: branch is gated on an attribute name matching the call site).

VERDICT: FIX

1. Attribute-assigned bound-method fields (`c.f = o.add`, `c.f = xs.append`) are newly accepted and produce a runtime `AttributeError` instead of CPython's result (see probe and outputs above); base refused them by name, so the change introduced the defect.
[cost $0.0000, opencode tokens {"total": 1775026, "input": 40029, "output": 7214, "reasoning": 18599, "cache.write": 0, "cache.read": 1709184}]
    tool time: bash 6.1 min
        120s bash   find / -name 'NAMES_methods.json' 2>/dev/null | head
         80s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre316 t
         49s bash   cd /tmp/probes && date && for p in pre316_*.py; do echo "===== ${p%.py}"; bash ~/tools/cmp.sh /tmp/probes/$p /
         25s bash   cd /tmp/rprobes && for p in p_basic p_arg p_routes p_noncall p_missing p_builtin_names; do echo "===== $p"; ba
         24s bash   cd /tmp/rprobes && for p in p_classattr p_classattr_partial p_classvar_func p_del p_callable_obj p_class_value
         18s bash   cd /tmp/rprobes && for p in p_list_item p_dict_value p_attr_chain p_init p_arity; do echo "===== $p"; bash ~/t
         18s bash   cd /tmp/rprobes && for p in p_bound_method p_builtin_bound p_staticmethod p_inherit p_iter_mut p_property; do 
          8s bash   cd /tmp/rprobes && for p in p_bound_method p_builtin_bound p_property; do echo "===== BASE $p"; bash ~/tools/c

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect: attribute-assigned bound methods are now refused by name at compile time instead of being accepted and failing at run time.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- Refused by name: `pre316_bound_user`, `pre316_bound_builtin`, `pre316_bound_arg`, `pre316_bound_alias`, `pre316_bound_list`, `pre316_bound_dict`, `pre316_bound_attr`, `pre316_bound_builtin_alias`, `pre316_bound_return`.
- Match CPython: `pre316_field_shadow_read`, `pre316_partial_still_works`, plus all 15 earlier `pre316_*` probes at their recorded results.

**Tests on final commit** (`f871ffe`, 5 modules, 157 s): `test_ail_pre316`, `test_ail_pre279`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed.
`python3 tools/update_manifest.py --check` passes.

Commits: `c309c62` (fix + tests + records), `f871ffe` (DEVLOG timing). No push.
[cost $0.0000, opencode tokens {"total": 6928727, "input": 136686, "output": 14323, "reasoning": 21366, "cache.write": 0, "cache.read": 6756352}]
    tool time: bash 9.6 min
        158s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre316 test_ail_pre279 test_ail
        158s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre316 test_ail_pre279 test_ail
        134s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre316 test_ail_safetynet test_
         44s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre279 > /tmp/tests3.log 2>&1; 
         34s bash   cd /tmp/probes && for p in pre316_attr_alias pre316_attr_bound_method pre316_attr_builtin_names pre316_attr_er
         12s bash   cd /tmp/probes && cat > pre316_bound_alias.py <<'EOF' class Other:     def __init__(self, n): self.n = n     d
          9s bash   cd /tmp/probes && for p in pre316_bound_user pre316_bound_builtin pre316_bound_arg; do echo "===== $p"; bash ~
          8s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > pre316_bound_user.py <<'EOF' class Other:     def __init__(sel

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the diff really does:** `bf8332e` (not mentioned in the report) adds the instance-table lookup for `instance.attr(...)` when no class method of that name exists but the name is assigned somewhere; `c309c62` adds a read-side guard refusing method-valued attribute reads by name; `f871ffe` only edits DEVLOG.

**Probes run** (`cmp.sh`, both builds, HEAD vs `/tmp/base`):
- Target fixed: `p7_plain` (partial/lambda/function/non-callable/missing/alias/reassign) matches CPython on HEAD; base refuses `.f()`. `p2_routes`, `p14_route2` (arg, list item, dict value, attribute chain, big/negative ints) match on both.
- Bound-method refusals: `p4_bound_used`, `p5_methodval`, `p21_bound_routes` refused by name on HEAD (base failed at run time) — as claimed.
- Unaffected programs: `p10_modulecall`, `p11_classattr`, `p15_file`/`p16_file_plain` match on both; `p11` generated `program.c` is identical to base (`native_report.json` differs only in metadata).
- **Regression found:** `p17_collide`, `p18_classattr_builtin`, `p19_arg` compile and match CPython on base, but are refused on HEAD because the read guard guesses "method" from global name sets when the receiver kind is unknown.
- Pre-existing (identical on base): `p20_directcall` (`cc(2)` → `TypeError: 'Call' object is not callable`); `p8_ospath`/`p9_ospath2` (`os.path` not built).
- `p6_callable`: the field call works; the remaining diff is the pre-existing direct `cc(2)` case.

**Tests:** `test_ail_pre316` and `test_ail_safetynet` pass on HEAD (66 s, 0 failed). `update_manifest.py --check` exits 0.

**Claims:** target fix verified; bound-method refusal verified; field-shadow/partial tests verified by the passing module. The "5 modules 157 s" claim is unverified beyond pre316+safetynet, and "all 15 earlier probes" unverified. The report omits commit `bf8332e`, which is the substantive pre-existing-difference fix in `work..HEAD`.

**Unverified:** `test_ail_pre279`, `test_ail_files`, `test_ail_corpus_findings3`; speed (change is compile-time plus a helper emitted only for affected programs).

`VERDICT: FIX`
1. The new read guard over-refuses ordinary attribute reads when the receiver's static kind is unknown and the attribute name coincides with any built-in method name or any user class method name, even when the attribute is a plain data/class attribute. This refuses valid programs that compiled and matched CPython on the base.
   - `p19_arg.py` (`class Config: get = 5`; `def show(c): return c.get`; `print(show(Config()))`): expected `5`; actual compile failure on both builds — `not in the subset: reading the method .get() as a value (a bound method is not modelled on the general path)`.
   - `p17_collide.py` (unrelated class with `def size`; `make()`/`d["c"]`/`xs[0]` returning an object with class attribute `size`): expected `3` three times; actual compile failure — `reading the method .size() as a value ...`.
   - `p18_classattr_builtin.py` (`class Config: index = 3`, `count = 4`, `get = 5`; `print(make().index, make().count, make().get)`): expected `3 4 5`; actual compile failure — `reading the method .index() as a value ...`.
   The guard should only fire when the attribute is actually resolved to a method (known owner/`_resolve_method`), not from the global name sets on an unknown receiver.
[cost $0.0000, opencode tokens {"total": 1724438, "input": 59412, "output": 6247, "reasoning": 18971, "cache.write": 0, "cache.read": 1639808}]
    tool time: bash 2.7 min
         67s bash   date && cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre316 test
         18s bash   cd /tmp/rprobes && cat > p14_route2.py <<'EOF' from functools import partial   def add(a, b):     return a + b
         16s bash   cd /tmp/rprobes && cat > p8_ospath.py <<'EOF' import os f = os.path.join print(f("a", "b")) EOF cat > p9_ospat
         11s bash   cd /tmp/rprobes && for p in p1_basic p3_modules p4_bound_used p5_methodval; do echo "########## $p BASE"; bash
         11s bash   cd /tmp/rprobes && cat > p6_callable.py <<'EOF' class Call:     def __init__(self, n):         self.n = n     
          9s bash   cd /tmp/rprobes && cat > p12_static.py <<'EOF' class C:     @staticmethod     def f(x):         return x + 1  
          8s bash   cd /tmp/rprobes && for p in p1_basic p2_routes p3_modules p4_bound_used p5_methodval; do echo "########## $p H
          5s bash   cd /tmp/rprobes && cat > p20_directcall.py <<'EOF' class Call:     def __call__(self, x):         return x * 1

FINAL VERDICT: FIX  2026-10-27T06:44:23Z
