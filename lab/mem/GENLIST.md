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

## (b) Census: 6 programs, general path

Each program is `lab/compare/src/<task>/typed.py` built with `AIL_UNIFIED_FORCE=1`. The census copy of the C walks
every live LIST at each new 5% high of the GC byte count and keeps the walk with the most list-buffer bytes. "int" =
every element has tag `AIL_T_INT` (a bool is not). Peak RSS is the median of 3 (`/usr/bin/time -v`); instructions are
from `tools/icount.c` (perf_event_open worked). All 6: census build output == plain build output == CPython 3.12 on
`main.py` (stdout and exit status).

Memory cap: every run under `ulimit -v 1700000`. Three inputs are scaled down: the full berth_sim and echo_pack perf
inputs stop loudly with `AIL internal error: out of memory` under that cap (the general path needs more than 1.7 GB
there), and tree_fold is superlinear on the general path (n=200,000 runs over 180 s; the full 3,000,000 ran 131e9
instructions before it hit the cap), so it runs at n=50,000. chain_relax and scar_life run over 180 s, rail_transfer
does not build under `AIL_UNIFIED_FORCE=1` (typed.py and main.py both refused), tally_lang peaks at 2.5 MB (nothing
to save); those four are left out.

| program | input | peak RSS | instructions | lists (int / all) | elements (int / all) | list buffers / RSS | int elements x32 B / RSS | projected RSS | gain | gain, saving halved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tree_fold | n=50,000 | 73.3 MiB | 23.38e9 | 39 / 48 | 0.94M / 1.16M | 0.59 | 0.39 | 51.7 MiB | 1.42x | 1.17x |
| berth_sim | ns=1,000,000 | 412.6 MiB | 16.06e9 | 28 / 31 | 10.52M / 10.52M | 0.85 | 0.78 | 171.7 MiB | 2.40x | 1.41x |
| echo_pack | size=10 MB | 1066.3 MiB | 125.40e9 | 228,063 / 228,064 | 16.18M / 16.18M | 1.26 | 0.46 | 695.9 MiB | 1.53x | 1.21x |
| ledger_bin | perf | 1053.3 MiB | 206.15e9 | 12 / 38,003 | 21.76M / 22.70M | 0.72 | 0.63 | 555.3 MiB | 1.90x | 1.31x |
| term_rank | perf | 1146.0 MiB | 243.12e9 | 194,388 / 1,508,247 | 16.16M / 19.09M | 0.61 | 0.43 | 776.3 MiB | 1.48x | 1.19x |
| ticket_audit | perf | 968.4 MiB | 332.97e9 | 10 / 338,088 | 0.24M / 1.67M | 0.09 | 0.01 | 962.8 MiB | 1.01x | 1.00x |

Projection: an INT list keeps 8 B per slot instead of 32 B, so the saving counted is 24 B per used int element at the
census peak. The unused doubled tail of a buffer is not counted (mostly untouched pages: echo_pack's list capacity is
larger than its whole peak RSS), nor the 4x smaller doubling slack, so the column is a lower bound on the byte
saving at that moment; the "halved" column halves it once more (the caller's rule) to cover the RSS peak not being
the list peak and the conversion copies.

## Step 3: emulation not built

The brief's step 3 (hand-edit the scratch C so all-int lists hold `int64_t`) was not done: an INT layout changes every
one of the 126 functions above that index `->p` directly, including the compiled user functions, so a faithful
hand edit of two 1.4 MB C files is the implementation itself, not a 25-minute emulation. The RSS rows above are
projections from the census, not emulation measurements, and **run instructions with an INT layout are unmeasured**
(the brief's "instructions not worse on any" half of the gate is open). What an INT layout would change for
instructions: element reads lose nothing (an int read is already one load plus a tag test), every element access gains
a strategy test, copies and `[0] * n` move 4x fewer bytes.

## Decision

- RSS: at least 10% lower on 5 of 6 programs even after halving the saving (tree_fold 1.17x, berth_sim 1.41x, echo_pack
  1.21x, ledger_bin 1.31x, term_rank 1.19x; ticket_audit 1.00x, its lists hold strs).
- Instructions: unmeasured (no emulation).
- fbgenint2 as written stops before code: its stop rule is "more than 25 sites", and the element array is touched by
  126 functions across 10 runtime files plus inline code from the generators (pyboxed2.py, unified.py). It needs its
  own design pass first, for example: rename `ail_vecobj.p` so the C compiler lists every site, route them through a
  small accessor set, and keep a one-way INT -> OBJ conversion at a single choke point; or decide that P1 (pyreach)
  moving these programs to the typed path (8 B already) covers them.

Functions fbgenint2 (or its design pass) must change: `ail_vec_reserve`, `ail_vec_new`, `ail__free_payload`,
`ail_gc_mark_value`, `ail_vec_getitem`, `ail_vec_getslice`, `ail_list_append`, `ail_list_pop`, `ail_list_insert`,
`ail_vec_index`, `ail_vec_count`, `ail_list_reverse`, `ail_list_extend`, `ail_list_setitem`, `ail_list_delitem`,
`ail_list_sort`, `ail_meth_list_*`, `ail_op_add`, `ail_op_imul`, `ail_op_contains`, `ail_next`, `ail__write_repr_body`,
`ail_copy_shallow`, the str/heapq/deque/itertools/statistics/copy/groupby helpers, and the inline `->p[i]` emitters in
pyboxed2.py and unified.py (126 functions in tree_fold's C alone).

go
