# Migrating from Python: the checklist

AIL compiles Python syntax ahead of time. A library of programs builds and prints exactly what
CPython 3.12 prints, or the build says why it cannot. This page is the short list of differences a
Python user meets *before* the first build: the programs that build but behave differently on
purpose. [PORTING.md](PORTING.md) covers the refusals and the rewrite for each one; this page
covers the declared behaviour. The full declarations are in
[spec/DIFFERENCES.md](spec/DIFFERENCES.md), and the first build is in [QUICKSTART.md](QUICKSTART.md).

Every item below has a sample in [`lab/migrating/`](../lab/migrating/), and
[`lab/migrating/RESULTS.md`](../lab/migrating/RESULTS.md) records what CPython 3.12 and the AIL
default build print for it. The test `AIL_CURRENT/test_ail_docs_migrating.py` runs every sample
under both and checks the class. Three classes appear:

- **same** — stdout and the exit status are CPython's.
- **loud stop** — the program exits non-zero with a named error on stderr. It never prints a
  different value.
- **refused** — the build fails and names the construct. There is no executable.

## Checklist

- [ ] 1. An int result outside int64 stops with `OverflowError`; CPython prints the big number.
- [ ] 2. Exact big ints need `--exact-int` (or `AIL_EXACT_INT=1`); the default is int64 for speed.
- [ ] 3. Deep recursion stops at the real C stack limit, not at CPython's 1,000 frames.
- [ ] 4. `eval()` is refused; write the expression in the program.
- [ ] 5. `exec()` is refused; write the statements in the program.
- [ ] 6. `compile()` is refused.
- [ ] 7. Dynamic `import` through `importlib.import_module` is refused.
- [ ] 8. `__import__()` is refused.
- [ ] 9. `except SystemExit` is refused; `sys.exit()` ends the process here, it is not an exception.
- [ ] 10. A bare `except:` in a program that calls `sys.exit()` is refused.
- [ ] 11. A complex result is refused; AIL has no complex type.
- [ ] 12. A complex literal is refused.
- [ ] 13. An `re` group that did not match raises `ValueError`, where CPython returns `None`.
- [ ] 14. An integer raised to a negative exponent stops; CPython returns a float.
- [ ] 15. `open()` needs a literal mode, so the text/binary kind is known at build time.
- [ ] 16. `open()` accepts only utf-8, ascii and latin-1; another encoding is refused.
- [ ] 17. An uncaught exception prints `Kind: message` with no traceback; the exit status is CPython's.
- [ ] 18. Threads are built on the general path under one interpreter lock; a `note:` line says so.
- [ ] 19. `py_compile` and byte-code caching are refused; a build is one executable, no `.pyc`.
- [ ] 20. A standard module that is not built is refused by name; the stdlib table lists which build.
- [ ] 21. A `range` whose length leaves int64 stops, as CPython's `len()` does.

---

## 1. Int64 overflow stops

```python
x = int("9223372036854775807")
y = x + 1
print(y)
```

- CPython: `9223372036854775808`, exit 0.
- AIL: **loud stop**. `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives
  exact ints)`, exit 1. Stdout is flushed first.

**What to do instead:** keep values inside int64, or build with `--exact-int` (item 2). A literal
that does not fit is refused at build time rather than at run time. See
[spec/DIFFERENCES.md](spec/DIFFERENCES.md) A1 and [PORTING.md](PORTING.md) section 14.

## 2. Exact big ints are opt-in

```python
x = int("9223372036854775807")
y = x * 2
print(y)
```

- CPython: `18446744073709551614`, exit 0.
- AIL default: **loud stop**. `OverflowError: integer overflow in * (ints are 64-bit; --exact-int
  gives exact ints)`, exit 1. Built with `--exact-int`: **same as CPython**, exit 0, about 20x
  slower.

**What to do instead:** build with `--exact-int` or set `AIL_EXACT_INT=1` for programs that need
CPython's arbitrary precision. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A1 and
[docs/design/BIGINT.md](design/BIGINT.md).

## 3. Deep recursion stops at the stack limit

```python
def down(n: int) -> int:
    if n == 0:
        return 0
    return down(n - 1) + 1

print(down(60000))
```

- CPython: `RecursionError: maximum recursion depth exceeded`, exit 1.
- AIL: **same**. The same `RecursionError` class and text, exit 1. The guard is 50,000 frames, not
  1,000, so a depth between the two succeeds here and fails in CPython; `sys.setrecursionlimit` is
  ignored.

**What to do instead:** convert deep recursion to a loop, or keep the depth well under 50,000. See
[spec/DIFFERENCES.md](spec/DIFFERENCES.md) A3.

## 4. `eval()` is refused

```python
print(eval("1 + 1"))
```

- CPython: `2`, exit 0.
- AIL: **refused**. `the name 'eval' is not a known function/class/builtin`.

**What to do instead:** write the expression in the program. The compiler sees the whole program
before it runs. See [PORTING.md](PORTING.md).

## 5. `exec()` is refused

```python
code = "x = 2"
exec(code)
print(x)
```

- CPython: `2`, exit 0.
- AIL: **refused**. `exec() is not built: this language compiles the whole program ahead of time,
  so there is no source text to run at run time.`

**What to do instead:** write the statements in the program, or call the function directly. See
[PORTING.md](PORTING.md).

## 6. `compile()` is refused

```python
c = compile("1 + 1", "<s>", "eval")
print(eval(c))
```

- CPython: `2`, exit 0.
- AIL: **refused**. `the name 'compile' is not a known function/class/builtin`.

**What to do instead:** there is no run-time compiler in the executable. See
[PORTING.md](PORTING.md).

## 7. Dynamic `import` is refused

```python
import importlib

m = importlib.import_module("math")
print(m.sqrt(9))
```

- CPython: `3.0`, exit 0.
- AIL: **refused**. `importlib.import_module (not yet published in NAMES_library.json)`.

**What to do instead:** write `import math` at the top of the program; a module name cannot be
chosen at run time. See [PORTING.md](PORTING.md).

## 8. `__import__()` is refused

```python
m = __import__("math")
print(m.sqrt(9))
```

- CPython: `3.0`, exit 0.
- AIL: **refused**. `call to __import__(); a program is built whole, so a module name cannot be
  chosen at run time`.

**What to do instead:** as item 7.

## 9. Catching `SystemExit` is refused

```python
import sys

try:
    sys.exit(3)
except SystemExit:
    print("caught")
```

- CPython: `caught`, exit 0.
- AIL: **refused**. `a caught exception type SystemExit (only builtin or user Exception subclasses
  are supported)`.

**What to do instead:** `sys.exit()` ends the process here; it is not an exception. Call it at the
point where the program should stop, or structure the code so it can return. See
[spec/DIFFERENCES.md](spec/DIFFERENCES.md) A54 and [PORTING.md](PORTING.md) section 5.

## 10. A bare `except:` around `sys.exit()` is refused

```python
import sys

try:
    sys.exit(3)
except:
    print("caught")
```

- CPython: `caught`, exit 0.
- AIL: **refused**. `a bare except: in a program that calls sys.exit(): CPython's bare except also
  catches the SystemExit, and sys.exit() ends the program here.`

**What to do instead:** write `except Exception:`, which both languages treat the same for every
exception the program can raise. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A54.

## 11. Complex results are refused

```python
print((-4.0) ** 0.5)
```

- CPython: `(1.2246467991473532e-16+2j)`, exit 0.
- AIL: **refused**. `a negative number raised to a fractional power is a complex number in Python,
  and AIL has no complex type; take the absolute value first or use an integer exponent`.

**What to do instead:** take `abs()` first, use an integer exponent, or use `cmath`-free real
arithmetic. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) C5 and [PORTING.md](PORTING.md).

## 12. Complex literals are refused

```python
z = 1 + 2j
print(z)
```

- CPython: `(1+2j)`, exit 0.
- AIL: **refused**. `a constant of type complex`.

**What to do instead:** keep the real and imaginary parts in two floats, or drop the complex
arithmetic.

## 13. A regex group that did not match

```python
import re

m = re.match("(a)|(b)", "a")
print(m.group(2))
```

- CPython: `None`, exit 0.
- AIL: **loud stop**. `ValueError: re: the group did not take part in the match (None is not
  built)`, exit 1.

**What to do instead:** test with `m.group(2) is not None`-style logic replaced by a separate
pattern, or use `m.group(0)`. AIL has no `None` for `str`. See
[spec/DIFFERENCES.md](spec/DIFFERENCES.md) A8.

## 14. A negative integer exponent stops

```python
def power(b: int, n: int) -> int:
    return b ** n

print(power(2, -1))
```

- CPython: `0.5`, exit 0.
- AIL: **loud stop**. `negative exponent on an integer; write float(x) ** n for Python's float
  answer`, exit 1.

**What to do instead:** write `float(2) ** -1`. A constant negative exponent already gives the
float. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A5.

## 15. `open()` needs a literal mode

```python
name = "out.txt"
mode = "w"
f = open(name, mode)
f.write("hi")
f.close()
```

- CPython: writes `out.txt`, exit 0.
- AIL: **refused**. `open() with a mode that is not a string literal: the file kind (text or
  binary) has to be known when the program is built.`

**What to do instead:** write `open(name, "w")` with the mode spelled out. See
[PORTING.md](PORTING.md) section 8 and [spec/DIFFERENCES.md](spec/DIFFERENCES.md) section B.

## 16. Only three text encodings

```python
path = "data.txt"
with open(path, "w", encoding="utf-16") as f:
    f.write("hi")
with open(path, "r", encoding="utf-16") as f:
    print(f.read())
```

- CPython: `hi`, exit 0.
- AIL: **refused**. `open(encoding='utf-16'): only utf-8, ascii and latin-1 are built.`

**What to do instead:** use the default utf-8, or read the bytes with `"rb"` and decode them
yourself. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A16 and section B.

## 17. An uncaught exception has no traceback

```python
def check(n: int) -> int:
    if n < 0:
        raise ValueError("negative")
    return n

print(check(-1))
```

- CPython: empty stdout, a traceback ending `ValueError: negative`, exit 1.
- AIL: **same** for stdout and the exit status: empty stdout, `ValueError: negative` on stderr,
  exit 1. The traceback is absent by design; stderr text is outside the promise.

**What to do instead:** nothing for the exit status. Print what you need to diagnose before
raising. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A4.

## 18. Threads run on the general path under one lock

```python
import threading

def work() -> None:
    print("thread ran")

t = threading.Thread(target=work)
t.start()
t.join()
```

- CPython: `thread ran`, exit 0.
- AIL: **same**, exit 0, with two `note:` lines on stderr. The first says the program is built on
  the general path because the thread modules are built there only, under one interpreter lock
  with CPython's GIL semantics.

**What to do instead:** nothing for correctness. Threads are about 20x slower than the typed path;
a program that needs speed should use the typed parallel shapes. `--strict` refuses this program
instead of building it on the general path. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A38 and
A62.

## 19. One executable: no `.pyc`, no byte-code compiler

```python
import py_compile

py_compile.compile("sample.py")
```

- CPython: `FileNotFoundError: ... 'sample.py'`, exit 1.
- AIL: **refused**. `py_compile.compile (not yet published in NAMES_library.json)`.

**What to do instead:** nothing to do; a build is a single executable and writes no `.pyc` and no
`__pycache__`. Local modules are compiled in. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md)
section B.

## 20. A standard module that is not built is refused by name

```python
import argparse

parser = argparse.ArgumentParser(prog="demo")
print(parser.prog)
```

- CPython: `demo`, exit 0.
- AIL: **refused**. `argparse.ArgumentParser (not yet published in NAMES_library.json)`.

**What to do instead:** pick a module from the stdlib table, or write the small part you need by
hand. The census that lists which modules build is
[`lab/stdcensus/RESULTS.md`](../lab/stdcensus/RESULTS.md); the built modules are listed there per
name, with the first refusal reason for the rest.

## 21. A `range` length that leaves int64 stops

```python
n = int("9223372036854775807")
r = range(-n, n)
print(len(r))
```

- CPython: `OverflowError: Python int too large to convert to C ssize_t`, exit 1.
- AIL: **same** for stdout and the exit status: empty stdout, `OverflowError: integer overflow in
  range() (ints are 64-bit; --exact-int gives exact ints)` on stderr, exit 1.

**What to do instead:** keep the range within int64, or use `--exact-int`. See
[spec/DIFFERENCES.md](spec/DIFFERENCES.md) A1 and C71.

---

The `--strict` build refuses any program that only the general path would accept, with every
blocker listed (exit 3); the default build falls back and prints one `note:` line. If you want the
typed path or a refusal, add `--strict`. See [spec/DIFFERENCES.md](spec/DIFFERENCES.md) A62.
