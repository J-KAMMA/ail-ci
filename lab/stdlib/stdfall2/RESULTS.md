# stdfall2: `copy`, `timeit` and `marshal` in compiled programs

Three stdlib modules that AIL had no model of (`copy` and `timeit` from CPython
3.12 `Lib/`, `marshal` from PyPy `lib_pypy/_marshal.py` @
`ad61ef7d8e42d7bbdec8d41cdd47d908aaa5241e`, MIT) are exercised by 18 lab
programs under `lab/stdlib/{copy,timeit,marshal}/` (6 programs per module).

**Before: 0/18. After: 9/18** (copy 4/6, timeit 5/6, marshal 0/6), in both
the default build and `AIL_UNIFIED_FORCE=1`, with stdout and exit status equal
to `python3` (CPython 3.12.3).  The nine remaining programs are named refusals,
listed below; none crashes or prints a wrong value.

`marshal.dumps(x, v)` is exact for CPython's explicit versions 0-2, whose
stream has no object-reference flags and no interned-string codes.  Version 3/4
choose `FLAG_REF` and the interned code from each object's CPython refcount and
interned bit; this compiler keeps neither (an int is a value, a string has no
interned flag and there is no `id`), and the flags even change when the same
value is held in a variable rather than passed as a temporary, so they cannot
be reproduced for an arbitrary value.  `version` therefore has no default: the
six programs (which call `marshal.dumps(x)`, CPython's default version 4) are
refused at build time by name, and an explicit 3/4 is refused at run time.
`marshal.loads` still reads version 4, including `r` references.

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
| `copy/02_tuples_sets.py` | same | same | tuples of any length, sets, frozenset (`sorted(s)`, no set walk) |
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
| `marshal/01_ints_bool_none.py` | build refused | build refused | no `version`, follow-up 3 |
| `marshal/02_big_ints.py` | build refused | build refused | `2**70` literal, follow-up 4 |
| `marshal/03_floats.py` | build refused | build refused | no `version`, follow-up 3 |
| `marshal/04_strings_bytes.py` | build refused | build refused | no `version`, follow-up 3 |
| `marshal/05_lists_tuples.py` | build refused | build refused | no `version`, follow-up 3 |
| `marshal/06_dicts.py` | build refused | build refused | no `version`, follow-up 3 |

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

   A caller-supplied memo dict is used in place, as CPython's is: each copied
   object gets an identity-token key plus one keep-alive slot inside that dict.
   `memo.clear()` followed by a reused dict therefore does not return a stale
   copy, and pre-existing keys are not overwritten (`len(memo)` grows by the
   same two entries per copied object as CPython).  A memo pre-seeded with
   `memo[id(x)] = y` cannot be expressed because this compiler has no `id`.

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

3. **`marshal.dumps` without a `version` is refused at build time.**  CPython's
   default is version 4, whose `FLAG_REF` and interned-string bytes depend on
   each object's CPython refcount and interned bit; this compiler keeps neither
   (and has no `id`), so the bytes cannot be reproduced for an arbitrary value.
   `version` is therefore a required argument, and the six marshal programs,
   which call `marshal.dumps(x)` exactly as CPython's signature allows, stop in
   the compiler with

   ```
   lab/stdlib/marshal/01_ints_bool_none.py:20:5: not in the subset: marshal.dumps() called without a required argument version
   ```

   This is deliberate: the programs were not edited to pass `version=2`.

4. **`2**70` is an int64 literal.**  `marshal/02_big_ints.py` is refused by the
   compiler before the module is reached:

   ```
   lab/stdlib/marshal/02_big_ints.py:3:1: int64 constant out of range: 1180591620717411303424
     write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower
   ```

5. **An explicit `marshal.dumps` version 3/4 is refused by name.**  A call such
   as `marshal.dumps(x, 4)` compiles and then raises

   ```
   ValueError: marshal.dumps: version 4 needs CPython's per-object refcount and
   interned bit, which this compiler does not keep; pass version=2 for the
   exact version-2 layout
   ```

   `marshal.dumps(x, 2)` (and 0/1) writes CPython's exact bytes, including the
   version-0/1 text floats the reader now accepts; `marshal.loads` reads version
   4, including `r` references, and `marshal.loads(b"0")` raises CPython's
   `TypeError: NULL object in marshal data for object`.
