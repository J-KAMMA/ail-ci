# stdfall2: `copy`, `timeit` and `marshal` in compiled programs

Three stdlib modules that AIL had no model of (`copy` and `timeit` from CPython
3.12 `Lib/`, `marshal` from PyPy `lib_pypy/_marshal.py` @
`ad61ef7d8e42d7bbdec8d41cdd47d908aaa5241e`, MIT) are exercised by 18 lab
programs under `lab/stdlib/{copy,timeit,marshal}/` (6 programs per module,
12-23 lines each).

**Before: 0/18. After: 15/18** (copy 5/6, timeit 5/6, marshal 5/6), in both
the default build and `AIL_UNIFIED_FORCE=1`, with stdout and exit status equal
to `python3` (CPython 3.12.3). Every `marshal.dumps` that builds produces
CPython's exact version-4 bytes (the five marshal programs below compare
`raw.hex()`).

## Before, per program

Baseline is `origin/integ` (`bac4e81a`) with no bundled `copy.py`, `timeit.py`,
or `marshal.py`. Every program is built with:

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile <program> -o <exe>
```

| Program | Before (first refusal) |
| --- | --- |
| `copy/01_nested_lists_dicts.py` | `not in the subset: copy.copy (not yet published in NAMES_library.json)` |
| `copy/02_tuples_sets.py` | `not in the subset: copy.copy (not yet published in NAMES_library.json)` |
| `copy/03_user_class_hooks.py` | `not in the subset: copy.deepcopy (not yet published in NAMES_library.json)` |
| `copy/04_user_class_plain.py` | `not in the subset: copy.copy (not yet published in NAMES_library.json)` |
| `copy/05_recursive_list.py` | `not in the subset: copy.deepcopy (not yet published in NAMES_library.json)` |
| `copy/06_shared_subobjects.py` | `not in the subset: copy.deepcopy (not yet published in NAMES_library.json)` |
| `timeit/01_default_timer.py` | `not in the subset: timeit.default_timer (not yet published in NAMES_library.json)` |
| `timeit/02_timer_timeit.py` | `not in the subset: timeit.Timer (not yet published in NAMES_library.json)` |
| `timeit/03_timer_repeat.py` | `not in the subset: timeit.Timer (not yet published in NAMES_library.json)` |
| `timeit/04_module_timeit.py` | `not in the subset: timeit.timeit (not yet published in NAMES_library.json)` |
| `timeit/05_setup_and_custom_timer.py` | `not in the subset: timeit.Timer (not yet published in NAMES_library.json)` |
| `timeit/06_string_stmt.py` | `not in the subset: timeit.Timer (not yet published in NAMES_library.json)` |
| `marshal/01_ints_bool_none.py` | `not in the subset: marshal.dumps (not yet published in NAMES_library.json)` |
| `marshal/02_big_ints.py` | `lab/stdlib/marshal/02_big_ints.py:9:7: int64 constant out of range: 1180591620717411303424` |
| `marshal/03_floats.py` | `not in the subset: marshal.dumps (not yet published in NAMES_library.json)` |
| `marshal/04_strings_bytes.py` | `not in the subset: marshal.dumps (not yet published in NAMES_library.json)` |
| `marshal/05_lists_tuples.py` | `not in the subset: marshal.dumps (not yet published in NAMES_library.json)` |
| `marshal/06_dicts.py` | `not in the subset: marshal.dumps (not yet published in NAMES_library.json)` |

## After, per program

Default build and `AIL_UNIFIED_FORCE=1` were both run with
`bash ~/tools/cmp.sh <program> $PWD`; "same" means stdout and exit status equal
`python3` on the same source.

| Program | Default | Forced general | Note |
| --- | --- | --- | --- |
| `copy/01_nested_lists_dicts.py` | same | same | shallow/deep of nested dict/list |
| `copy/02_tuples_sets.py` | same | same | tuples, sets, frozenset; tuple copy of length 2 |
| `copy/03_user_class_hooks.py` | differs | differs | `__copy__`/`__deepcopy__` follow-up below |
| `copy/04_user_class_plain.py` | same | same | plain class copied through `__dict__` |
| `copy/05_recursive_list.py` | same | same | self-referential list and dict memo |
| `copy/06_shared_subobjects.py` | same | same | shared sub-objects stay shared |
| `timeit/01_default_timer.py` | same | same | `default_timer()` difference is a float `>= 0` |
| `timeit/02_timer_timeit.py` | same | same | `Timer(callable).timeit(number=3)` calls 3 times |
| `timeit/03_timer_repeat.py` | same | same | `repeat(repeat=2, number=2)` calls 4 times |
| `timeit/04_module_timeit.py` | same | same | module `timeit()` and `repeat()` |
| `timeit/05_setup_and_custom_timer.py` | same | same | setup and injected clock |
| `timeit/06_string_stmt.py` | refused at run time | refused at run time | string statement follow-up below |
| `marshal/01_ints_bool_none.py` | same | same | `i`/`l` forms, int64 boundaries, booleans, None |
| `marshal/02_big_ints.py` | build refused | build refused | `2**70` literal follow-up below |
| `marshal/03_floats.py` | same | same | binary `g` floats, `-0.0`, 1e100 |
| `marshal/04_strings_bytes.py` | same | same | ASCII short/long, interned, UTF-8, bytes |
| `marshal/05_lists_tuples.py` | same | same | list/tuple nesting, ref flags |
| `marshal/06_dicts.py` | same | same | dict pairs, nested list/tuple, `0` terminator |

## Follow-ups (compiler-side)

1. **User `__copy__` / `__deepcopy__` hooks are not dispatched.** A module-level
   `getattr(x, "__copy__")()` compiles only when the call site's static type
   has the method; with a container call site the compiler refuses it with

   ```
   not in the subset: the method .__copy__() (on a value of unknown static kind)
   ```

   `copy/03_user_class_hooks.py` therefore builds and copies `Bag` through its
   `__dict__`, so it prints `box` where CPython prints `box_shallow`/`box_deep`.
   `copy/04_user_class_plain.py` (no hooks) passes.

2. **A string `stmt`/`setup` needs `exec`.** `timeit.Timer` raises, by name,

   ```
   TypeError: timeit.Timer: a string stmt needs exec, which is not built; pass a callable
   ```

   `timeit/06_string_stmt.py` builds and stops at run time with that message;
   the callable form (programs 01-05) is CPython's.

3. **`2**70` is an int64 literal.** `marshal/02_big_ints.py` is still refused
   by the compiler, before the module is reached:

   ```
   lab/stdlib/marshal/02_big_ints.py:3:1: int64 constant out of range: 1180591620717411303424
     write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower
   ```

   The other five marshal programs include the int64 boundaries, which are the
   exact `l` long form.
