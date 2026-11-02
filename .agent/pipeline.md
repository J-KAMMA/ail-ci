# job job-onelangs1-11030257  started 2026-11-02T17:58:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

**Commit:** `0a885be` on `job-onelangs1-11030257` (no push, per job rules)

**Added**
- `tools/ail2py.py` — brace→annotated-Python converter with comments, `use` imports, entry wrapper, and `--check`.
- `AIL_CURRENT/test_ail_ail2py.py` + `tests.d/test_ail_ail2py.txt` — five programs, two `--check` identical, three runtime-matched.
- `DEVLOG.md` entry and regenerated manifest pins.

**Done-check (all ten)**
```
berth_sim identical
chain_relax identical
echo_pack identical
ledger_bin identical
rail_transfer identical
scar_life identical
tally_lang identical
term_rank identical
ticket_audit identical
tree_fold identical
```

**Tests**
- `test_ail_ail2py`: 3/3 OK
- `test_ail_files`: 18 OK, 1 skipped
- `test_ail_corpus_findings3`: 2/2 OK
- `test_ail_safetynet`: 5/5 OK with `ulimit -v unlimited`; under `-v 1500000`, its `S4_generators_gc` case fails with `AIL internal error: generator: no stack` because 100k generator stacks exceed the address-space cap. Compiler unchanged.

**Note:** One small `--check` candidate (`float_list`) differs under `--strict` in compiler `int(float)` handling between brace and Python surfaces; using the plain translated text gives the same difference, so it is not caused by `ast.unparse`. It is covered as a runtime case instead.
[cost $0.0000, opencode tokens {"total": 2370345, "input": 141808, "output": 10437, "reasoning": 17268, "cache.write": 0, "cache.read": 2200832}]
    tool time: bash 21.8 min, write 0.0 min
        456s bash   ulimit -v 1500000; for m in test_ail_files test_ail_corpus_findings3 test_ail_safetynet; do echo ==== $m ====;
        183s bash   ulimit -v 1500000; for m in test_ail_ail2py test_ail_files test_ail_corpus_findings3 test_ail_safetynet; do ec
        173s bash   ulimit -v unlimited; python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -14
        157s bash   ulimit -v unlimited; python3 -B AIL_CURRENT/test_ail_safetynet.py GeneralPathSafetyNet.test_programs 2>&1 | ta
        106s bash   python3 - <<'PY' p='tools/ail2py.py' s=open(p).read() s=s.replace("""def main(argv=None):     parser = argpars
        105s bash   ulimit -v 1500000; python3 tools/update_manifest.py --check && echo manifest-ok; for t in berth_sim chain_rela
        105s bash   ulimit -v 4000000; python3 -B AIL_CURRENT/test_ail_safetynet.py GeneralPathSafetyNet.test_programs 2>&1 | tail
          4s bash   ulimit -v 1500000; python3 - <<'PY' import subprocess,sys,tempfile,pathlib sys.path.insert(0,'AIL_CURRENT') im

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds `tools/ail2py.py`, a thin converter over `ail_syntax.translate` that rewrites `__ail_checked_*` markers, re-renders top-level nodes with `ast.unparse`, re-inserts source comments, emits `from m import *` for `use`, wraps the entry `sys.exit(main())`, and provides `--check`; plus a five-program test module, manifest pins, and a DEVLOG entry. This matches the report.

**Checks run**
- Done-check loop on all ten `lab/compare/src/*/main.ail` with `--check --flags "--strict"`: **10/10 identical**.
- `python3 tools/update_manifest.py --check`: **manifest-ok**.
- `python3 tools/par_check.py -j 2 test_ail_ail2py test_ail_safetynet`: **2 modules, 0 failed**.
- Converted all **260** brace `.ail` files under `AIL_CURRENT/language_examples`; none failed, and every converted AST equalled the plain `translate` AST (comments/entry wrapper normalised). So `ast.unparse` does not change meaning.
- `p_contracts2.ail` (`requires`/`ensures`) and `p_nested.ail`: `--check` **identical**.
- `p_nocomment.ail` (`int(float)`): `--check` differs, but plain `translate` output gives the same 3-line difference and converter C equals plain C; this is the pre-existing brace-vs-Python surface difference the report notes, not `ast.unparse`.

**Claims**
- Branch/commit `0a885be`: verified.
- Added tool/test/manifest/DEVLOG files: verified.
- Done-check 10/10: verified.
- `test_ail_ail2py` 3/3: verified (module passes).
- `test_ail_safetynet` passes with unlimited memory: verified (module passes).
- `test_ail_files` and `test_ail_corpus_findings3`: unverified (not rerun per review instructions).
- Safetynet failure under `ulimit -v 1500000`: unverified.
- `float_list` note: verified.
- `use` imports: the output does start with `from m import *`; however `--check` on a `use` source reports `py-refused` because the converted file is placed in a temp directory, so that path is not covered by `--check`. This is a limitation, not counted as a blocking defect because the task's ten tasks have no `use`.

**Defects**
1. End-of-line comment on a multi-line statement is emitted **after** the statement, not before it.
   Probe `p_multiline.ail`:
   ```
   fn main() -> int {
       let x = add(
           1,
           2); # end: the sum
       print(x);
       return 0;
   }
   ```
   Expected: `# end: the sum` immediately before `x = add(1, 2)`.
   Actual: it is emitted after `x = add(1, 2)` and before `print(x)`. This violates the stated rule that an end-of-line comment goes on the line before that statement.

2. Comments before a `struct` or its fields are moved inside the class body.
   Probe `p_struct_comment.ail`:
   ```
   # file head: before the struct
   struct Box {
       # field note: value
       value: int;
   }
   impl Box {
       # method note: bump
       fn bump(self, n: int) -> void { self.value += n; # end: inline note
       }
   }
   ```
   Expected: `# file head` before `class Box:`, and `# field note` near the field/`__init__`.
   Actual: both are emitted at indent 4 immediately before `def bump`, inside the class, because generated `class`/`__init__`/field lines have no `source_map` entry. A comment before `use` is similarly emitted before `def main` rather than before the generated import.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2244907, "input": 42754, "output": 9334, "reasoning": 34739, "cache.write": 0, "cache.read": 2158080}]
    tool time: bash 4.9 min
        173s bash   cd /home/runner/work/ail-ci/ail-ci; ulimit -v unlimited; python3 ../ail-ci/tools/par_check.py -j 2 test_ail_ai
        105s bash   ulimit -v 1500000; for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term
          3s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p_struct_comment p_contracts p_nested p_nocomment; do printf '%s:
          2s bash   cd /home/runner/work/ail-ci/ail-ci; python3 - <<'PY' import sys, pathlib, ast sys.path.insert(0,'tools'); sys.
          2s bash   cd /home/runner/work/ail-ci/ail-ci; python3 - <<'PY' import sys, pathlib, ast, re sys.path.insert(0,'tools'); 
          1s bash   cd /home/runner/work/ail-ci/ail-ci; python3 - <<'PY' import sys, pathlib sys.path.insert(0,'tools'); sys.path.
          1s bash   cd /home/runner/work/ail-ci/ail-ci; python3 - <<'PY' import sys, pathlib, traceback sys.path.insert(0,'tools')
          1s bash   cd /home/runner/work/ail-ci/ail-ci; python3 -B tools/ail2py.py AIL_CURRENT/language_examples/number_lines.ail 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `tools/ail2py.py` and committed as `07678f0`.

- End-of-line comments on multi-line statements now precede the annotated statement.
- Comments before `struct`/fields and `use` imports now stay with the generated `class`/`__init__`/field/import lines.
- Added regression coverage in `AIL_CURRENT/test_ail_ail2py.py`; refreshed the manifest.

Verification:
- Done-check: **10/10 identical** (`--check --flags "--strict"`).
- All **260** brace examples convert and parse; every source comment kept.
- `test_ail_ail2py`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **4 modules, 0 failed**.
- Probes `p_multiline`, `p_struct_comment`, `p_use`, `p_blocks` all parse with comments retained.
- `tools/update_manifest.py --check`: clean.
[cost $0.0000, opencode tokens {"total": 1394884, "input": 52385, "output": 6397, "reasoning": 18598, "cache.write": 0, "cache.read": 1317504}]
    tool time: bash 13.9 min, read 0.0 min, edit 0.0 min
        336s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v unlimited; python3 tools/par_check.py -j 2 test_ail_ail2py tes
        280s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v unlimited; python3 tools/par_check.py -j 2 test_ail_ail2py tes
        105s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; for t in berth_sim chain_relax echo_pack ledger_bin r
        103s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; for t in berth_sim chain_relax echo_pack ledger_bin r
          3s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v unlimited; python3 -B AIL_CURRENT/test_ail_ail2py.py 2>&1 | ta
          2s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v unlimited; python3 -B AIL_CURRENT/test_ail_ail2py.py 2>&1 | ta
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B - <<'PY' import sys, ast, io, tokenize from pathlib import Pa
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds `tools/ail2py.py` (a converter over `ail_syntax.translate` that rewrites `__ail_checked_*` markers, re-renders top-level nodes with `ast.unparse`, re-inserts brace comments, prepends `from m import *`, wraps `sys.exit(main())`, and offers `--check`), plus `test_ail_ail2py.py`, registration, manifest pins, and DEVLOG. This matches the report.

**Checks run (HEAD 07678f0)**
- Done-check all ten compare-lab tasks with `--check --flags "--strict"`: **10/10 identical**.
- `tools/update_manifest.py --check`: clean.
- `par_check.py -j 2 test_ail_ail2py test_ail_safetynet test_ail_files test_ail_corpus_findings3`: **4 modules, 0 failed**.
- All **260** brace examples convert, parse, and have every source comment exactly once.
- AST-equality of converted vs `head + translate` for all 260 (entry wrapper normalised): **0 mismatches**, so `ast.unparse` changes no meaning.
- No compiler/runtime file changed, so unrelated programs' C is unchanged by construction.

**Claims**
- Fixed multiline end-of-line comment: **verified** (`x = add(1, 2)` now follows `# end: the sum`).
- Comments before struct/fields/use stay with generated lines: **partially false** (see defect 2; use-after-struct ordering breaks it).
- Regression coverage, 260 examples, 4 modules, manifest, 10/10: **verified**.
- Probes `p_multiline`, `p_struct_comment`, `p_use`, `p_blocks` parse with comments retained: **verified in substance** (placement still has the defects below).

**Defects**

1. An end-of-line comment on a block-closing `}` is emitted before the last statement *inside* the block, not before the statement it closes.
   Probe `/tmp/rprobes/r_close.ail`:
   ```
   struct Box {
       value: int;
   } # after struct
   fn main() -> int {
       if true {
           print(1);
       } # after if
       print(2);
       return 0;
   } # after main
   ```
   Expected: `# after struct` before `class Box:`, `# after if` before `if True:`, `# after main` before/after `def main` — not inside those bodies. Actual:
   ```
       def __init__(self, value: int):
           # after struct
           self.value = value
   ...
       if True:
           # after if
           print(1)
   ...
       # after main
       return 0
   ```
   (`--check` is still `identical`; only placement is wrong. The test module has no closing-brace case.)

2. A field comment in a struct that appears before a later `use` is moved onto the generated import line.
   Probe `/tmp/rprobes/r_use_after_real.ail` (compiles; `use` after `struct` is accepted):
   ```
   # top
   struct A {
       # field note
       a: int;
   }
   use block_math;
   # before main
   fn main() -> int {
       print(1);
       return 0;
   }
   ```
   Expected: `# field note` immediately before `self.a = a` (the report's claim). Actual:
   ```
   # top
   # field note
   from block_math import *
   ...
   class A:
       def __init__(self, a: int):
           self.a = a
   ```
   The new `head_meta` gives the import the `use` line (7), so the earlier field comment targets it.

**Pre-existing / Unverified**
- `--check` on a `use` source still reports `py-refused` (converted file is in a temp dir); same limitation the prior review noted, not counted.
- Speed: not applicable (no compiler/runtime change).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1382566, "input": 33262, "output": 7604, "reasoning": 21636, "cache.write": 0, "cache.read": 1320064}]
    tool time: bash 2.8 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; for t in berth_sim chain_relax echo_pack ledger_bin r
         45s bash   sleep 45; tail -12 /tmp/rprobes/tests.log; ps -p 22833 >/dev/null && echo RUNNING || echo DONE; date
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import glob, ast, sys sys.path.insert(0,'tools'); sys.p
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B AIL_CURRENT/test_ail_ail2py.py 2>&1 | tail -15
          3s bash   cd /home/runner/work/ail-ci/ail-ci && for f in block_use_math binary_cursor_file binary_transform_main; do pri
          2s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import glob, ast, sys, re sys.path.insert(0,'tools'); s
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import glob, sys, ast, io, tokenize sys.path.insert(0,'
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B tools/ail2py.py /tmp/rprobes/r_close.ail --check --flags '--s

FINAL VERDICT: FIX  2026-11-02T19:05:04Z
