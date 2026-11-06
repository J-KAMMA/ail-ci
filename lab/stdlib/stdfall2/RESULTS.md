# stdfall2: `copy`, `timeit` and `marshal` in compiled programs

Three stdlib modules that AIL had no model of (`copy` and `timeit` from CPython
3.12 `Lib/`, `marshal` from PyPy `lib_pypy/_marshal.py`) are exercised by 18 lab
programs under `lab/stdlib/{copy,timeit,marshal}/` (6 programs per module,
12-23 lines each).

**Before: 0/18.**

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
