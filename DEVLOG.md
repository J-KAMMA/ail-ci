# Development log

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
