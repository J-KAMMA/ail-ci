# stdfall2: `copy`, `timeit` and `marshal` in compiled programs

Three stdlib modules that AIL had no model of (`copy` and `timeit` from CPython
3.12 `Lib/`, `marshal` from PyPy `lib_pypy/_marshal.py` @
`ad61ef7d8e42d7bbdec8d41cdd47d908aaa5241e`, MIT) are exercised by 18 lab
programs under `lab/stdlib/{copy,timeit,marshal}/` (6 programs per module).

**Before: 0/18. After: 14/18** (copy 4/6, timeit 5/6, marshal 5/6), in both
the default build and `AIL_UNIFIED_FORCE=1`, with stdout and exit status equal
to `python3` (CPython 3.12.3).  The four remaining programs are named refusals,
listed below; none crashes or prints a wrong value.

`marshal.dumps` is exact for CPython's versions 0-2, whose stream has no
object-reference flags and no interned-string codes (the marshal programs pass
`version=2`).  Version 3/4 choose `FLAG_REF` and the interned code from each
object's CPython refcount and interned bit; this compiler keeps neither (an int
is a value, and a string has no interned flag), so `marshal.dumps` refuses
versions 3 and 4 by name instead of writing different bytes.  `marshal.loads`
still reads version 4, including `r` references.

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
| `copy/02_tuples_sets.py` | same | same | tuples of any length, sets, frozenset |
| `copy/03_user_class_hooks.py` | refused by name | refused by name | class instance (hooks), follow-up 1 |
| `copy/04_user_class_plain.py` | refused by name | refused by name | plain class instance, follow-up 1 |
| `copy/05_recursive_list.py` | same | same | self-referential list and dict memo, shared memo dict |
| `copy/06_shared_subobjects.py` | same | same | shared sub-objects stay shared |
| `timeit/01_default_timer.py` | same | same | `default_timer()` difference is a float `>= 0` |
| `timeit/02_timer_timeit.py` | same | same | `Timer(callable).timeit(number=3)` calls 3 times |
| `timeit/03_timer_repeat.py` | same | same | `repeat(repeat=2, number=2)` calls 4 times |
| `timeit/04_module_timeit.py` | same | same | module `timeit()` and `repeat()` |
| `timeit/05_setup_and_custom_timer.py` | same | same | setup and injected clock |
| `timeit/06_string_stmt.py` | build refused | build refused | string statement uses `exec`, follow-up 2 |
| `marshal/01_ints_bool_none.py` | same | same | `i`/`l` forms, int64 boundaries, booleans, None |
| `marshal/02_big_ints.py` | build refused | build refused | `2**70` literal, follow-up 3 |
| `marshal/03_floats.py` | same | same | binary `g` floats, `-0.0`, 1e100 |
| `marshal/04_strings_bytes.py` | same | same | ASCII/UTF-8 strings, bytes (version 2) |
| `marshal/05_lists_tuples.py` | same | same | list/tuple nesting (version 2) |
| `marshal/06_dicts.py` | same | same | dict pairs and `0` terminator (version 2) |

## Follow-ups (named refusals)

1. **A class instance is refused by name.**  This compiler has no
   `object.__new__`, no `cls.__new__` and no `type(x)` as a value, so a copy
   cannot have the class of the original.  `copy.copy`/`copy.deepcopy` stop
   with

   ```
   copy.Error: un(shallow)copyable object of type Bag (class instances have no instance constructor in this compiler)
   ```

   naming the type, instead of returning an object of a different class.
   `__copy__`/`__deepcopy__` hooks are not dispatched for the same reason.
   Programs 01, 02, 05 and 06 (no user class) match CPython.

2. **A string `stmt`/`setup` needs `exec`.**  The string form is a CPython
   `exec` program, so `timeit/06_string_stmt.py` calls `exec` and the compiler
   refuses it by name at build time:

   ```
   not in the subset: exec() is not built: this language compiles the whole
   program ahead of time, so there is no source text to run at run time.
   ```

   The callable form (programs 01-05) is CPython's.  A `Timer("...")` that
   reaches the module also stops, at run time, with
   `TypeError: timeit.Timer: a string stmt needs exec, which is not built`.

3. **`2**70` is an int64 literal.**  `marshal/02_big_ints.py` is refused by the
   compiler before the module is reached:

   ```
   lab/stdlib/marshal/02_big_ints.py:3:1: int64 constant out of range: 1180591620717411303424
     write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower
   ```

4. **`marshal.dumps` versions 3/4 are refused by name.**  Their `FLAG_REF` and
   interned-string bytes depend on each object's CPython refcount and interned
   bit, which AIL does not keep.  `marshal.dumps(x)` (default version 4) raises

   ```
   ValueError: marshal.dumps: version 4 needs CPython's per-object refcount and
   interned bit, which this compiler does not keep; pass version=2 for the
   exact version-2 layout
   ```

   `marshal.dumps(x, 2)` (and 0/1) writes CPython's exact bytes; `marshal.loads`
   reads version 4, including `r` references, and `marshal.loads(b"0")` raises
   CPython's `TypeError: NULL object in marshal data for object`.
