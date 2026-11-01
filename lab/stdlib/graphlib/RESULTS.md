# `graphlib` coverage (job-std_graphlib-11020038)

Environment: CPython 3.12.3, the default build
`python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python` (typed path first, general path as the
fallback). Date: 2026-11-01.

All twelve programs were built in the default mode. "General" means the typed path refused
`import graphlib` by name and the same command built the program on the general path.

## Before the fix

| program | result | first refusal |
| --- | --- | --- |
| `add_edges.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `build_order.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `cycle_detect.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `dependency_layers.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `diamond_deps.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `empty_graph.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `from_import.py` | refused | `not in the subset: import of 'graphlib' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `get_ready_loop.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `graph_keyword.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `reverse_lookup.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `sorter_errors.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |
| `task_scheduler.py` | refused | `not in the subset: graphlib.TopologicalSorter (not yet published in NAMES_library.json)` |

Before: 0 of 12 built, 12 refused, all on the same missing `graphlib.TopologicalSorter`.

## After the fix

| program | result |
| --- | --- |
| `add_edges.py` | general |
| `build_order.py` | general |
| `cycle_detect.py` | general |
| `dependency_layers.py` | general |
| `diamond_deps.py` | general |
| `empty_graph.py` | general |
| `from_import.py` | general |
| `get_ready_loop.py` | general |
| `graph_keyword.py` | general |
| `reverse_lookup.py` | general |
| `sorter_errors.py` | general |
| `task_scheduler.py` | general |

After: 12 of 12 build (12 general) and every one matches CPython's stdout and exit code on both
`AIL_IR=0` and `AIL_IR=1`. `AIL_CURRENT/test_ail_std_graphlib.py` (registered by
`AIL_CURRENT/tests.d/test_ail_std_graphlib.txt`) compiles every program in the default mode, runs it and
compares the exit status and stdout with CPython.

## What was fixed

`graphlib.TopologicalSorter` and `graphlib.CycleError` were the single blocker shared by all twelve
programs. The general path now publishes both through `python/pkg-v12/genlib.py` (the `TABLE` entries and
the `graph=` keyword) and `python/pkg-v12/prelude_genlib.py`:

* the constructor with `graph=None` or `graph=...`, `add(node, *predecessors)` (no predecessors, repeated
  adds, duplicate predecessors), `prepare()`, `get_ready()`, `is_active()`, `bool(sorter)`, `done(*nodes)`
  and `static_order()` (as a generator, including partial iteration);
* CPython's node states and insertion order, so `static_order`, the `get_ready` batches and the `done`
  order match;
* CPython's `CycleError` (a `ValueError` subclass) with the same two `args`, message, `str()` and cycle
  list, including self-loops, several cycles and the nodes that can still be returned after `prepare`
  raises;
* CPython's `ValueError` texts for `prepare()` twice, `add` after `prepare`, `get_ready` / `is_active` /
  `done` before `prepare`, an unknown node, a node not yet passed out and a node already marked done.

The typed path still refuses `import graphlib` by name; the default command uses the general path for
these programs.

## Follow-up

None: all twelve programs build. The general path does not model `TopologicalSorter[T]` (CPython's
`__class_getitem__` generic alias) or `graphlib.__all__`; neither appears in the twelve programs.
