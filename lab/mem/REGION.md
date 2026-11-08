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
- Every `for`/`while` body gets a `rt_tick(id)`; every call of `ail_sarena_alloc` (str payload),
  `ail__bpay_alloc` (bytes payload), `ail__blk_take` (arena block), `ail_obj_new` (class object / tuple) and
  `ail_alloc`/`ail_alloc_raw` (general) gets a site id, its innermost enclosing loop id and the requested
  bytes. The matching releases (`ail_obj_dealloc`, `ail__blk_release`, `ail__bpay_release`) and `free` are
  hooked. `malloc`/`calloc` are wrapped so an allocation that actually reaches the heap is marked; a block
  served from `ail__blk_cache` or an object served from the per-size pool is not.
- **Same-iteration** means: at free time the allocation's loop counter has not advanced since the alloc.
  This is the exact "died inside the iteration of its innermost loop" predicate. It excludes values live
  across the back edge and values that escape (the static rule below).
- The 6 object programs run with `ulimit -v 1500000`; all runs are sequential (well under the `-j 2` rule).
  `tree_fold` uses the compare input from `gen.py` at N = 3,000,000, chain 0.35.
- **Loud stop on the instruction value.** This runner has no CPU PMU (`/sys/bus/event_source/devices/cpu`
  is absent; `tools/icount.c` fails `perf_event_open`), and `valgrind` is not installed
  (`command -v valgrind` -> nothing). A calibrated dynamic instruction count therefore cannot be produced
  here. The `s` column uses **rc1's `est_total_instructions`** (a gcov line-count x static-instruction
  estimate) only as the denominator, and is labelled an *estimate*, not a calibrated count. It is not the
  go/no-go instrument the brief asks for; the counts of pairs (the numerator) are exact.
- `peak RSS` is rc1's `/usr/bin/time -v` median-of-3 value from `lab/rc/PRICE.json`.
- **`bytes at peak`** is the peak concurrent live bytes of allocations that (a) were made inside a loop and
  (b) died in the same iteration: the maximum of the per-iteration live total. It is an upper bound on what
  a per-iteration region would have to hold, and it includes one-shot buffers (noted below), so it is not a
  claim of reclaimable RSS.

## (a) Dynamic census: what dies inside one iteration

`tracked allocs` counts every allocation seen at the hooks; `same-iter (all)` counts the ones freed in
their allocation's loop iteration; `same-iter heap pairs` restricts that to allocations that really reached
`malloc`/`calloc` and were freed with `free` (the only ones a bump region can turn into ~5-instruction
allocations). `allocator share (all)` = all heap allocs x 170 / estimated instructions; `same-iter share`
= the pairs x 170 / estimated instructions.

| program | tracked allocs | same-iter (all) | same-iter heap pairs | all heap allocs | allocator share (all) | same-iter share | bytes at peak | peak RSS | bytes/RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 3001253 | 1249 | 1186 | 1190 | 0.000% | 0.000% | 0.00 MiB | 239.8 MiB | 0.00% |
| chain_relax | 38 | 12 | 7 | 25 | 0.000% | 0.000% | 0.00 MiB | 3.7 MiB | 0.02% |
| echo_pack | 41 | 2 | 2 | 41 | 0.000% | 0.000% | 34.00 MiB | 347.7 MiB | 9.78% |
| ledger_bin | 374015 | 4 | 3 | 374014 | 0.165% | 0.000% | 64.86 MiB | 337.9 MiB | 19.20% |
| rail_transfer | 284923 | 187480 | 131 | 138 | 0.001% | 0.001% | 0.79 MiB | 28.3 MiB | 2.81% |
| scar_life | 1009 | 1007 | 8 | 9 | 0.000% | 0.000% | 8.00 MiB | 17.1 MiB | 46.72% |
| tally_lang | 79 | 26 | 25 | 78 | 0.000% | 0.000% | 0.00 MiB | 1.5 MiB | 0.04% |
| term_rank | 26512925 | 23979744 | 16194761 | 16831798 | 4.342% | 4.177% | 8.00 MiB | 158.0 MiB | 5.06% |
| ticket_audit | 30943951 | 5723217 | 813 | 2606696 | 0.610% | 0.000% | 2.13 MiB | 248.7 MiB | 0.85% |
| tree_fold | 1768097 | 1768065 | 1768062 | 1768092 | 0.305% | 0.305% | 22.89 MiB | 404.4 MiB | 5.66% |
| binarytrees | 16369 | 16369 | 0 | 0 | 0.000% | 0.000% | 0.00 MiB | 1.5 MiB | 0.00% |
| cfold | 32766 | 0 | 0 | 0 | 0.000% | 0.000% | 0.00 MiB | 1.9 MiB | 0.00% |
| deriv | 163838 | 0 | 0 | 0 | 0.000% | 0.000% | 0.00 MiB | 7.5 MiB | 0.00% |
| linkedlist | 200000 | 1 | 0 | 0 | 0.000% | 0.000% | 0.00 MiB | 5.9 MiB | 0.00% |
| objscan | 500000 | 1 | 0 | 0 | 0.000% | 0.000% | 0.00 MiB | 16.5 MiB | 0.00% |
| rbtree | 100000 | 1 | 0 | 0 | 0.000% | 0.000% | 0.00 MiB | 5.2 MiB | 0.00% |

### Per kind

`obj_pool` is a class object served from `ail_pool_head` (32 size classes, i.e. <= 264 B); `obj` is the
malloc path for an oversize object. `blk` is an arena block, `alloc`/`bpay` are the payload paths,
`str` is an arena pointer (released in bulk, never per pointer).

| program | kind | allocs | same-iter | heap same-iter | peak bytes |
|---|---|---:|---:|---:|---:|
| berth_sim | alloc | 1186 | 1186 | 1186 | 64 |
| berth_sim | blk | 3000066 | 63 | 0 | 45 |
| berth_sim | obj_pool | 1 | 0 | 0 | 80 |
| chain_relax | alloc | 14 | 3 | 3 | 545 |
| chain_relax | blk | 17 | 9 | 4 | 37 |
| chain_relax | str | 7 | 0 | 0 | 0 |
| echo_pack | alloc | 40 | 2 | 2 | 35651680 |
| echo_pack | blk | 1 | 0 | 0 | 0 |
| ledger_bin | alloc | 68 | 2 | 2 | 68011185 |
| ledger_bin | blk | 373946 | 1 | 1 | 12 |
| ledger_bin | obj_pool | 1 | 1 | 0 | 40 |
| rail_transfer | alloc | 132 | 129 | 129 | 524288 |
| rail_transfer | blk | 184946 | 184924 | 1 | 309100 |
| rail_transfer | obj | 1 | 1 | 1 | 320 |
| rail_transfer | obj_pool | 99844 | 2426 | 0 | 160 |
| scar_life | alloc | 6 | 6 | 6 | 8388768 |
| scar_life | blk | 1002 | 1001 | 2 | 26 |
| scar_life | obj_pool | 1 | 0 | 0 | 0 |
| tally_lang | alloc | 76 | 24 | 24 | 577 |
| tally_lang | blk | 1 | 0 | 0 | 0 |
| tally_lang | obj | 1 | 1 | 1 | 408 |
| tally_lang | obj_pool | 1 | 1 | 0 | 72 |
| term_rank | alloc | 16519743 | 15894744 | 15894744 | 8388650 |
| term_rank | blk | 9993181 | 8084999 | 300016 | 48 |
| term_rank | obj | 1 | 1 | 1 | 384 |
| ticket_audit | alloc | 2606675 | 808 | 808 | 2228291 |
| ticket_audit | blk | 8462406 | 2861606 | 3 | 24 |
| ticket_audit | bpay | 19874065 | 2860802 | 1 | 24 |
| ticket_audit | obj | 1 | 1 | 1 | 600 |
| ticket_audit | str | 804 | 0 | 0 | 0 |
| tree_fold | alloc | 1768066 | 1768059 | 1768059 | 24000064 |
| tree_fold | blk | 30 | 5 | 3 | 124 |
| tree_fold | obj_pool | 1 | 1 | 0 | 160 |
| binarytrees | obj_pool | 16369 | 16369 | 0 | 262112 |
| cfold | obj_pool | 32766 | 0 | 0 | 0 |
| deriv | obj_pool | 163838 | 0 | 0 | 0 |
| linkedlist | obj_pool | 200000 | 1 | 0 | 24 |
| objscan | obj_pool | 500000 | 1 | 0 | 24 |
| rbtree | obj_pool | 100000 | 1 | 0 | 40 |

### The sites that carry the churn (heap same-iteration >= 1,000)

| program | C site | function | line | loop | allocs | same-iter | heap same-iter | bytes same-iter |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 17 | ail_stdin_read_raw | 2084 | 45 | 1186 | 1186 | 1186 | 75904 |
| term_rank | 67 | ail_barena_push | 4833 | 18 | 7797376 | 7797359 | 7797359 | 499030976 |
| term_rank | 69 | ail_bytearray_freeze | 5416 | 169 | 7797358 | 7797358 | 7797358 | 50207021 |
| term_rank | 19 | ail_str_from_int | 1323 | 23 | 300025 | 300025 | 300025 | 2086577 |
| term_rank | 11 | ail__str_cat_slow | 1185 | 9 | 347243 | 300025 | 300009 | 4800400 |
| tree_fold | 22 | ail_str_from_int | 1661 | 57 | 1768053 | 1768052 | 1768052 | 7879863 |

### rc1's candidates, checked

- **term_rank** is the real one: 16,194,761 same-iteration heap pairs. The churn is two paths per word --
  `ail_barena_push` (the pointer table of a fresh bytes arena, 64 B each, 7,797,359 pairs) and
  `ail_bytearray_freeze` (the bytes payload, 7,797,358 pairs) -- plus 300,025 `ail_str_from_int` and
  300,009 `ail__str_cat_slow` blocks. `ail_bytes_hex` performs 7,784,974 same-iteration releases but only
  **7** reach the heap: the arena's block cache already recycles them. That is why rc1's same-size reuse
  count (9.35 M) is smaller than the number of iteration-local allocations but its 2.4% share is the same
  order as our 4.18%.
- **ticket_audit** is not a region candidate. It makes 19,874,065 `bpay` payload allocations and releases
  2,860,802 of them in the same iteration, but only **1** reaches the heap (the `bpay` payload lives in an
  arena block); `ail_str_catn` is 2,800,801 same-iteration releases and also 1 heap alloc. The 19.9 M
  `ail__bpay_release` calls rc1 counted are arena/cache traffic, so a region adds nothing. This matches
  rc1's 0.069% instruction share for ticket_audit.
- **Class objects**: `objscan` allocates 500,000 objects and frees all of them, with **0** same-iteration
  heap pairs (all from the per-size pool); `linkedlist` 200,000 and `rbtree` 100,000 likewise 0;
  `binarytrees` 16,369 allocations, 0 heap pairs. The pool already reuses the memory, so a region adds
  nothing for class objects.
- **rail_transfer**: 187,480 same-iteration releases but 131 heap pairs; the `Item` object is pool-backed.
  Nothing.
- **tree_fold**: 1,768,062 heap pairs, almost all `ail_str_from_int` (1,768,052 pairs, 4.5 B each) in
  `do_print` -- the int-to-str temporaries. The 22.9 MiB "bytes at peak" is not churn: it is one
  `ail_list_snapshot` (24,000,000 B, 1 allocation) plus a single returned output string (22,555,223 B,
  2 allocations). A region changes their allocator, not their size.
- **echo_pack / ledger_bin / scar_life**: 2, 3 and 8 same-iteration heap pairs. Their large "bytes at peak"
  (34.0, 64.9 and 8.0 MiB) are one-shot input/scratch buffers (`ail_bytes_return_owned` 59 MB with one
  allocation in ledger_bin; two 4 MiB `ail_bytearray_new` in scar_life).

## (b) Static census: what the compile-time proof can mark iteration-local

Rule applied (the brief's rule): an allocation in a loop body is iteration-local when the value is never
stored into a field, list, dict, set, global or closure, never returned, never yielded, never put into an
exception, never passed to a parameter that `ir/borrow.py` does not mark borrowed, and not live across the
loop's back edge. A `__del__` class never qualifies. The script imports `ir/ownership.py`,
`ir/effects.py` and `ir/borrow.py` read-only; the borrowed-parameter set is `borrow.analyze(ast)` on each
source. All 16 programs are covered; `chain_relax` has no allocation expression in its source (its 38
tracked allocations are all inside the stdin/allocator helpers), so 64 sites sit in the other 15;
**7 static yes**, 11 in a loop but blocked, 46 not inside a loop.

Blockers, by first use: 46 "not inside a loop"; 7 "stored into a container/field"; 2 "captured in a
closure/comprehension"; 1 "used as the for-loop iterable (live across the back edge)"; 1 "passed to a
callee whose parameter is not borrowed" (`Node(...)` in `linkedlist.build`). The full 64-site table:

| program | function | line | kind | static iteration-local | first use that blocks the proof | dynamic (program/family) | dynamic heap pairs |
|---|---|---:|---|---|---|---|---:|
| berth_sim | main | 71 | obj | no | not inside a loop | - | 0 |
| binarytrees | make | 16 | obj | no | not inside a loop | - | 0 |
| cfold | leaf | 19 | obj | no | not inside a loop | - | 0 |
| cfold | build | 26 | obj | no | not inside a loop | - | 0 |
| cfold | build | 27 | obj | no | not inside a loop | - | 0 |
| cfold | fold | 39 | obj | no | not inside a loop | - | 0 |
| deriv | leaf | 19 | obj | no | not inside a loop | - | 0 |
| deriv | build | 26 | obj | no | not inside a loop | - | 0 |
| deriv | build | 27 | obj | no | not inside a loop | - | 0 |
| deriv | deriv | 34 | obj | no | not inside a loop | - | 0 |
| deriv | deriv | 35 | obj | no | not inside a loop | - | 0 |
| deriv | deriv | 35 | obj | no | not inside a loop | - | 0 |
| deriv | deriv | 36 | obj | no | not inside a loop | - | 0 |
| echo_pack | pack | 23 | bpay | no | not inside a loop | - | 0 |
| echo_pack | unpack | 100 | bpay | no | not inside a loop | - | 0 |
| ledger_bin | main | 61 | obj | no | not inside a loop | - | 0 |
| ledger_bin | main | 216 | tuple | no | not inside a loop | - | 0 |
| linkedlist | build | 15 | obj | no | passed to unknown callee Node (line 15) | no | 0 |
| objscan | build | 15 | obj | no | stored into append() | no | 0 |
| rail_transfer | relax | 55 | obj | no | not inside a loop | - | 0 |
| rail_transfer | relax | 55 | tuple | no | not inside a loop | - | 0 |
| rail_transfer | relax | 57 | obj | no | not inside a loop | - | 0 |
| rail_transfer | relax | 57 | tuple | no | not inside a loop | - | 0 |
| rail_transfer | solve | 91 | obj | yes |  | yes | 1 |
| rail_transfer | solve | 93 | tuple | no | captured in a closure/comprehension (line 93) | n/a | 0 |
| rail_transfer | solve | 95 | tuple | no | captured in a closure/comprehension (line 95) | n/a | 0 |
| rail_transfer | main | 208 | obj | no | not inside a loop | - | 0 |
| rbtree | insert | 44 | obj | no | not inside a loop | - | 0 |
| scar_life | main | 66 | obj | no | not inside a loop | - | 0 |
| scar_life | main | 67 | bpay | no | not inside a loop | - | 0 |
| scar_life | main | 71 | bpay | no | not inside a loop | - | 0 |
| scar_life | main | 95 | bpay | no | not inside a loop | - | 0 |
| scar_life | main | 106 | bpay | no | not inside a loop | - | 0 |
| scar_life | main | 112 | bpay | no | not inside a loop | - | 0 |
| scar_life | main | 157 | bpay | no | stored into extend() | yes | 8 |
| tally_lang | run | 415 | str | no | stored into append() | yes | 24 |
| tally_lang | run | 416 | str | yes |  | yes | 24 |
| tally_lang | main | 468 | obj | no | not inside a loop | - | 0 |
| tally_lang | main | 469 | obj | no | not inside a loop | - | 0 |
| term_rank | add_term | 22 | bpay | no | not inside a loop | - | 0 |
| term_rank | add_term | 24 | bpay | no | not inside a loop | - | 0 |
| term_rank | add_term | 24 | str | no | not inside a loop | - | 0 |
| term_rank | add_term | 28 | str | no | not inside a loop | - | 0 |
| term_rank | add_term | 32 | str | no | not inside a loop | - | 0 |
| term_rank | add_term | 34 | str | no | not inside a loop | - | 0 |
| term_rank | emit_line | 63 | bpay | yes |  | yes | 16194760 |
| term_rank | main | 94 | bpay | no | used as the for-loop iterable (live across the back edge) | yes | 16194760 |
| term_rank | main | 103 | obj | no | not inside a loop | - | 0 |
| term_rank | main | 105 | bpay | yes |  | yes | 16194760 |
| term_rank | main | 105 | str | no | stored into add() | yes | 16194760 |
| term_rank | main | 128 | bpay | no | not inside a loop | - | 0 |
| term_rank | main | 138 | tuple | yes |  | n/a | 0 |
| term_rank | main | 139 | bpay | no | stored into extend() | yes | 16194760 |
| term_rank | main | 146 | bpay | no | stored into extend() | yes | 16194760 |
| term_rank | main | 150 | tuple | no | not inside a loop | - | 0 |
| term_rank | main | 151 | bpay | no | not inside a loop | - | 0 |
| term_rank | main | 158 | bpay | no | stored into extend() | yes | 16194760 |
| ticket_audit | main | 264 | obj | no | not inside a loop | - | 0 |
| ticket_audit | main | 331 | tuple | no | not inside a loop | - | 0 |
| tree_fold | do_sort | 191 | tuple | no | not inside a loop | - | 0 |
| tree_fold | do_print | 280 | str | yes |  | yes | 1768062 |
| tree_fold | do_find | 297 | str | no | not inside a loop | - | 0 |
| tree_fold | main | 311 | obj | no | not inside a loop | - | 0 |
| tree_fold | main | 380 | str | yes |  | yes | 1768062 |

The `dynamic` column is a **program/family aggregate** (the C allocation for a `str`/`bytes` expression is
made inside a runtime helper, not in the user function, so a per-function join would be fiction); a dash
means the site is not in a loop, so a region does not apply, and the pairs column is then left at 0.
`lab/mem/REGION.json` carries all 115 C sites and 115 joined rows.

The 7 static yes sites and what the dynamic side says:

| static site | dynamic verdict |
|---|---|
| term_rank `emit_line:63` bytes | yes: the 16.19 M heap pairs above |
| term_rank `main:105` bytes | yes: same paths |
| term_rank `main:138` tuple | none measured: the `(int, str)` tuple is an unboxed lambda result; no `ail_obj_new` call site |
| tree_fold `do_print:280` str | yes: 1.77 M `ail_str_from_int` pairs |
| tree_fold `main:380` str | yes: same site |
| tally_lang `run:416` str | yes: 25 heap pairs |
| rail_transfer `solve:91` Item | no for a region: the object is pool-backed (the program's 131 heap pairs are the `alloc`/`blk` path, not this `Item`) |

## (c) The price

`pairs` x 170 instructions (rc1's malloc/free pair estimate) is what a bump region (about 5 instructions,
free 0) would remove. `s = pairs x 170 / est_total_instructions`; Amdahl `1/(1-s)`; roof 60% `1/(1-0.6s)`;
halved projection `1 + (roof-1)/2`. Go if the halved projection is >= 1.03x, or if loop-local bytes are
>= 5% of peak RSS on at least two programs.

| program | pairs | s | Amdahl 1/(1-s) | roof 60% | halved projection | RSS share | go |
|---|---:|---:|---:|---:|---:|---:|:--:|
| berth_sim | 1186 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |
| chain_relax | 7 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.02% |  |
| echo_pack | 2 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 9.78% | no (one-shot peak) |
| ledger_bin | 3 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 19.20% | no (one-shot peak) |
| rail_transfer | 131 | 0.001% | 1.0000x | 1.0000x | 1.0000x | 2.81% |  |
| scar_life | 8 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 46.72% | no (one-shot peak) |
| tally_lang | 25 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.04% |  |
| term_rank | 16194761 | 4.177% | 1.0436x | 1.0257x | 1.0129x | 5.06% | yes |
| ticket_audit | 813 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.85% |  |
| tree_fold | 1768062 | 0.305% | 1.0031x | 1.0018x | 1.0009x | 5.66% | no (one-shot peak) |
| binarytrees | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |
| cfold | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |
| deriv | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |
| linkedlist | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |
| objscan | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |
| rbtree | 0 | 0.000% | 1.0000x | 1.0000x | 1.0000x | 0.00% |  |

**fbregion2: NO-GO.** The instruction route misses everywhere: the best halved projection is **1.0129x**
(term_rank), then 1.0009x (tree_fold); every object program is exactly 1.0000x because the pool already
serves them. The RSS route, taken mechanically, shows >= 5% on five programs, but four are one-shot bulk
buffers, not per-iteration churn: echo_pack (34.0 MiB, 2 pairs), ledger_bin (64.9 MiB, 3 pairs), scar_life
(8.0 MiB, 8 pairs) and tree_fold (22.9 MiB, of which a 24 MB list snapshot is 1 allocation). Only
**term_rank** (8.0 MiB, 16.2 M pairs, 5.06%) is genuine churn -- one program, short of the required two.
If the owner chooses to count tree_fold's one-shot 24 MB snapshot as a region target, the letter of the
rule is met (2 programs, RSS-only), but a region cannot remove a buffer that is allocated once and held.

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

If it is built anyway, the only defensible target is term_rank's bytearray/barena churn (16.19 M pairs,
4.18% of estimated instructions) and tree_fold's int-to-str temporaries (1.77 M pairs, 0.31%), behind an
opt-in; the expected halved instruction gain is <= 1.013x, below the 1.03x bar.

## Reproduce

    python3 -B lab/mem/region_census.py --census
    python3 -B lab/mem/region_census.py --static
    python3 -B lab/mem/region_census.py --price

`REGION.json` carries `programs` (per-program totals and kinds), `dynamic_sites` (115 C sites),
`static_sites` (64 Python sites), `sites` (115 joined rows) and `price`.
