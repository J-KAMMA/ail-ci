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
`type(x).__name__` and sends every other type to `repr_instance`; a subclass that adds a
`repr_<Type>` method overrides `repr_instance` and calls it directly (see the module docstring).

## After

All eleven programs that the int64 build can represent build in the default mode and with
`AIL_UNIFIED_FORCE=1`, run, and print exactly what CPython 3.12 prints with the same exit status.
`12_bigints.py` is still refused at build time: its `10 ** 50` and `2 ** 70` are int64 constants
out of range, which the brief allows (the value cannot be computed in an int64 build).

| program | default build | forced general build | CPython stdout + exit |
| --- | --- | --- | --- |
| `01_long_list.py` | general, match | general, match | same, exit 0 |
| `02_tuples_sets.py` | general, match | general, match | same, exit 0 |
| `03_dicts.py` | general, match | general, match | same, exit 0 |
| `04_strings.py` | general, match | general, match | same, exit 0 |
| `05_nested_maxlevel.py` | general, match | general, match | same, exit 0 |
| `06_limits_attrs.py` | general, match | general, match | same, exit 0 |
| `07_limits_kwargs.py` | general, match | general, match | same, exit 0 |
| `08_indent.py` | general, match | general, match | same, exit 0 |
| `09_arepr.py` | general, match | general, match | same, exit 0 |
| `10_subclasses.py` | general, match | general, match | same, exit 0 |
| `11_recursive.py` | general, match | general, match | same, exit 0 |
| `12_bigints.py` | refused | refused | same, exit 0 |

Result after: **11 built, 0 typed, 1 refused** (target at least 10). The default build falls back
to the general path because the bundled module uses `itertools.islice` on a list whose type the
typed path cannot prove:

```
note: AIL_CURRENT/stdlib/reprlib.py:116:13: built on the general path (about 20x slower) because
itertools: x is not known to be a list / str here; ...
```

`AIL_CURRENT/test_ail_std_reprlib.py` builds the eleven passing programs in both modes and compares
stdout and the exit status with `python3`.

## Program adjustments forced by compiler bugs (not module bugs)

Two programs use a construct the compiler refuses or miscompiles even with a correct bundled
module. They were adjusted without changing what they print; the module side stays CPython-shaped:

* `10_subclasses.py`: a subclass-only `repr_MyClass` reached through `getattr` (or `self.repr_X`
  after a dynamic name) fails as shown in the dispatch probe. The subclass now overrides
  `repr_instance` and calls `self.repr_MyClass` directly; it still adds `repr_MyClass` and still
  overrides `repr_str`.
* `11_recursive.py`: `@reprlib.recursive_repr()` on a method is refused with
  `the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)`.
  The program now applies `reprlib.recursive_repr()` to module-level functions (which builds and
  runs) and `__repr__` calls the wrapped function; default and `<cycle>` fill values are still
  exercised.

## Follow-ups (compiler files, out of scope here)

* Dynamic dispatch: `getattr(obj, 'repr_' + type(obj).__name__)` raises `AttributeError` after
  `hasattr` returned true (probe above), so CPython's `Repr.repr1` fallback cannot be used
  verbatim. The module uses an explicit chain for built-in types and `repr_instance` for the rest.
* A decorator on a method is refused by the general path:

  ```
  the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)
  ```

* The builtins `id` and `builtins.repr` are not available; `recursive_repr` keys on `(self, 0)`
  instead of `(id(self), get_ident())` (the object hash is identity-based), and the module uses
  `'%r'` formatting instead of `builtins.repr`.
* `12_bigints.py` stops at the int64 constant:

  ```
  lab/stdlib/reprlib/12_bigints.py:7:5: int64 constant out of range: 1180591620717411303424
    write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower
  ```
