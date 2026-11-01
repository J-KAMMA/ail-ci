# collections lab: build results

Command for every program (default build, both paths available):

    python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/collections/<name>.py --syntax python -o <exe>

The CPython oracle (`python3 <name>.py`) is run for each program.  A built program is accepted only when
its stdout and exit code are byte-identical to CPython's.

Result: **9 of 12 build and match CPython**.  3 are refused by name (follow-ups below).

| program | result | path | first refusal / note |
| --- | --- | --- | --- |
| config_layers.py | built, matches | general | ChainMap; bool/int mix in a dict operand |
| coordinate_freq.py | built, matches | general | Counter of tuple keys, arithmetic, defaultdict(Counter) |
| counter_edges.py | built, matches | general | Counter.subtract |
| graph_bfs.py | built, matches | general | defaultdict, deque |
| group_anagrams.py | built, matches | general | defaultdict(list) |
| inventory.py | built, matches | general | Counter mapping and arithmetic |
| queue_sim.py | built, matches | typed | deque |
| sliding_window.py | built, matches | typed | deque |
| word_stats.py | built, matches | general | Counter |
| log_report.py | refused | -- | see follow-up 1 |
| lru_cache.py | refused | -- | see follow-up 2 |
| point_records.py | refused | -- | see follow-up 3 |

## Refusal text (first line, exactly as printed)

`log_report.py`

    lab/stdlib/collections/log_report.py:1:1: not in the subset: import of 'collections' with a use that is not built: Counter, defaultdict (int, float, str, list, lambda: <constant>), OrderedDict and deque are built for str / int / tuple keys and int / float / str / tuple elements; the rest of the module is not (namedtuple and ChainMap are built by the library pass) -- the notes below name the use (the general path could not build this program either); general path: collections.OrderedDict (not yet published in NAMES_library.json)
    note: lab/stdlib/collections/log_report.py:37: OrderedDict.popitem is built only as a statement (`d.move_to_end(k)`, `k, v = d.popitem(last=False)`)

`lru_cache.py`

    lab/stdlib/collections/lru_cache.py:135:9: not in the subset: iterating a OrderedDict: its __iter__ is not `return iter(...)` or a generator (an iterator class with __next__ is not built) (the general path could not build this program either); general path: get() called with too many positional arguments
    note: lab/stdlib/collections/lru_cache.py:1: no repr for this type
    note: lab/stdlib/collections/lru_cache.py:95: cannot tell the type of element 0 of this tuple (an empty list or a value of unknown type); give it a name with an annotation

`point_records.py`

    lab/stdlib/collections/point_records.py:1:1: not in the subset: import of 'collections' with a use that is not built: Counter, defaultdict (int, float, str, list, lambda: <constant>), OrderedDict and deque are built for str / int / tuple keys and int / float / str / tuple elements; the rest of the module is not (namedtuple and ChainMap are built by the library pass) -- the notes below name the use (the general path could not build this program either); general path: keyword arguments in a call through a function value
    note: lab/stdlib/collections/point_records.py:28: _field_defaults: not built
    note: lab/stdlib/collections/point_records.py:1: from collections import namedtuple: namedtuple is not built -- its fields carry no types and a tuple is not a value here; write a @dataclass with annotated fields (or a class with __init__)
    note: lab/stdlib/collections/point_records.py:17: a list display holding elements of different types (int and str) is not built; keep one element type in the list
    note: lab/stdlib/collections/point_records.py:22: a comparison of tuples of different shapes (or of a tuple with something else); compare field by field

## Reasons fixed

1. `Counter.subtract` (the blocker shared by `counter_edges`): `python/pkg-v12/collib.py` lowers
   `c.subtract(iterable)` / `c.subtract(mapping)` to typed helpers, and
   `python/pkg-v12/pyboxed2.py` adds the general-path runtime pair (`ail__counter_subtract`,
   `ail__counter_subtract_map`).  The mapping form handles a dict display or comprehension, a
   module-level dict, an unannotated name bound to a dict, a loop variable over dicts, and a mapping
   reached through an attribute, a list item or a dict value; `ChainMap` subtracts every item's value
   through `items()`.  The typed helper walks `other.keys()` (a tuple-keyed table has no `__iter__`),
   and the general path reads the `ks` / `vs` / `live` rows of a tuple-keyed table before subtracting.
   A mapping whose value type is not int is refused by name, and an argument whose type cannot be
   told is left to the general path, which dispatches on the runtime type.

2. `Counter(mapping)` where the mapping has tuple keys (the blocker for `coordinate_freq`, and the
   reason the others could not use tuple-keyed inventory data): the tuple pass makes such a mapping a
   table class, but the general path's `Counter` reads a mapping only as `AIL_T_DICT`, so it stopped with
   `TypeError: '_AilD_Pi_iQ__i' object is not iterable`.  In `tupexpr.py` / `tupcalls.py`, a mapping
   display passed straight to `Counter(...)` is kept a plain dict, and any other table-typed mapping is
   converted back through the table's `items` helper before the call.  Probes `q1`-`q8` cover direct
   literals, a function argument, a function return, a list item, an instance attribute, a dict value,
   empty mappings, zero/negative counts and the int-keyed/iterable Counter forms, on both builds.

3. The lab programs' own CPython bugs were corrected so the oracle is a real successful program:
   `config_layers` sorted a mixed bool/int value list and called `dict(ChainMap)`; `lru_cache` popped a
   key it had already evicted; `point_records` called `_make` with too few fields.  These edits did not
   remove a build refusal.

## Follow-ups (out of scope here)

1. **`OrderedDict.popitem` as an expression** (`log_report.py:37`, `print(order.popitem(last=False))`).
   Built only as a statement or `k, v = d.popitem(last=...)`.  A result-position form needs a tuple value
   from the collections pass; exact text is in the refusal block above.

2. **Iterating an `OrderedDict` and general-path `OrderedDict.get`** (`lru_cache.py`): the typed path needs
   `__iter__` to be `return iter(...)` or a generator; the general path refuses `get()` with too many
   positional arguments.  Exact text is above.

3. **`namedtuple`** (`point_records.py`): the library pass knows the name but not typed fields, defaults,
   `_replace`, `_asdict` or `_field_defaults`; the refusal names each use (above).  A typed namedtuple
   lowering is the big new feature here.

## Generated C of the compare tasks

Checked against `HEAD` with `compile --syntax python` and a fresh `--debug-dir` for every
`lab/compare/src/*/main.py`: `berth_sim`, `echo_pack`, `ledger_bin`, `term_rank` and `ticket_audit` are
byte-identical; `chain_relax` and `rail_transfer` are byte-identical with `--exact-int` (as the compare
harness builds them); `scar_life`, `tally_lang` and `tree_fold` fail to build identically before and
after (same refusal text, so they generate no C).
