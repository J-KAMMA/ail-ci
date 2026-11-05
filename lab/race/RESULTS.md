# Race probe suite: measured today

`python3 lab/race/run.py`. CPython 3.12.3; the default AIL build and `AIL_UNIFIED_FORCE=1`; hybrid probes built with `ail build --cpython`; `AIL_THREADS` 1, 2, 4, 16, three runs each.

## Today

| count | value |
|---|---|
| silent races | **0** |
| safe matched | **11** of 12 |
| safe GIL-free | **11** of 12 |

No racy probe was a silent race: every one was refused by name or built on the general path under the lock, printed CPython's output, and passed TSan where it had a typed parallel build.

## Per-probe table

| probe | kind | default path | default match | force path | force match | hybrid | TSan |
|---|---|---|---|---|---|---|---|
| racy/float_cell.py | racy | general | yes | general (forced) | yes | - | - |
| racy/global_add.py | racy | general | yes | general (forced) | yes | - | - |
| racy/map_writes_global.py | racy | general | yes | general (forced) | yes | - | - |
| racy/max_cell.py | racy | general | yes | general (forced) | yes | - | - |
| racy/mod_two.py | racy | general | yes | general (forced) | yes | - | - |
| racy/neighbour.py | racy | general | yes | general (forced) | yes | - | - |
| racy/nested_writes_outer.py | racy | general | yes | general (forced) | yes | - | - |
| racy/resize_while_index.py | racy | general | yes | general (forced) | yes | - | - |
| racy/same_list_twice.py | racy | general | yes | general (forced) | yes | - | - |
| racy/shared_append.py | racy | general | yes | general (forced) | yes | - | - |
| racy/shared_dict.py | racy | general | yes | general (forced) | yes | - | - |
| racy/submit_shared.py | racy | general | yes | general (forced) | yes | - | - |
| racy/two_names.py | racy | general | yes | general (forced) | yes | - | - |
| racy/write_slot0.py | racy | general | yes | general (forced) | yes | - | - |
| safe/exception_first.py | safe | general | yes | general (forced) | yes | - | - |
| safe/int_beyond_int64.py | safe | typed parallel | no | general (forced) | no | - | exit 1: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| safe/large_map.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_float.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_int.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/more_results.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/one_worker.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/partial_sums.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/pool_map.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/sixteen_on_three.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/thread_blocks.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/thread_k.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| hybrid/hybrid_bytearray.py | hybrid | refused | no | refused | no | accelerated tagged; extension loaded; match yes | - |
| hybrid/hybrid_ints.py | hybrid | typed parallel | yes | general (forced) | yes | accelerated combine; extension loaded; match yes | - |
| hybrid/hybrid_list_append.py | hybrid | general | yes | general (forced) | yes | accelerated total; extension loaded; match yes | - |

## Notes

- Paths: `typed parallel` is the lock-free `_ail_par_range` build (its C holds `ail_par_run`); `general` is the `note: ... built on the general path ...` build under one lock; `refused` is a compile-time refusal by name.
- `force` is `AIL_UNIFIED_FORCE=1`, which the job asks for as the second build. It forces the general path for every program, so it is a soundness check rather than a second typed build.
- A racy probe is counted silent if its default build is typed parallel, if any run differs from CPython, or if ThreadSanitizer reports on it.
- `safe GIL-free` counts safe probes whose default build is the typed parallel path; it is the count later steps raise.
- Each hybrid row is a helper module `<name>.py` built with `python3 -B AIL_CURRENT/ail_chatgpt.py build --cpython lab/race/hybrid/<name>.py -o <out>`, plus the threaded CPython runner `<name>_run.py`. `run.py` copies the runner to a directory that does not hold the helper, so `import <name>` reaches the generated wrapper and its native module; the `extension loaded` column proves that. The runner's stdout and exit status are compared with CPython.
- The default and forced columns also compile and run the same runner copy in the ordinary AIL builds, so every row has both. Two hybrid runners build there; `hybrid_bytearray_run.py` is refused by both with `general path: join() called with too many positional arguments` (a `bytearray` subscript in a thread body), so that row's match is measured from the hybrid build, where `checksum` stays in CPython and only `tagged` is accelerated.

### Refusals (by name)

- `hybrid/hybrid_bytearray.py` (default): `lab/race/hybrid/hybrid_bytearray_run.py:3:1: not in the subset: threading, queue and concurrent.futures are built on the general path only (one interpreter lock, CPython's GIL semantics); this program is compiled there (the general path could not build this program either); general path: join() called with too many positional arguments`
- `hybrid/hybrid_bytearray.py` (force): `not in the subset: join() called with too many positional arguments`

Elapsed: 182 s. 29 rows (14 racy, 12 safe, 3 hybrid).
