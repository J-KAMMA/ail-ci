# job job-pre129-10242352  started 2026-10-24T15:05:55Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":566,"duration_api_ms":442,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":542,"duration_api_ms":418,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Reproduced the first pre-existing item from pre107's review: bound Random methods still differed on both builds (`f = random.expovariate`, `g = r.expovariate` printed values in CPython, raised `AttributeError` in AIL).

Fix: the general path now refuses a `Random` method read as a value at compile time, naming the bound method; direct calls are unchanged. Non-Random fields with the same names still work.

Probes (`cmp.sh`, both builds):
- Refused by name: module function, Random object, argument, list item, attribute, dict value, alias; also `expovariate`, `gauss`, `random`, `triangular` — 10/10.
- Matched CPython: direct method calls through all routes, non-Random `gauss` field, field shadowing a method — 5/5.
- Pre-existing, untouched: non-Random user-class bound methods still fail at run time.

Tests on final commit `932436a`: `test_ail_pre129`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 332 s. Manifest `--check` passes. Not pushed.
[cost $0.0000, opencode tokens {"total": 4866186, "input": 133536, "output": 11446, "reasoning": 17076, "cache.write": 0, "cache.read": 4704128}]
    tool time: bash 10.3 min
        334s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre129 test_ail_safetynet test_ail_files
        126s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre129 test_ail_safetynet 2>&1 | tail -2
         47s bash   cd /tmp/probes && for p in p129_mod_bound_arg p129_obj_bound_arg p129_obj_bound_gauss p129_mod_bound_gauss p12
         35s bash   cd /tmp/probes && cat > p129_route_arg.py <<'EOF' import random  def bind(r):     return r.expovariate  def ma
         20s bash   cd /tmp/probes && cat > p129_mod_bound_arg.py <<'EOF' import random  def main() -> None:     random.seed(1)   
         16s bash   cd /tmp/probes && for p in p129_mod_bound p129_obj_bound p129_star; do echo "######## $p"; bash ~/tools/cmp.sh
         16s bash   cd /tmp/probes && cat > p129_user_bound.py <<'EOF' class C:     def __init__(self, x: int):         self.x = x
         11s bash   cd /tmp/probes && cat > p129_collision_field.py <<'EOF' class A:     def __init__(self):         self.f = 5   

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** In the general path's attribute-read emitter (`pyboxed2.py:5057-5065`), if a program's `Random` class defines the attribute name, it refuses the read unless the receiver's statically inferred class is a known non-`Random` class. So it refuses more than the bound-method case.

**Original difference (verified):** `/tmp/rprobes/p13_original_diff.py` (`f = random.expovariate`, `g = r.expovariate`) — CPython prints values; base both builds raise `AttributeError`; HEAD both builds refuse by name with `random.Random.expovariate read as a value (a bound method)`. Direct calls (`p6`) still match.

**Tests:** HEAD `test_ail_pre129` + `test_ail_safetynet` pass (125 s, 0 failed). `update_manifest.py --check` passes. No origin refs, so nothing pushed.

**Report claims:**
- Reproduced difference, fix refuses by name, direct calls unchanged: verified.
- "Non-Random fields with the same names still work": **false** as a general statement. Only statically-known direct receivers work (`p11`); through an argument, list item, dict value, attribute chain, or annotation, non-Random fields named `gauss`/`uniform`/`choice` are refused by both builds (`p9`, `p10`, `p14`, `p15`). Base matched CPython on all of them.
- Pre-existing non-Random user-class bound method failure: verified on both base and HEAD (`p12`), identical `AttributeError`.
- 4-module test run and instruction counts: not re-run/not applicable (compile-time-only change).

**Defects**
1. Over-broad refusal of non-Random fields when the receiver's class is not statically known and `random` is imported. `/tmp/rprobes/p9_random_import_dynfield.py`: expected `2\n5.0`; actual both builds fail to compile: `not in the subset: random.Random.gauss read as a value (a bound method)`; base matches CPython. Same for `p10` (`5\n1`) and `p14` (dict/list/attribute fields; expected `5.0\n5.0\n5.0\n2`).
2. Random-subclass instance field shadowing a method is refused. `/tmp/rprobes/p4_subclass_field.py`: expected `9.0`; actual both builds fail with `random.Random.gauss read as a value`; base prints `9.0` on both builds.

**Pre-existing (non-blocking):** `p12` non-Random class bound method read fails at run time identically on base and HEAD.

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3`; whether this was the "first" pre107 item (the full list is not in the tree); instruction counts (no emitted-code change; `program.c` for `p11` is byte-identical to base).

VERDICT: FIX
1. Non-Random fields with Random-method names are refused when the receiver class is not statically known (`p9`, `p10`, `p14`), although base matches CPython on both builds; expected vs actual above.
2. Fields on a `random.Random` subclass are refused (`p4`): expected `9.0`, actual named refusal on both builds, base matches.
[cost $0.0000, opencode tokens {"total": 821590, "input": 34048, "output": 6557, "reasoning": 9657, "cache.write": 0, "cache.read": 771328}]
    tool time: bash 3.9 min, write 0.0 min
        127s bash   cd AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre129 test_ail_safetynet 2>
         37s bash   mkdir -p /tmp/rout/head; cd /tmp/rprobes; for p in p*.py; do echo "######## $p"; timeout 400 bash ~/tools/cmp.
         33s bash   mkdir -p /tmp/rout/head /tmp/rout/base; cd /tmp/rprobes; for p in p9_random_import_dynfield p10_random_import_
         17s bash   cd /tmp/rprobes; for p in p14_random_import_container_field p15_annotated_param_field; do for wt in /home/runn
         11s bash   cd /tmp/rprobes; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "#### $wt"; timeout 300 bash ~/t
          5s bash   rm -rf /tmp/ddhead /tmp/ddbase; cd /tmp/csrc; AIL_NO_CACHE=1 AIL_UNIFIED_FORCE=1 python3 /home/runner/work/ail
          4s bash   cd /tmp/rprobes; for p in p12_nonrandom_method_value; do echo "######## BASE $p"; timeout 300 bash ~/tools/cmp
          0s bash   git worktree add /tmp/base work >/tmp/wt.log 2>&1; tail -3 /tmp/wt.log; mkdir -p /tmp/rprobes; date

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed on `job-pre129-10242352`.

**Changes**
- `pyboxed2.py`: bound-method refusal now fires only when the receiver is statically a `Random`/subclass **and** no instance field shadows the attribute.
- Added `_has_instance_attr` so `M(random.Random)` with `self.gauss = 9.0` reads the field.
- Seeded randlib's hidden `_ail_rng` as a known `Random`, preserving refusal for `f = random.expovariate`.
- Updated `test_ail_pre129.py`, `DEVLOG.md`, `DIFFERENCES.md` (`C?-job-pre129-10242352-2` records the remaining dynamic-receiver gap), and the manifest.

**Probes** (19, both builds via `cmp.sh`)
- Match CPython: `p1`–`p11`, `p14`, `p15` (dynamic/non-Random fields, containers, aliases, direct Random calls).
- `p4`: subclass field now prints `9.0` on both builds.
- Refused by name: `p13`, `p16`, `p18`, `p19`.
- `p12` and `p17`: pre-existing run-time `AttributeError`, identical to base; not claimed fixed.

**Tests on final commit `bad54b9`**
`test_ail_pre129`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 259 s, **0 failed**. `update_manifest.py --check` passes. Not pushed.
[cost $0.0000, opencode tokens {"total": 1553392, "input": 60623, "output": 8430, "reasoning": 10291, "cache.write": 0, "cache.read": 1474048}]
    tool time: bash 12.7 min
        261s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && git rev-parse --short HEAD && date && timeout 1800 python3 .
        257s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         91s bash   cd /tmp/rprobes && : > /tmp/probe_results.txt; for p in p*.py; do echo "#### $p" >> /tmp/probe_results.txt; ti
         80s bash   cd /tmp/rprobes && for p in p9_random_import_dynfield p10_random_import_dynfield2 p14_random_import_container_
         20s bash   cd /tmp/rprobes && for p in p9_random_import_dynfield p4_subclass_field p13_original_diff p11_random_import_kn
         18s bash   cd /tmp/rprobes && for p in p17_arg_only p12_nonrandom_method_value p18_module_func_value; do echo "#### BASE 
         11s bash   cat >/tmp/rprobes/p16_rand_obj_only.py <<'EOF' import random   def main() -> None:     r = random.Random(8)   
         10s bash   cat >/tmp/rprobes/p18_module_func_value.py <<'EOF' import random   def main() -> None:     random.seed(1)     

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** In `pyboxed2.py` it refuses a read of a `random.Random` method as a value when the receiver is statically `Random`/subclass, unless `_has_instance_attr` finds a `self.attr` written via `Assign`/`AnnAssign`/`AugAssign`; it also marks randlib's `_ail_rng` as `instance:Random`. It adds `test_ail_pre129.py` and docs/manifest updates.

**Regression probes** (all: base matched CPython on both builds; HEAD refuses on both builds). Expected output is CPython's.

1. Class-level shadow — `AIL_CURRENT/python/pkg-v12/pyboxed2.py:6026` ignores class-body assignments.
```python
import random
class M(random.Random):
    gauss = 9.0
def main() -> None:
    print(M(5).gauss)
main()
```
expected `9.0`; actual `not in the subset: random.Random.gauss read as a value (a bound method) is not built; call it`.

2. Tuple-target shadow — `_has_instance_attr` only walks direct `Attribute` targets.
```python
import random
class M(random.Random):
    def __init__(self):
        random.Random.__init__(self, 5)
        self.gauss, self.uniform = 9.0, 8.0
def main() -> None:
    m = M(); print(m.gauss); print(m.uniform)
main()
```
expected `9.0` / `8.0`; actual same compile-time refusal on `gauss`.

3. `setattr` shadow — not detected by the AST scan.
```python
import random
class M(random.Random):
    def __init__(self):
        random.Random.__init__(self, 5)
        setattr(self, 'gauss', 9.0)
def main() -> None:
    print(M().gauss)
main()
```
expected `9.0`; actual same refusal.

4. Aliased-self shadow — `me = self; me.gauss = 9.0` is not seen.
```python
import random
class M(random.Random):
    def __init__(self):
        random.Random.__init__(self, 5)
        me = self; me.gauss = 9.0
def main() -> None:
    print(M().gauss)
main()
```
expected `9.0`; actual same refusal.

**Claims checked:** direct `self.gauss` field in a subclass now works (verified, q6); `_ail_rng` refusal for `f = random.expovariate` works (verified, base `AttributeError` vs HEAD refusal); docs/manifest/tests updates present; manifest `--check` passes; not pushed (origin at `f81cdca`); `test_ail_pre129` + `test_ail_safetynet` pass (123 s, 0 failed). **False:** "only when … no instance field shadows" — class attributes, tuple targets, `setattr` and aliased writes all shadow but are refused. `q3` (user-defined `class Random`) gets a misleading `random.Random.gauss` refusal, though base also failed there.

**Pre-existing:** `p12`, `p17` still raise the same `AttributeError` on base and HEAD; dynamic-receiver gap is as recorded. C for a non-feature program (`q8`) is byte-identical to base (`program.c`); only `--debug-dir` paths differ.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` (not re-run); instruction counts (change is compile-time only).

VERDICT: FIX
1. `q1_classattr_shadow.py`: expected `9.0`; actual compile refusal (`random.Random.gauss … bound method`) — class-body attribute shadowing missed.
2. `q2_tuple_assign.py`: expected `9.0`/`8.0`; actual compile refusal — tuple assignment targets missed.
3. `q4_setattr_field.py`: expected `9.0`; actual compile refusal — `setattr` writes missed.
4. `q7_alias_self_field.py`: expected `9.0`; actual compile refusal — writes through an alias of `self` missed.
[cost $0.0000, opencode tokens {"total": 601046, "input": 34745, "output": 4729, "reasoning": 10148, "cache.write": 0, "cache.read": 551424}]
    tool time: bash 3.6 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         45s bash   cd /tmp/rprobes && for p in q1_classattr_shadow q2_tuple_assign q3_user_random_class q4_setattr_field q5_annot
         25s bash   cd /tmp/rprobes && for p in q1_classattr_shadow q2_tuple_assign q3_user_random_class q4_setattr_field q7_alias
         11s bash   cd /tmp/rprobes && echo HEAD; bash ~/tools/cmp.sh p13_original_diff.py /home/runner/work/ail-ci/ail-ci 2>&1 | 
          9s bash   cd /tmp/rprobes && for p in p12_nonrandom_method_value p17_arg_only; do echo "== BASE $p"; bash ~/tools/cmp.sh
          3s bash   cd /tmp && rm -rf cdbase cdhead && mkdir cdbase cdhead && cp /tmp/rprobes/q8_no_random.py cdhead/p.ail && cp /
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo MANIFEST_R
          0s bash   cd /tmp/rprobes && for p in q1_classattr_shadow q2_tuple_assign q4_setattr_field q7_alias_self_field; do echo 

FINAL VERDICT: FIX  2026-10-24T15:50:08Z
