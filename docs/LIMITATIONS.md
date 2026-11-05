# AIL limitations and documented differences

These are behaviours a reader might expect to match CPython 3.12 but that AIL deliberately does
not, with the reason and the stop rule. Everything else either matches CPython or is refused by
name (see `DIFFERENCES.md`).

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
