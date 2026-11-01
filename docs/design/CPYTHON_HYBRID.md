# CPython plus fast parts

Status: design + prototype, explicit `ail build --cpython` only (2026-11-01). The standalone build is
unchanged. The prototype lives in `AIL_CURRENT/ail_cpython_hybrid.py`; its test is
`test_ail_cpython_hybrid.py`.

The rule is: **AIL may be faster than CPython, never different from CPython.** A program that CPython
runs must produce CPython's stdout and exit status. If a function cannot preserve that promise for a
particular call, the call goes back to the original Python function.

## 1. Unit of acceleration

The unit is one top-level function. Selection reuses the existing mixed-mode machinery:

* `pymix.analyze` performs the whole-module kind fixed point and names candidates.
* In the hybrid analysis only, a parameter with a complete `int`/`bool`/`float`/`str`/`list[int]`/
  `list[float]` annotation seeds the fixed point. CPython does not enforce annotations, so this is
  only a hint: the boundary checks every argument and falls back on a different type.
* The CLI's Python-surface pass rewrites return annotations to `__ail_checked_*__` contracts.
  Those markers are stripped only inside the hybrid analysis, because `to_c` otherwise refuses a
  checked `str` entry; the Python wrapper still checks the returned value.
* `pyboxed2`'s mixed-mode `_setup_mix` rechecks every candidate by actually calling `pyfunc.to_c`; a
  function participates only if the real typed emitter accepts it.
* `bigcap` marks functions whose ints may leave int64; the mixed-mode overflow wrapper is reused.
* the existing exception rule keeps a function boxed when a typed exception could escape past a
  CPython `try`. The prototype adds no second exception mechanism.
* the prototype additionally refuses a body with any operation that can trap in the typed runtime:
  subscripting (index/key errors), division or power (zero division, complex results), a call (an
  arbitrary side effect or exception), `raise`/`assert`, `try`/`with`/import, `global`/`nonlocal`,
  deletes and attribute/index stores. Those bodies stay in CPython, so a trap cannot bypass the
  caller's `try/except`. This is conservative by design: a missed speed-up is safe.

The analysis runs the real CLI general path in a temporary subprocess and captures the mixed-mode
units it already emits. If the CLI refuses the program, a direct `pyboxed2.build` on the original
source is tried; this still finds independent helpers in a program whose `main` needs an
unpublished library call. If neither build emits a unit, the hybrid is a plain CPython run.

A candidate is wrapped only when all of these hold:

* every parameter is `int`, `bool`, `float`, `str`, `list[int]` or `list[float]`;
* the result is `int`, `bool`, `float` or `str`;
* no list parameter is mutated (directly, by augmented assignment, or by being passed on to another
  program function that could mutate it);
* the function does not print (`print`/`assert` I/O is excluded by `_setup_mix`);
* a function marked as possibly needing a big int is either an int result (the overflow wrapper can
  fall back) or stays in CPython;
* the program has no `is` comparison that could compare numbers to a float candidate (the existing
  C102 identity rule).

Everything else stays in CPython. This includes methods, nested functions, classes, generators,
list/dict/tuple results, and functions with an argument or result kind outside the ABI.

The mixed-mode ABI is int64 in and out. The analysis therefore generates the units with int64
lowering even when the surrounding general build runs with exact ints; the overflow flag sends a
value that does not fit back to the original Python function. This keeps a large CPython int exact
without asking the int64 ABI to carry `ail_tint` parameters.

## 2. The boundary

| Python value | C form | rule |
| --- | --- | --- |
| `int` | `int64_t` | exact `int` only; outside int64 -> fallback |
| `bool` | `int` (0/1) | exact `bool` only; numeric `int` -> fallback |
| `float` | `double` | exact `float` only; `int`/`bool` -> fallback |
| `str` | `ail_str` over UTF-8 bytes | exact `str`, encoded with `PyUnicode_AsUTF8AndSize`; surrogates -> fallback |
| `list[int]` | `const int64_t *, len` | fresh copy; every element exact int inside int64 |
| `list[float]` | `const double *, len` | fresh copy; every element exact float |
| `None`, `dict`, `tuple`, other `list` | -- | fallback to the original function |
| result `int` | `int64_t` -> `PyLong_FromLongLong` | overflow flag -> fallback |
| result `bool` | `int` -> `PyBool_FromLong` | overflow flag -> fallback |
| result `float` | `double` -> `PyFloat_FromDouble` | direct |
| result `str` | UTF-8 length + fill -> `PyUnicode_DecodeUTF8` | invalid UTF-8 -> fallback |

The native function is exposed as a `METH_VARARGS` function. The generated Python module wraps it
in a small closure. Any conversion failure, or the overflow flag set by the typed clone, raises a
private `Fallback` exception; the closure catches it and calls the original Python function with the
same positional arguments. Keyword arguments and wrong arity go straight to the original function,
so CPython's own `TypeError` and defaults are preserved.

Measured per-call cost (Linux x86-64, CPython 3.12, `inc(n) = n + 1`, 2,000,000 calls, median of 5):

```
plain Python function       32.5 ns/call
native extension directly   67.7 ns/call
generated hybrid wrapper   115.4 ns/call
```

So the boundary costs about 83 ns per call over the plain Python function in this prototype (the
Python-level fallback closure accounts for most of it). Acceleration pays when the function itself
does enough work; it is not a win for a one-line arithmetic helper. A future revision can replace the
closure with a C callable type and remove the `try/except` overhead.

## 3. Semantics

**Unbounded ints.** Python ints are unbounded. At the boundary an argument outside int64 is never
truncated: the native call is abandoned and the original function runs. Inside an accelerated int
function the existing tagged-int/overflow wrapper is used. Its `__builtin_*_overflow` stops and
`ail_tint_to_int64` failures set a per-function overflow flag instead of exiting, and the call site
falls back to Python. Thus an argument value, a list item, an attribute or a dict value that reaches
the function through any route produces CPython's exact answer. A value that fits int64 prints what
CPython prints.

**Exceptions.** The typed exception rule from mixed mode is unchanged, and the hybrid adds the
body gate above. A function whose typed closure could raise an exception that would escape a CPython
handler is not accelerated; a function with indexing, division, a call or an explicit raise stays in
CPython (for example `a // b` with a zero divisor and `xs[0]` on an empty list). The same exception
class, message, traceback shape and caller `try/except` behavior are therefore observed. Conversions
never leak a partial result: the wrapper either returns a value or re-enters Python.

**Mutation.** A list parameter is copied into the native call. A function that mutates a list
parameter (item/store/delete, `append`/`extend`/`pop`/..., or passing the list to another program
function that may mutate it) is therefore not accelerated; it remains the original Python function,
so the mutation is visible to the caller. Direct-mutation syntax is refused at selection time, not
silently copied back.

## 4. Parallelism

All native calls are surrounded by `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS`. The arguments
are converted (or copied) while the GIL is held; the typed C body runs with no Python object access
and no GIL; the result is boxed after the GIL is reacquired. A fallback flag is read after
reacquisition before returning to Python.

Typed parallel loops (`# ail: par`, typedpar) compile inside the same typed clone. The extension is
compiled and linked with `-pthread`; if such a clone spawns native threads, they run while the
calling thread has already released the GIL. They do not use CPython objects. Parallel work is
therefore not restricted by the GIL. For a program with a typed parallel plan, the same rule as
every other call applies: if the clone cannot be emitted, the function stays in CPython and its work
runs exactly as CPython runs it.

Free-threaded CPython (3.13t/3.14t) is **not claimed** by this prototype. The wrapper only touches
Python objects with the GIL held and uses public C-API calls, so it should be portable, but it has
not been built or tested on a free-threaded interpreter. A future step should add that build to the
test matrix before claiming support.

## 5. Packaging

`python3 AIL_CURRENT/ail_chatgpt.py build --cpython prog.py -o DIR` writes:

```
DIR/
  prog                         launcher: exec "${AIL_PYTHON:-python3}" DIR/prog.py "$@"
  prog.py                      the original module with a generated preamble and one rebinding
                               after each accelerated top-level def
  prog.orig.py                 the unmodified source, kept for audit/oracle runs
  _ail_prog_fast.<ext>.so      the extension module (typed clones + CPython wrappers)
  build.json                   accelerated names, rejected names/reasons, Python version
```

`prog.py` imports the extension if it is loadable and defines

```python
def f(...): ...
f = _ail_hybrid_make(_ail_hybrid_native.f, f)
```

so later calls (including calls from other functions, which look the name up at call time) use the
native path. If the extension is missing or cannot be imported, `_ail_hybrid_make` returns the
original function and the program is a plain CPython run. The extension is built for the CPython
that ran the build; at run time the launcher must find the same major/minor ABI (the normal CPython
extension rules apply). The source file is never rewritten in place.

The prototype does not switch automatically. A later step may make a refused standalone build fall
back to this layout, but only as an explicit owner decision; the current command is opt-in.

Measured on the prototype's real runs:

* `lab/compare` `berth_sim` and `term_rank` are general-path programs today; the hybrid builds run
  them in CPython and match the interpreter on all 26 and 43 public+hidden cases. On medium inputs
  the hybrid took 0.249 s vs CPython 0.246 s (`berth_sim`, 2.6 MB) and 0.067 s vs 0.065 s
  (`term_rank`, 444 KB); the standalone general builds took 0.528 s and 0.126 s.
* five corpus programs the standalone compiler refuses today (`t440`, `t447`, `t472`, `t437`,
  `t456`) build and match CPython on every `in0`/`in1`/`in2` case. They have no wrappable unit, so
  the hybrid correctly runs the original module.
* the prototype does accelerate a helper in another corpus program: `t264` (`classify`), built and
  compared against CPython. Other candidates examined (`t081` `is_palindrome`, `t139` `fmt`,
  `t211` `evaluate`, `t314` `longest_non_decreasing`) index or call and stay in CPython under the
  no-trap body gate.

## 6. What stays standalone

Programs that fully compile keep today's output byte for byte. `ail compile`, `ail build --project`
and every other default path are untouched by this feature. Even under `--cpython`, a program whose
functions are all accepted still produces a native extension only because the user asked for the
hybrid; the default standalone artifact is never silently replaced by it.
