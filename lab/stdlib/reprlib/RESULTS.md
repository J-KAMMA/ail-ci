# `reprlib` coverage results

Build command for every program:

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/reprlib/<program>.py --syntax python -o <exe>
```

The oracle is `python3 <program>.py` (CPython 3.12.3), comparing stdout and the exit status. The
forced general build is the same command with `AIL_UNIFIED_FORCE=1`.

## Before (integ a6d2703)

All twelve programs were refused. The common first-refusal prefix `P` on eleven of them was:

```
not in the subset: import of 'reprlib' is not available: this compiler builds only the modules it
models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path
could not build this program either); general path:
```

| program | default build | first refusal before the fix | CPython stdout + exit |
| --- | --- | --- | --- |
| `01_long_list.py` | refused | `P reprlib.repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `02_tuples_sets.py` | refused | `P reprlib.repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `03_dicts.py` | refused | `P reprlib.repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `04_strings.py` | refused | `P reprlib.repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `05_nested_maxlevel.py` | refused | `P reprlib.repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `06_limits_attrs.py` | refused | `P reprlib.Repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `07_limits_kwargs.py` | refused | `P reprlib.Repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `08_indent.py` | refused | `P reprlib.Repr (not yet published in NAMES_library.json)` | same, exit 0 |
| `09_arepr.py` | refused | `P reprlib.aRepr used as a plain value` | same, exit 0 |
| `10_subclasses.py` | refused | `P a non-name base class in class MyRepr` | same, exit 0 |
| `11_recursive.py` | refused | `P the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)` | same, exit 0 |
| `12_bigints.py` | refused | `lab/stdlib/reprlib/12_bigints.py:7:33: int64 constant out of range: 1180591620717411303424` | same, exit 0 |

Result before: **0 built, 0 typed, 12 refused** (target at least 10).

## Dispatch probe (sub-step 2)

The probe is `/tmp/probes/repr_dispatch.py`; it defines `WithInit` (an `__init__`) and
`WithoutInit` (no `__init__`), both with a `repr_int` method, and dispatches with
`getattr(self, 'repr_' + type(x).__name__)` after `hasattr` returns true:

```python
class WithInit:
    def __init__(self):
        self.value = 0

    def repr1(self, x):
        typename = type(x).__name__
        if hasattr(self, 'repr_' + typename):
            return getattr(self, 'repr_' + typename)(x)
        return 'fallback'

    def repr_int(self, x):
        return 'int:%d' % x


class WithoutInit:
    def repr1(self, x):
        typename = type(x).__name__
        if hasattr(self, 'repr_' + typename):
            return getattr(self, 'repr_' + typename)(x)
        return 'fallback'

    def repr_int(self, x):
        return 'int:%d' % x


print('with init', WithInit().repr1(5))
print('without init', WithoutInit().repr1(5))
```

Before any bundled module existed, both builds compiled the probe (the default build fell back to
the general path because `WithoutInit` has no `__init__`) and the executable stopped with:

```
AttributeError: 'WithInit' object has no attribute 'repr_int'
```

exit status 1, and no stdout at all. CPython 3.12 prints:

```
with init int:5
without init int:5
```

exit 0. This is a compiler bug, not a `reprlib` bug: `hasattr(self, 'repr_int')` is true but the
following `getattr(self, 'repr_int')` raises, so a class that has a `repr_int` method cannot be
dispatched to. The module therefore dispatches built-in type names through an explicit chain on
`type(x).__name__` and only falls back to `getattr` for a name a subclass defines (see the module
docstring).
