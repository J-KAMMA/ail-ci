# job job-rbstd_typing-11021401  started 2026-11-02T05:09:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied and committed as `53a8bf0` on `job-rbstd_typing-11021401`.

- Re-applied the accepted `std_typing` change. Conflicts kept both sides: `ail_syntax` gate keeps `numbers` and adds `typing`; `stdlib5.rewrite_text` keeps `numberslib` and adds `typinglib.run`.
- Added `typinglib.py`, `test_ail_std_typing.py`, `tests.d/test_ail_std_typing.txt`, 13 `lab/stdlib/typing/` programs plus `RESULTS.md`; added DEVLOG/DIFFERENCES records and regenerated `manifest.d`.
- `tools/diff_ids.py` does not exist on this tree; `tools/update_manifest.py` ran and `--check` passes.

Tests on the final tree (before commit, no code changed after): `test_ail_std_typing` 3/3 OK, `test_ail_safetynet` 5/5 OK, `test_ail_files` 18/18 OK (1 skipped), `test_ail_corpus_findings3` 2/2 OK.

Probes (`bash ~/tools/cmp.sh`, both g and d builds):
- `p_td_values.py`, `p_nt_values.py`, `p_nt_arity.py`, `p_cast_values.py`, `p_typing_shadow.py`: all match CPython on both builds.
- `p_refuse_module_rebind.py` and `p_refuse_global.py`: refused by name on both builds.
- `p_refuse_nonlocal.py`: matches CPython (`2`) on both builds.
[cost $0.0000, opencode tokens {"total": 3158380, "input": 127041, "output": 11199, "reasoning": 9708, "cache.write": 0, "cache.read": 3010432}]
    tool time: bash 10.9 min, edit 0.0 min, write 0.0 min
        225s bash   python3 -m unittest -q test_ail_corpus_findings3 2>&1 | tail -20; echo "EXIT:${PIPESTATUS[0]}"
        210s bash   python3 -m unittest -q test_ail_safetynet 2>&1 | tail -20; echo "EXIT:${PIPESTATUS[0]}"
        142s bash   python3 -m unittest -q test_ail_files 2>&1 | tail -20; echo "EXIT:${PIPESTATUS[0]}"
         33s bash   python3 -m unittest -q test_ail_std_typing 2>&1 | tail -30; echo "EXIT:${PIPESTATUS[0]}"
         16s bash   for p in /tmp/probes/p_td_values.py /tmp/probes/p_nt_values.py /tmp/probes/p_cast_values.py /tmp/probes/p_typi
          9s bash   for p in /tmp/probes/p_td_values.py /tmp/probes/p_nt_values.py /tmp/probes/p_nt_arity.py /tmp/probes/p_cast_va
          7s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-std_typing-11020445 2>&1 | tail -5
          4s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_typing_shadow.py') s=p.read_text() s=s.replace

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: re-apply `std_typing` on current tree

**What the change does:** adds `typing` to the stdlib-5 gate in `ail_syntax.python_surface` and calls new `typinglib.run` from `stdlib5.rewrite_text`; `typinglib.py` lowers `TypedDict` declarations to `dict`, `NewType(...)` to identity, and `cast(T, v)` to `v` (with scope-aware shadowing for TypedDict/NewType, not cast). Tests, lab programs, DEVLOG/DIFFERENCES, and regenerated manifest entries are included. This matches the report.

**Re-application check:** `typinglib.py`, the test module, lab files and `tests.d` entry are byte-identical to `FETCH_HEAD`; the two conflicts kept both sides (`numbers` + `typing`, `numberslib` + `typinglib.run`). `tools/diff_ids.py` is indeed absent. `tools/update_manifest.py --check` passes.

**Tests:** `test_ail_std_typing` and `test_ail_safetynet` pass on HEAD (`0 failed`, 190s).

**Claim check:** commit, files added, conflict resolution, absent `diff_ids.py`, manifest check, and the 8 named worker probes verified. `test_ail_files` / `test_ail_corpus_findings3` were not rerun (reviewer scope); not independently verified. C output of a typing-annotation-only program and a plain program was unchanged vs base (`program.c` same).

### Defects

1. **`cast` lowering ignores lexical shadowing.** `visit_Call` treats any name bound to the imported `cast` as `typing.cast` without checking the scope stack.
   ```python
   from typing import cast

   def run(cast, a, b):
       return cast(a, b)

   def local():
       cast = lambda a, b: a - b
       return cast(9, 4)

   print(run(lambda a, b: a - b, 9, 4), local())
   print(cast(str, "12") + "!")
   ```
   Expected CPython: `5 5`, then `12!`. Actual on both builds: `4 4`, then `12!` (exit 0). Base refuses the program, so this is introduced by the change.

2. **TypedDict lowering uses the shadowable name `dict`.** `Movie(**data)` becomes `dict(data)` even when `dict` is a parameter/local.
   ```python
   from typing import TypedDict

   class Movie(TypedDict):
       title: str

   def build(dict, data):
       return Movie(**data)

   print(build(lambda d: {"title": "shadow:" + d["title"]}, {"title": "right"}))
   ```
   Expected CPython: `{'title': 'right'}`. Actual on both builds: `{'title': 'shadow:right'}` (exit 0). Base refuses `class Movie(TypedDict)`, so this is introduced by the change.

### Unverified
- `test_ail_files`, `test_ail_corpus_findings3` (not rerun per reviewer scope).
- Speed (change is compile-time only; no runtime hot path added).

VERDICT: FIX
1. cast shadowing: `p_cast_param.py` expected `5 5` / actual `4 4`.
2. TypedDict `dict` shadowing: `p_td_dict_param.py` expected `{'title': 'right'}` / actual `{'title': 'shadow:right'}`.
[cost $0.0000, opencode tokens {"total": 963079, "input": 131013, "output": 6512, "reasoning": 15954, "cache.write": 0, "cache.read": 809600}]
    tool time: bash 4.5 min
        191s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_typing te
         27s bash   cd /home/runner/work/_temp/w2; for p in /tmp/probes/p_td_values.py /tmp/probes/p_nt_values.py /tmp/probes/p_nt
         15s bash   cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) HEAD"; bash ~/tools/c
         11s bash   cat > /tmp/rprobes/p_cast_param.py <<'EOF' from typing import cast   def run(cast, a, b):     return cast(a, b
          7s bash   sed -i 's/print(cast(str, 12) + "!")/print(cast(str, "12") + "!")/' /tmp/rprobes/p_cast_param.py; cd /tmp/base
          7s bash   cd /home/runner/work/_temp/w2; echo "== cast"; bash ~/tools/cmp.sh /tmp/rprobes/p_cast_param.py "$PWD" 2>&1 | 
          5s bash   d=$(mktemp -d /tmp/dbgXXXX); cd "$d"; cp /tmp/rprobes/p_typing_only.py p.ail; printf 'print("hello", 1 + 2)\n'
          2s bash   cat > /tmp/rprobes/p_td_method.py <<'EOF' from typing import TypedDict   class Movie(TypedDict):     title: st

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed both defects and committed as `d8ae83d`.

- `cast` now respects lexical shadowing (including a shadowed module alias).
- `TypedDict(...)` construction no longer captures a local/parameter named `dict`.
- Probes `p_cast_param`, `p_review_cast_shadow`, `p_td_dict_param`, `p_review_td_dict_shadow`: all match CPython on both `cmp.sh` builds.
- Tests: `test_ail_std_typing`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (411s).
- `tools/diff_ids.py` is absent; `update_manifest.py --check` passed.
[cost $0.0999, opencode tokens {"total": 3680205, "input": 436203, "output": 13790, "reasoning": 27652, "cache.write": 0, "cache.read": 3202560}]
    tool time: bash 8.8 min
        412s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_std_typing test_ail_safetynet test_a
         17s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/pkg-v1
         11s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_review_cast_shadow.py') s=p.read_text() s=s.re
         11s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_review_td_dict_shadow.py') s=p.read_text() s=s
          8s bash   cd /tmp && d=$(mktemp -d /tmp/mini10XXXX); cd $d; cat > t1.ail <<'EOF' def new(positional, keywords):     if l
          8s bash   cd /tmp && d=$(mktemp -d /tmp/mini9XXXX); cd $d; cat > t1.ail <<'EOF' def f(data):     return dict(data) print
          7s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_review_td_dict_shadow.py') s=p.read_text() s=s
          7s bash   cd /tmp && d=$(mktemp -d /tmp/mini7XXXX); cd $d; cat > t1.ail <<'EOF' def merge(base, extra):     result = dic

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review — `work..HEAD` (`53a8bf0`, `d8ae83d`)

**What the change really does.** Re-applies the accepted `std_typing` lowering (`TypedDict`, `NewType`, `cast` in `typinglib.py`, `typing` added to the stdlib-5 gate) and then adds scope-aware `cast` shadowing and a helper-based TypedDict constructor for scopes where `dict` is shadowed. It also brings the lab programs, `test_ail_std_typing`, `DIFFERENCES`/`DEVLOG` and manifest updates. This matches the task; the report's summary omits the re-apply itself but the commits contain it.

**Claims checked**
- `cast` respects lexical shadowing: **partially verified**. Parameter, local, nested closure and local module-alias shadowing match CPython; module-level rebinding does not (defect 1).
- `TypedDict(...)` no longer captures local/parameter `dict`: **verified** (`p_td_dict_param`, `p_td_dict_local`, `p_td_nested_close`, `p_td_dict_module2`, `p_td_helper_errors` all match both builds, including positional/`**`/keyword/error-text cases).
- Four named probes match: **unverified** for `p_cast_param`/`p_td_dict_param` (files absent); `p_review_cast_shadow.py` and `p_review_td_dict_shadow.py` both match.
- Tests: **verified** — `test_ail_std_typing test_ail_safetynet test_ail_files test_ail_corpus_findings3`, 4 modules, 0 failed (362s).
- `tools/diff_ids.py` absent: **verified**. `update_manifest.py --check`: **verified** (rc 0).
- Non-typing C unchanged: **verified** (`program.c` and binary identical to base for a `List[int]` program and for a program containing a `typing_count` identifier).

**Tests run:** 4 modules, 0 failed (above).

**Pre-existing (identical on `/tmp/base`):** `cast` used as a value (`f = cast`), local `NewType(...)`, local `TypedDict` class — all refused identically on base, so not blocking.

**Speed:** not measured; the change only lowers code for programs importing `typing`, so no hot-path effect.

---

VERDICT: FIX

1. Module-level `cast` shadowing is silently lowered to the value (regression: base and CPython call the rebound name).
   `p_cast_module_shadow.py`:
   ```python
   from typing import cast
   def mycast(ty, v): return "MY:" + str(v)
   cast = mycast
   print(cast(0, 5))
   ```
   Expected/CPython/base: `MY:5`; actual HEAD (both builds): `5`.
   Same with a rebound module alias (`import typing as t; t = Mod()`, `p_cast_alias_module.py`): expected `M:5`, actual `5`.

2. TypedDict construction via `**` accepts non-string keys instead of raising.
   `p_td_kw_unshadow.py` (and the same with a parameter named `dict`):
   ```python
   from typing import TypedDict
   class Movie(TypedDict):
       title: str
   def a():
       return Movie(**{1: 2})
   try: print("unshadow", a())
   except Exception as exc: print("unshadow", type(exc).__name__, exc)
   ```
   Expected/CPython: `unshadow TypeError keywords must be strings`; actual HEAD (both builds): `unshadow {1: 2}`. The `dict(data)` special case and `_ail_typed_dict_new` both drop CPython's string-key requirement for `**`.
[cost $0.0341, opencode tokens {"total": 1356788, "input": 76864, "output": 6943, "reasoning": 24469, "cache.write": 0, "cache.read": 1248512}]
    tool time: bash 7.7 min
        364s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_st
         30s bash   cd /tmp/rprobes2 && cat > p_cast_local_shadow.py <<'EOF' from typing import cast  def fake(ty, v):     return 
         18s bash   date; cd /tmp/rprobes2 && for p in *.py; do echo "===== $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes2/$p 
         13s bash   date; cd /tmp/probes && for p in p_review_cast_shadow.py p_review_td_dict_shadow.py; do echo "=== $p"; timeout
         13s bash   cd /tmp/rprobes2 && cat > p_td_dict_module2.py <<'EOF' from typing import TypedDict  class Movie(TypedDict):  
          8s bash   date; cd /tmp/rprobes2 && for p in p_cast_module_shadow.py p_cast_alias_module.py; do echo "===== BASE $p"; ti
          7s bash   cd /tmp/rprobes2 && cat > p_td_kw_unshadow.py <<'EOF' from typing import TypedDict  class Movie(TypedDict):   
          4s bash   date; cd /tmp/rprobes2 && for p in p_cast_local_shadow.py p_td_dict_param.py p_td_dict_local.py p_cast_value.p

FINAL VERDICT: FIX  2026-11-02T06:10:04Z
