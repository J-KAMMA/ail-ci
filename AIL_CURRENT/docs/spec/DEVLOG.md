# DEVLOG

## 2026-10-23

- pre20: `chr(0x1F600)` in an untyped program stopped with
  `AIL internal error: chr() non-BMP code point requires 32-bit strings` because the general
  runtime stores UTF-16. A literal non-BMP argument is now refused at build time by name; a
  value only known at run time stops with `AIL limit: chr_non_bmp` instead of an internal
  error. The typed/default path represents the character and still matches CPython
  (`test_ail_pre20.py`).

## 2026-10-22

- fuzz20: `int.from_bytes` on the general path converted its argument with the `bytes()` constructor
  rules, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned 0 where CPython
  raises TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is
  rejected with CPython's TypeError too (`test_ail_fuzz20.py`).
