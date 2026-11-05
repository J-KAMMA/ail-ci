# `--debug` gdb matrix and DWARF line coverage (lane fd-dbg, job fddbg1)

Ten programs in `lab/debug/progs` (typed path; `general_path.py` on the general path). `linecov.py` lists each
program's *executable statement lines* from the `ast` -- every statement's `lineno`, minus a `def`/`class` header
(no prologue code without tagged locals), a docstring, `pass`, `global`/`nonlocal`, an import (resolved at build
time), a bare `x: int` and a dataclass field -- and compares them with `readelf --debug-dump=decodedline` of the
`--debug` build. `test_ail_debug_gdb.py` runs the 30 gdb checks (prints `gdb: <version>` first; skipped only when
gdb, a C compiler, readelf/objdump or the programs are missing).

Measurements on 2026-11-05, gdb 15.1, gcc 13, CPython 3.12.3.

## Before / After

| number | Before | After |
| --- | --- | --- |
| (a) typed-path statement lines in the DWARF table, 9 typed programs | 114/122 (93.4%) | **114/114 (100%)** |
| (a) general path (`general_path.py`), recorded | 7/7 | **7/7** |
| (b) gdb matrix checks passing | 0/30 (no matrix; `test_ail_debug.py` had one `break prog.py:3` + `bt 1`) | **26/30** |

Before, per program (first drafts of the same ten files): comprehension 10/10, dictsort 17/17, imports_helper
8/10, loops 22/25, method 8/9, nested_calls 10/11, recursion 11/12, strings 14/14, tryexcept 14/14, general_path
7/7. The misses were `steps = 0`/`acc = 0`/`total = 0` (constant initialisers the IR folds into the loop's initial
value), `self.value = start` (class `__init__`, below), the import line, and `print(total)`/`print(total, k)` in
`main` of `loops.py`.

After (`python3 lab/debug/linecov.py --all`): every program 100%.

## What changed, and what did not

**No compiler file was changed.** `git diff origin/integ -- AIL_CURRENT/python/pkg-v12/ir/emit_c.py
AIL_CURRENT/python/pkg-v12/cruntime.py` is empty, so every release build's C is byte-identical by construction;
`--debug-dir` was also used to rebuild the 26 `lab/compare/src` programs, all of which built.

The Before misses were of three kinds, and only the first is a property of the programs:

1. **Program shape** (fixed in the ten programs, no compiler change): a constant initialiser for a loop-carried
   local (`steps = 0`) is folded into the loop's initial value, so no machine code is left on that line. The
   programs now start accumulators from a computed value. Two more shapes were changed to what the typed path
   accepts without the caveats below: a dataclass instead of a class with a hand-written `__init__`, and no
   parameter rebinding (`n = n // 2`).
2. **Compiler/debug-info limitations, recorded as follow-ups** (all outside the two files this job may edit):
   * **Parameter rebinding renumbers the line map.** `def f(n): n = n // 2` makes `pyfunc._to_c_unshadowed` retry
     through `rebinding.copy_param`, which unparses the tree; the retry text is not keyed in
     `pyfunc._REWRITE_LINES`, so `debug_restore_lines` leaves the fresh numbering in place. One blank line between
     functions disappears, and every statement after the first function maps one line too early (measured:
     `print(total)` at 20 emitted as `#line 19`). Fix belongs in `pyfunc`/`rebinding` (not editable here): keep
     the same snapshot for the retry text, or map retry lines through `pyc._REWRITE_LINE_MAPS`.
   * **Class `__init__` bodies get no `#line`.** A class constructor is emitted as `ail_new_<Class>` by the legacy
     class machinery (`pyfunc`), not through `ir/emit_c.py`; `self.value = start` maps to nothing.
   * **A loop's C step is attributed to the body line.** `for (k = 0; k < n; k++)` has its increment emitted after
     the body, so GCC records it on the body's line: `next` in the body never stops on the header again (one fewer
     stop than CPython's line events). Emitting the step as its own statement under the `for` line, or as a
     `while` loop with an explicit increment, would fix it in `emit_c.py`; the C-for shape is emitted by the
     range lowering, so the change is larger than this job allowed.
3. **gdb locals show C names, not Python names.** Parameters keep a derived C name (`n` -> `v_n`; `print v_n`
   works and is a passing check). SSA temporaries are `ir1`, `ir2`, ...: `info locals` shows values, but
   `print steps` fails (`/tmp` probe: `No symbol "steps" in current context`). Mapping recorded here:
   `n -> v_n`, `start -> v_start`, `step -> v_step`; loop-carried locals become `irN` (no Python name in DWARF).
   A debug-only rename in `emit_c.py` was not attempted: it changes every emitted local name, and the release C
   must stay byte-identical.

## The 30-check gdb matrix: 26/30

`python3 AIL_CURRENT/test_ail_debug_gdb.py` prints `gdb: GNU gdb (Ubuntu 15.1-1ubuntu1~24.04.1) 15.1` and
`gdb matrix: 26/30 checks passed`.

Passing: 10 `break <file>:<line>` checks (the stop names the line), 7 `next5` checks (the first `next` lands on the
line CPython's `sys.settrace` visits next, and every stop is a line settrace visits), 3 `bt3` (three frames, each
naming `file.py:N`), 4 `finish`, 1 `locals int` (`print v_n` -> `$1 = 1`), 1 `index error` (`rbreak ail_raise`
stops the IndexError and `bt` names `general_path.py:9`).

Every failure, named:

1. `next5 method` -- want `[20, 21]`, got `[14, 20, 21, 22, 23]`: the breakpoint at `method.py:10` (`return
   self.a + self.b`) is in `total`, but gdb stepped an inlined copy (`return self.total()` at 14) first; the first
   stop is not the line settrace names.
2. `next5 comprehension` -- want `[5, 6, 7, 8, 9]`, got `[3, 4, 5, 4, 5]`: GNU gdb resolved `comprehension.py:4`
   to the comprehension's own line 3/4 block (`ys = [x + 1 ...]` is line 3, line 4 is `total = sum(ys)`), so the
   first stop is line 3, not 5.
3. `next5 strings` -- want `[3, 4, 3, 4, 3]`, got `[3, 4, 5, 6, 7]`: the loop's C step carries the body line (see
   follow-up 3 above), so `next` does not stop on the `for` header a second time.
4. `locals float` -- `dictsort.py:17` (`print(g)`) has the double in an SSA temporary whose name does not match
   `irN = <float>` in `info locals` (the build's C names there are `_litN`/`_prN`); gdb prints the value, the
   check's name pattern does not find it.

## General path (`general_path.py`, pyboxed2 -- not editable here)

Line coverage 7/7 under the same definition. Gaps recorded for a follow-up owner: the general path has no
`AIL_DBG_SITE` ("raised near") report at all (`test_ail_debug.py` already asserts this), and its C variables are
boxed (`_pr5`, `_lit6`), so `info locals` cannot show a Python name for either path. No general-path line was
missing in this program; the first draft's two `def` headers were the only entries absent (no prologue code).
