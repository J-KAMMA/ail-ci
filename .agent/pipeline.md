# job job-pre300-10270742  started 2026-10-26T22:46:40Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":415,"duration_api_ms":284,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":393,"duration_api_ms":268,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed on `job-pre300-10270742` as `30749de`.

**Fix:** Reproduced the first pre284 difference exactly (`d1/e1` printed 12 vs 7; `d2/d4/d5` printed `2**59` vs 0/AttributeError). `pyboxed2` now resolves earlier class-body assignments through the class namespace before a module class, including lazy class-attribute fills. Method defaults requiring class scope are refused by name.

**Probes** (`/tmp/probes/pre300`, both general and default builds):
- Match CPython: `d1_alias_val`, `d2_alias_bignum`, `d4_alias_missing`, `d5_alias_dynamic`, `e1_alias_val2`, `class_plain_value`, `class_nonclass`, `module_alias`, `module_alias_missing`, `p_duplicate`, `p_selfref`, `p_routes`, `p_plain_shadow`, `p_comprehension`, `p_argument`, `p_types`, `p_attr_route_container`, `p_order`.
- Refused by name: `p_default` (`a method default that reads the class-body local ...`).

**Tests on final commit:** 6 modules (`test_ail_pre300`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre170`, `test_ail_pre255`) — 226 s, 0 failed. Earlier related runs (12 more modules, including default/class/hoisting tests) — 0 failed. Manifest `--check` passes. DEVLOG and DIFFERENCES (`C?-job-pre300-10270742-1`) updated.

**Not verified:** full suite and gdev instruction counts (not run by design).
[cost $0.0869, opencode tokens {"total": 9270518, "input": 235319, "output": 17847, "reasoning": 23176, "cache.write": 0, "cache.read": 8994176}]
    tool time: bash 16.8 min
        290s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_fuzz47 test_ail_pre141 test_ail_pre89 test_
        228s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_pre300 test_ail_safetynet test_ail_files te
        168s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 test_ail_pr
        103s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_pre300 test_ail_safetynet 2>&1 | tail -30
         37s bash   cd /tmp/probes/pre300 && for f in d1_alias_val.py d2_alias_bignum.py d4_alias_missing.py d5_alias_dynamic.py e
         35s bash   cd /tmp/probes/pre300 && for f in d1_alias_val.py d2_alias_bignum.py d4_alias_missing.py d5_alias_dynamic.py e
         34s bash   cd /tmp/probes/pre300 && for f in d1_alias_val.py d2_alias_bignum.py d4_alias_missing.py d5_alias_dynamic.py e
         34s bash   cd /tmp/probes/pre300 && cat > p_duplicate.py <<'EOF' class E:     x = 5  class C:     x = 7  class D:     x =

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** `pyboxed2` records a class body's earlier attribute assignments in `ctx.class_attr_shadow` and resolves later `LOAD_NAME`s (and lazy class-attr fills) through those slots; it refuses method defaults that read such a local. That matches the report.

**Verified**
- Go: base `r01` prints `12`, HEAD prints `7`; base `r02` prints `2**59`, HEAD raises the CPython `AttributeError` (exit 1). The first pre-284 difference is fixed.
- Both builds: plain values, reassignment, `K = K`, argument/list/dict/attribute routes, `A().x`, a comprehension body (module scope), and the lazy array-entry fill (`8`) match CPython or are refused by name.
- Method default reading a class local is refused by name on both builds; the refusal is new (base printed `12`).
- Non-feature generated C is unchanged: `g00_000`, `g01_008`, `g01_014`, and a normal class program are byte-identical base vs HEAD. No icount run needed.
- Tests on HEAD: `test_ail_pre300 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 4 modules, 0 failed, 220 s. Manifest `--check` passes. Commit message/DEVLOG/DIFFERENCES are consistent.

**Pre-existing (base identical, not blocking)**
- Comprehension outermost iterable stays module-scope: `[i for i in A.xs]` after a class-local `A = C` raises `AttributeError` on both builds (r09).
- Class-local class used as a constructor still reads the module class (r14).
- Lambda defaults/immediate lambdas still hit `RecursionError` on both (r15/r16).
- Property/staticmethod/classmethod through a *module alias* of a class already fail at run time on base (r32/r33/r34).

**Defects introduced by this change:** a class body that shadows a module class with an earlier assignment now resolves the class-local class, but then bypasses the existing class-value method/property refusal and fails at run time instead of matching CPython or being refused by name.

`VERDICT: FIX`
1. Property read through a shadowed class value. Probe `/tmp/rprobes/r38_property_shadow.py` (`class C: ... @property def p ...; class B: A = C; y = A.p`): CPython prints `property`; base refuses by name (`name 'A' is not defined`); HEAD exits 1 with `NotImplementedError: reading method/property 'p' through the class value C is not built on the general path` and empty stdout.
2. Static/class method call through a shadowed class value. Probe `/tmp/rprobes/r31_static_shadow.py` (`class C: @staticmethod def get(): return 42; class B: A = C; y = A.get()`): CPython prints `42`; base refuses by name; HEAD exits 1 with `TypeError: get() takes more arguments`.
[cost $0.0432, opencode tokens {"total": 2429012, "input": 76121, "output": 10813, "reasoning": 30526, "cache.write": 0, "cache.read": 2311552}]
    tool time: bash 8.8 min
        221s bash   date; cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_pre300 test_ail_safetynet test_ail_fi
         67s bash   cd /tmp/rprobes; for s in g01_008 g01_014; do cp ~/corpus/gdev/$s.py $s.ail; rm -rf dgH$s dgB$s dgH$s.exe dgB$
         38s bash   date; cd /tmp/rprobes; for f in r*.py; do echo "=== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail
         27s bash   cd /tmp/rprobes cat > r21_array_entry.py <<'EOF' class C:     x = 7     y = x + 1 class B:     A = C     z = A
         20s bash   cd /tmp/rprobes; cat > r30_method_shadow.py <<'EOF' class C:     x = 7     def m(self):         return self.x 
         18s bash   cd /tmp/rprobes; for f in r07_lambda_body.py r08_lambda_default.py r12_default_method.py; do echo "=== $f HEAD
         15s bash   cd /tmp/rprobes cat > r15_lambda_immediate.py <<'EOF' class A:     x = 12 class C:     x = 7 class B:     A = 
         14s bash   cd /tmp/rprobes; cat > r28_prop_shadow.py <<'EOF' class C:     x = 7     @property     def p(self):         re

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed `d3d7cd2`.

**Fix:** class-body locals that statically hold a class now use the direct class-value path: static/class/instance method calls match CPython; method/property reads are refused at compile time by name. Class identity is proven through aliases, reassignment, list/dict items, class/instance attributes, constant `if`, and single-return wrapper calls.

**Probes** (`/tmp/probes/pre300b`, both builds):
- Refused by name: `prop_direct`, `prop_alias_chain`, `prop_reassign`, `prop_list_literal`, `prop_list_var`, `prop_dict_literal`, `prop_dict_var`, `prop_attr`, `prop_argument`, `prop_ifexp`, `method_value_direct`, `method_value_list_var`
- Match CPython: `classattr_direct`, `classmethod_direct`, `classmethod_list_var`, `instance_method_direct`, `instance_method_list_var`, `prop_instance_attr`, `prop_instance_list`, `prop_instance_var`, `static_argument`, `static_attr`, `static_dict_var`, `static_direct`, `static_list_var`
- Lazy array-entry fill: `8` on both.
- Review probes: r28/r38 refused by name; r29/r31/r37/r01 match; r09 remains pre-existing (`AttributeError`, base identical).

**Tests on final commit:** `test_ail_pre300 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 4 modules, 0 failed, 223 s. `update_manifest.py --check` passes.
[cost $0.0738, opencode tokens {"total": 6761968, "input": 132407, "output": 21679, "reasoning": 35338, "cache.write": 0, "cache.read": 6572544}]
    tool time: bash 11.2 min
        225s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_pre300 test_ail_safetynet 
         72s bash   cd /tmp/probes/pre300b && for f in *.py; do [ "$f" = lazy_array_entry.py ] && continue; out=$(bash ~/tools/cmp
         61s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_pre300 2>&1 | tail -30
         59s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_pre300 2>&1 | tail -40
         54s bash   cd /tmp/probes/pre300b && for f in *.py; do [ "$f" = lazy_array_entry.py ] && continue; out=$(bash ~/tools/cmp
         38s bash   cd /tmp/probes/pre300b && for f in *.py; do [ "$f" = lazy_array_entry.py ] && continue; out=$(bash ~/tools/cmp
         31s bash   cd /tmp/rprobes && for f in r09_comp_iterable.py r10_comp_body.py r01_orig.py r03_plain.py r06_later.py r11_re
         30s bash   cd /tmp/rprobes && for f in r01_orig.py r03_plain.py r06_later.py r11_reassign.py r14_instance.py r20_normal_c

## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed HEAD `d3d7cd2` against base `work` (`81d779d`). No source edits made.

**What the change really does:** keeps a class-body namespace shadow while evaluating class attributes, and adds a static class-identity prover (module bindings, aliases, list/dict items, instance/class attrs, wrapper calls) so reads/calls through a class-local class value use the direct class-value path; method defaults needing the class scope are refused by name. The prover is broader than the report implies and is unsound when the proven value is mutated through a call.

**Claims**
- Commit/fix committed: verified.
- Primary shadow fixed: verified. `p01` HEAD 7 vs base 12; `p02` HEAD AttributeError vs base `2**59`; `p17` plain list HEAD `[10, 20]` vs base `[99]`.
- Method calls through a class-local class / property-method reads refused: verified by passing `test_ail_pre300` (its MATCH/REFUSED cases cover these).
- "Class identity is proven through list/dict items, class/instance attributes": **false as a correctness claim** (defects below).
- Lazy array-entry fill `8`; worker probe list; r-probes: unverified (not re-run).
- Tests: `test_ail_pre300` + `test_ail_safetynet` on HEAD, 0 failed, 100 s. `test_ail_files` / `test_ail_corpus_findings3` not run (review instructions). Worker's 4-module run unverified.
- `update_manifest.py --check`: verified.
- Non-feature C: a class program's `--debug-dir program.c` is byte-identical to base; no speed work needed.

**Pre-existing (identical on base, non-blocking)**
- `p04` comprehension iterable over a class-local list: both builds TypeError vs CPython `[10, 20]`.
- `p05` comprehension iterable over a module global shadowed in the class: both print `[99]` vs `[10, 20]`.
- `p03` `B.f()` where `f` is a lambda class attr: both builds refuse by name (CPython 12).
- `p08` conditional instance attribute: both refuse or match; no new difference.

**Defects**
1. A list/dict item is presumed to hold a class even when a called function mutates it. `p07_list_mutated_in_func.py`:
```python
class C: x = 7
class D: x = 9
def poison(xs): xs[0] = D
lst = [C]; poison(lst)
class B:
    A = lst[0]
    y = A.x
print(B.y)
```
CPython prints `9`; HEAD prints `7` (both builds); base refuses by name (`name 'A' is not defined`). Same with a dict (`p16`: HEAD `7`, CPython `9`, base refusal).
2. An instance attribute is presumed to hold the class assigned in `__init__`, ignoring a later external overwrite. `p09_attr_overwritten.py`:
```python
class C: x = 7
class D: x = 9
class Holder:
    def __init__(self): self.c = C
h = Holder(); h.c = D
class B:
    A = h.c
    y = A.x
print(B.y)
```
CPython prints `9`; HEAD prints `7` (both builds); base refuses by name.

The static proof must treat a value that can be mutated through a call/alias as unknown (fall back to the previous named refusal) before this can be accepted.

VERDICT: FIX
[cost $0.0227, opencode tokens {"total": 957490, "input": 56301, "output": 4394, "reasoning": 14875, "cache.write": 0, "cache.read": 881920}]
    tool time: bash 3.3 min
        102s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre300 tes
         37s bash   cd /tmp/rprobes2 && for f in p*.py; do echo "=== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-ci
         27s bash   cd /tmp/rprobes2 && for f in p03_lambda.py p04_comp_iter_classlist.py p05_comp_iter_nonclass.py p07_list_mutat
         20s bash   cd /tmp/rprobes2 && cat > p15_classattr_overwrite.py <<'EOF' class C:     x = 7 class D:     x = 9 class Holde
          7s bash   cd /tmp/rprobes2 && cat > p17_plain_shadow.py <<'EOF' items = [99] class B:     items = [10, 20]     y = items
          4s bash   cd /tmp && mkdir -p benignh benignb && cp /tmp/rprobes2/p01_direct.py /tmp/benign.py && cat > /tmp/benign.py <
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo rc=$?; head -12 DEVLOG.md
          0s bash   date; git log --oneline work..HEAD; echo ---; git diff --stat work..HEAD; echo ---; ls

FINAL VERDICT: FIX  2026-10-26T23:54:15Z
