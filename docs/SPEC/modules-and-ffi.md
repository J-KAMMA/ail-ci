# Modules and FFI

AIL builds a whole program. There is no `exec`, no dynamic import and no module value. The C
boundary is declared and checked, and the hybrid mode is an explicit opt-in. This chapter fixes
those rules.

## MF1 — A program is built whole; dynamic code is refused

**Rule.** The compiler sees every module of the program. It refuses by name, with file and line:

* `eval`, `exec`, `compile`;
* `importlib.import_module`, `__import__`, a dynamic `import` with a computed name;
* `open()` with a mode that is not a literal, where the mode decides text or binary.

```python
code = "print(1)"
exec(code)                    # refused: exec is not part of AIL
```

**CPython.** Runs the code.

**Status.** refused by name.

**Proof.** [`docs/MIGRATING.md`](../MIGRATING.md) 4-8; [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 5, 9;
`test_ail_*` refusal probes.

## MF2 — A function-local import is hoisted or refused

**Rule.** A function-local `import` of a module with no effect at import time is hoisted to module
scope; the function sees the module as a global. If any imported module has an effect at import
time, the local import is refused by name. A top-level import is the ordinary form.

```python
def f():
    import math               # hoisted; math has no import-time effect
    return math.sqrt(2)
```

**CPython.** Executes the import at the call, once, and caches the module.

**Status.** implemented (hoist for the effect-free set; refusal otherwise).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C148.

## MF3 — The standard library is a declared subset

**Rule.** The built library is the subset named in the standard-library census and the limits
page. A name outside the subset is refused by name with the missing name (or the closest list);
it is never silently absent at run time. A subset change is a SPEC change, not an accident of a
build.

```python
import statistics           # built if the name is in the census
import xml.dom.minidom      # refused by name if it is not
```

**CPython.** Has the full standard library.

**Status.** implemented for the declared subset; the subset is the census, not the whole library.

**Proof.** [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 10-12; `lab/stdcensus/RESULTS.md`;
[`AIL_CURRENT/docs/design/STDLIB_REACH.md`](../../AIL_CURRENT/docs/design/STDLIB_REACH.md).

## MF4 — `@extern` declarations are checked

**Rule.** An `@extern` declaration names a C header and a symbol. The compiler compares the
declared parameter and result types with the header's prototype. `trust=True` skips the
comparison for a type the stub language cannot spell; it does not skip the call or the ownership
rules. A declaration whose symbol is missing stops at link time by name.

```python
from ail import extern

@extern("mylib.h")
def fill(buf: bytearray, n: int) -> None: ...
```

**CPython.** Uses `ctypes`, which checks the call at run time.

**Status.** implemented.

**Proof.** [`docs/FFI.md`](../FFI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A63.

## MF5 — FFI integers are range-checked

**Rule.** An integer argument is checked against the declared C width before the call. A result
wider than int64 (`uint64` above 2**63 - 1, an unsigned 64-bit return) is a loud stop unless
exact ints are on. The type is declared in the JSON stub; a `uint64` result on a 64-bit host is
`uint64_bits`.

```python
# extern uint64_t counter(void);
print(counter())              # above 2**63-1: loud stop; exact ints print it
```

**CPython.** `ctypes` returns a Python int of any size.

**Status.** implemented.

**Proof.** [`docs/FFI.md`](../FFI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A1, A69;
`AIL_CURRENT/docs/design/FFI_STAGE3.md`.

## MF6 — Handles, pointers and callbacks

**Rule.** A C pointer is a `bytearray`, a typed array, or an integer handle below 2**63. A
`Handle` frees its resource exactly once; at exit, newest first (this order matters for a
`FILE*` chain). There is no AIL function pointer passed to C; a callback must be a module-level
`def` (MF9). A resource freed twice is a loud stop, not double free.

```python
from ail.ffi import Handle

h = Handle(open_resource())
h.close()
```

**CPython.** Has `ctypes` and the same hazards.

**Status.** implemented for the declared forms.

**Proof.** [`docs/FFI.md`](../FFI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A63.

## MF7 — The CPython hybrid is explicit

**Rule.** `ail build --cpython prog.py -o prog` builds a binary in which the selected top-level
functions run natively and the rest of the Python program runs on CPython. At each boundary the
hybrid copies a typed list in and out and refuses a call that mutated its list argument; any
boundary failure runs the original Python function. The standalone build (`ail build`) is not
changed by this flag.

```bash
ail build --cpython prog.py -o prog
```

**CPython.** The original program.

**Status.** implemented (opt-in; not the default, and not the compatibility mode of CM2).

**Proof.** [`docs/design/CPYTHON_HYBRID.md`](../design/CPYTHON_HYBRID.md); `test_ail_cpython_hybrid`.

## MF8 — A module is a name at each use

**Rule.** A module object cannot be stored, passed, returned or compared. `m = math` and
`return math` are refused; `math.sqrt(...)` at the use is the form. The same holds for
`sys.stdin` and `sys.stdout` used as plain values: call `sys.stdout.write(...)` or use
`print(...)`.

```python
m = math                      # refused: a module is not a value
print(math.sqrt(2))           # correct
```

**CPython.** A module is an ordinary object.

**Status.** refused.

**Proof.** [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 8, 13.

## MF9 — A callback must be a module-level `def`

**Rule.** A callback passed to C must name a module-level `def`. A lambda, a closure, a method or
a variable holding a function is refused. `retain=True` and `threads=True` are refused (CO9). The
callback's arguments and result must use the FFI-safe types.

```python
@extern("mylib.h")
def on_item(x: int) -> int: ...

apply(on_item)                # correct
apply(lambda x: x + 1)        # refused
```

**CPython.** A `ctypes` callback may be any callable, with the corresponding lifetime hazards.

**Status.** refused.

**Proof.** [`docs/FFI.md`](../FFI.md); [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) "FFI".
