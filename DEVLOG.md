# Development log

## 2026-10-22 — job-fuzz18-10221632: review fix, named class

* The class/function rejection in `_ail_math_checknum` (and `floor` / `ceil`) matched the
  run-time type *name*, so a legal user class named `function` with `__float__` (or
  `__floor__` / `__ceil__`) was refused.  The `type` / `function` names are gone from the
  reject list; on the general path the `__float__` / `__index__` / `__floor__` / `__ceil__`
  `hasattr()` probes now answer from the program's classes, so a real class or function still
  answers False and reaches the CPython `TypeError`, while an instance of a user class with
  that name converts normally.
* `test_ail_fuzz18.py` F8 adds a user class named `function` (with all three dunders and
  `__call__`), an `__index__`-only class, an inner `TypeError` from `__float__`, and reaches
  them directly, through an argument, a list item, a dict value and an attribute.

## 2026-10-22 — job-fuzz18-10221632: review fixes

* `math.floor` / `math.ceil` now call an object's own `__floor__` / `__ceil__` before any
  conversion and return the dunder's result unchanged (CPython returns `J.__floor__()` as
  is); only an object without the dunder falls back to `__float__` / `__index__` conversion.
  int and float arguments are unchanged. The dunder call is kept resolvable on the general
  path by a never-instantiated `_AilMathStub` helper class (pulled in by the floor/ceil
  helpers), and `__floor__` / `__ceil__` are now accepted dunders so the typed path scans
  the stub without refusing it.
* `_ail_math_checknum` rejects `type` and `function` values by name before its `hasattr`
  probe, so `math.sin/sqrt/fsum/floor/...` on a class or function raises CPython's
  `TypeError must be real number, not type` / `... not function` instead of leaking the
  general path's `NotImplementedError hasattr() ...`.
* `test_ail_fuzz18.py` gains F6 (`__floor__` / `__ceil__`, direct/argument/attribute/list/
  dict, dunder results, int/float/bool/inf/NaN/wrong types) and F7 (class/function through
  sin/sqrt/fsum/floor/ceil/copysign/pow/isnan/fabs, argument and list/dict).
* Residual builtin-function/iterator type-name and `hasattr` differences are recorded as
  DIFFERENCES rows C?-job-fuzz18-10221632-3.

## 2026-10-22 — job-fuzz18-10220949: review fixes

* `math.floor` / `math.ceil` now go through helpers that raise CPython's `OverflowError
  cannot convert float infinity to integer` for ±inf (instead of `ValueError ... NaN`),
  keep int/`bool` arguments as ints, and fall back to `__float__`/`__index__` conversion.
* `_ail_math_checknum` converts Fraction and objects with `__float__` (CPython's
  `PyFloat_AsDouble` behaviour) instead of rejecting them; str/bytes/bytearray stay a
  `TypeError must be real number, not ...`.
* `test_ail_fuzz18.py` gains F4 (floor/ceil inf and wrong types) and F5 (Fraction /
  `__float__` objects through arguments, attributes, list items and dict values).

## 2026-10-22 — job-fuzz18-10220949: math / float edge cases

* `math.fsum` now follows CPython's `math_fsum_impl` for non-finite inputs and immediate
  overflow (`ValueError -inf + inf in fsum`, `OverflowError intermediate overflow in fsum`) and
  converts each element to `float`, so a list of ints returns a float.
* Float `//`, `%` and `divmod` now use CPython's `float_divmod` adjustment and half-even
  quotient snap: signed zeros, infinities and NaN match CPython.
* Math helpers that call the C function directly (`sqrt`, the one-argument libm helpers,
  `fabs`, `isnan`/`isinf`/`isfinite`, `hypot`, `atan2`, `copysign`, `fmod`, `pow`, `fsum`)
  check `isinstance(x, (int, float))` and raise CPython's `TypeError` instead of passing a
  pointer-sized value to C as a double.
* Added `AIL_CURRENT/test_ail_fuzz18.py` (3 programs, both builds) and registered it in
  `ail_check.MODULES`.
* Remaining differences are recorded in `DIFFERENCES.md` rows C?-job-fuzz18-10220949-4..8.
