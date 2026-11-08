# fbregion1: which short-lived objects die inside one loop iteration, and what a per-iteration region would save

Measure only. No compiler, runtime or C-compiler file was changed. Base `origin/integ`, branch
`job-fbregion1-11090339`. Every number here comes from `lab/mem/region_census.py` and is reproduced in
`lab/mem/REGION.json`.

    python3 -B lab/mem/region_census.py --census      # 16/16, scratch-instrumented C
    python3 -B lab/mem/region_census.py --static      # the rule over the Python sources
    python3 -B lab/mem/region_census.py --price       # join + (c)

## Method and limits

- **16/16 programs** (10 `lab/compare/src/*/typed.py` tasks plus the 6 `lab/rc/progs`) were built through
  AIL's default path with `--debug-dir`. The tracked build is a **scratch copy of `program.c` only** (never
  the compiler); it printed byte-identical stdout and the same exit status as the plain `-O2` build on all 16.
- Every `for`/`while` body gets a `rt_tick(id)` (its own iteration counter). The **whole** loop is wrapped as
  `{ rt_enter(id); for (...) {...} rt_leave(); }`, so `rt_cur` is the innermost loop actually executing at an
  allocation point: `continue` cannot skip the exit, `break`/normal exit reach it, and `rt_popn` is emitted
  before a `return` or an out-of-loop `goto` (which jump past `rt_leave`). An allocation that is lexically
  inside a runtime helper (`ail__bpay_alloc`, `ail_str_from_int`, `ail_barena_push`, ...) is therefore
  attributed to the **caller's** loop, and a helper's own internal loops restore the caller's loop when they
  exit. This is the corrected predicate: the earlier `rt_cur` was never restored on loop exit, so helper
  allocations after a helper-internal loop (and every allocation after a completed `for`) were attributed to
  a stale loop. The reviewer's `stale.py` probe (a `bytes(100000)` after a three-iteration `for`) now reports
  `heap_same_iter 0`, and `tree_fold`'s int-to-str temporaries now report 9 instead of 1,768,062.
- Every call of `ail_sarena_alloc` (str payload), `ail__bpay_alloc` (bytes payload), `ail__blk_take` (arena
  block), `ail_obj_new` (class object / tuple) and `ail_alloc`/`ail_alloc_raw` (general) gets a site id, its
  innermost enclosing loop id and the requested bytes. The matching releases (`ail_obj_dealloc`,
  `ail__blk_release`, `ail__bpay_release`) and `free` are hooked. `malloc`/`calloc` are wrapped so an
  allocation that actually reaches the heap is marked; a block served from `ail__blk_cache` or an object
  served from the per-size pool is not.
- **Same-iteration** means: at free time the allocation's loop counter has not advanced since the alloc.
  This is the exact "died inside the iteration of its innermost loop" predicate. It excludes values live
  across the back edge and values that escape (the static rule below).
- **`bytes at peak`** is the maximum, over iterations, of the bytes of **heap-backed** allocations freed in
  that same iteration. It is an upper bound on the live bytes a per-iteration bump region would have to
  hold; it is not concurrent-peak RSS. (The JSON also carries `same_bytes_peak` for all allocations,
  including pool-served objects, and the old loop-local `peak_bytes`; the RSS column below uses the
  heap-backed value so pool reuse cannot inflate it.)
- The 6 object programs run with `ulimit -v 1500000`; all runs are sequential (well under the `-j 2` rule).
  `tree_fold` uses the compare input from `gen.py` at N = 3,000,000, chain 0.35.
- **Loud stop on the instruction value.** This runner has no CPU PMU (`/sys/bus/event_source/devices/cpu`
  is absent; `tools/icount.c` fails `perf_event_open`), and `valgrind` is not installed
  (`command -v valgrind` -> nothing). A calibrated dynamic instruction count therefore cannot be produced
  here, and the brief forbids a gcov estimate for a go/no-go number. The `s`/Amdahl/roof/halved columns
  below use **rc1's `est_total_instructions`** (a gcov line-count x static-instruction estimate) only as an
  explicitly-labelled *estimate*; the **instruction route is "not computable"** and is not the go/no-go
  instrument. The pair counts (the numerator) are exact.
- `peak RSS` is rc1's `/usr/bin/time -v` median-of-3 value from `lab/rc/PRICE.json`.

## (a) Dynamic census: what dies inside one iteration

`tracked allocs` counts every allocation seen at the hooks; `same-iter (all)` counts the ones freed in
their allocation's loop iteration; `same-iter heap pairs` restricts that to allocations that really reached
`malloc`/`calloc` and were freed with `free` (the only ones a bump region can turn into ~5-instruction
allocations). `allocator share (all)` = all heap allocs x 170 / estimated instructions; `same-iter share`
= the pairs x 170 / estimated instructions.

| program | tracked allocs | same-iter (all) | same-iter heap pairs | all heap allocs | allocator share (all) | same-iter share | bytes at peak | peak RSS | bytes/RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 3001253 | 1188 | 1186 | 1190 | 0.000% | 0.000% | 64 B | 239.8 MiB | 0.00% |
| chain_relax | 38 | 0 | 0 | 25 | 0.000% | 0.000% | 0 | 3.7 MiB | 0.00% |
| echo_pack | 41 | 0 | 0 | 41 | 0.000% | 0.000% | 0 | 347.7 MiB | 0.00% |
| ledger_bin | 374015 | 0 | 0 | 374014 | 0.165% | 0.000% | 0 | 337.9 MiB | 0.00% |
| rail_transfer | 284923 | 2561 | 105 | 138 | 0.001% | 0.001% | 0.50 MiB | 28.3 MiB | 1.77% |
| scar_life | 1009 | 1 | 0 | 9 | 0.000% | 0.000% | 0 | 17.1 MiB | 0.00% |
| tally_lang | 79 | 11 | 11 | 78 | 0.000% | 0.000% | 11 B | 1.5 MiB | 0.00% |
| term_rank | 26512925 | 25275827 | 15594725 | 16831798 | 4.342% | 4.023% | 114 B | 158.0 MiB | 0.00% |
| ticket_audit | 30943951 | 8462404 | 5 | 2606696 | 0.610% | 0.000% | 17 B | 248.7 MiB | 0.00% |
| tree_fold | 1768097 | 10 | 9 | 1768092 | 0.305% | 0.000% | 22.89 MiB | 404.4 MiB | 5.66% |
| binarytrees | 16369 | 16369 | 0 | 0 | 0.000% | 0.000% | 0 | 1.5 MiB | 0.00% |
| cfold | 32766 | 0 | 0 | 0 | 0.000% | 0.000% | 0 | 1.9 MiB | 0.00% |
| deriv | 163838 | 0 | 0 | 0 | 0.000% | 0.000% | 0 | 7.5 MiB | 0.00% |
| linkedlist | 200000 | 1 | 0 | 0 | 0.000% | 0.000% | 0 | 5.9 MiB | 0.00% |
| objscan | 500000 | 1 | 0 | 0 | 0.000% | 0.000% | 0 | 16.5 MiB | 0.00% |
| rbtree | 100000 | 1 | 0 | 0 | 0.000% | 0.000% | 0 | 5.2 MiB | 0.00% |

### Per kind

`obj_pool` is a class object served from `ail_pool_head` (32 size classes, i.e. <= 264 B); `obj` is the
malloc path for an oversize object. `blk` is an arena block, `alloc`/`bpay` are the payload paths,
`str` is an arena pointer (released in bulk, never per pointer). `bytes at peak` here is
`same_bytes_peak`, **all** allocations, so pool-served objects can appear in it; only the heap column
matters to a region.

| program | kind | allocs | same-iter | heap same-iter | bytes at peak |
|---|---|---:|---:|---:|---:|
| berth_sim | alloc | 1186 | 1186 | 1186 | 64 |
| berth_sim | blk | 3000066 | 2 | 0 | 5 |
| berth_sim | obj_pool | 1 | 0 | 0 | 0 |
| chain_relax | alloc | 14 | 0 | 0 | 0 |
| chain_relax | blk | 17 | 0 | 0 | 0 |
| chain_relax | str | 7 | 0 | 0 | 0 |
| echo_pack | alloc | 40 | 0 | 0 | 0 |
| echo_pack | blk | 1 | 0 | 0 | 0 |
| ledger_bin | alloc | 68 | 0 | 0 | 0 |
| ledger_bin | blk | 373946 | 0 | 0 | 0 |
| ledger_bin | obj_pool | 1 | 0 | 0 | 0 |
| rail_transfer | alloc | 132 | 104 | 104 | 524288 |
| rail_transfer | blk | 184946 | 20 | 1 | 20 |
| rail_transfer | obj | 1 | 0 | 0 | 0 |
| rail_transfer | obj_pool | 99844 | 2437 | 0 | 64 |
| scar_life | alloc | 6 | 0 | 0 | 0 |
| scar_life | blk | 1002 | 1 | 0 | 21 |
| scar_life | obj_pool | 1 | 0 | 0 | 0 |
| tally_lang | alloc | 76 | 11 | 11 | 11 |
| tally_lang | blk | 1 | 0 | 0 | 0 |
| tally_lang | obj | 1 | 0 | 0 | 0 |
| tally_lang | obj_pool | 1 | 0 | 0 | 0 |
| term_rank | alloc | 16519743 | 15594717 | 15594717 | 83 |
| term_rank | blk | 9993181 | 9681110 | 8 | 72 |
| term_rank | obj | 1 | 0 | 0 | 0 |
| ticket_audit | alloc | 2606675 | 2 | 2 | 13 |
| ticket_audit | blk | 8462406 | 8462400 | 3 | 24 |
| ticket_audit | bpay | 19874065 | 2 | 0 | 12 |
| ticket_audit | obj | 1 | 0 | 0 | 0 |
| ticket_audit | str | 804 | 0 | 0 | 0 |
| tree_fold | alloc | 1768066 | 6 | 6 | 24000000 |
| tree_fold | blk | 30 | 4 | 3 | 102 |
| tree_fold | obj_pool | 1 | 0 | 0 | 0 |
| binarytrees | obj_pool | 16369 | 16369 | 0 | 262112 |
| cfold | obj_pool | 32766 | 0 | 0 | 0 |
| deriv | obj_pool | 163838 | 0 | 0 | 0 |
| linkedlist | obj_pool | 200000 | 1 | 0 | 24 |
| objscan | obj_pool | 500000 | 1 | 0 | 24 |
| rbtree | obj_pool | 100000 | 1 | 0 | 40 |

### The sites that carry the churn (heap same-iteration >= 1,000)

| program | C site | function | line | loop | allocs | same-iter | heap same-iter | bytes same-iter |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 17 | ail_stdin_read_raw | 2084 | 129 | 1186 | 1186 | 1186 | 75904 |
| term_rank | 67 | ail_barena_push | 4833 | 180 | 7797376 | 7797358 | 7797358 | 499030912 |
| term_rank | 69 | ail_bytearray_freeze | 5416 | 168 | 7797358 | 7797358 | 7797358 | 50207021 |

Everything else is below 1,000 heap same-iteration pairs: `rail_transfer` 105 (its 512 KiB `alloc` peak
is a `ail_list_snapshot` on the stdin path), `tally_lang` 11, `tree_fold` 9, `ticket_audit` 5.

### rc1's candidates, checked

- **term_rank** is the only real instruction target: **15,594,725** same-iteration heap pairs. The churn is
  two paths per word -- `ail_barena_push` (the pointer table of a fresh bytes arena, 64 B each, 7,797,358
  pairs) and `ail_bytearray_freeze` (the bytes payload, 7,797,358 pairs) -- plus a few small sites. The
  300,025 `ail_str_from_int`, `ail_bytes_fromhex` and `ail_str_return_owned` allocations are **not**
  same-iteration: their sarena payloads are released by `ail_sarena_keep_roots` at the top of the next
  caller iteration, after the tick (the `_fmark1`/`_froots1` call the reviewer identified in `program.c`),
  so they cross the back edge. That is why the corrected count is 15.59 M rather than the stale-`rt_cur`
  16.19 M; the reviewer's 16.49 M also came from the old predicate. `ail_bytes_hex` performs 9,633,891
  same-iteration releases but only **8** reach the heap: the arena's block cache already recycles them. So
  rc1's same-size reuse count (9.35 M) is smaller than the number of iteration-local allocations, and its
  2.4% share is the same order as our 4.02%.
- **ticket_audit** is not a region candidate. It makes 19,874,065 `bpay` payload allocations; only **2** are
  same-iteration and **0** reach the heap (the payload lives in an arena block). The `fields`/blist payloads
  are rebuilt each iteration and released at the top of the next, so they cross the back edge. Its 8,462,400
  same-iteration `blk` releases are cache traffic (3 heap). rc1's 19.9 M `ail__bpay_release` calls are
  arena/cache traffic, so a region adds nothing; rc1's 0.069% instruction share agrees.
- **Class objects**: `objscan` allocates 500,000 objects and frees them, with **0** same-iteration heap
  pairs (all from the per-size pool); `linkedlist` 200,000 and `rbtree` 100,000 likewise 0; `binarytrees`
  16,369 allocations, 0 heap pairs (its 262 KiB `same_bytes_peak` is pool memory the pool already reuses).
  A region adds nothing for class objects.
- **rail_transfer**: 105 heap same-iteration pairs, 512 KiB at peak (the `alloc` path); the `Item` object is
  pool-backed. Nothing.
- **tree_fold**: **9** heap same-iteration pairs, not 1.77 M. Its 22.89 MiB "bytes at peak" is not churn: it
  is one `ail_list_snapshot` (24,000,000 B, 1 allocation) plus a single returned output string (22,555,184 B,
  2 allocations), both allocated once. A region changes their allocator, not their size.
- **echo_pack / ledger_bin / scar_life**: **0** same-iteration heap pairs. Their large loop-local live peaks
  (34.0, 8.9 and 0 MiB) are one-shot input/scratch buffers, not per-iteration churn. The earlier 2/3/8
  same-iteration pairs were stale-`rt_cur` artifacts.

## (b) Static census: what the compile-time proof can mark iteration-local

Rule applied (the brief's rule): an allocation in a loop body is iteration-local when the value is never
stored into a field, list, dict, set, global or closure, never returned, never yielded, never put into an
exception, never passed to a parameter that `ir/borrow.py` does not mark borrowed, and not live across the
loop's back edge. A `__del__` class never qualifies.

The script imports `ir/ownership.py`, `ir/effects.py` and `ir/borrow.py` read-only. `borrow.analyze(ast)` is
actually called on each source for the borrowed-parameter set. `ownership`/`effects` operate on the lowered
IR and are imported as the rule's named references; this source-level census does not run the compiler's
lowering, and the AST flow test implements the escape/liveness predicates they name (this is a limitation,
stated rather than hidden). The value's uses are followed in source order from its binding to the next
rebind; a use in the binding's own right-hand side (`head = Node(i, head)`) or earlier in the loop body
reads the previous iteration's value and blocks as a back-edge read. An allocation lexically inside a
lambda/comprehension is blocked (the closure may run after the iteration). A temporary is followed through
its expression context: a method receiver is read and dies at the call (`w.encode()` feeding `.hex()`), an
operand is consumed (`out += str(x)`), an argument follows `borrow.analyze`, and a store/return/raise blocks.

All 16 programs are covered; `chain_relax` has no allocation expression in its source (its 38 tracked
allocations are all inside stdin/allocator helpers), so 64 sites sit in the other 15: **6 static yes**,
12 in a loop but blocked, 46 not inside a loop. Blockers, by first use: 7 "stored into a container/field"
(`append`/`extend`/`add`), 3 "inside/captured by a closure or comprehension", 1 "used as the for-loop
iterable", 1 "live across the loop back edge (read before it is rebound)". The full 64-site table:

| program | function | line | kind | static iteration-local | first use that blocks the proof | dynamic (program/family) |
|---|---|---:|---|---|---|---|
| berth_sim | main | 71 | obj | no | not inside a loop | - |
| binarytrees | make | 16 | obj | no | not inside a loop | - |
| cfold | leaf | 19 | obj | no | not inside a loop | - |
| cfold | build | 26 | obj | no | not inside a loop | - |
| cfold | build | 27 | obj | no | not inside a loop | - |
| cfold | fold | 39 | obj | no | not inside a loop | - |
| deriv | leaf | 19 | obj | no | not inside a loop | - |
| deriv | build | 26 | obj | no | not inside a loop | - |
| deriv | build | 27 | obj | no | not inside a loop | - |
| deriv | deriv | 34 | obj | no | not inside a loop | - |
| deriv | deriv | 35 | obj | no | not inside a loop | - |
| deriv | deriv | 35 | obj | no | not inside a loop | - |
| deriv | deriv | 36 | obj | no | not inside a loop | - |
| echo_pack | pack | 23 | bpay | no | not inside a loop | - |
| echo_pack | unpack | 100 | bpay | no | not inside a loop | - |
| ledger_bin | main | 61 | obj | no | not inside a loop | - |
| ledger_bin | main | 216 | tuple | no | not inside a loop | - |
| linkedlist | build | 15 | obj | no | live across the loop back edge (read before it is rebound) (line 15) | no |
| objscan | build | 15 | obj | no | stored into append() (line 15) | no |
| rail_transfer | relax | 55 | obj | no | not inside a loop | - |
| rail_transfer | relax | 55 | tuple | no | not inside a loop | - |
| rail_transfer | relax | 57 | obj | no | not inside a loop | - |
| rail_transfer | relax | 57 | tuple | no | not inside a loop | - |
| rail_transfer | solve | 91 | obj | yes |  | no |
| rail_transfer | solve | 93 | tuple | no | inside/captured by a closure or comprehension (line 93) | - |
| rail_transfer | solve | 95 | tuple | no | inside/captured by a closure or comprehension (line 95) | - |
| rail_transfer | main | 208 | obj | no | not inside a loop | - |
| rbtree | insert | 44 | obj | no | not inside a loop | - |
| scar_life | main | 66 | obj | no | not inside a loop | - |
| scar_life | main | 67 | bpay | no | not inside a loop | - |
| scar_life | main | 71 | bpay | no | not inside a loop | - |
| scar_life | main | 95 | bpay | no | not inside a loop | - |
| scar_life | main | 106 | bpay | no | not inside a loop | - |
| scar_life | main | 112 | bpay | no | not inside a loop | - |
| scar_life | main | 157 | bpay | no | stored into extend() (line 157) | no |
| tally_lang | run | 415 | str | no | stored into append() (line 415) | yes |
| tally_lang | run | 416 | str | yes |  | yes |
| tally_lang | main | 468 | obj | no | not inside a loop | - |
| tally_lang | main | 469 | obj | no | not inside a loop | - |
| term_rank | add_term | 22 | bpay | no | not inside a loop | - |
| term_rank | add_term | 24 | bpay | no | not inside a loop | - |
| term_rank | add_term | 24 | str | no | not inside a loop | - |
| term_rank | add_term | 28 | str | no | not inside a loop | - |
| term_rank | add_term | 32 | str | no | not inside a loop | - |
| term_rank | add_term | 34 | str | no | not inside a loop | - |
| term_rank | emit_line | 63 | bpay | yes |  | yes |
| term_rank | main | 94 | bpay | no | used as the for-loop iterable (live across the back edge) (line 94) | yes |
| term_rank | main | 103 | obj | no | not inside a loop | - |
| term_rank | main | 105 | bpay | yes |  | yes |
| term_rank | main | 105 | str | no | stored into add() (line 105) | yes |
| term_rank | main | 128 | bpay | no | not inside a loop | - |
| term_rank | main | 138 | tuple | no | inside/captured by a closure or comprehension (line 138) | - |
| term_rank | main | 139 | bpay | no | stored into extend() (line 139) | yes |
| term_rank | main | 146 | bpay | no | stored into extend() (line 146) | yes |
| term_rank | main | 150 | tuple | no | not inside a loop | - |
| term_rank | main | 151 | bpay | no | not inside a loop | - |
| term_rank | main | 158 | bpay | no | stored into extend() (line 158) | yes |
| ticket_audit | main | 264 | obj | no | not inside a loop | - |
| ticket_audit | main | 331 | tuple | no | not inside a loop | - |
| tree_fold | do_sort | 191 | tuple | no | not inside a loop | - |
| tree_fold | do_print | 280 | str | yes |  | yes |
| tree_fold | do_find | 297 | str | no | not inside a loop | - |
| tree_fold | main | 311 | obj | no | not inside a loop | - |
| tree_fold | main | 380 | str | yes |  | yes |

The `dynamic` column is a **program/family aggregate** (the C allocation for a `str`/`bytes` expression is
made inside a runtime helper, not in the user function, so a per-function join would be fiction); a dash
means the site is not in a loop, so a region does not apply. `lab/mem/REGION.json` carries all 115 C sites
and 115 joined rows.

The 6 static yes sites and what the dynamic side says:

| static site | dynamic verdict |
|---|---|
| term_rank `emit_line:63` bytes | yes: part of the 15.59 M heap pairs (bytearray payload path) |
| term_rank `main:105` bytes | yes: `w.encode()` is read by `.hex()` and dies at that call |
| tree_fold `do_print:280` str | 9 heap pairs only: the int-to-str temps cross the back edge |
| tree_fold `main:380` str | same |
| tally_lang `run:416` str | yes: 11 heap pairs |
| rail_transfer `solve:91` Item | no for a region: the object is pool-backed (0 heap pairs) |

Note on the reviewer's `stat.py` probe: `a = bytes([65]); b.v = a` is blocked (field), `c = bytearray();
lst.append(c)` is blocked (list), `e = bytes([68]); return len(e)` is blocked (return). `d = bytes([67]);
take(d)` is **iteration-local**, because `borrow.analyze` marks `take`'s parameter `x` borrowed (it is never
used in `take`). A callee that stores its parameter is blocked by the same test (`borrow.analyze` demotes
it).

## (c) The price

`pairs` x 170 instructions (rc1's malloc/free pair estimate) is what a bump region (about 5 instructions,
free 0) would remove. `s = pairs x 170 / est_total_instructions`; Amdahl `1/(1-s)`; roof 60% `1/(1-0.6s)`;
halved projection `1+(roof-1)/2`. **These four columns are estimates from rc1's gcov denominator; the
instruction route is NOT COMPUTABLE on this runner and is not the go/no-go instrument.** The RSS route is
computable: same-iteration heap bytes at peak >= 5% of peak RSS on at least two programs, excluding
one-shot bulk peaks, is a GO.

| program | pairs | s (est) | Amdahl (est) | roof 60% (est) | halved (est) | heap same-iter bytes peak | RSS share | go |
|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| berth_sim | 1186 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 64 B | 0.00% |  |
| chain_relax | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| echo_pack | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| ledger_bin | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| rail_transfer | 105 | 0.001% | 1.0000x | 1.0000x | 1.0000x | 0.50 MiB | 1.77% |  |
| scar_life | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| tally_lang | 11 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 11 B | 0.00% |  |
| term_rank | 15594725 | 4.023% | 1.0419x | 1.0247x | 1.0124x | 114 B | 0.00% |  |
| ticket_audit | 5 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 17 B | 0.00% |  |
| tree_fold | 9 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 22.89 MiB | 5.66% | no (one-shot bulk, 9 pairs) |
| binarytrees | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| cfold | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| deriv | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| linkedlist | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| objscan | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |
| rbtree | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0 | 0.00% |  |

**Instruction route: NOT COMPUTABLE.** No PMU and no valgrind on this runner, so the required calibrated
count cannot be produced; the estimates are shown only for orientation. Even taken as an upper bound, the
best halved projection is **1.0124x** (term_rank), below the 1.03x bar; every other program is 1.0000x.

**RSS route:** only `tree_fold` reaches 5% (22.89 MiB, 5.66%), and that peak is a single 24 MB
`ail_list_snapshot` allocated once (9 same-iteration pairs in total); it is excluded as a one-shot bulk
peak, not per-iteration churn. No program qualifies.

**fbregion2: NO-GO.** One program (term_rank) carries genuine instruction churn and it projects to
1.0124x, below the bar; the RSS route has no qualifying program. The object programs are exactly 1.0000x
because the per-size pool already reuses their memory.

### What fbregion2 would edit, and whether it is busy

- `AIL_CURRENT/python/pkg-v12/cruntime.py` -- bump-region runtime and the allocator hooks. Not listed busy.
- `AIL_CURRENT/python/pkg-v12/ir/emit_c.py` -- region enter/exit at loop boundaries and routing the five
  allocators. Not listed busy.
- `AIL_CURRENT/python/pkg-v12/ir/ownership.py` -- the iteration-local proof (liveness, escape). **Busy/shared**
  with rc2/rc3; it already carries the `test_ail_borrowed_*` tests that rc2 extended.
- `AIL_CURRENT/python/pkg-v12/ir/effects.py` -- effect records the proof reads. Shared with rc2/rc3.
- `AIL_CURRENT/python/pkg-v12/ir/borrow.py` -- the borrowed-parameter set (read-only input here).
- `AIL_CURRENT/python/pkg-v12/pyfunc.py` -- codegen/emission of the helpers. **Busy** (codegen).
- `AIL_CURRENT/python/pkg-v12/ir/passes/*` -- **busy** (bce-ranges, pyreach).

If it is built anyway, the only defensible target is term_rank's bytearray/barena churn (15.59 M pairs,
4.02% of estimated instructions); behind an opt-in the expected halved instruction gain is <= 1.013x, below
the 1.03x bar.

## Reproduce

    python3 -B lab/mem/region_census.py --census
    python3 -B lab/mem/region_census.py --static
    python3 -B lab/mem/region_census.py --price

`REGION.json` carries `programs` (per-program totals and kinds), `dynamic_sites` (115 C sites),
`static_sites` (64 Python sites), `sites` (115 joined rows) and `price`.
