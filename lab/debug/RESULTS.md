# fddbg1: `--debug` builds under gdb, and DWARF line coverage

Measured 2026-11-06 on a GitHub Actions ubuntu-24.04 runner, gcc, GNU gdb 15.1 (installed with apt for this run:
the runner image has no gdb), readelf 2.42. Base: `origin/integ` at d4be646.

    python3 lab/debug/linecov.py              # (a) line coverage, typed path (`--strict`)
    python3 lab/debug/linecov.py --general    # (a) the same programs with AIL_UNIFIED_FORCE=1
    python3 lab/debug/linecov.py --gdb        # (b) the 30-check gdb matrix
    python3 AIL_CURRENT/test_ail_debug_gdb.py # both, on 4 programs + the matrix (registered in tests.d)

## Method

**(a) Lines.** `linecov.py` takes the executable statement lines of each program with `ast`: the first line of every
statement except `def`/`class` headers, `import`, `pass`, `global`/`nonlocal`, a docstring and a `try:` header. It
compares them with the lines `readelf --debug-dump=decodedline` lists for the `.py` file in the `--debug` build. An
imported helper module is measured against its own file name. `stray` lists lines the table names that hold no
statement (blank lines, lines past the end of the file). Those are wrong mappings. They are shown but not counted.

**(b) gdb matrix**, 30 checks, each one `gdb -batch -nx -x script` run:

| checks | what |
|---|---|
| 10 | `break file.py:N` + `run` stops on file.py:N (one per program) |
| 10 | 10 × `next`: the first ≤5 lines of the file gdb stops on equal the line events of CPython 3.12's `sys.settrace` after line N. The trace follows the frame and the frames it returns to (`next` steps over calls) plus line N in any frame (the breakpoint is hit again). |
| 1 | `bt` 3 calls deep (p02 `inner`): every frame names `p02_nested.py:N`, and the lines are inner:2 middle:7 outer:12 main:17 |
| 1 | `finish` from `inner` returns to middle:7 and shows the value 11 |
| 1 | `info locals` in p08 `calc` names `k`, `g`, `r` |
| 4 | `print n` (int param), `print f` (float param), `print k` (int local), `print g` (float local) by the Python name, with CPython's value. One gdb run each, because an error ends a `-x` script. |
| 2 | p09 IndexError: `break ail_die` stops there (message "list index out of range"), and `bt` names `pick` at p09_raise.py:2 |
| 1 | `break p06_helper.py:2` (the imported module) stops in `scale` |

The `next` comparison normalises two things, both written in `next_lines`:
- A hit of *another location of the same breakpoint* on the line gdb already stopped on is not counted as a step. A
  `for` header has code before the loop and in each iteration.
- The stop gdb makes in a caller on the line of the call it returns from is not counted. That is the middle of the
  statement, and CPython reports no line event there.

Programs (`progs/`): p01 loops (for/while/if-else), p02 nested calls 3 deep, p03 a class with a method, p04 a list
comprehension, p05 try/except, p06 `from p06_helper import scale`, p07 the general path (no annotations,
`isinstance`), p08 int and float locals, p09 an IndexError, p10 strings, a dict and a for loop over a list.

## Before (origin/integ, d4be646)

**(a) typed path: 72/77 lines (93.5%).** Missing: p01_loops.py 2, 8 (`acc = 0`, `k = 0`), p03_method.py 3
(`self.value = start`), p08_locals.py 9, 10 (`n = 42`, `f = 1.5`).
Stray: p04_comp.py 4, 5 (the list-returning wrapper of `squares`, so gdb put a second location of
`break p04_comp.py:7` inside `squares`), plus the lines past the end of p03/p04/p10 described below.
**General path: 77/77 (100%)**, no stray line.

**(b) 21/30.** Failed: next p01:3 (`gdb [4, 5, 4, 3, 4]` vs settrace `[4, 5, 3, 4, 7]`: after each branch gdb went
back to the `if`), next p05:2, next p10:9, finish, info locals, print n, print f, print k, print g.

## After

**(a) typed path: 76/77 lines (98.7%). Target 100%: not met.** One line is missing, p03_method.py:3
(`self.value = start` in `__init__`). The class constructor `ail_new_Counter` comes from pyfunc.py's class
lowering, which writes no `#line` for the `__init__` body. pyfunc.py is not editable in this lane (follow-up 1).
**General path: 77/77 (100%)**, unchanged, so pyboxed2 has no gap to record on these 10 programs.

**(b) 27/30. Target ≥26: met.** The 3 failures:

| check | gdb / CPython | cause | where to fix |
|---|---|---|---|
| next x5 p05_try.py:2 | `[6, 11, 2, 5, 6]` / `[3, 6, 11, 2, 3]` | the `try` body is outlined into another C function (`ail_ir_try` runs it under setjmp), so `next` steps over line 3 | ir/emit_c.py design (outlined bodies); a gdb `step` reaches it |
| next x5 p10_strings.py:9 | `[10, 11, 10, 11, 12]` / `[10, 11, 12, 11, 12]` | the legacy emitter writes one `#line 9` before a statement it spreads over 3 C lines, so the 2nd and 3rd C lines map to 10 and 11 | pyfunc.py (`_debug_site`) |
| finish from inner → middle:7 with 11 | back in middle:7, no "Value returned" | `inner` is `__attribute__((always_inline))` in debug builds too (pyfunc's straight-line predicate). ir/driver.py checks that the IR signature equals the legacy one, so emit_c cannot drop it alone. | pyfunc.py (skip the attribute under AIL_DEBUG=1) |

`info locals` (names k, g, r) and `print n`/`f`/`k`/`g` pass since change 4 below (Python-named locals).

### What changed (ir/emit_c.py, debug builds only)

1. **Statements lowered to no instruction get a line.** A constant assignment folded into a loop's carried value
   (`acc = 0`) or propagated into a call (`n = 42`) used to leave no C line, so gdb could neither break on it nor
   step onto it. Before the next statement's first instruction, the emitter now writes `#line N` +
   `AIL_DBG_SITE("file:N")` for each executable statement line of the function (by `ast`) that no instruction left
   after the passes came from. `I.SRC` also holds the loads and stores that mem2reg removed and the folded `const`s,
   so the lines are taken from the function's live, C-writing instructions. Fixed p01:2, p01:8, p08:9, p08:10.
2. **A branch's closing copies stay on the branch's line.** The region's closing `yield` (the `ir8 = ir11;` copies
   and the `}`) was tagged with the `if`'s line. Now it keeps the line that ran last. Fixed next p01:3.
3. **The wrappers after a function are `<ail-generated>`.** `#line 1 "<ail-generated>"` now comes before the
   list-return / pending / depth wrappers, not after them. They had gone on numbering from the user's last line.
   Fixed p04's stray 4, 5 and the second breakpoint location inside `squares`.
4. **Locals by their Python name** (rerun after review, 2026-11-06). In an IR function with no `try`, each
   int/float local is mirrored into a C variable of its Python name: `int64_t k; /* --debug: the Python local */`
   at the top, and `k = ir1; /* --debug: the Python local */` (under the statement's `#line`) right after the
   instruction that computes the stored value; a parameter's mirror is set at the first statement. The name comes
   from the stores mem2reg removed (still in `I.SRC`) and the statement's AST. No mirror for a name that could go
   stale or clash: a `for` target or a tuple assignment binds it, a store whose value is not computed on that
   statement's line (a loop-carried value), a name that is a C word, a runtime macro's identifier, starts with
   `ail_`, or appears anywhere in the function's C. Every added C line ends with that marker comment, and
   `test_ail_debug_lines` (debug C = release C + `#line` + site lines) now also strips lines ending with it: the
   one edit outside this task's file list, made because the review asked for it. Fixed info locals, print n, f,
   k, g.

cruntime.py is unchanged.

### Locals: the C names

Without the mirror (release builds, functions with a `try`, loop-carried values such as p01's `acc`) gdb shows the
IR path's locals only under their C names. In p08 `calc(n: int, f: float)`: `n` is `v_n`, `f` is `v_f`, `k = n + 1`
is `ir1`, `g = f * 2.0` is `ir2`, `r = g + k` is `ir4` (`ir3` is `(double)k`). The legacy emitter names a local
`v_<name>`, and compiler temporaries `v__tN`. With the mirror, gdb at p08:5 shows `f g k n r` with CPython's values.

A probe (`/tmp/probes/shadowcheck.py`) compares every Python-named local gdb shows at 34 breakpoints over 15 programs
(9 of them typed, with C-word names, `ir1`/`v_n`/`ail_die` names, swaps, reassignments, loops, floats, values from an
attribute, a list item and a dict value) with CPython's `f_locals` at the same line: 0 mismatches.

### Release C byte-identical

`--debug-dir` C of a release build (no `--debug`), origin/integ vs this branch, AIL_NO_CACHE=1 AIL_SERVER=0, over 44
programs: the 20 `lab/compare/src/*/{main,typed}.py`, the 11 `progs/` files and 13 probes (rerun after the locals change).
**40 have byte-identical `program.c`, 0 differ**. The other 4 (`main.py` of chain_relax, rail_transfer, tally_lang and
tree_fold) are refused with the same exit status on both trees, so they write no C (for example chain_relax: an int64
literal out of range). All the changes are gated on AIL_DEBUG=1
(`debug_lines`) and need `I.SRC`, which is filled only in debug builds.

## Follow-ups (outside this lane's files)

1. pyfunc.py class lowering: `#line` for the `__init__` body inside `ail_new_<Class>` (p03_method.py:3).
2. pyfunc.py legacy statements: a `#line` before *every* C line of a statement, as ir/emit_c.py does (p10:9 maps its
   2nd/3rd C lines to 10, 11). The same cause gives the stray lines past the end of the file in p03 (14–21), p04
   (10–20) and p10 (14–24): the module code after the last `#line`.
3. Python-named locals for loop-carried values (p01's `acc`, `i`) and in functions with a `try`: not mirrored yet.
4. pyfunc.py: no `always_inline` under AIL_DEBUG=1, so `finish` shows the value returned.
5. CI: the ubuntu-24.04 image has no gdb. `test_ail_debug_gdb` skips the matrix there (and prints
   `gdb: not installed`), and its readelf part runs. Running the matrix on CI needs `sudo apt-get install gdb` in
   tests.yml, which this lane may not edit.
6. A running `ail_server.py` keeps the compiler modules it loaded. A build sent to it after a source edit uses the
   old emitter, so linecov.py sets AIL_SERVER=0.
