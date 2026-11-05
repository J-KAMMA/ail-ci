# GENLIST: what a general-path list of ints costs, and how much of peak RSS it holds (fbgenint1)

Base `origin/integ` 8f7bc17cc. Measured 2026-11-06 on the WSL laptop. Script: `lab/mem/genlist_census.py`; raw
numbers: `lab/mem/GENLIST.json`.

## (a) The representation

The general path (`AIL_UNIFIED_FORCE=1`, runtime in `AIL_CURRENT/python/pkg-v12/cruntime.py`, the v2 boxed section)
backs LIST and TUPLE with one object (`cruntime.py:11447`):

```c
typedef struct { ail_gcobj hdr; ail_obj *p; int64_t n, cap;
    uint8_t from_generator; int64_t gen_idx; } ail_vecobj;          /* 56 B header, a GC object */
typedef struct ail_obj { uint8_t tag; union { int64_t i;           /* BOOL, INT */
    struct { ail_gcobj *backing; int64_t off, len; } sv;            /* STR view, 24 B */
    ail_gcobj *o; }; } ail_obj;                                     /* cruntime.py:11286 -> 32 B */
```

- **32 B per element slot**, against the typed path's 8 B (`ail_list {int64_t *p; n, cap}`): 4x. The union is sized
  by the inline STR view (3 words), plus the 1-byte tag padded to 8.
- An int element is **tagged inline** (`tag = AIL_T_INT`, value in `.i`), not boxed: no per-int allocation. Only floats
  are boxed (`ail_floatbox`, 24 B more each).
- The buffer `p` is a plain `malloc` block owned by the header (no refcount), grown by doubling from 8
  (`ail_vec_reserve`, `cruntime.py:11463`); so an appended list holds 32-64 B per element, `[0] * n` exactly 32 B.
  The sweep frees it in `ail__free_payload` (`cruntime.py:14693`).

Functions that read or write elements: the list helpers `ail_vec_getitem` / `ail_vec_getslice` / `ail_list_append` /
`ail_list_pop` / `ail_list_insert` / `ail_vec_index` / `ail_vec_count` / `ail_list_reverse` / `ail_list_extend` /
`ail_list_setitem` / `ail_list_delitem` / `ail_list_sort` (`cruntime.py:15859-15976`), `ail_meth_list_*`
(`cruntime.py:20396` and the deque section), `ail_op_add` / `ail_op_imul` / `ail_op_contains` / `ail_next` /
`ail__write_repr_body` / `ail_copy_shallow` / `ail_gc_mark_value`, and many more: in tree_fold's generated C,
**126 functions** touch a `ail_vecobj` element array (`->p[...]`) directly, among them str split/join, heapq, deque,
itertools, statistics, copy, groupby, bytes, and the compiled user functions themselves (`pf_*`: pyboxed2.py and
unified.py emit `((ail_vecobj *)x.o)->p[i]` inline). The `ail_vecobj` type is named in 10 runtime files (cruntime.py
136 times, pyboxed2.py 27, safetyrt.py 16, statbrt.py 9, unified.py 9, randrt.py 7, rebrt.py 7, dictviews.py 3,
mix_call.h 3, boxclosure.py 2).
