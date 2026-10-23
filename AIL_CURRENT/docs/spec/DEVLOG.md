# DEVLOG

## 2026-10-23 - pre22: `with` around `yield` (job-pre22-10240312)

The p12/p23/p24 case still differs on this tree: a generator with `with` around its `yield`
and then `g.close()` runs no `__exit__` at all, because the general path's generator close finishes
the fiber without running the suspended frames (CPython raises `GeneratorExit` there and passes it
to `__exit__`). Building real `GeneratorExit` close semantics is a runtime change outside this job,
so the construct is refused by name before file-lowering removes the `with`:

* `withlib.refuse_with_yield` (called from `pyboxed2.Compiler.compile`) refuses any `with` whose
  body yields in the same function, for every manager expression and for `with open(...)` too.
* `test_ail_pre22.py` covers the refusal on both builds and checks that a `with` beside (not
  around) a `yield` still runs and matches CPython.

## 2026-10-22

- fuzz20: `int.from_bytes` on the general path converted its argument with the `bytes()` constructor
  rules, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned 0 where CPython
  raises TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is
  rejected with CPython's TypeError too (`test_ail_fuzz20.py`).
