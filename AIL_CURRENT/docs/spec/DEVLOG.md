# DEVLOG

## 2026-10-23

- pre24/fuzz67: a class value's `__name__` (`C.__name__`, and through an argument, a list item,
  an instance attribute or a dict value) raised `AttributeError: 'type' object has no attribute
  '__name__'` on both builds. The general path now returns the class-statement name, even when
  the class body assigns `__name__` (CPython keeps the statement name; the assignment only lands
  in the class dict). `test_ail_pre24.py`. The other fuzz67 items are unchanged: `del c.attr` and
  a class-body reference to an earlier class-body name are still refused by name, and
  `C.__qualname__` is not addressed.

## 2026-10-22

- fuzz20: `int.from_bytes` on the general path converted its argument with the `bytes()` constructor
  rules, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned 0 where CPython
  raises TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is
  rejected with CPython's TypeError too (`test_ail_fuzz20.py`).
