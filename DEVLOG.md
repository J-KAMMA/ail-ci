# Development log

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
