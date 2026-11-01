# job job-lazymod1-11020054  started 2026-11-01T15:59:05Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

- **Defect 1 — earlier rebinding:** `need_name` now hoists every earlier binding of the same name with its dependencies, or refuses by name if that earlier binding acts/raises. `p1_rebind` now prints `(2, 2)` on both builds; `p1_three`, `p1_unpack`, `p1_aug`, `p1_ann`, `p1_def_before` also match CPython; `p1_effectful` is refused by name.
- **Defect 2 — unfoldable subscript:** `move_bad_expr` now treats an unfoldable subscript as potentially raising (annotations excepted). `p3_raise`, `p_direct_subscript`, `p2_subscript_list`, `p2_subscript_arg` are refused by name; `p5_control`, `p2_subscript_safe`, `p2_subscript_annotation` match CPython on both builds.
- Added `computed_rebind` and a two-program subscript-refusal test to `test_ail_lazymod1`.
- Final tests: `test_ail_lazymod1`, `test_ail_modsys`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **5/5 ok, 0 failed**.
- lab/compare: all 10 `.ail` generated C byte-identical to base; `.py` 5 identical + 5 fail identically.
- `update_manifest.py --check` passes. Committed as `eb83d95`.
[cost $0.0000, opencode tokens {"total": 3264884, "input": 94829, "output": 9638, "reasoning": 16865, "cache.write": 0, "cache.read": 3143552}]
    tool time: bash 22.4 min
        425s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_lazymod1 test_ail_
        414s bash   cd /home/runner/work/ail-ci/ail-ci && same=0; diffs=0; fails=0; ok=1; for src in lab/compare/src/*/main.py; do
        320s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_lazymod1 test_ail_
         80s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/base_ail /tmp/labcmp && cp -a AIL_CURRENT /tmp/base_ail && g
         31s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && timeout 900 python3 tools/par_check.
         28s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_lazymod1
         21s bash   mkdir -p /tmp/probes/p1_three /tmp/probes/p1_unpack /tmp/probes/p1_aug /tmp/probes/p1_ann /tmp/probes/p1_effec
         13s bash   mkdir -p /tmp/probes/p1_rebind /tmp/probes/p3_raise /tmp/probes/p_direct_subscript /tmp/probes/p5_control cat 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — lazymod1 (work..eb83d95)

**What the change really does:** `need_name` now also hoists every earlier binding of a needed name (recursively, refusing effectful ones), and `move_bad_expr` refuses a non-annotation subscript it cannot fold. No runtime/C-generator change.

**Tests (HEAD):** `test_ail_lazymod1 test_ail_modsys test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 5/5 ok (317s). `update_manifest.py --check` exit 0.

**Lab/compare C:** all 15 `program.c` (10 `.ail` + 5 compiling `.py`) byte-identical to base; only `native_report.json` temp paths differ. (No lab source has a local import, so `merge_program` is not entered.)

**Defects (the change causes these; base had the earlier `mid 1`/`show 10` right):**

1. The earlier binding is hoisted past an intervening *read*, so the reader sees the later value.
   `p_rebind_print/lib.py`: `print("lib start")` / `SIZE = 1` / `print("mid", SIZE)` / `SIZE = 2` / `def f(a=SIZE): return a`; main calls `lib.f(), lib.SIZE`.
   Expected (CPython and base): `lib start\nmid 1\n(2, 2)`. Actual HEAD (both builds and general path): `lib start\nmid 2\n(2, 2)`.
   Same with a call: `SIZE=10; def show(): print("show",SIZE); show(); SIZE=20; def f(a=SIZE)` → expected `show 10\n(20, 20)`, actual `show 20\n(20, 20)`.
   `p_rebind_cond_read` (`if True: print("mid", SIZE)` between the two bindings): expected `mid 1`, actual `mid 2`.

2. The same omission turns an intervening *mutation* onto the later value.
   `p_rebind_mutate/lib.py`: `SIZE = [1]` / `SIZE.append(2)` / `SIZE = [3]` / `def f(a=len(SIZE))`.
   Expected `(1, [3])`; actual HEAD `(1, [3, 2])` (base was `(1, [1, 2])`, also wrong).
   Cause: only earlier *bindings* are checked with `effectful`; a statement between them that reads or mutates the name stays in `_ail_init_<mod>` and now runs after the hoisted later value. Either refuse when such a statement reads the name, or hoist it with its own dependencies.

**Claims:** verified — `p1_rebind` `(2,2)` both builds; `p3_raise`, `p_sub_call`, `p_sub_attr`, `p_sub_class`, `p_sub_in_dict`, `p_sub_in_list` refused by name; `p_sub_safe`, `p_sub_annot`, `p_sub_negative`, `p_rebind_unpack`, `p_rebind_aug` match. False — the change does not yet keep CPython's order of effects for an earlier rebinding. Unverified — `p1_three`, `p1_ann`, `p1_def_before`, `p1_effectful`, `p_direct_subscript`, `p2_subscript_*`.

**Pre-existing (identical on base):** `p_annot_raise` (AIL skips an annotation subscript that CPython evaluates: exit 0 vs 1); `p_read_before_single`/`p_read_before_rebind` (`print(SIZE)` before any binding: AIL succeeds, CPython NameError).

**Unverified:** gdev instruction counts (C of non-lazy programs unchanged, runtime untouched).

VERDICT: FIX
1. Earlier rebinding hoisted past an intervening read: `/tmp/rprobes/p_rebind_print` expected `lib start\nmid 1\n(2, 2)`, actual `lib start\nmid 2\n(2, 2)`; `/tmp/rprobes/p_rebind_call` expected `show 10\n(20, 20)`, actual `show 20\n(20, 20)`.
2. Earlier rebinding hoisted past an intervening mutation: `/tmp/rprobes/p_rebind_mutate` expected `(1, [3])`, actual `(1, [3, 2])`.
[cost $0.0000, opencode tokens {"total": 1503888, "input": 62090, "output": 7431, "reasoning": 24191, "cache.write": 0, "cache.read": 1410176}]
    tool time: bash 15.0 min
        506s bash   date; cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/lh /tmp/lb; mkdir -p /tmp/lh /tmp/lb; ok=0; bad=0; for d
        319s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         20s bash   date; for p in p_rebind_print p_rebind_mutate p_rebind_call p_sub_safe p_sub_call p_sub_attr p_sub_annot p_sub
         18s bash   date; cd /tmp && rm -rf labh labb && mkdir -p labh labb && cd /home/runner/work/ail-ci/ail-ci && for f in lab/
         15s bash   cd /tmp/rprobes mkdir -p p_read_before_rebind p_read_before_single p_rebind_cond_read cat > p_read_before_rebi
          8s bash   cd /tmp/rprobes && sed -i 's|^for ir in 0 1; do|for ir in 0 1; do\n  rm -f "exe_$ir"|' /tmp/cmpd.sh; cat /tmp/
          6s bash   cd /tmp/rprobes mkdir -p p1_rebind p3_raise p_sub_default p_annot_raise cat > p1_rebind/lib.py <<'PY' print("l
          4s bash   cd /tmp/rprobes mkdir -p p_sub_in_dict p_sub_in_list p_sub_negative cat > p_sub_in_dict/lib.py <<'PY' def base

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects by turning the unsafe cases into named compile-time refusals in `init_split` (`AIL_CURRENT/ail_modules.py:2684`): a statement between earlier bindings and the binding a definition needs that reads or mutates that name (including through calls) is now refused by name.

- Probes (both builds): `p_rebind_print`, `p_rebind_call`, `p_rebind_mutate`, `p_rebind_cond_read` refused by name; `p1_rebind`, `p1_three`, `p1_aug`, `p1_unpack`, `p1_ann`, `p1_def_before`, `p5_control`, `p_sub_safe`, `p_sub_annot`, `p_sub_negative` match CPython; prior refusal probes still refused.
- Added 2 refusal tests (3 programs) to `test_ail_lazymod1`.
- Final tests: `test_ail_lazymod1 test_ail_modsys test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 5/5 ok, 0 failed (320s); `update_manifest.py --check` exit 0.
- Lab/compare sources have no local imports, so `merge_program` is not entered and their C is unchanged.

Committed as `7e14e0a`.
[cost $0.0000, opencode tokens {"total": 2690751, "input": 91890, "output": 5669, "reasoning": 16808, "cache.write": 0, "cache.read": 2576384}]
    tool time: bash 11.2 min, edit 0.0 min, read 0.0 min
        322s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_laz
        319s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_laz
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_rebind p1_three p1_aug p1_unpack p1_ann p1_def_before; do ec
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p3_raise p5_control p_sub_safe p_sub_annot p_sub_negative p_sub
          3s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p5_control p_direct_subscript p1_effectful; do echo "##### $p";
          1s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_rebind_print p_rebind_call p_rebind_mutate p_rebind_cond_read
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — lazymod1 (work..7e14e0a)

**What the change really does:** extends `init_split` so an earlier binding of a name a definition needs is hoisted too (recursively), refuses non-hoisted statements between hoisted bindings that read/write a hoisted name, and refuses unfoldable subscripts (except in annotations).

**Prior review defects**
1. Earlier same-name binding overwriting the hoisted value — **fixed**. `p1_rebind` now matches CPython on both builds: `lib start` / `(2, 2)`.
2. Raising subscript over an unfoldable call moved to start — **fixed**. `p3_raise` is refused by name on both builds (was base refusal).

**Tests / checks**
- `test_ail_lazymod1 test_ail_modsys test_ail_safetynet`: 3/3 ok, 0 failed (168s, HEAD).
- `update_manifest.py --check`: exit 0.
- Lab/compare: `merge_program` returns `None` for all 10 `lab/compare/src/*/main.ail`, so the merge path and their C are unchanged.

**Worker claims:** review fixes verified; added refusal tests (3 programs in the final commit) present; manifest and lab/compare claims verified. The wider 5/5 test count and the worker's other probe names were not re-run/absent.

**New defect (introduced; base matches CPython)**
1. A raising non-subscript expression in an earlier binding is still hoisted, moving the exception before earlier output. `move_bad_expr` only refuses unfoldable `Subscript`, so `effectful()` judges `SIZE = 1 // Z` (with `Z` from an unfoldable call) pure and `need_name` hoists it to program start.

   Probe `/tmp/rprobes/p_div_unfold` (`lib.py`: `print("before")`, `def zero(): return 0`, `Z = zero()`, `SIZE = 1 // Z`, `SIZE = 2`, `def f(a=SIZE): return a`; main imports `lib` in `g()` after `print("calling")`):
   - Expected CPython (and base, both builds): stdout `calling\nbefore\n`, `ZeroDivisionError`, exit 1.
   - Actual HEAD (both builds): stdout empty, `ZeroDivisionError`, exit 1.

   Same with `/tmp/rprobes/p_binop_unfold` (`SIZE = 1 + T`, `T = text()` returning `"x"`): expected `calling\nbefore\n` + `TypeError`, exit 1; actual empty stdout + `TypeError`, exit 1 (base matches CPython).

**Pre-existing (does not block):** `/tmp/rprobes/p_annot_raise` (`def f(a: D["y"] = 0)` with `D = base()`) prints an extra `0` and exits 0 on both HEAD and base, while CPython raises `KeyError`; identical on base.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` not re-run; several worker probe names (`p1_three`, `p1_aug`, `p1_unpack`, `p1_ann`, `p1_def_before`, `p5_control`, `p_sub_*`) were not re-run this round.

VERDICT: FIX
1. Raising non-subscript expressions (e.g. `SIZE = 1 // Z`, `SIZE = 1 + T` where `Z`/`T` come from an unfoldable call) in an earlier binding are hoisted, so the exception fires at program start and earlier stdout (`calling\nbefore\n`) is lost. Probe `/tmp/rprobes/p_div_unfold` (and `p_binop_unfold`): expected `calling\nbefore\n` + exit 1, actual empty stdout + exit 1; base matches CPython. The purity/raise check must cover non-subscript expressions (or refuse such earlier bindings by name).
[cost $0.0000, opencode tokens {"total": 1611021, "input": 71802, "output": 6097, "reasoning": 27330, "cache.write": 0, "cache.read": 1505792}]
    tool time: bash 3.6 min
        170s bash   date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_lazymod1 test_ail_safetynet t
         13s bash   mkdir -p /tmp/rprobes/p_div_unfold /tmp/rprobes/p_binop_unfold cat > /tmp/rprobes/p_div_unfold/lib.py <<'PY' p
          8s bash   date; for p in p_def_rebind p_after_mutate p_after_alias_mut p_after_read; do echo "##### $p HEAD"; timeout 30
          5s bash   mkdir -p /tmp/rprobes/p_def_rebind_imp /tmp/rprobes/p_def_rebind_imp2 cat > /tmp/rprobes/p_def_rebind_imp/lib.
          5s bash   date; for p in p_def_rebind_imp p_def_rebind_imp2; do echo "##### $p BASE"; timeout 300 bash /tmp/cmpdir.sh /t
          5s bash   echo "=== p_annot_raise lib"; cat /tmp/rprobes/p_annot_raise/lib.py; echo "=== main"; cat /tmp/rprobes/p_annot
          4s bash   date; for p in p1_rebind p3_raise p_rebind_print p_rebind_call p_rebind_mutate p_rebind_cond_read; do echo "##
          3s bash   mkdir -p /tmp/rprobes/p_after_wrap /tmp/rprobes/p_after_const_mut cat > /tmp/rprobes/p_after_wrap/lib.py <<'PY

FINAL VERDICT: FIX  2026-11-01T17:07:26Z
