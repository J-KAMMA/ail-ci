# stdfall1: `fnmatch`, `reprlib` and `sched` in compiled programs

Three stdlib modules that AIL had no model of are shipped as AIL source in
`AIL_CURRENT/stdlib/`, written from CPython 3.12's pure-Python sources. The 18
lab programs under `lab/stdlib/{fnmatch,reprlib,sched}/` exercise them; each is
compiled with the default command and with `AIL_UNIFIED_FORCE=1`, then run
beside `python3` on the same source.

**Before: 0/18. After: 16/18 in the default build and 16/18 with
`AIL_UNIFIED_FORCE=1`** - fnmatch 6/6, reprlib 4/6, sched 6/6. The two that do
not build fail on compiler limits, not on the module (see Follow-ups).

## Before and after, per program

Baseline is `origin/integ` (18703a92) with no bundled module. Every program
stops at the import with

```
prog.py:1:1: not in the subset: import of '<mod>' is not available: this compiler builds only the
modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json)
(the general path could not build this program either); general path: <reason below>
```

| Program | Before (first refusal) | After, default | After, `AIL_UNIFIED_FORCE=1` |
| --- | --- | --- | --- |
| `fnmatch/01_basic_patterns.py` | `fnmatch.fnmatch (not yet published in NAMES_library.json)` | builds and matches | builds and matches |
| `fnmatch/02_brackets.py` | `fnmatch.fnmatchcase (not yet published ...)` | builds and matches | builds and matches |
| `fnmatch/03_filter.py` | `fnmatch.filter (not yet published ...)` | builds and matches | builds and matches |
| `fnmatch/04_translate.py` | `fnmatch.translate (not yet published ...)` | builds and matches | builds and matches |
| `fnmatch/05_bytes.py` | `fnmatch.fnmatchcase (not yet published ...)` | builds and matches | builds and matches |
| `fnmatch/06_paths_and_case.py` | `fnmatch.fnmatch (not yet published ...)` | builds and matches | builds and matches |
| `reprlib/01_long_list.py` | `reprlib.repr (not yet published ...)` | builds and matches | builds and matches |
| `reprlib/02_dict_nested.py` | `reprlib.repr (not yet published ...)` | builds and matches | builds and matches |
| `reprlib/03_strings.py` | `reprlib.repr (not yet published ...)` | builds and matches | builds and matches |
| `reprlib/04_big_ints.py` | `prog.py:7:5: int64 literal out of range: 123456789012345678901234567890` | refused (compiler, see F1) | refused (compiler, see F1) |
| `reprlib/05_custom_limits.py` | `reprlib.Repr (not yet published ...)` | builds and matches | builds and matches |
| `reprlib/06_recursive.py` | `general path: the decorator on def __repr__ (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)` | refused (compiler, see F2) | refused (compiler, see F2) |
| `sched/01_events.py` | `sched.scheduler (not yet published ...)` | builds and matches | builds and matches |
| `sched/02_priorities.py` | `sched.scheduler (not yet published ...)` | builds and matches | builds and matches |
| `sched/03_cancel.py` | `sched.scheduler (not yet published ...)` | builds and matches | builds and matches |
| `sched/04_queue.py` | `sched.scheduler (not yet published ...)` | builds and matches | builds and matches |
| `sched/05_nonblocking.py` | `sched.scheduler (not yet published ...)` | builds and matches | builds and matches |
| `sched/06_enterabs_kwargs.py` | `sched.scheduler (not yet published ...)` | builds and matches | builds and matches |

"Builds and matches" means: compile exit 0, then stdout and exit status equal
to `python3 -B <program>` run in the same directory.

## How it was measured

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile <program> --syntax python -o <exe>
AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile ...   # second build
```

`AIL_CURRENT/test_ail_std_stdfall1.py` repeats this for the 16 passing
programs and compares stdout and exit status with CPython. The baseline was
taken by moving the three `AIL_CURRENT/stdlib/*.py` files out of the tree and
rebuilding all 18.

## Probes

Six probe programs in `/tmp/probes/`, each compiled in both builds and compared
with `python3` (stdout and exit status). All six match in both builds.

| Probe | Covers | Default | Force |
| --- | --- | --- | --- |
| `p_fnmatch_edge.py` | empty name/pattern, `**`, newline in name, `[]]`, `[]`, `[[]`, `[^a]`, `[!]`, `[-a]`, `[a-]`, reversed range `[c-a]`, `&`/`~`/`|` set ops, backslash, unicode, and `translate()` text for 16 patterns | match | match |
| `p_fnmatch_types.py` | `bytes`/`str` mixed arguments (four entry points), high latin-1 bytes, `filter` over list/tuple/generator, `translate(bytes)` error text | match | match |
| `p_reprlib_edge.py` | empty/singleton containers, set/frozenset, `maxlevel=0`, `maxother`, `fillvalue`, `indent` as int/str/negative/float (both error texts), nested lists, strings, ints | match | match |
| `p_reprlib_attr.py` | objects with custom `__repr__`, an action through an instance attribute, a `Repr` passed through a dict value, limits set after construction | match | match |
| `p_reprlib_recursive.py` | `recursive_repr()` applied by calling the factory (the `@` form is refused by the compiler), recursion through a global, custom fill value | match | match |
| `p_sched_edge.py` | empty queue and `run()` on it, equal time+priority ordering, `queue` copy isolation, `cancel` twice (`ValueError` text), `enterabs`, 0/1/2-argument actions, non-blocking return value | match | match |
| `p_sched_args.py` | arguments reaching actions through a list, a tuple and a dict value; `sequence` fields | match | match |

### Fix round (review 0)

The review's three failing probes now agree with CPython in both builds:

| Probe | Covers | Default | Force |
| --- | --- | --- | --- |
| `p_filter.py` | `fnmatch()`/`filter()` normcase type check (`expected str, bytes or os.PathLike object, not int` for `filter([], 5)`, `fnmatch("a", 5)`, `fnmatch(5, "a*")`), bytes/str mixing, list/tuple/generator names | match | match |
| `p_reprec3.py` | `recursive_repr` guard with distinct-but-equal values (`[1]` and `[1]`); removal is by identity, so the outer guard survives the inner call | match | match |
| `p_replim2.py` | `_join` invalid indents: `Odd()` -> `<class '__main__.Odd'>`, `1.5` -> `<class 'float'>`, `[1]` -> `<class 'list'>`, negative int `ValueError`, empty/singleton lists | match | match |

### Fix round (review 1)

`_type_label` no longer guesses the module from the class name: a program class
called `deque`/`Counter` now prints `__main__`, while a real collections value
is recognised by its representation in this runtime (a deque is a flagged list,
a Counter/defaultdict a flagged dict) and `array.array` by its prelude class
name `_AilArray`. `repr1` dispatches an array to `repr_array` on that same
name, so a limited array repr is CPython's text instead of `repr_instance`.

| Probe | Covers | Default | Force |
| --- | --- | --- | --- |
| `p_typ1.py`, `p_typ2.py` | a program class named `deque` / `Counter` as `Repr(indent=...)`: `<class '__main__.deque'>` / `<class '__main__.Counter'>` (was `collections.*`) | match | match |
| `r_names.py` | program classes named `deque`, `Counter`, `defaultdict`, `OrderedDict`, `UserDict`, `UserList`, `UserString`, `array` | match | match |
| `r_real.py` | real `deque`, `Counter`, `defaultdict`, `array` as `Repr(indent=...)`: `collections.*` / `array.array` | match | match |
| `r_limits.py` | `Odd`, `1.5`, `[1]`, negative int, empty/singleton list indents | match | match |
| `q_arr.py` | `reprlib.repr(array('i', [1..7]))` and `maxarray=3` | match | match |

`OrderedDict` as `indent=` is refused by the compiler by name ("a collection
passed as indent= to reprlib__Repr() is not built"), so no real
`OrderedDict`/`UserDict` can reach `_type_label`; a program class of one of
those names prints `__main__`.


## What was rewritten, per module

All three keep CPython 3.12's logic and message text. The rewrites are forced
by the compiler and are described in each module docstring.

- `fnmatch.py`: `os.path.normcase` is `os.fspath` on POSIX; `_normcase` reproduces it - str and
  bytes pass unchanged, anything else raises CPython's
  `expected str, bytes or os.PathLike object, not <name>` TypeError from `fnmatch()` and `filter()`.
  A `__fspath__` class is refused by the compiler at the class definition, so no PathLike value can
  reach it. CPython compiles `translate()`'s regular expression at run time; this compiler accepts
  only a literal pattern in `re.compile`, so matching walks the pattern directly, with
  `translate()` still returning CPython's exact regex text. Bytes patterns and names are matched as
  ISO-8859-1 text, and the mixed-type and non-string argument errors reproduce CPython's `TypeError`
  texts. The `functools.lru_cache` on `_compile_pattern` is dropped (no visible effect).
- `reprlib.py`: `builtins.repr` is not available, so `_py_repr` asks `%r` for the builtin
  representation. `recursive_repr` keeps the guard but keys it by object identity instead of
  `(id(self), get_ident())`, because `id()` is not available; both the membership test and the
  removal compare with `is`, so equal-but-distinct objects do not defeat it. The only visible
  difference is concurrent threads, which this runtime does not have. `_join`'s invalid-indent
  message needs CPython's full `type(indent)` text; this compiler exposes only
  `type(x).__name__`, so `_type_label` rebuilds it: builtin scalar/container types are recognised
  by identity and print bare, a real collections value and `array.array` are told from a program
  class of the same name by the runtime representation (a deque is a flagged list, a
  Counter/defaultdict a flagged dict, an array the prelude class `_AilArray`), the builtin types
  the compiler cannot name (`slice`, `memoryview`, exceptions, ...) are recognised by name, and
  every other class - including a program class called `deque` or `Counter` - is a class of the
  program, printed as `<class '__main__.Name'>`. `repr1` dispatches an array on `_AilArray` too,
  so `repr_array` applies the `maxarray` limit. A class defined in another program module
  would still be printed as `__main__`; the compiler exposes no module for an instance's class,
  so that one case cannot be made exact.
- `sched.py`: `threading.RLock` is not available, so the scheduler is not
  thread-safe. `Event` is a plain class and the queue is kept sorted by
  `(time, priority, sequence)` - the same key CPython's `heapq` orders the
  namedtuple by. The sequence number is an integer rather than
  `itertools.count()`. `*argument`/`**kwargs` calls are refused by the
  compiler, so an action with more than two positional arguments, or with
  keyword arguments, raises `RuntimeError` instead of being called (F3/F4).

## Follow-ups

Compiler refusals (a compiler file would have to change; the programs are not
edited):

- **F1 `reprlib/04_big_ints.py`** - big integers are outside int64 in the
  default build:

  ```
  prog.py:7:5: int64 literal out of range: 123456789012345678901234567890
    write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1)
  ```

- **F2 `reprlib/06_recursive.py`** - a decorator on `__repr__`:

  ```
  not in the subset: the decorator on def __repr__ (only @staticmethod on a method and
  @functools.lru_cache/@lru_cache/@cache are supported)
  ```

  The same refusal applies to `@decorator` on any def, so `recursive_repr` can
  only be used by calling the factory (verified in `p_reprlib_recursive.py`).

- **F5** - `reprlib.py`'s `recursive_repr` uses a doubly nested def, which the
  fast path does not support; importing `reprlib` prints
  `note: AIL_CURRENT/stdlib/reprlib.py:33:9: built on the general path (about 20x
  slower) because a nested def that is not a direct statement of its enclosing
  function ('wrapper') is not available`. The module still builds and behaves
  like CPython; the fallback is a performance note only.

Module refusals (deliberate, loud):

- **F3** keyword arguments to an action:
  `RuntimeError: keyword arguments to sched actions are not available here`.
- **F4** more than two positional arguments:
  `RuntimeError: sched actions take at most two positional arguments here`.

Packaging (fixed in this PR):

- **F6** `test_ail_third_party_notices.test_wheel_contains_notices` used to fail
  because the wheel had no `LICENSE-PSF.txt`: `packaging/ail_wheel_backend.py`
  copied only the two root licenses. `collect()` now also copies the PSF text
  (`AIL_CURRENT/stdlib/LICENSE-PSF.txt`) and the typeshed license into
  `.dist-info/licenses/`; the notices test passes 6/6.

## Notices

`THIRD_PARTY_NOTICES.md` lists `AIL_CURRENT/stdlib/fnmatch.py`,
`reprlib.py` and `sched.py` (origin CPython 3.12 `Lib/<name>.py`, PSF-2.0,
notice yes). While updating it, the missing row for `AIL_CURRENT/stdlib/quopri.py`
(the `quopri1` lane, which landed after the inventory) was added with notice
"no" and a follow-up; the test's derived-file count went from 13 to 17.
