# job job-pre318-10271507  started 2026-10-27T06:07:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"acdbfbf8-00f9-4d62-8670-2d942df324f6","session_id":"09820e67-70d3-4136-b329-4d6b80e673eb"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"a841f426-4616-4140-8404-25c9133aa7c4","session_id":"ac3354bf-aa7a-4638-9d20-daef610903a9"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `0927212` (`job pre318`).

- Added `_check_bound_method_values` to refuse user method values by name on both builds, resolving receivers through constructors, parameters, list/dict items, attributes, aliases, inheritance, classmethods, and staticmethods.
- Preserved direct calls, properties, same-name fields, `getattr`, and `callable(d.g)`.
- Added `test_ail_pre318.py`, DIFFERENCES/DEVLOG entries, manifest pins, and CI shard registration.
- Removed the stale duplicate `test_ail_pre126` shard entry.

Final checks with `par_check -j 2`: `test_ail_pre318`, `test_ail_safetynet`, `test_ail_files`, and `test_ail_corpus_findings3` all passed, 0 failed. All 19 final probes either matched CPython or were refused by name. Manifest and shard checks pass.
[cost $0.0000, opencode tokens {"total": 8917274, "input": 343951, "output": 24434, "reasoning": 32409, "cache.write": 0, "cache.read": 8516480}]
    tool time: bash 18.2 min
        345s bash   python3 tools/par_check.py -j 2 test_ail_pre318 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
        192s bash   python3 -B AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tail -25
        134s bash   python3 -B AIL_CURRENT/test_ail_files.py 2>&1 | tail -25
        126s bash   python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -20
         75s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() old="""        
         40s bash   mkdir -p /tmp/probes/pre318 && cat > /tmp/probes/pre318/default_arg.py <<'EOF' class D:     def g(self):      
         32s bash   for f in /tmp/probes/pre318/*.py; do case $(basename "$f") in control_builtin_method.py) continue;; esac; echo
         26s bash   git worktree add --detach /tmp/rb278 FETCH_HEAD >/dev/null 2>&1; for f in /tmp/probes/b2/*.py; do echo ==== $(

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `0927212` (base `6218e96`, `/tmp/base318`).

**What the change really does:** adds a common front-end AST pass `_check_bound_method_values` that resolves possible receiver classes and raises `not in the subset: a bound method value (C.m)` for an attribute read when the resolved class defines it as a method but not as a `self.attr` field. It also adds `test_ail_pre318.py`, DIFFERENCES/DEVLOG entries, manifest pins and a shard entry.

**Claims checked**
- Four recorded cases: verified. Base gives `AttributeError: 'D' object has no attribute 'g'`; HEAD refuses by name on both builds.
- Direct calls, properties, `getattr(d, "g")`, `callable(d.g)`, and a `self.g = ...` field: verified.
- "same-name fields preserved": **false**; only fields assigned directly as `self.attr` in a method body are recognised (defects below).
- Record/test/manifest/shard additions and removal of the duplicate `test_ail_pre126`: verified; `update_manifest.py --check` and `ci_shards.py --check` pass.
- `test_ail_pre318` and `test_ail_safetynet`: verified, 0 failed. `test_ail_files`/`test_ail_corpus_findings3` were not re-run per reviewer scope.
- Non-feature C: `control_ordinary` gives identical executable hash and identical generated C; only temporary paths differ in `native_report.json`.

**Pre-existing (not blocking):** `D.g.__name__` is refused on both base and HEAD ("reading method D.g through a class value"); a nested same-name class is refused on both (base by the nested-class check, HEAD by this one).

**Defects**
1. Fields not assigned directly as `self.attr` are missed, so valid field reads are refused.
   `class D: def g(self): return 1` / `d = D()` / `setattr(d, 'g', 42)` / `print(d.g)`
   Expected `42`; actual both builds: `not in the subset: a bound method value (D.g)`. Same failure for `d.g = 42` at module scope and `d.g = 42` inside a function (`/tmp/rprobes/field_module_assign.py`, `field_arg_assign.py`; base matches CPython).
2. Tuple-unpacked field assignment is missed.
   `self.g, self.h = v, 2` with `def g(self): return 1`; `print(D(5).g, D(5).h)`
   Expected `5 2`; actual refusal on both builds (`field_tuple.py`).
3. Field assignment inside a nested function is missed.
   `def setup(o): o.g = 7` called with `self`; expected `7`; actual refusal (`field_nested.py`).
4. List-item receiver inference unions every element class, so a field read is refused because another element type has a method of that name.
   `xs = [E(), D()]` where `E.g` is `5` and `D.g` is a method; `print(xs[0].g)`
   Expected `5`; actual refusal (`list_mixed.py`).
5. Explicit unbound calls mis-index the argument as the receiver.
   `D.m(D(), E())` where `m` returns `x.g` and `E.g` is `9`; expected `9`; actual refusal at `return x.g` (`param_second.py`).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 453335, "input": 19006, "output": 4152, "reasoning": 12001, "cache.write": 0, "cache.read": 418176}]
    tool time: bash 3.6 min, write 0.0 min
        127s bash   date; python3 tools/par_check.py -j 2 test_ail_pre318 test_ail_safetynet 2>&1 | tail -30
         49s bash   for f in /tmp/rprobes/*.py; do echo "==== $(basename $f)"; bash ~/tools/cmp.sh "$f" /tmp/base318 2>&1 | grep -
         17s bash   for f in /tmp/rprobes/rec_factory.py /tmp/rprobes/rec_methodarg.py /tmp/rprobes/control_getattr_callable.py /t
          9s bash   for f in /tmp/rprobes/*.py; do echo "==== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E 'cpy
          9s bash   for f in /tmp/rprobes/rec_factory.py /tmp/rprobes/rec_methodarg.py /tmp/rprobes/control_getattr_callable.py /t
          2s bash   rm -rf /tmp/dbg_head /tmp/dbg_base; mkdir -p /tmp/dbg_head /tmp/dbg_base; cp /tmp/rprobes/control_ordinary.py 
          0s bash   python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "manifest_rc=$?"; python3 tools/ci_shards.py --c
          0s bash   for f in field_setattr field_module_assign field_arg_assign field_tuple field_nested list_mixed param_second; 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all 5 review defects and committed as `10d3fc6` (not pushed).

- Field stores outside class bodies (`setattr`, module/function assignment), tuple unpacking, nested helpers, and stores through aliases/list items/dict values/attributes are now recognised.
- Constant list/tuple subscripts use the indexed element, including negative indices.
- Explicit unbound calls like `D.m(D(), E())` no longer shift the second argument by implicit `self`.
- Method reads still refused by name.

Probes (`/tmp/probes`, both builds):
- Match CPython (17): `field_setattr`, `field_module_assign`, `field_arg_assign`, `field_tuple`, `field_nested`, `field_alias`, `field_list_item`, `field_dict_value`, `field_attribute`, `field_types`, `field_augassign`, `field_annotation`, `list_mixed`, `list_negative_field`, `param_second`, `param_second_classattr`, `param_second_dmethod`.
- Refused by name (3): `method_still_refused`, `list_negative_method`, `list_nonconstant`.

Final commit tests (`-j 2`): `test_ail_pre318`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **4 modules, 0 failed** (273 s). `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0000, opencode tokens {"total": 1568069, "input": 27204, "output": 10435, "reasoning": 19262, "cache.write": 0, "cache.read": 1511168}]
    tool time: bash 8.2 min, edit 0.0 min
        275s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre318 test_ail_safetynet test_
        129s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre318 test_ail_safetynet 2>&1 
         60s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m py_compile AIL_CURRENT/ail_chatgpt.py && for f in /tmp/probes
         14s bash   cd /tmp/probes && cat > field_types.py <<'EOF' class D:     def g(self):         return 1 d = D() for value in
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/field_*.py /tmp/probes/list_mixed.py /tmp/probes/pa
          4s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/param_second.py "$PWD"
          4s bash   cd /tmp/probes && cat > param_second_classattr.py <<'EOF' class D:     def m(self, x):         return x.g clas
          0s bash   cd /tmp/probes && cat > param_second_dmethod.py <<'EOF' class D:     def g(self):         return 1     def m(s

## review 1
[model opencode/deepseek-v4.1-flash-free]
Review of `10d3fc6` (two commits over base `6218e96`; base worktree `/tmp/base`).

**What the change really does:** adds a common front-end AST pass `_check_bound_method_values` that resolves receiver classes (constructors, parameters, list/dict items, attributes, aliases, bases) and refuses an attribute read by name when the class defines it as a method and has no discovered field of that name; plus field-discovery, constant-index and explicit-unbound-call fixes, tests, DIFFERENCES/DEVLOG, manifest and shard entries.

**Claims checked**
- The 5 previous review defects: verified fixed (`field_setattr`, `field_module_assign`, `field_arg_assign`, `field_tuple`, `field_nested`, `list_mixed`, `param_second` all match CPython now).
- "Field stores through aliases/list items/dict values/attributes are now recognised": **partly false**; field stores through a loop target, `*args`, or a non-constant dict key are still missed, so valid field reads are newly refused (defects 1–3).
- Method values still refused: verified (recorded `p_default` refused on both builds).
- Non-feature C unchanged: verified; `p_plain` generated `program.c` is byte-identical to base.
- `test_ail_pre318` + `test_ail_safetynet` on HEAD: pass, 0 failed. `update_manifest.py --check` and `ci_shards.py --check`: pass.
- `test_ail_files` / `test_ail_corpus_findings3`: not re-run (unverified).

**Defects** (base matches CPython on both builds; HEAD refuses, so the change caused them)

1. Field assigned through a loop-variable alias is not discovered.
```python
class D:
    def g(self): return 1
d = D()
for o in [d]:
    o.g = 5
print(d.g)
```
Expected `5`; actual both builds: `not in the subset: a bound method value (D.g)`.

2. Field assigned through `*args` is not discovered.
```python
class D:
    def g(self): return 1
def setg(*args):
    args[0].g = 5
d = D(); setg(d); print(d.g)
```
Expected `5`; actual both builds: `not in the subset: a bound method value (D.g)`.

3. Field assigned through a non-constant dict key is not discovered.
```python
class D:
    def g(self): return 1
d = D(); dd = {'x': d}; k = 'x'
dd[k].g = 5
print(dd['x'].g)
```
Expected `5`; actual both builds: `not in the subset: a bound method value (D.g)`.

4. A class-body attribute assigned after the method shadows it in CPython, but is treated as a method.
```python
class D:
    def g(self): return 1
    g = 5
print(D().g)
```
Expected `5`; actual both builds: `not in the subset: a bound method value (D.g)`.

**Pre-existing:** `vars(d)['g'] = 5; print(d.g)` fails on base and HEAD (base `AttributeError`, HEAD named refusal) — does not block.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, compile-time speed; no runtime change.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 973383, "input": 50358, "output": 4567, "reasoning": 17722, "cache.write": 0, "cache.read": 900736}]
    tool time: bash 6.4 min
        129s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre318 tes
        120s bash   grep -rn "r_bound_default\|bound_default" /home/runner 2>/dev/null | head; find / -name 'r_bound_default.py' 2
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for f in field_setattr field_module_assign field_arg_assign field_tuple 
         25s bash   date; cd /tmp/rprobes && cat > p_field_return.py <<'EOF' class D:     def g(self):         return 1 def make()
         14s bash   cd /tmp/rprobes && cat > p_field_star.py <<'EOF' class D:     def g(self):         return 1 def setg(*args):  
         13s bash   cd /tmp/base && for f in p_class_attr_shadow p_class_attr_after p_default; do echo "######## $f BASE"; bash ~/
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_default p_class_attr_shadow p_class_attr_after p_subclass_fie
          9s bash   cd /tmp/rprobes && cat > p_class_attr_after_def.py <<'EOF' class D:     def g(self):         return 1     g = 

FINAL VERDICT: FIX  2026-10-27T07:02:45Z
