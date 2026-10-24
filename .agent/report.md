# job job-pre127-10242351  started 2026-10-24T15:01:19Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":560,"duration_api_ms":441,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":479,"duration_api_ms":360,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing item from the pre96 list: **r6** (class name shadowed by a parameter/local). At `AIL_CURRENT/python/pkg-v12/pyboxed2.py:4341`, a class name is now treated as a class value only when the activation has no parameter/local/cell/closure binding for it.

Commit: `3d59aa8` on `job-pre127-10242351` (not pushed).

**Probes** (`cmp.sh`, both g/d builds):
- Match CPython: `r6`, `r6_classattr`, `r6_annot`, `r6_nested`, `r6_sources` (argument, list item, attribute, dict value), `r6_local_inst`, `r6_cell_inst`, `r6_nonlocal_inst`, `r6_unbound`, `r6_unshadowed`.
- Still differ as recorded, unchanged: `r7` (`cls.__name__`), `r8` (`K.upper`), `r9` (`[U][0].m`). Class reassignment followed by `.m` also hits the pre-existing r9 class-object receiver, not r6.

**Tests on final commit:** `test_ail_pre127`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **4/4 passed, 0 failed (264 s)**. `update_manifest.py --check` exit 0. Speed not probed.
[cost $0.0000, opencode tokens {"total": 4169623, "input": 132938, "output": 10506, "reasoning": 15555, "cache.write": 0, "cache.read": 4010624}]
    tool time: bash 6.9 min
        266s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         44s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r6 r6_classattr r6_annot r6_nested r6_sources r6_local_inst r6_
         34s bash   mkdir -p /tmp/probes && cat > /tmp/probes/r6.py <<'EOF' class U:     def m(self):         return 42   def f(U)
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p
         13s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         10s bash   mkdir -p /tmp/probes && cat > /tmp/probes/r7.py <<'EOF' class U:     @classmethod     def name(cls):         r
         10s bash   cat > /tmp/probes/r7b.py <<'EOF' class U:     @classmethod     def name(cls):         return cls.__name__ prin
         10s bash   cat > /tmp/probes/r6_local_inst.py <<'EOF' class U:     m = 1   class V:     def m(self):         return 2   d

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** In `expr_Name` (`AIL_CURRENT/python/pkg-v12/pyboxed2.py:4341`), a module-level class name is emitted as the class value only if the current `Ctx` has no `slot_of`/`ptr_names`/`clo_index`/`free_names`/`cell_slots` binding for that name. Otherwise the name falls through to the normal local/cell path. Plus one new test module, manifest, DEVLOG, DIFFERENCES. No benchmark/runtime change.

**Claims checked**
- r6 fixed (parameter, method parameter, nested, lambda, instance via arg/list/dict/attribute): **verified** – p1/p9/p12/p15 match CPython on g and d.
- Local/cell/closure coverage: **verified** – p2 (unbound local) and p3 (cell/nonlocal) match.
- r7/r8/r9 unchanged: **verified** – p22/p23/p24 identical to `/tmp/base` (all still differ from CPython).
- No emitted-C change for non-shadowing programs: **verified** – `p10` `program.c` byte-identical HEAD vs base.
- `test_ail_pre127`, `test_ail_safetynet`: **verified** – 2/2 passed on HEAD, 103 s; `update_manifest.py --check` exit 0.
- `test_ail_files`/`test_ail_corpus_findings3` 4/4: **unverified** (outside reviewer scope).
- Speed: not probed; emitted C unchanged for non-shadowing code.

**Defects (caused by this change; base passed these under `cmp.sh`)**

1. A self-referential local assignment still takes the class branch on the RHS, then the new local path makes the invalid program silently succeed.
```
class U:
    m = 3
    def value(self):
        return 4
def f():
    U = U()
    return U.m, U.value()
print(f())
```
Expected: `UnboundLocalError` (no stdout, exit 1). Actual HEAD (g and d): prints `(3, 4)`, exit 0. Base: no stdout, exit 1. Same with `U: object = U()` (prints `(1, 2)`, exit 0) and `U, x = U(), 5` (prints `(1, 2, 5)`, exit 0): `slot_of` is populated only after the RHS is compiled, so the RHS still sees the class.

2. A class name shadowed by a loop target is read as the local but still called as the class constructor.
```
class U:
    m = 8
    def value(self):
        return 9
def f(items):
    total = 0
    for U in items:
        total = total + U.m
    return total, U().value()
print(f([U(), U()]))
```
Expected: `TypeError` after the loop (`U` is an instance), no stdout, exit 1. Actual HEAD: prints `(16, 9)`, exit 0. Base: no stdout, exit 1. Root: the constructor-call path still ignores the shadowing local; the new local read exposes it.

**Pre-existing (identical on base, not blocking)**
- p4: comprehension/loop name shadowing, then `[x.m for x in [U()]]` – both builds AttributeError.
- p5: `global U` then `U.m`/`U().value()` – both builds AttributeError.
- p14/p17: class value arriving via parameter/list/dict/attribute then `.m` – both builds AttributeError.
- p25: class constructor called through a shadowed parameter (`f(A)` returns 105, both builds; CPython 5).
- r7/r8/r9 (p22–p24) remain as documented.

**Unverified:** wider suite, `test_ail_files`, `test_ail_corpus_findings3`, speed/instruction counts.

VERDICT: FIX
1. Probe `p13` (`U = U()` inside a function, also annotated and tuple-target forms): expected `UnboundLocalError`/exit 1, actual `(3, 4)`/exit 0 on both builds; allocate/scan locals before compiling the RHS, or refuse the construct by name.
2. Probe `p16` (loop target shadows class, then `U()` after the loop): expected `TypeError`/exit 1, actual `(16, 9)`/exit 0; the constructor-call path must honor the same shadowing binding.
[cost $0.0000, opencode tokens {"total": 740257, "input": 42255, "output": 5396, "reasoning": 15358, "cache.write": 0, "cache.read": 677248}]
    tool time: bash 4.4 min
        105s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         36s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; bash ~/tool
         22s bash   cd /tmp/base && for n in p13_rhs p14_class_value_arg p16_afterloop p17_class_sources p18_construct p19_isinsta
         22s bash   cd /tmp/rprobes cat > p17_class_sources.py <<'EOF' class A:     m = 5     def __init__(self, v=0):         sel
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for n in p11_default p12_lambda p13_rhs p14_class_value_arg p15_attrvalu
         20s bash   cd /tmp/rprobes cat > p22_r7.py <<'EOF' class U:     @classmethod     def name(cls):         return cls.__name
         16s bash   cd /tmp/rprobes cat > p20_annot_assign.py <<'EOF' class U:     m = 1     def value(self):         return 2  de
         10s bash   cd /tmp/base && for n in p4_comp_loop p5_global p6_assign_inst; do echo "===== $n BASE"; bash ~/tools/cmp.sh /

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `_call_name` (`AIL_CURRENT/pkg-v12/pyboxed2.py:6258`): a shadowing local/cell/closure binding now wins before the class-constructor path, matching `expr_Name`.

Commit: `4c11a24` (`pre127: a shadowing binding wins at a call site too`).

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds):
- `r1`, `r1b`, `r1c`: self-referential `U = U()` plain/annotated/tuple -> `UnboundLocalError`, exit 1: match.
- `r2`: loop-target `U`, then `U()` -> no stdout, exit 1: match stdout/exit (runtime TypeError text names `instance`, not `U`).
- `c01`, `c03`, `c05`, `c07`, `c13`, `c14`: unshadowed constructor, `global U`, class passed as parameter, class from attribute/list/dict -> match.
- `c04`, `c06`, `c08`, `c10`, `c11`, `c12`: instance via parameter/local/cell call, empty loop, use before assignment, alias self -> match.
- `c09`: nonlocal instance call refused by name on both builds (`not in the subset: the method .U() ...`).
- Existing `r6_*`: 10/13 match; `r6_local`/`r6_cell`/`r6_nonlocal` differ identically on base (pre-existing class-alias attribute case).
- `r7`/`r7b`/`r7d`/`r8`/`r9` still differ as documented; `r7c` matches.
- `c02` module-level `U = U()` differs identically on base (pre-existing, unchanged).

**Tests:** `test_ail_pre127`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` -> 4/4 passed on `4c11a24` in 204 s. `update_manifest.py --check` exits 0. Non-shadowing `c01` generated `program.c` is byte-identical to base.
[cost $0.0000, opencode tokens {"total": 2559479, "input": 73028, "output": 8737, "reasoning": 12050, "cache.write": 0, "cache.read": 2465664}]
    tool time: bash 11.2 min, edit 0.0 min
        207s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
        206s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
        113s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r1.py /tmp/probes/r1b.py /tmp/probes/r1c.py /tmp/pr
         39s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/c*.py; do echo "===== $(basename $p)"; bash ~/tools
         20s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         17s bash   ls /tmp/base >/dev/null 2>&1 && cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/c02_module_selfref.
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r1.py /tmp/probes/r1b.py /tmp/probes/r1c.py /tmp/pr
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r1.py /tmp/probes/r1b.py /tmp/probes/r1c.py /tmp/pr

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Reviewed** `4c11a24` + `3d59aa8` (diff `work..HEAD`).

**What the change really does:** `expr_Name` and `_call_name` no longer take the module-class path when the name has a local/param/cell/free binding, so a shadowing binding is read and called like CPython. Matches the report.

**Report checks**
- r6 fixed; local/cell/closure coverage fixed for params, self-ref local (plain/annotated/tuple), loop target, cell/free, list/attr/dict sources — verified (`r6`, `r1*`, `r2`, `r6_annot/cell_inst/local_inst/nested/nonlocal_inst/sources/unbound/classattr`, plus my `p1`–`p5`, `p8`, `p10`, `p12`, `p15`, `p20`–`p27`). `r6_local/cell/nonlocal` still differ but byte-identically on base (class-value attribute limitation) — pre-existing.
- r7/r7b/r7d/r8/r9 still differ (identical on base); r7c matches — verified.
- Non-shadowing C unchanged: `program.c` byte-identical to base for `c01_normal` and `p10_nonshadow`, both general and default builds (`--debug-dir`). Verified.
- `test_ail_pre127` + `test_ail_safetynet`: 2/2 ok, 101 s, rc 0. `update_manifest.py --check` rc 0. `test_ail_files`/`test_ail_corpus_findings3`: not re-run (outside reviewer scope).
- Speed: compiler-only change, no runtime or accepted-C change; instruction counts not probed (not applicable). Verified by identical `program.c`.

**Probes (`bash ~/tools/cmp.sh`, both builds)**
- Match: `p1_lambda`, `p2_comp`, `p3_except`, `p4_default`, `p5_loop`, `p8_with`, `p10_mutate` (mutation during iteration), `p27_typed` (int/float/bool/negative/empty args).
- `p7_kwargs` (shadowed class, keyword ctor args): named compile-time refusal (`keyword arguments in a call through a function value`); base matched only because it ignored the binding. Refusal acceptable per rules.
- `p6_callable` (shadowed name holding `__call__` instance): runtime `TypeError`; `__call__` on instances is unsupported everywhere (`p11_callable_plain` fails identically on base/HEAD), so pre-existing limitation, not a new defect.
- `p26_nesteddef` (nested `def U` called as `U()`): still class path, identical on base — pre-existing call-path gap; the value-read half is improved.

**Pre-existing (identical or same root cause on base, not blocking)**
- `r6_local/cell/nonlocal`, `p14_class_value_arg`, `p17_class_sources`: attribute read on a class value.
- `p9_global` / `p5_global`: `global` rebind of a class name.
- `c02_module_selfref`: module-level `U = U()`.
- `p26` nested-def constructor call; `p6`/`p11` instance `__call__` (AIL refuses/errors generally).

`DEVLOG` top entry dated 2026-10-24, DIFFERENCES id uses the branch placeholder, commits carry the co-author line, only compiler/tests/docs changed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1631166, "input": 67525, "output": 8485, "reasoning": 24148, "cache.write": 0, "cache.read": 1531008}]
    tool time: bash 8.1 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         75s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_method p2_local_unbound p3_cell p4_comp_loop p5_global p6_as
         60s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r1 r1b r1c r2 c01_normal c02_module_selfref c03_global_decl c04
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_lambda p2_comp p3_except p4_default p5_loop p6_callable p7_k
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r6 r6_local r6_cell r6_nonlocal r6_sources r6_unbound r6_classa
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r6_annot r6_cell_inst r6_local_inst r6_nested r6_nonlocal_inst 
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r6_local r6_cell r6_nonlocal c02_module_selfref; do src=/tmp/pr
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r6 r6_local r6_cell r6_nonlocal r7 r8 r9; do echo "##### BASE $

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T16:42:10Z
