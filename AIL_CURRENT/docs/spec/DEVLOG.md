# DEVLOG

## 2026-10-24 - pre134: refuse `del` of a class name by name

`class C: pass; del C` made both builds fail with the compiler's own `KeyError: 'C'`.
A class name is read from its dedicated class slot, not an ordinary frame/global slot,
so deleting the binding cannot be cleared the way a local or module variable is. The
construct is now refused by name at compile time (`del on the class name C`); deleting
ordinary globals, locals, list/dict items and slices is unchanged and still matches
CPython on both builds. Added `test_ail_pre134.py`.

## 2026-10-22

- fuzz20: `int.from_bytes` on the general path converted its argument with the `bytes()` constructor
  rules, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned 0 where CPython
  raises TypeError. Only bytes-like objects and iterables of ints are accepted now; a str is
  rejected with CPython's TypeError too (`test_ail_fuzz20.py`).
## 2026-10-23 -- fuzz51: explicit None fillchar on bytes padding

Fuzzing the string-method area found a silent wrong answer in `bytes` and
`bytearray`: `ljust`, `rjust` and `center` used `None` as the sentinel for an
omitted fillchar, so an explicit `None` was treated as the default space.
CPython raises `TypeError: ljust() argument 2 must be a byte string of length 1,
not None` (and likewise for the other two). The generated wrappers now use a
private sentinel, and an explicit `None` is rejected with CPython's wording on
both builds. Omitted and valid bytes/bytearray fillchars are unchanged.
`test_ail_fuzz51.py` keeps the probe.

Also seen, not changed: `bytes.strip(None)`/`lstrip(None)`/`rstrip(None)` are
refused by name although CPython accepts them, and a bytes fillchar of the wrong
type raises a different TypeError message (both pre-existing, not silent).
