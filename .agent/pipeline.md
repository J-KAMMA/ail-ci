# job job-pre295-10270439  started 2026-10-26T19:40:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":332,"duration_api_ms":202,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":321,"duration_api_ms":194,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the class-attribute-store difference.

**Change:** General runtime now handles `C.x = v` for a CLASS receiver: existing class-body attributes update their shared slot, new names get a dynamic class entry; instance/class reads, `getattr`/`hasattr`/`setattr` and `vars` follow CPython; `Sub.v = x` hides `Base.v`. `del Box.v` remains refused by name.

**Probes** (`/tmp/probes/p_*.py`, 20 total): `direct, alias, index, return, attr, param, cond, global, local, dict, inst, inst_read, inst_attrs, new, new_inst, inherit, aug, setattr, types, empty` — all matched CPython on both builds.

**Tests on final commit `2f241b0`:**
- `test_ail_pre295`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- Class-related targeted: `pre133, fuzz29, pre127, typed_inherit, dunders, pre96, virtual_dispatch`: 7 modules, 0 failed.
- `tools/update_manifest.py --check`: passes.
[cost $0.0708, opencode tokens {"total": 7821684, "input": 158947, "output": 18897, "reasoning": 21184, "cache.write": 0, "cache.read": 7622656}]
    tool time: bash 16.7 min
        338s bash   python3 tools/par_check.py -j 2 test_ail_pre295 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
        204s bash   python3 tools/par_check.py -j 2 test_ail_pre133 test_ail_fuzz29 test_ail_pre127 test_ail_typed_inherit test_ai
        157s bash   python3 tools/par_check.py -j 2 test_ail_typed_inherit test_ail_dunders test_ail_pre96 test_ail_virtual_dispat
         85s bash   cat > /tmp/probes/p_dict.py <<'EOF' class Box:     v = 1 classes = {"box": Box} classes["box"].v = 2 print(Box
         70s bash   cat > /tmp/probes/p_new.py <<'EOF' class Box:     v = 1 Box.w = 5 Box.v = 2 print(Box.v, Box.w) EOF cat > /tmp
         63s bash   python3 tools/par_check.py -j 2 test_ail_pre295 test_ail_pre133 test_ail_fuzz29 test_ail_pre127 2>&1 | tail -8
         30s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_index.py <<'EOF' class Box:     v = 1  boxes = [Box, Box] i = 0 bo
         20s bash   for p in /tmp/probes/p_inherit.py /tmp/probes/p_inst_read.py /tmp/probes/p_direct.py /tmp/probes/p_new.py /tmp

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** Routes a CLASS receiver in `ail_inst_setattr_chk`/`setattr` to a new `ail_class_setattr` (own class-body attr updates its shared slot, anything else becomes a per-class dynamic entry), adds class-chain/dyn lookups, and removes the old "copy class-body attributes onto every instance" emission in `_call_class` so instance reads/`vars` fall back to the class. It also changes direct inherited class reads to go through the runtime. This matches the report except that the report understates the breadth: every general-path program with class attributes gets different C, and method/property-named stores are accepted but not honoured on all read paths.

**Probes run** (all via `~/tools/cmp.sh`, general + default, compared to CPython, and to `/tmp/base`):
- Store routes (`direct, index, return, attr, param, cond, global, dict, alias`), values (`int/float/str/list/dict/None/bool`), new names, inheritance (`Sub.v` hides `Base.v`), instance shadowing, `vars`/`getattr`/`hasattr`/`setattr`, ownership/rebinding: match CPython both builds.
- `p_inst_only`, `p_mutate`, `p_newattr`, `p_shadow_after`, `p_dc_initfalse_full`: match.
- `del Box.v`: refused by name (as claimed).
- Non-feature program (`class` attrs read only, no store): general-path C differs from base (the copy lines disappear); output still matches CPython.

**Tests:** `test_ail_pre295` + `test_ail_safetynet` on HEAD: 2/2 ok, 0 failed. `tools/update_manifest.py --check`: rc 0. Manifest/shard/ail_check registration present.

**Defects (caused by this change):**

1. Store over a class-body `@property` is accepted but instance reads still run the old getter.
```python
class Box:
    @property
    def v(self):
        return 1
Box.v = 5
b = Box()
print(b.v)
```
CPython: `5`. HEAD (both builds): `1`, exit 0. Base: AttributeError at the store (exit 1). The runtime comment says a property-named store gets a dynamic entry, but `_property_read` (`pyboxed2.py:5317`) bypasses it.

2. Store over a class-body method is accepted but calls still dispatch to the original method.
```python
class Box:
    def v(self):
        return 1
Box.v = 5
b = Box()
print(b.v)
print(b.v())
```
CPython: `5`, then `TypeError 'int' object is not callable`. HEAD (both builds): `5`, then `1`. Base: AttributeError at the store. A named refusal would be acceptable; a silently wrong call result is not.

3. Instance read of an inherited class attribute shadowed by a method now crashes on the general path.
```python
class Base:
    x = 1
class Sub(Base):
    def x(self):
        return 7
print(Sub().x)
```
CPython: bound method. Base general path: `1` (already wrong). HEAD general path: no stdout, exit 1, `AttributeError: 'Sub' object has no attribute 'x'` (the new fallback returns the method sentinel 2). Default build still prints `1`. This is a new crash caused by removing the copy; `hasattr` with a computed name still works because the compiler handles methods separately.

**Pre-existing (also differs on base):** `vars()`/`getattr()`/`hasattr()` visibility of class attributes was wrong on base and is now CPython-correct; `getattr` of a method/property value remains unsupported (refused by name); `del C.attr` remains refused. Class-attribute method-shadow reads were already wrong on base, but defect 3 is the new crashing form.

**Unverified:** the worker's 7 class-related modules, `test_ail_files`, `test_ail_corpus_findings3`; speed (not a speed task).

VERDICT: FIX
1. Property-named class store: `class Box: @property def v(self): return 1` then `Box.v = 5; print(Box().v)` → expected `5`, actual `1` (both builds).
2. Method-named class store: `class Box: def v(self): return 1` then `Box.v = 5; print(Box().v())` → expected `TypeError: 'int' object is not callable`, actual `1` (both builds).
3. General-path crash on `class Base: x = 1` / `class Sub(Base): def x(self): return 7` / `print(Sub().x)` → base printed `1` (already wrong vs CPython's bound method), HEAD now exits 1 with `AttributeError` instead of running.
[cost $0.0567, opencode tokens {"total": 3825492, "input": 102596, "output": 9754, "reasoning": 40694, "cache.write": 0, "cache.read": 3672448}]
    tool time: bash 5.2 min
        125s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre295 test_ail_safetynet 2>&1 | tail -20
         29s bash   cat > /tmp/rprobes/p_method_shadow.py <<'EOF' class Base:     x = 1  class Sub(Base):     def x(self):        
         21s bash   cat > /tmp/rprobes/p_shadow_after.py <<'EOF' class Box:     v = 1  b = Box() b.v = 9 Box.v = 5 print(Box.v, b.
         12s bash   cat > /tmp/rprobes/p_dc_initfalse_full.py <<'EOF' from dataclasses import dataclass, field  @dataclass class R
         12s bash   for p in /tmp/rprobes/p_method_shadow.py /tmp/rprobes/p_inst_only.py /tmp/rprobes/p_mutate.py; do echo "===== 
         10s bash   cat > /tmp/rprobes/p_dc_initfalse.py <<'EOF' from dataclasses import dataclass, field  @dataclass class Rect: 
          9s bash   cat > /tmp/rprobes/p_vars_read.py <<'EOF' class Box:     v = 1     xs = []  b = Box() print(b.v, b.xs, vars(b)
          9s bash   cat > /tmp/rprobes/p_method_computed.py <<'EOF' class Base:     x = 1  class Sub(Base):     def x(self):      

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `6b4b777` on `job-pre295-10270439`.

- Property-named class store now replaces the property for class/instance reads, inheritance, setters, later instance assignment, `getattr`/`hasattr`, and calls (stored non-callable raises CPython's `TypeError`).
- Method-named class store is refused by name (`NotImplementedError: assigning method 'v' on class ...`); method/property value reads are also refused by name instead of crashing, including the typed-path method-shadow case.
- Probes `p_prop*`, `p_meth*`, `p_new_after_method`, `p_inst_shadow_meth*`, `p_shadow*` all match CPython or are refused by name on both builds.
- Tests: `test_ail_pre295` (11 tests), `test_ail_typed_inherit`, `test_ail_dunders`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed.
- `tools/update_manifest.py --check`: rc 0.
[cost $0.1003, opencode tokens {"total": 10939686, "input": 191862, "output": 23824, "reasoning": 41888, "cache.write": 0, "cache.read": 10682112}]
    tool time: bash 25.3 min
        399s bash   python3 ../tools/update_manifest.py --check && python3 ../tools/par_check.py -j 2 test_ail_pre295 test_ail_typ
        399s bash   python3 ../tools/update_manifest.py >/dev/null && python3 ../tools/par_check.py -j 2 test_ail_pre295 test_ail_
        377s bash   python3 ../tools/par_check.py -j 2 test_ail_typed_inherit test_ail_dunders test_ail_safetynet test_ail_files t
         87s bash   for p in p_prop p_prop_main p_prop_routes p_prop_inherit p_prop_setter p_prop_exc p_prop_then_call p_prop_inhe
         46s bash   python3 ../tools/update_manifest.py >/dev/null && python3 ../tools/par_check.py -j 2 test_ail_pre295 2>&1 | ta
         42s bash   for p in p_prop_then_call p_inst_shadow_meth_call p_prop p_prop_setter p_prop_routes p_prop_inherit p_meth p_s
         25s bash   for p in p_prop p_meth p_shadow p_prop_main p_meth_main p_inst_shadow_meth; do echo "===== $p"; bash /home/run
         22s bash   cat > /tmp/probes/p_meth_direct.py <<'EOF' class Box:     def v(self):         return 1   def main():     Box.

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review of `job-pre295-10270439` (`work..HEAD`, 2 commits)

**What the change really does.** Routes a store whose receiver is a class to a new runtime `ail_class_setattr` (updates the class-body shared slot, or a per-class dynamic entry; refuses method-named stores at run time), makes instance reads fall back to the class chain, removes the old copy-class-attrs-onto-instance code, adds dynamic checks around property getters/setters and method calls, and adds a typed-path refusal for a method hiding an inherited class attribute. Matches the report except that the method-store refusal is a **run-time** `NotImplementedError`, not the compile-time refusal the task asked for (base refused those statically).

**Probes (HEAD, both builds unless noted)**
- `p1` two classes with same-named class attr, `p2` list alias/mutation, `p3` Base/Sub hide order, `p4` instance shadow, `p5` dict/`getattr`/`hasattr` routes, `p6` property on two unrelated classes, `p7` property store + instance shadow, `p8` inherited property + subclass store, `p10` new name, `p11` augmented through alias/param, `p12` identity, `p13` property with setter, `p25` same-kind method control, `p30` subclass attr hides base method, `p41` same-kind iteration: **match CPython**.
- `p9` argument evaluated once on the new shadow path: matches (one `f`).
- `p37` method-named store: both builds exit 1 with `NotImplementedError: assigning method 'v' on class A ...`; base refused at compile time. Named refusal, acceptable.
- `p29` class read of a method: refused by name (base `d` printed `10`, so this is an improvement).
- `p14` `getattr` of a property as a value: both builds refuse by name; acceptable.

**Defects**

1. **Cross-kind class store leaves the old static kind, causing a segfault.**
   ```
   class A:
       xs = [1, 2]
   def main():
       a = A()
       A.xs = "ab"
       for c in a.xs:
           print(c)
   main()
   ```
   Expected `a\nb`; actual **segmentation fault, exit 139, empty stdout** on both `g` and `d`. Base exits 1 (`AttributeError: 'type' object has no attribute 'xs'`), so the crash is new behaviour of the newly working store. Same root via a route (`c.s = v` in a function): `a.s.append(2)` after storing a list over a `s = "abc"` class attr gives exit 1 `AttributeError: 'list' object has no attribute 'append'` (expected `[1, 2]`); `A.s = 42` over `s = "abc"` then `a.s.upper()` gives exit 1 `AttributeError: 'str' object has no attribute 'upper'` (expected `ABC True`). Control `p25` (same-kind store) passes, so it is the stale class-body kind (`pyboxed2.py` `infer_kind`, class-attr branch) not invalidated by class stores.

2. **Same cause for method dispatch after a class store.** 
   ```
   class A:
       s = "abc"
   def main():
       a = A()
       A.s = [1]
       a.s.append(2)
       print(a.s)
   main()
   ```
   Expected `[1, 2]`; actual exit 1 `AttributeError: 'list' object has no attribute 'append'`. The program compiles the call against the class-body `str` kind.

**Pre-existing (identical on base)**
- Instance-store cross-kind: `a.xs = "ab"; for c in a.xs` segfaults on HEAD **and base** (`p45`); same for `a.s = [1]; a.s.append(2)` (`p36`). The kind-inference gap is pre-existing; class stores only make it newly reachable.
- `class Base: @property v` + `class Sub(Base): v = 10`: first `print(Base().v, Sub().v)` gives `1 1` instead of `1 10` on both (`p15`); later class stores do work on HEAD.
- `@dataclass` class read `A.x` raises `AttributeError` on both (`p35`).

**Tests / records**
- `test_ail_pre295` (11 tests) and `test_ail_safetynet`: pass. `test_ail_typed_inherit`: pass. `python3 tools/update_manifest.py --check`: rc 0.
- `test_ail_dunders`, `test_ail_files`, `test_ail_corpus_findings3`: not re-run (unverified).
- Speed: `perf_event_open` denied on this runner, so `tools/icount.c` could not be used (unverified); no wall-clock regression noticed on `g04_028`/`g12_000`.

VERDICT: FIX
1. Class attribute store changing the value kind leaves reads compiled as the old class-body kind: `p40_iterfor.py` (above) segfaults (exit 139) instead of printing `a\nb`; `p22_str2list.py`/`p26_route.py` fail with `AttributeError: 'list' object has no attribute 'append'` after `A.s = [1]` where the class body had `s = "abc"`, and `A.s = 42` over `s = "abc"` makes `a.s.upper()` fail. Same-kind controls pass. Class stores must invalidate `infer_kind` for that attribute (or reads must not assume the class-body kind).
[cost $0.0523, opencode tokens {"total": 3788039, "input": 95213, "output": 10933, "reasoning": 34149, "cache.write": 0, "cache.read": 3647744}]
    tool time: bash 9.3 min
        157s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_type
        129s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         26s bash   cd /tmp/rprobes && for p in p1_shared p2_mutate p3_inherit p4_instshadow p5_getattr p6_propunrel; do echo "###
         25s bash   cd /tmp/rprobes && cat > p16_i2l.py <<'EOF' class A:     v = 1 def main():     a = A()     A.v = [10, 20]     
         23s bash   cd /tmp/rprobes && cat > p11_augalias.py <<'EOF' class A:     v = 1     xs = [1] class H:     def __init__(sel
         18s bash   cd /tmp/rprobes && cat > p34_funcval.py <<'EOF' def g():     return 7 class A:     f = g def main():     a = A
         18s bash   cd /tmp/rprobes && for p in p7_propinst p8_propinherit p9_argeval p10_newinst; do echo "########## $p"; bash ~
         16s bash   cd /tmp/rprobes && cat > p28_methhide.py <<'EOF' class Base:     size = 10 class Sub(Base):     def size(self)

FINAL VERDICT: FIX  2026-10-26T21:08:09Z
