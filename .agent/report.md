# job job-pre260-10261651  started 2026-10-26T07:52:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":372,"duration_api_ms":248,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":374,"duration_api_ms":247,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `e9a1536` (`job pre260: call Callable values stored in instance fields`).

- General path now calls Callable values stored in class/instance fields; field-name lookup is scoped through the receiver’s class chain.
- Added `test_ail_pre260.py` with direct, aliased, argument, list/dict, inherited, error, and type/width cases.
- Updated `ail_check.py`, DEVLOG, DIFFERENCES, and MANIFEST.
- Passed `test_ail_pre260`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (4 modules, 0 failed); manifest check clean.

Left untracked: `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 6957116, "input": 291689, "output": 17424, "reasoning": 24003, "cache.write": 0, "cache.read": 6624000}]
    tool time: bash 19.3 min
        332s bash   git add AIL_CURRENT/test_ail_pre260.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py
        332s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_quirks 2>&1 | tail -60
        258s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd AIL_CURRENT && python3 ../t
         85s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ffi test_ail_ir_s2 2>&1 | tail -80
         51s bash   for p in p01_void p02_list_callable p03_dict_callable p04_nested_closure p05_class_field p06_class_attr p07_fi
         28s bash   for p in p01_void p02_list_callable p03_dict_callable p04_nested_closure p05_class_field p06_class_attr; do ec
         27s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s=p.read_text() old
          9s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s = p.read_text()

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does (one line):** Adds `callable_fields` discovery (class-level `Callable[...]` annotations without value + `self.<attr>: Callable[...]` annotations in methods) and, at the end of `_call_attribute`, calls such a field through `call_value` instead of refusing. Matches the report/DEVLOG claim.

**Probes (`/tmp/rprobes`, HEAD; base `/tmp/base`):**
- Match CPython, both builds: p01 (direct/instance), p04 (inherited/overridden), p06 (alias+reassign), p07 (annotation in dead branch), p09 (string annotation), p14 (class as value), p17 (`o.inner.f`), p18 (`None` field), p23 (lambda), p24 (returned closure), p25 (bare `Callable`), p27 (2 args, int64 max), p28 (list/bytearray mutation), p30 (int64 min/bool), p32 (`len`/`abs`), p35 (chained result), p36 (receiver from list/dict), p37 (loop/comprehension), p38 (lambda capturing self), p39 (field→field), p41/p42 (untyped/typed receiver), p43 (repr pre-existing).
- Named refusals (acceptable): p03 (`upper` field), p15 (`Other.add` via class), p16 (kwargs), p21, p33 (defaults), p34 (dataclass general path).
- C unchanged: p26, p40 `program.c` byte-identical base vs HEAD in both builds (only `native_report.json` temp paths differ).

**Defects (new: base refused by name, HEAD compiles then fails):**
1. Bound method stored in a `Callable` field. p22 (`self.f = self.add; c.f(1)`) and p13 (`self.f = o.add`): expected `101 102` / `11 12`+`13`, actual exit 1, empty stdout, `AttributeError: 'C' object has no attribute 'add'` / `'Other' object has no attribute 'add'` (both builds). Base: compile refusal `the method .f() ...`.
2. `__call__` instance stored in a `Callable` field. p29 (`self.f = Adder(10); c.f(1)`): expected `11`, actual exit 1, `TypeError: 'instance' object is not callable` (both builds). Base: compile refusal.

**Pre-existing (identical on base):** p02 field/method name collision (`101 102`); p05/p43 printed function `<object>` vs `<function ...>`; p31/p20 bound-method/`__call__` value via local/argument crash on both; p03 named refusal; p15/p16/p21/p33/p34 named refusals.

**Claims:** plain-function feature, scoping, test file contents, ail_check/DEVLOG/DIFFERENCES/MANIFEST edits, "default build matched CPython" (p01 base default), untracked `.agent/pipeline.md` — verified. `test_ail_pre260` + `test_ail_safetynet` pass on HEAD (0 failed); `update_manifest.py --check` clean. `test_ail_files`/`test_ail_corpus_findings3` claim not rerun (out of reviewer scope) — unverified. Speed: runtime C identical for non-feature programs, so no icount needed.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; typed-only build.

VERDICT: FIX

1. Bound-method values in a `Callable` field now compile and crash instead of being refused.
   ```
   class C:
       f: Callable[[int], int]
       def __init__(self): self.k = 100; self.f = self.add
       def add(self, x: int) -> int: return self.k + x
       def run(self, x: int) -> int: return self.f(x)
   print(C().f(1), C().run(2))
   ```
   Expected `101 102`; actual exit 1, `AttributeError: 'C' object has no attribute 'add'`.
2. `__call__` instances in a `Callable` field now compile and crash instead of being refused.
   ```
   class Adder:
       def __init__(self, k): self.k = k
       def __call__(self, x: int) -> int: return self.k + x
   class C:
       f: Callable[[int], int]
       def __init__(self): self.f = Adder(10)
   print(C().f(1))
   ```
   Expected `11`; actual exit 1, `TypeError: 'instance' object is not callable`.
[cost $0.0000, opencode tokens {"total": 1283874, "input": 54127, "output": 10488, "reasoning": 20923, "cache.write": 0, "cache.read": 1198336}]
    tool time: bash 7.5 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         47s bash   date; cd /tmp/rprobes && for p in p01_repro p02_method_collision p03_builtin_collision p04_inherit p05_errors 
         29s bash   cd /tmp/rprobes && cat > p12_builtin_values.py <<'EOF' from typing import Callable  class C:     f: Callable[[
         28s bash   date; cd /tmp/rprobes && cat > p27_twoarg.py <<'EOF' from typing import Callable  def add(a: int, b: int) -> i
         27s bash   cd /tmp/rprobes && cat > p24_closure.py <<'EOF' from typing import Callable  def make(k: int) -> Callable[[int
         25s bash   cd /tmp/rprobes && cat > p21_static.py <<'EOF' from typing import Callable  class C:     f: Callable[[int], in
         24s bash   cd /tmp/rprobes && cat > p32_builtins.py <<'EOF' from typing import Callable  class C:     f: Callable[[list[i
         19s bash   cd /tmp/rprobes && cat > p38_self_lambda.py <<'EOF' from typing import Callable  class C:     f: Callable[[int

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both defects on branch `job-pre260-10261651` (commit `e93d138`).

- Bound-method values now bind the receiver (`self.f = self.add`, `o.add`), including inherited/overridden methods and instance-field shadowing.
- `__call__` instances are dispatched when called through a function value.
- Method values with defaults, `*args`, `**kwargs` or `yield` remain named compile refusals.

Probes `/tmp/probes/q01`–`q08` match CPython on both builds, covering 0/1/2 args, int64 edges, empty/negative values, aliasing, inheritance, argument/list/item/attribute/dict routes. `q09`/`q10` are refused by name on both builds. All 43 reviewer probes: p13/p22/p29 fixed; p20/p31 also now match; only the documented pre-existing p02/p05/p43 diffs remain.

Required tests on the final commit: `test_ail_pre260`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 5144751, "input": 116325, "output": 14007, "reasoning": 21907, "cache.write": 0, "cache.read": 4992512}]
    tool time: bash 13.5 min, edit 0.0 min
        268s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 3000 python3 ../tools/par_check.py -j 2 test
        218s bash   cd /tmp/rprobes && rm -f /tmp/head_probes.txt && for p in p*.py; do echo "=== $p" >> /tmp/head_probes.txt; bas
        129s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         54s bash   cd /tmp/probes && for p in q0*.py q10*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci
         43s bash   cd /tmp/rprobes && for p in p13_bound_method p22_self_callback p29_callable_instance p20_bound_arg p31_callabl
         39s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         22s bash   cd /tmp/rprobes && for p in p13_bound_method p22_self_callback p29_callable_instance p20_bound_arg p31_callabl
          8s bash   cd /tmp/probes && for p in q09_bound_default_refused.py q10_bound_vararg_refused.py; do echo ===$p; bash ~/too

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review: job `pre260-10261651` (HEAD `e93d138`)

**What the change really does:** adds (a) `Callable[...]` field tracking plus a `_call_attribute` fallback that calls such fields through `call_value`, (b) bound-method FUNC values for `obj.method` reads, and (c) `__call__` dispatch for instances called through a function value. This matches the report except that the refusal is program-wide and the receiver is re-evaluated.

**Probes** (`/tmp/rprobes2`, base `/tmp/base`):
- New: r01/r01b/r01c/r01d (unrelated attr name collision), r02/r11 (2/3-arg bound methods, field/list/dict), r04/r05/r08/r13 (default/`*args`/shadowed/inherited `__call__`), r09/r14 (receiver mutation, field shadowing), r15 (no feature), r17/r18 (receiver side effects), r19/r20 (map), r21 (mixed FUNC/instances), r22–r26 (class-attribute shadowing).
- Reused: p13/p20/p22/p29/p31 now match; q01–q08 match; q09/q10 refused by name; p02/p43 unchanged on base.
- r15 `program.c` byte-identical base vs HEAD in both builds (only temp paths in `native_report.json` differ).
- Tests run on HEAD: `test_ail_pre260 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 4/4 ok, 0 failed. `update_manifest.py --check` clean.

**Claims:** bound methods (verified, incl. inherited and field shadowing), `__call__` dispatch (verified), defaults/`*args` refusals (verified for q09/q10, but over-broad — defect 1), q01–q08 (verified), p13/p22/p29 fixed and p20/p31 fixed (verified), p02/p43 pre-existing (verified), p05 still differs only in function repr (base differed more), tests/manifest (verified). Report omits the two regressions below.

**Pre-existing:** p02 method/field collision; p43 (and p05) function `<repr>`; r23/r25 class-attribute shadowing produce the same output as base.

**Unverified:** full quirks module, other original target modules, typed-only build, instruction counts (gdev has no `__call__`; non-feature C is identical).

VERDICT: FIX

1. **Any unsupported method signature now refuses unrelated attribute reads (both builds).** `expr_Attribute` calls `_method_value_owners` for every read and `_method_value` raises for any class defining that name with defaults/`*args`/`yield`, whatever the receiver is. Probe `r10`: class `A` with `self.f = 5` in `__init__` and `def f(self, x: int = 1)`; `print(A().f)` → CPython and base print `5`, HEAD refuses: `the method .f() as a value (it has defaults, *args, **kwargs or yield)`. Probe `r01b` (unrelated class `A`, field `f` on `B`) gives `5` on base, same refusal on HEAD. `r26` (subclass overrides a default-arg base method) also refuses although CPython calls the override.

2. **Callable-field calls evaluate the receiver twice (general build).** `_call_attribute` emits `self.expr(recv)` before the new field branch, then `self.expr(field)` evaluates `recv` again. Probe `r18`: `hs = [H(inc)]; print(hs.pop().f(1), len(hs))` → CPython/default build `2 0`; HEAD general exits 1 with `IndexError: pop from empty list`. Probe `r17` (`print(make().f(1))`, `make` prints `make`) → CPython/default prints `make` once, HEAD general prints it twice.

3. **New bound-method/`__call__` arity errors still differ from CPython.** Probe `r12`: `f = P(1).add; f(1)` / `f(1, 2, 3)` → CPython `TypeError P.add() missing 1 required positional argument: 'b'` and `TypeError P.add() takes 3 positional arguments but 4 were given`; HEAD `TypeError add() ...` and `TypeError add() takes 2 ...`. Probe `r06`: CPython `A.__call__() takes 2 positional arguments but 3 were given`, HEAD `__call__() takes other arguments`. (Base also differed here — it crashed with `AttributeError`/`not callable` — so this is a remaining defect of the new feature, not the blocking regression.)
[cost $0.0447, opencode tokens {"total": 3097100, "input": 83542, "output": 11675, "reasoning": 27035, "cache.write": 0, "cache.read": 2974848}]
    tool time: bash 11.2 min
        266s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         55s bash   cd /tmp/probes && for p in q01_bound_self.py q02_bound_routes.py q03_bound_inherit.py q04_bound_types.py q05_b
         48s bash   cd /tmp/rprobes2 && cat > r10_sameclass_shadow_default.py <<'EOF' class A:     def __init__(self) -> None:    
         45s bash   cd /tmp/rprobes2 && date && for p in r*.py; do echo "##### $p"; timeout 300 bash ~/tools/cmp.sh "$p" /home/run
         42s bash   cd /tmp/rprobes && for p in p13_bound_method.py p20_bound_arg.py p22_self_callback.py p29_callable_instance.py
         37s bash   cd /tmp/rprobes && for p in p09_string_annotation.py p01_repro.py p04_inherit.py p27_twoarg.py p02_method_coll
         28s bash   cd /tmp/rprobes2 && for p in r01_unrelated_default.py r03_bound_default.py r06_call_wrongarity.py r04_call_def
         27s bash   cd /tmp/rprobes2 && cat > r01b_unrelated_default_init.py <<'EOF' class A:     def __init__(self) -> None:     

FINAL VERDICT: FIX  2026-10-26T10:18:52Z
