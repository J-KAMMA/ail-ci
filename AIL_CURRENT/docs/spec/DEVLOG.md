# DEVLOG

## 2026-10-23

- pre21: the boxed runtime and the unified path's inline float `%` used `fmod`'s zero sign (the
  dividend's) rather than the divisor's, so `0.0 % -3.0` and `-0.0 % 3.0` printed the wrong signed
  zero; nonzero signs were already corrected. Those paths now use `copysign(0.0, divisor)` for a
  zero remainder, matching the typed `ail_ffloormod` (`test_ail_pre21.py`).

## 2026-10-22

- fuzz20: `int.from_bytes` on the general path converted its argument with the `bytes()` constructor
  rules, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned 0 where CPython
  raises TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is
  rejected with CPython's TypeError too (`test_ail_fuzz20.py`).
