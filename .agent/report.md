# job job-pre293-10270436  started 2026-10-26T19:37:44Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":584,"duration_api_ms":450,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":610,"duration_api_ms":487,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed as `78664a3` on `job-pre293-10270436`.

**Reproduced:** the baseline general path (both builds) printed `101` for `C().f(1)` where CPython reads the instance field and prints `11`; the non-callable case silently ran the method instead of raising `'F' object is not callable`.

**Fix:** the general path now records each class's instance fields (`self.x = ...`, tuple unpacking, `setattr(self, ...)`) and refuses `obj.x(...)` by name when such a field shadows a method, naming the field and class. Works for static and dynamic receivers. `super().x(...)`, `C.x(obj, ...)` and typed `Callable` fields remain unchanged.

**Probes (`/tmp/probes`, `cmp.sh` on both builds):**
- Refused by name: `p1_callable_instance`, `p2_noncallable_instance`, `p3_bytes_field`, `p4_int_field`, `p5_lambda_field`, `p6_argument`, `p7_list_item`, `p8_attribute`, `p9_dict_value`, `p11_inherit`, `p12_annotated`, `p16_setattr`, `p17_unpack`, `p18_descendant`, `callable_field`, `callable_field_attr`, `callable_field_var`, `bytes_field`, `noncall_field` (19)
- Match CPython on both builds: `p14_super`, `p15_unbound` (2)
- `callable_typed_field`: matches CPython on the default/typed build; refused by name on forced-general (1)
- Pre-existing named refusals unchanged: `p10_plain_field`, `p13_getattr`, `field_only_callable`, `field_only_func`, `field_only_int` (5)

`p18_descendant` is conservatively refused (CPython's `C()` has no field there); it is refused by name, not silently wrong.

**Tests on final commit:** `test_ail_pre293`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 254 s, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass. Instruction counts were not measured.

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the diff does:** records instance fields assigned in a class's own methods (`self.x =`, tuple unpack, `setattr(self, "x", ...)`, `pyboxed2.py:3118-3140`) and raises `Unsupported` for `obj.x(...)` when such a field shadows a method, in both the static (`:8454`) and dynamic (`:8701`) call paths. It adds `test_ail_pre293.py`, a DIFFERENCES row and a DEVLOG entry.

**Target defect:** fixed. Original probe (callable instance field) is refused by name on both builds; base silently printed `101` where CPython prints `11`. Non-callable instance field likewise refused by name; base printed the method result. `super().f(...)`/`C.f(obj, ...)` still match CPython.

**Tests/checks on HEAD:** `test_ail_pre293` and `test_ail_safetynet` pass (`-j 2`, 124 s). `update_manifest.py --check` and `ci_shards.py --check` pass. `program.c` for a non-feature program is byte-identical to base, so no codegen/hot-path change; speed not measured.

**Pre-existing (not caused, identical on base):**
- Field set outside a method (`c.f = F(); c.f(1)`) and via `vars(self)["f"]` or an alias (`s = self; s.f = F()`): base and HEAD both print `101`, CPython `11` (probes p03/p08/p09).
- `type(self).f = ...` is refused on both trees for the unrelated `type` name.

**Report claims:** target reproduction, the field-recording/refusal, `super`/unbound unchanged, and the test/manifest claims verified. "Works for ... dynamic receivers" is true only in a blanket sense: the dynamic path refuses based on any class in the program, not the receiver (see defects). The DEVLOG says 331 s where the report says 254 s (minor inconsistency).

**Unverified:** the 19 worker probes in `/tmp/probes` were not all rerun; instruction counts not measured (compile-time-only change).

**Defects (caused by this change; base matched CPython):**
1. Unrelated classes: dynamic dispatch refuses every `x.f()` if any class anywhere has a shadowing field `f`.
```python
class A:
    def __init__(self): self.f = 5
    def f(self, x): return x + 10
class B:
    def f(self, x): return x + 100
def go(x): return x.f(1)
print(go(B()))
```
Expected (CPython and base): `101`. Actual HEAD: build fails, `calling the instance field 'f' of A ...`. The receiver is `B`, which has no field.
2. Unrelated builtin: a user class with a field named like a builtin method poisons calls on builtin receivers.
```python
class C:
    def __init__(self): self.append = 5
    def append(self, x): return x
def go(x): x.append(1)
go([])
print('ok')
```
Expected (CPython and base): `ok`. Actual HEAD: build fails, naming `'append'` of `C`, although the receiver is a list.
3. False instance field from a nested scope: `ast.walk` descends into nested functions and treats their `self` as the instance.
```python
class C:
    def f(self, x): return x + 100
    def g(self):
        def h(self):
            self.f = 5
        return 1
print(C().f(1))
```
Expected (CPython and base): `101`. Actual HEAD: build fails, `calling the instance field 'f' of C`; `C` has no instance field. (`self` in `h` is a different parameter.)

Also over-refused, but arguably conservative: a field assigned only in an uncalled method (p04) and a field present only on a descendant when calling on the base instance (p10, disclosed by the worker).

VERDICT: FIX
[cost $0.0186, opencode tokens {"total": 591596, "input": 35133, "output": 4649, "reasoning": 14854, "cache.write": 0, "cache.read": 536960}]
    tool time: bash 4.7 min
        126s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre293 t
         62s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p) HEAD"; ba
         58s bash   cd /tmp/base; date; for p in /tmp/rprobes/p01_orig.py /tmp/rprobes/p02_noncall.py /tmp/rprobes/p03_external.py
         30s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p03_external p08_vars p09_alias; do echo "== $p HEAD"; out=$(bash
          6s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/dbgrh /tmp/dbgrb; mkdir -p /tmp/dbgrh /tmp/dbgrb; mkdir -p /tm
          0s bash   git worktree add /tmp/base work 2>&1 | tail -3; mkdir -p /tmp/rprobes; date
          0s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/dbg_head /tmp/dbg_base; mkdir -p /tmp/dbg_head /tmp/dbg_base; 
          0s bash   cd /home/runner/work/ail-ci/ail-ci; python3 tools/update_manifest.py --check 2>&1 | tail -3; python3 tools/ci_

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `9f26821` on `job-pre293-10270436`.

Fixed the three review defects:
- Unrelated dynamic receiver: `go(B())` now prints CPython's `101`; only refuses when every user class defining the method has the shadowing field.
- Built-in poisoning: `go([])` with `x.append(1)` now prints `ok`; a same-named built-in method suppresses the dynamic refusal.
- Nested scope: a nested `def h(self)` no longer marks `C.f` as an instance field; `C().f(1)` prints `101`.

Probes on both builds:
- Match CPython: `def1_unrelated_classes`, `def2_unrelated_builtin`, `def3_nested_scope`, `dyn_field_unrelated_reverse`, `dyn_field_third_class`, `dyn_builtin_count`, `dyn_field_via_routes`, `nested_lambda_own_self`, `nested_rebind_self`, `p14_super`, `p15_unbound`.
- Refused by name: `target_callable_field`, `target_noncallable_field`, `target_bytes_field`, `p6_argument`, `p7_list_item`, `p8_attribute`, `p9_dict_value`, `p11_inherit`, `p12_annotated`, `p16_setattr`, `p17_unpack`, `p18_descendant`, `nested_lambda_field`.

Final commit tests: `test_ail_pre293`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 203 s, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass. Instruction counts not measured (compile-time-only change); untracked `.agent/pipeline.md` left untouched.
[cost $0.0487, opencode tokens {"total": 3979605, "input": 105527, "output": 13876, "reasoning": 21738, "cache.write": 0, "cache.read": 3838464}]
    tool time: bash 9.7 min, edit 0.0 min
        206s bash   python3 tools/par_check.py -j 2 test_ail_pre293 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
        204s bash   python3 tools/par_check.py -j 2 test_ail_pre293 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
         60s bash   for p in def1_unrelated_classes def2_unrelated_builtin def3_nested_scope target_callable_field target_noncalla
         39s bash   cat > /tmp/probes/nested_closure_field.py <<'EOF' class F:     def __call__(self, x): return x + 10 class C:  
         32s bash   for p in def1_unrelated_classes def2_unrelated_builtin def3_nested_scope target_callable_field target_noncalla
         12s bash   for p in def1_unrelated_classes def2_unrelated_builtin def3_nested_scope; do echo "===== $p"; bash ~/tools/cmp
          5s bash   bash ~/tools/cmp.sh /tmp/probes/nested_closure_field.py "$PWD" 2>&1 | tail -20
          4s bash   cd /tmp && rm -rf dbgt && mkdir dbgt && cp /tmp/probes/target_callable_field.py dbgt/p.ail && cd dbgt && for e

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** `pyboxed2.py` now records each class's instance-field names assigned by its own methods (`self.x=`, tuple unpacking, `setattr(self,...)`, skipping nested scopes that bind their own `self`) and raises a named `Unsupported` for `obj.x(...)` when `x` also names a method: always for a statically known receiver, and on the dynamic path only when every method-defining user class has the shadowing field and no built-in handler exists. Tests/manifest/DIFFERENCES/DEVLOG added. This matches the report.

**Probing (HEAD, then base where relevant):**
- Target case `C().f(1)` (callable instance): HEAD both builds refuse by name (`calling the instance field 'f' of C`); base prints `101` vs CPython `11`. Fix is the permitted refusal.
- Non-callable/bytes/int fields, `setattr`, unpack, inherited, annotated, and value routes through a list item, attribute, dict value: refused by name, both builds.
- Claimed non-refusals all verified on both builds: `def1_unrelated_classes` (`101`), `def2_unrelated_builtin` (`ok`), `def3_nested_scope` (`101`), plus `dyn_field_unrelated_reverse`, `dyn_field_third_class`, `dyn_builtin_count`, `dyn_field_via_routes`, `nested_lambda_own_self`, `nested_rebind_self`, `p14_super`, `p15_unbound` all match CPython.
- `program.c` for a non-feature program (`class C: self.x=3; def f`) is byte-identical between base and HEAD; only `native_report.json` metadata differs.
- New, but named/acceptable over-refusals: `handler()`, `def setup(self): self.f=5` never called, descendant `D(C)` field refusing a call on a `C` instance, and `self` rebound in the same method. Base ran all of these correctly; each is now a named compile-time refusal, which the rubric allows.

**Pre-existing (identical output on base, non-blocking):**
- Dynamic receiver with two method owners where only one class has the field: HEAD and base print `101`, CPython raises `TypeError: 'int' object is not callable`.
- Field assigned outside a method (`c.f = F()`), via `vars(self)['f']`, or via `s = self; s.f = ...`: HEAD and base both print `101` vs CPython `11`.
- Field-only callable (`self.f(...)` with no same-named method) is refused with the older "method .f()" message on both trees.

**Tests/claims:** `test_ail_pre293` + `test_ail_safetynet` pass on HEAD (118 s, 0 failed). `update_manifest.py --check` and `ci_shards.py --check` pass. `test_ail_files`/`test_ail_corpus_findings3` and instruction counts were not re-run (compile-time-only change; not measured).

**Unverified:** worker's 4-module 203 s run (I only re-ran the two required modules), instruction counts (not applicable).

VERDICT: ACCEPT
[cost $0.0208, opencode tokens {"total": 649197, "input": 45642, "output": 4281, "reasoning": 16106, "cache.write": 0, "cache.read": 583168}]
    tool time: bash 4.8 min
        119s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_
         50s bash   cd /tmp/probes && for p in def1_unrelated_classes def2_unrelated_builtin def3_nested_scope dyn_field_unrelated
         30s bash   cd /tmp/rprobes && for p in p03_external p04_uncalled p07_dunder p08_vars p09_alias p10_descendant; do echo "=
         29s bash   cd /tmp/rprobes && for p in p1_callable_static p2_unrelated p3_builtin p4_nested p5_rebind_self p6_route_list 
         24s bash   cd /tmp/rprobes && for p in p5_rebind_self p9_dyn_two_owners_field p11_field_only p12_descendant p1_callable_s
         17s bash   cd /tmp/rprobes && for p in p03_external p04_uncalled p07_dunder p08_vars p09_alias p10_descendant p14_classat
         15s bash   cd /tmp/probes && for p in target_callable_field target_noncallable_field target_bytes_field p16_setattr p17_u
          2s bash   date; rm -rf /tmp/dbgH /tmp/dbgB; mkdir -p /tmp/dbgH /tmp/dbgB; cp /tmp/rprobes/p13_no_feature.py /tmp/dbgH/p.

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T21:48:21Z
