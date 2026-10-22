# DEVLOG

## 2026-10-22 - job-fuzz14-10220830

Fuzzed lists and sorting (sort key/reverse stability, insert, pop, remove, slice assignment and
deletion, list repetition/aliasing, index bounds, nested-list comparisons) with 130+ small
programs on both builds. Two silent differences were fixed in the general path:

- A slice read converted each bound with `(value).i`, so an explicit or run-time None bound became
  0 (`a[None:None]` was empty) and a float/str bound read payload bits instead of raising
  TypeError. Slice reads now use `ail_op_getslice_obj`, which applies CPython's bound conversion.
- `list.index`/`tuple.index` start/stop and `list.insert`/`list.pop` index arguments were read as
  `.i` too. They now use `ail_op_index_bound` / `ail_op_int_index` (None is not a valid list.index
  bound; insert/pop use CPython's integer-conversion message).

New cases are in `AIL_CURRENT/test_ail_fuzz14.py`. Remaining observed differences: the declared
NaN sort contract (typed list sort raises ValueError; a general-path sort key containing NaN does
not follow CPython's Timsort order), and str.find/rfind/startswith/endswith still read a None
window bound as 0 (not touched by this list/sort job).
