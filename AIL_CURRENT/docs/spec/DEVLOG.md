# DEVLOG

## 2026-10-24

- pre16 p5: `Counter < <= > >=` raised `TypeError` on both builds because a Counter is a flagged
  dict and the comparison fell through to the plain dict check. CPython 3.12 compares the union of
  both operands' keys with a missing count read as 0: `<=` / `>=` are the subset / superset tests,
  `<` / `>` their proper forms (the base test plus Counter inequality). The general path now has
  `ail_counter_cmp` for the four operators; counts go through the ordinary comparison operators, so
  a NaN count makes the test false. The typed path still refuses ordering between collections by
  name, and the default build falls back to the general path. `test_ail_pre16.py` checks empty,
  equal, zero, negative, float and NaN counts, aliasing, counters through arguments / list items /
  attributes / dict values, and every non-Counter operand kind against CPython on both builds.

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
