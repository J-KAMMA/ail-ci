# Migrating-from-Python checklist: measured results

Measured on branch `job-docmigr1-11060315` (base `origin/integ`) with CPython 3.12.3 as the
oracle. Each row is one sample in this directory. The build command is

    python3 -B AIL_CURRENT/ail_chatgpt.py compile <sample>.py -o <exe>

in the default mode (`AIL_UNIFIED_FORCE` unset). The classes are those of
`docs/MIGRATING.md`:

- **same** — stdout and the exit status equal CPython's.
- **loud stop** — non-zero exit with the named error on the last line of stderr.
- **refused** — the build fails with the quoted text.

| # | Sample | Class | CPython 3.12 | AIL (default build) |
|---|---|---|---|---|
| 1 | `int64_overflow.py` | loud stop | `9223372036854775808`, exit 0 | `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)`, exit 1 |
| 2 | `exact_int.py` | loud stop (same with `--exact-int`) | `18446744073709551614`, exit 0 | `OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)`, exit 1; built with `--exact-int` it prints `18446744073709551614`, exit 0 |
| 3 | `recursion.py` | same | `RecursionError: maximum recursion depth exceeded`, exit 1 | `RecursionError: maximum recursion depth exceeded`, exit 1 |
| 4 | `eval.py` | refused | `2`, exit 0 | build refuses: `the name 'eval' is not a known function/class/builtin` |
| 5 | `exec.py` | refused | `2`, exit 0 | build refuses: `exec() is not built: this language compiles the whole program ahead of time, so there is no source text to run at run time.` |
| 6 | `compile_builtin.py` | refused | `2`, exit 0 | build refuses: `the name 'compile' is not a known function/class/builtin` |
| 7 | `dynamic_import.py` | refused | `3.0`, exit 0 | build refuses: `importlib.import_module (not yet published in NAMES_library.json)` |
| 8 | `dunder_import.py` | refused | `3.0`, exit 0 | build refuses: `call to __import__(); a program is built whole, so a module name cannot be chosen at run time` |
| 9 | `catch_systemexit.py` | refused | `caught`, exit 0 | build refuses: `a caught exception type SystemExit (only builtin or user Exception subclasses are supported)` |
| 10 | `bare_except_exit.py` | refused | `caught`, exit 0 | build refuses: `a bare except: in a program that calls sys.exit(): CPython's bare except also catches the SystemExit, and sys.exit() ends the program here.` |
| 11 | `complex_power.py` | refused | `(1.2246467991473532e-16+2j)`, exit 0 | build refuses: `a negative number raised to a fractional power is a complex number in Python, and AIL has no complex type` |
| 12 | `complex_literal.py` | refused | `(1+2j)`, exit 0 | build refuses: `a constant of type complex` |
| 13 | `regex_group.py` | loud stop | `None`, exit 0 | `ValueError: re: the group did not take part in the match (None is not built)`, exit 1 |
| 14 | `negative_exponent.py` | loud stop | `0.5`, exit 0 | `negative exponent on an integer; write float(x) ** n for Python's float answer`, exit 1 |
| 15 | `open_mode.py` | refused | writes `out.txt`, exit 0 | build refuses: `open() with a mode that is not a string literal: the file kind (text or binary) has to be known when the program is built.` |
| 16 | `open_encoding.py` | refused | `hi`, exit 0 | build refuses: `open(encoding='utf-16'): only utf-8, ascii and latin-1 are built.` |
| 17 | `uncaught_error.py` | same | empty stdout, `ValueError: negative` on stderr, exit 1 | empty stdout, `ValueError: negative` on stderr (no traceback), exit 1 |
| 18 | `threads.py` | same | `thread ran`, exit 0 | `thread ran`, exit 0 (built on the general path; two `note:` lines, one naming the interpreter lock) |
| 19 | `no_pyc.py` | refused | `FileNotFoundError: ... 'sample.py'`, exit 1 | build refuses: `py_compile.compile (not yet published in NAMES_library.json)` |
| 20 | `stdlib_refusal.py` | refused | `demo`, exit 0 | build refuses: `argparse.ArgumentParser (not yet published in NAMES_library.json)` |
| 21 | `range_overflow.py` | same | `OverflowError: Python int too large to convert to C ssize_t`, exit 1 | `OverflowError: integer overflow in range() (ints are 64-bit; --exact-int gives exact ints)`, exit 1 |

With `--strict`, `threads.py` is refused (exit 3) instead of built on the general path; the
default build prints the `note:` line quoted above.

## Bugs

The stop rule found one silent wrong output. It is not an item; it is listed here so it is not
mistaken for declared behaviour.

| Sample | Class | CPython 3.12 | AIL (default build) |
|---|---|---|---|
| `str_is.py` (see below) | silent | `True`, exit 0 | `False`, exit 0 |

    a = "x" + "y"
    b = "xy"
    print(a is b)

Section B of `docs/spec/DIFFERENCES.md` says `is` / `is not` on `str` is refused. This program
builds on the general path and prints `False` where CPython prints `True`, with no stop. That is
a bug against the declared refusal, reported rather than documented as an item.

## Not probed further

`int.from_bytes(bytes([255] * 8), "big", signed=False)` makes the default build fail with exit 4
and a generated-C error, not a named refusal. It is outside this checklist.
