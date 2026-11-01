# functools coverage: 12 real programs

Built with the default mode, `python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python`.
Every build below was also run through `bash ~/tools/cmp.sh X.py <repo root>` (default build and
`AIL_UNIFIED_FORCE=1` build) and compared with CPython 3.12.3 on stdout and exit status.

| program | result | first refusal / note |
| --- | --- | --- |
| `reduce_orders.py` | general, matches CPython | `reduce` with and without an initializer; the empty case now raises CPython's `TypeError: reduce() of empty iterable with no initial value`. |
| `partial_pipeline.py` | general, matches CPython | `partial` with positional and keyword bindings, defaults, as a sort key and as a map function. |
| `lru_fib.py` | general, matches CPython | `@lru_cache(maxsize=None)`, recursive hits, `cache_info()` and `cache_clear()`. |
| `cache_collatz.py` | general, matches CPython | `@cache` (unbounded), 2228 distinct entries and CPython's hits/misses/currsize. |
| `lru_typed.py` | general, matches CPython | `lru_cache(maxsize=8, typed=True)`, the lone int/str fast-path keys, the untyped float/bool collision, `cache_info()` / `cache_clear()`. |
| `cmp_key.py` | general, matches CPython | `cmp_to_key` with a named comparator and a lambda in `sorted`, `list.sort(reverse=True)`, `min` and `max`. |
| `total_order.py` | general, matches CPython | `@total_ordering` filling `>`, `>=`, `<=` from `__lt__` / `__eq__`, including `max` / `min`. |
| `functools_errors.py` | general, matches CPython | The `TypeError`s from `reduce()` of an empty iterable and from caching an unhashable list argument, both caught. |
| `partial_method.py` | general, matches CPython | `partialmethod` with keyword-bound arguments, positional overrides and a plain `render` call. |
| `wraps_meta.py` | refused | `not in the subset: functools.wraps used here is not built: reduce, lru_cache / cache and cmp_to_key are built (see the reference) (the general path could not build this program either); general path: the decorator on def add (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)` |
| `dispatch_shapes.py` | refused | `dispatch_shapes.py:16:1: duplicate AIL name: _ (`def _` / `class _` is bound a second time at module level; a function here has one definition, which also rules out the `@f.register` / `def _(...)` overload pattern)` |
| `cached_report.py` | refused | `not in the subset: functools.cached_property used here is not built: reduce, lru_cache / cache and cmp_to_key are built (see the reference) (the general path could not build this program either); general path: the decorator on def total (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)` |

Result: 9 of 12 build and match CPython; 3 are refusals.

## Follow-ups (out of scope: each needs a large new feature)

* **`functools.wraps` / arbitrary `@decorator` functions.** Both paths only accept `@staticmethod` on a
  method and `@functools.lru_cache` / `@lru_cache` / `@cache` on a function; a user decorator that
  returns a closure is a separate feature (first-class function values and closure calls). Exact refusal
  for `wraps_meta.py`:
  `not in the subset: functools.wraps used here is not built: reduce, lru_cache / cache and cmp_to_key are built (see the reference) (the general path could not build this program either); general path: the decorator on def add (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)`
* **`functools.singledispatch` / `.register`.** The plain-Python spelling uses the overload idiom
  (`@area.register` + repeated `def _`), which the front end refuses as a duplicate AIL name before the
  dispatcher can be lowered. Exact refusal for `dispatch_shapes.py`:
  `dispatch_shapes.py:16:1: duplicate AIL name: _ (`def _` / `class _` is bound a second time at module level; a function here has one definition, which also rules out the `@f.register` / `def _(...)` overload pattern)`
* **`functools.cached_property`.** It is a decorator on a method, plus per-instance cache storage that
  `del obj.name` and `"name" in obj.__dict__` must see; the class decorator support does not exist.
  Exact refusal for `cached_report.py`:
  `not in the subset: functools.cached_property used here is not built: reduce, lru_cache / cache and cmp_to_key are built (see the reference) (the general path could not build this program either); general path: the decorator on def total (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)`

## Compiler work that made the nine build

* `functools.reduce` without an initializer over an empty iterable raised `IndexError` (typed tuple
  lowering) or `RuntimeError` (stream lowering) instead of CPython's `TypeError`; both now raise it.
* The general path's `@lru_cache` wrapper now has `cache_info()` / `cache_clear()` /
  `cache_parameters()`, real `hits` / `misses`, the decorator's `maxsize`, `typed=True` keys, the
  lone-int/str fast-path key rule, and CPython's unhashable-argument `TypeError`. A program that reads
  these keeps every call on the wrapper (mixed-mode typed clones bypass the cache). Programs that do
  not call them emit exactly the previous C.
* `functools.cmp_to_key` is lowered on the general path to a stable merge sort in the prelude, for
  `sorted`, `list.sort`, `min` and `max`, with a function or lambda comparator.
* `functools.partialmethod` with keyword-bound arguments is rewritten into an ordinary method of the
  class on the general path.

## Verification

* `bash ~/tools/cmp.sh` on all nine: default and unified builds both print CPython's bytes and exit
  with CPython's status.
* `AIL_CURRENT/test_ail_std_functools.py` rebuilds and reruns the nine in both modes.
* Generated C of the lab/compare tasks that build on this tree is byte-identical to `HEAD`
  (`berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit`, plus `chain_relax` and
  `rail_transfer` with `--exact-int`); `scar_life`, `tally_lang` and `tree_fold` already fail to
  compile at `HEAD` with the same refusals, so they have no C to compare.
