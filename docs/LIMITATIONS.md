# Limitations in AIL 0.1

AIL compiles a Python program to C, or refuses it at compile time with a message that names the
construct. It is not CPython: this page lists the limits a person writing a small command-line tool
meets first, what the compiler says when they hit one, and what to write instead. Every entry is
backed by a program in `lab/limits/`, and `AIL_CURRENT/test_ail_limits.py` re-runs that program and
checks the behaviour recorded here. When a limit below is lifted the test fails and asks for this
page and `lab/limits/expected.json` to be updated.

Two conventions used throughout:

- a refusal exits non-zero (2 for a syntax or size limit, 3 for a construct outside the subset) and
  prints its message on stderr; the message below has the leading `file.py:line:column:` location
  removed;
- without `--strict` the default build may fall back to the general path (about 20x slower, same
  output) and prints a `note: ... built on the general path` line on stderr.

`docs/PORTING.md` has the most common refusals with a before/after rewrite each; this page links to
it instead of repeating the rewrites.

## Language

### 1. An integer literal beyond int64

`int` is a signed 64-bit integer in the default build. A literal (or constant expression) that needs
a wider value is refused when the program is built, not at run time:

```text
int64 constant expression out of range: 99999999999999999999
```

Keep the value inside int64, or compile with `--exact-int` (`AIL_EXACT_INT=1`) for CPython's exact
big integers, which is about 20x slower. `docs/PORTING.md` section 14 shows the rewrite.

Probe: `lab/limits/01_int_literal_beyond_int64.py` (CPython prints `100000000000000000000`).

### 2. Integer overflow at run time

A value produced by arithmetic or read from text stops loudly when it leaves int64 instead of
wrapping or silently widening. The program keeps the stdout it already wrote and exits 1:

```text
OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)
```

The same rule covers `-`, `*`, `//`, `%`, `**`, `abs()`, `round()` and an `int()` conversion. Use
`--exact-int` when a tool must handle arbitrary-sized integers. A loud stop is deliberate: AIL never
returns a wrapped value.

Probe: `lab/limits/02_int_overflow_runtime.py` (CPython prints `9223372036854775807` then
`9223372036854775808`, on two lines).

### 3. A dictionary view kept in a name

A view is live in CPython: it follows a later store and a loop over it raises when the dict changes
size. AIL has no view object, so the direct form `x = d.items()` would be a snapshot and is refused:

```text
not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 2): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.items()` where it is used, or keep `list(d.items())` for a snapshot
```

Call `d.items()` / `d.keys()` / `d.values()` where it is used, or take `list(...)` when a snapshot is
wanted. `docs/PORTING.md` section 1 has the before/after pair.

The refusal fires when the view is stored: bound to a name, assigned to a field or an item, or put in
a list or dict container (`b.v = d.items()`, `m["k"] = d.items()`, `xs = [d.items()]`). It does not
catch a view passed straight into a call (`f(d.items())`) or returned from a function: those build on
the general path, with the `dict.items used as a value` note, and can then print a stale snapshot
with no error. That case is recorded under "Silent differences found" at the end of this page.

Probe: `lab/limits/03_dict_view_is_snapshot.py` (CPython prints `[('a', 1), ('b', 2)]`).

### 4. `with` around a `yield`

A generator may not hold a `with` block across a yield, because closing the generator would not pass
`GeneratorExit` to `__exit__`:

```text
not in the subset: `with` around a `yield`: closing the generator does not pass GeneratorExit to __exit__ (not built)
```

No workaround yet. Keep the resource open for the whole loop (open it outside the generator), or
build a list with `out.append(x)` and `return out` instead of yielding from inside the block.

Probe: `lab/limits/04_with_around_yield.py` (CPython prints `[1]`).

### 5. `open()` with a mode that is not a string literal

The file kind (text or binary) has to be known when the program is built, so the mode must be a
literal:

```text
not in the subset: open() with a mode that is not a string literal: the file kind (text or binary) has to be known when the program is built.
```

Write the mode out (`open(path, "r")` or `open(path, "rb")`). A command-line flag that selects a
mode needs one `if` with a literal `open()` in each branch. `docs/PORTING.md` section 8 has the
rewrite.

Probe: `lab/limits/05_open_mode_not_literal.py` (CPython prints `True`).

### 6. A decorator other than `@staticmethod` and `@lru_cache`

A decorator runs arbitrary code when the function is defined, so only `@staticmethod` on a method and
`@functools.lru_cache` / `@lru_cache` / `@cache` are modelled:

```text
not in the subset: the decorator on def bump (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)
```

Write the wrapping as an ordinary call (`bump = deco(bump)` is not enough for the same reason; call
the helper explicitly where the function is used). `docs/PORTING.md` section 4 shows the rewrite.

Probe: `lab/limits/06_unsupported_decorator.py` (CPython prints `20`).

### 7. Multiple inheritance

A class may have at most one base:

```text
not in the subset: multiple inheritance in class C
```

No workaround yet beyond flattening the hierarchy into one base class or composition (an attribute
holding the other object). Mixin-style code that only inherits helpers needs the helpers copied or
moved to a free function.

Probe: `lab/limits/07_multiple_inheritance.py` (CPython prints `C`).

### 8. A module used as a plain value

A module must be named at each use; it cannot be passed, stored or compared:

```text
not in the subset: the module sys used as a plain value
```

Write `sys.maxsize` where it is used. For a value that must be forwarded (a flag, a stream), pass the
one object or callable you need instead of the module. `docs/PORTING.md` section 10 has the rewrite.

Probe: `lab/limits/08_module_used_as_value.py` (CPython prints `True`).

### 9. `eval` and `exec`

The builtins are not available, so a program that interprets source text is refused:

```text
not in the subset: the name 'eval' is not a known function/class/builtin; did you mean 'eval'?
```

No workaround yet. Replace the dynamic form with explicit code: parse the text with `int()` /
`float()` / `json.loads` where the shape is known, or switch on the command name instead of building
a string.

Probe: `lab/limits/09_eval_not_available.py` (CPython prints `3`).

## Standard library

The pure-Python stdlib census (`lab/stdcensus/RESULTS.md`) finds 3 of 197 modules built in the
default mode. Anything not listed as built is refused by name, and the refusal usually names the
first missing function.

### 10. `argparse`

`argparse` is refused at its first use (`NAMES_library.json` does not publish it):

```text
not in the subset: argparse.ArgumentParser (not yet published in NAMES_library.json)
```

No workaround yet. Read `sys.argv` directly (AIL builds `len`, indexing and `int()` conversions) and
write the usage text yourself; keep the parsing at the top of `main`, one branch per flag.

Probe: `lab/limits/10_argparse_refused.py` (CPython prints nothing on stdout and exits 2; the usage
line and `error: the following arguments are required: name` go to stderr).

### 11. `os` functions that are not built

Only a fixed set of `os` names is available; the refusal lists what is built:

```text
not in the subset: os.system is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath
```

Use the listed functions. `os.system`, `os.spawn*` and `os.fork` are not built; run a child process
with `subprocess.run([...])` or `subprocess.check_output([...])`, which are built on the typed path
and need no general-path fallback (`subprocess.Popen` is still refused).

Probe: `lab/limits/11_os_system_not_built.py` (CPython prints `0` then `True`).

### 12. `tempfile` and most of the stdlib

A module outside the built set is refused at its first name, for example:

```text
not in the subset: tempfile.mkdtemp (not yet published in NAMES_library.json)
```

Build the path yourself (`os.getenv("TMPDIR")` or `/tmp` plus a counter, then `os.mkdir`), or pass
the path in from the shell. The full list of what is built is in `lab/stdcensus/RESULTS.md`; the
names that are built are the ones the refusal prints for `os` and the modules in
`AIL_CURRENT/stdlib/`.

Probe: `lab/limits/12_tempfile_not_built.py` (CPython prints `True`).

### 13. `sys.stdin` kept in a name

A stream has to be named at each use, like a module:

```text
not in the subset: sys.stdin used as a plain value
```

Read with `sys.stdin.read()` or `sys.stdin.readline()` at the point of use, or read everything into
a `str` once and work on that. `docs/PORTING.md` section 9 has the rewrite.

Probe: `lab/limits/13_sys_stdin_as_value.py` (CPython prints `False`).

## Speed and build

Two kinds of slowdown a tool author notices before any wrong output. Both build and print exactly
what CPython prints; only the build note and the running time differ.

### 14. Threads run on the general path

`threading`, `queue` and `concurrent.futures` are built on the general path only, so a program that
uses them anywhere is compiled there and prints:

```text
note: ... built on the general path (about 20x slower) because threading, queue and concurrent.futures are built on the general path only (one interpreter lock, CPython's GIL semantics); this program is compiled there
```

One interpreter lock, CPython's GIL semantics. `ThreadPoolExecutor.map` (and `Pool.map`) over a typed
module-level function does run on the typed path; a plain `Thread` started and joined in one block, as
in the probe, still keeps the general path and prints the note above, so a small tool that starts one
thread pays the lock. For CPU-bound work, split the input into files and run several processes from
the shell instead.

Probe: `lab/limits/14_threads_general_path.py` (CPython prints `5`; AIL prints `5` too).

### 15. An untyped `json.loads()` falls back to the general path

Without a declared result type the typed lowering cannot pick a representation, so the whole program
is built on the general path:

```text
note: ... built on the general path (about 20x slower) because json.loads(s): the type of the result is not declared here; write the type down: `data: dict[str, int] = json.loads(s)` (the types are int, float, str, bool, list[T], list[list[T]], dict[str, T])
```

Write the type down inside a function: an annotated local (`data: dict[str, int] = json.loads(text)`
in a `def`), an annotated parameter (`def use(data: dict[str, int])` called with `json.loads(...)`),
or an annotated return type (`def load(text) -> dict[str, int]: return json.loads(text)`). An
annotation on a module-level assignment is not read by the lowering, so `data: dict[str, int] =
json.loads(text)` at the top of a file still takes the general path. The output is the same either
way; only the speed changes, and `--strict` turns the note into a refusal so a build script can catch
it.

Probe: `lab/limits/15_untyped_json_general_path.py` (CPython prints `1`; AIL prints `1` too).

## Silent differences found

One gap is recorded here rather than as a limitation, because nothing stops the program: the check in
entry 3 catches a view stored in a name, field, item or container, but not one returned straight from
a function. A view returned from a function builds on the general path (with the `dict.items used as
a value` note) and then prints a stale snapshot with exit status 0:

```python
def view(d):
    return d.items()

d = {"a": 1}
v = view(d)
d["b"] = 2
print(list(v))
```

CPython prints `[('a', 1), ('b', 2)]`; AIL prints `[('a', 1)]`. Keep `list(d.items())` when the result
leaves the function, or read the dict again at the point of use.

Every probe in `lab/limits/` either matches CPython's stdout and exit status or is refused by name; the
program above is the only silent difference found.

## Recursion depth

AIL does **not** emulate CPython's default recursion limit of 1000. Recursion runs on the real C
stack, so a depth that fits keeps working: `descend(5000)` completes and prints its result, where
CPython raises `RecursionError` at its default limit. This is an owner decision (2026-11-05);
`lab/safety/stops/09_rec_deep5000.py` is classified as a **documented difference**, not as a
silent-wrong row.

Only an actual stack exhaustion stops the program. It stops loudly and by name:

- the general path (and the default build for a recursive method or nested function) performs a
  real stack check at each generated function entry: the lowest address of the activation's frame
  is compared with `cx->stack_limit`, the lowest address the current OS stack may still touch
  (`RLIMIT_STACK` for the main thread, the thread's mapped bounds for a thread, the generator's own
  buffer for a generator body), and it raises `RecursionError("maximum recursion depth exceeded")`
  through its ordinary exception path while a 64 KiB reserve is left for the raise. `except
  RuntimeError` and `except RecursionError` catch it and a `finally` runs. There is no frame
  count, so a depth that fits the real stack keeps working, and a function with many locals is
  stopped before it overflows. When `RLIMIT_STACK` is unlimited the main stack is taken to be
  1 GiB (256 MiB on a 32-bit address space), a conservative bound far below the first other
  mapping, so a real exhaustion still stops by name rather than faulting and depth 300000
  completes;
- a `yield from` chain has no frame cap either: each generator runs on its own mapped stack, so
  the stack check cannot see the Python nesting, and the chain keeps working until the OS can no
  longer provide a stack; the resume then raises the same `RecursionError`, never a silent stop;
- the typed path keeps its own check at `AIL_MAX_RECURSION_DEPTH` (50000) and reports the same
  name. A caught trap is a real `RecursionError` instance when the program can observe the class
  (it names `RecursionError` or binds an `as e`): `type(e).__name__`, `repr(e)`, `isinstance` and
  `type(e) is` agree with CPython, and `except RecursionError` does not take plain RuntimeErrors;
- an uncaught one exits 1 with `RecursionError: maximum recursion depth exceeded` as the last
  stderr line. It never dies with a bare signal and empty stderr.

The general path's limit is therefore the real stack, not a constant: on an 8 MiB stack a
small-frame recursion reaches about 20000 frames (CPython stops at 1000), and a function with
about 60 locals stops by name where it used to segfault.
