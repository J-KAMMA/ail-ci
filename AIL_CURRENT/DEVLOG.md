# DEVLOG

## 2026-10-24 -- job-pre38: dict(<user instance>) mapping protocol (pre25 q01/q07)

`dict(D())` where `D` has a `keys` method (or a `keys` class / instance attribute) now takes
CPython's mapping protocol: call `keys()` once, then map every key through `__getitem__`.
The class object records the two user methods, and the runtime helper also finds a class or
instance attribute named `keys` (so `keys = [..]` / `keys = ".."` is CPython's
`'list'/'str' object is not callable`). A keys result with no iteration protocol is
`D.keys() returned a non-iterable (type NoIter)`. Iterating an instance with neither
`__iter__` nor `__next__` now names its class (`'D' object is not iterable`), not `instance`.
Both builds agree with CPython on the probes; the pair-sequence error text (pre25 q02) is
unchanged and remains a separate difference. Added `test_ail_pre38.py` (two programs, both
builds).

## 2026-10-23 -- fuzz37: ordering TypeError names the written operator

Fuzzing while loops and counters against CPython on both builds found that an
ordering comparison between built-in values that cannot be ordered raised
`TypeError '<' not supported ...` for every operator.  `while s > 0` with
`s = "5"` printed `'<'` where CPython prints `'>'`, and `<=`, `>`, `>=` and
chained comparisons had the same wrong symbol.  The general-path comparison
helper now receives the operator symbol from `ail_op_lt/le/gt/ge`, passes it
through nested list/tuple comparisons, and uses it in the message; callers such
as sorting keep `<`.  Both builds now match CPython.  `test_ail_fuzz37.py`
keeps the probe.  Also seen but not changed: the general build refuses an
integer literal outside int64 range that the default build accepts, and
`sorted([1, "x"])` names the operand types in the opposite order from CPython
(`'int' and 'str'` instead of `'str' and 'int'`); both are pre-existing.
