# `copy` coverage: twelve real programs

Build used for every program (from the repository root, 2026-11-01):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/copy/<program>.py --syntax python -o /tmp/<program>
```

CPython 3.12 is the oracle. Every program below built, and its stdout and exit code match CPython on the default
build and with `AIL_UNIFIED_FORCE=1` (`test_ail_std_copy.py`). All twelve use the general path: the typed path does
not model the `copy` module, so the default build falls back there and prints the note below.

| program | result | first diagnostic (fallback note) |
| --- | --- | --- |
| p01_nested_config.py | general | `p01_nested_config.py:3:1: built on the general path ... because 'DEFAULTS' is a module-level dict that a function cannot read` |
| p02_shallow_list.py | general | `p02_shallow_list.py:1:1: built on the general path ... because import of 'copy' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json)` |
| p03_dict_copy.py | general | same `import of 'copy' is not available` note at line 1 |
| p04_shared_refs.py | general | same `import of 'copy' is not available` note at line 1 |
| p05_cycle.py | general | same `import of 'copy' is not available` note at line 1 |
| p06_shallow_object.py | general | same `import of 'copy' is not available` note at line 1 |
| p07_deep_object.py | general | same `import of 'copy' is not available` note at line 1 |
| p08_tuple_set.py | general | same `import of 'copy' is not available` note at line 1 |
| p09_errors.py | general | same `import of 'copy' is not available` note at line 1 |
| p10_memo.py | general | same `import of 'copy' is not available` note at line 1 |
| p11_list_objects.py | general | same `import of 'copy' is not available` note at line 1 |
| p12_deep_keys.py | general | same `import of 'copy' is not available` note at line 1 |

Summary: 12 built / 12 compared, 0 refused. The compiler change is `copy.copy` and `copy.deepcopy` in
`genlib.py` (names and keyword checking), `prelude_genlib.py` (CPython call signatures) and `safetyrt.py`
(the boxed shallow/deep copier, memo and keep-alive lists).

## Review fixes (2026-11-01)

- A generator now raises CPython's `TypeError: cannot pickle 'generator' object` from `copy.copy` and
  `copy.deepcopy` (also through a list or dict value), instead of being copied silently.
- Copying a typed tuple-keyed table (`_AilD_...`) or tuple-element set (`_AilS_...`) now rebuilds a plain
  `dict` / `set`, as CPython returns, so generic iteration of the copy works instead of failing with
  `TypeError: '_AilD_...' object is not iterable`.
- A class that defines the copy protocol is now refused by name instead of being copied as a plain instance
  (see the follow-up below). The check also covers `__getstate__` / `__setstate__` (both are part of what
  CPython's `_reconstruct` honours) and hooks assigned after the class statement (`C.__copy__ = f`,
  `C.__deepcopy__: object = f`, `setattr(C, "__reduce__", f)`), not only class-body `def`s.
- The deep copy of a `set` / `frozenset` now builds CPython's temporary reduce list first, so an explicit
  `memo` sees the same three entries as CPython (`len(memo) == 3`, with a copied list among the values).

## Follow-ups (not needed by these programs)

- Typed-path `copy`: the typed path has no model of `copy.copy` / `copy.deepcopy` over arbitrary object graphs;
  every program here takes the general path instead. A typed implementation is a new feature, not a refusal.
- Copy protocol: the general-path copier copies list/dict/tuple/set/frozenset/bytearray/bytes/atomic values and
  plain instance attributes. A user class's `__copy__`, `__deepcopy__`, `__reduce__` / `__reduce_ex__`,
  `__getstate__` / `__setstate__` and `copy.dispatch_table` entries are not called; supporting them needs method
  dispatch and `_reconstruct` semantics (a new feature). A program that calls `copy.copy` / `copy.deepcopy` and
  defines any of those hooks (as a method, a class-body assignment or a later attribute assignment) is now
  refused by name, for example:
  `not in the subset: copy.copy()/copy.deepcopy() with WithCopy.__copy__ is not built on the general path: the copy protocol needs method dispatch and _reconstruct`.
