# heapq lab: build results

All twelve programs were built in the default mode (`ail_chatgpt.py compile X.py --syntax python`).
"Typed" is the typed path; "general" means the same command fell back to the general boxed path.
Every built program was compared with CPython 3.12 (stdout and exit status) on both `AIL_IR=0`
and `AIL_IR=1`.

| Program | Initial result | First refusal | Final result |
|---|---|---|---|
| `closest_points.py` | general | - | general |
| `dijkstra.py` | general | - | general |
| `event_sim.py` | general | - | general |
| `from_import.py` | refused | `import of 'heapq' with a function that is not built in; ... general path: heapq.merge (not yet published in NAMES_library.json)` | general |
| `heap_errors.py` | general | - | general |
| `heap_variants.py` | general | - | general |
| `median_stream.py` | typed | - | typed |
| `merge_k_lists.py` | refused | `import of 'heapq' with a function that is not built in; ... general path: a starred call of heapq.merge()` | refused |
| `merge_logs.py` | refused | `import of 'heapq' with a function that is not built in; ... general path: heapq.merge (not yet published in NAMES_library.json)` | general |
| `priority_queue.py` | general | - | general |
| `scheduler.py` | general | - | general |
| `top_scores.py` | general | - | general |

Initial: 1 typed, 8 general, 3 refused. Final: 11 build (1 typed, 10 general), 1 refused.

## Fix applied

`heapq.merge` was the blocker shared by the three refused programs. The general path now publishes
`heapq.merge` through `genlib.py` / `prelude_genlib.py` (`_ail_merge`): `key=` and `reverse=`, any
number of positional streams, empty and infinite inputs. It uses CPython's heap algorithm and list
comparison, so equal keys keep the earlier iterable first (also when reversed), `key` is not called
again once only one stream remains, and `__lt__`-only objects and NaNs order as CPython does. The
typed path still falls back to the general path for it, as it already did for `nlargest` /
`nsmallest`.

## Follow-up (out of scope)

`merge_k_lists.py` still refuses because it calls `heapq.merge(*rows)`, and the general path does
not model a starred call argument in general. The current exact refusal is:

```
not in the subset: import of 'heapq' with a function that is not built in; heappush, heappop, heapify, heappushpop, heapreplace, bisect_left, bisect_right, bisect, insort, insort_left and insort_right are built in (no import needed), nothing else from heapq or bisect is (the general path could not build this program either); general path: a starred (*args) call argument (only print(*xs), zip(*rows), and a call to a def f(*args) or a fixed-arity def with no defaults are modelled)
```

Supporting a starred call argument in general (expanding a list into a call) is a new feature, so
this program stays out of the passing set.
