# tree_fold peak memory: where 605 MiB went and what the runtime now does

`lab/compare` tree_fold, performance input (`lab/compare/tasks/tree_fold/gen.py`): 27,877,476 input
bytes, 3,000,000 nodes, 3.65 name bytes a node.  AIL is the typed build of `src/tree_fold/main.ail`;
Rust is `rustc -C opt-level=3`.

## Result

| build | peak RSS (`/usr/bin/time -v`) | allocator peak live | wall (median) |
|---|---:|---:|---:|
| AIL before (HEAD `cb285e1`) | 618,160 KiB = **603.7 MiB** | 723,097,572 B = 689.6 MiB | 1.875 s |
| AIL after | 460,992 KiB = **450.2 MiB** | 493,107,684 B = 470.3 MiB | 1.764 s |
| Rust | 322,376 KiB = 314.8 MiB | - | 1.818 s |

tree_fold peak RSS fell by 157,168 KiB (153.4 MiB, 25.4%); the allocator's simultaneous live
bytes fell by 230.0 MiB (33.4%).  Allocated bytes over the run fell from 3.77 GB to 3.10 GB and
allocation calls from 3,786,368 to 3,786,111.  The source in `lab/compare/src` was not touched.

## Measurement

The allocation profile is an `LD_PRELOAD` counting allocator: it puts a 16-byte header in front of
each block, records `__builtin_return_address(0)` and the requested size, and keeps current, peak,
per-site and per-size-class-bucket counters.  The C was produced with
`compile ... --debug-dir DIR`, rebuilt with `gcc -O2 -o prog DIR/program.c -lm`, and the printed
addresses were resolved against `nm -n prog` (run under `setarch -R` so the PIE base is stable).
RSS is from `lab/compare/run_task.py --task tree_fold --langs ail,rust --icount none`, which takes
the median of five `/usr/bin/time -v` runs on the performance input.

### Live bytes at the global peak, by allocation site (after)

| site | allocations | allocated over run | live at peak |
|---|---:|---:|---:|
| `ail_list_reserve` (int/float vectors) | 32 | 575.1 MiB | 137.3 MiB |
| `ail_numfield_list_append_slow` (`T.w`, `T.dep`, `T.par` field growth) | 60 | 192.0 MiB | 96.0 MiB |
| `ail_slist_reserve` (one `list[str]` spine, 3,000,000 x 24 B) | 5 | 265.0 MiB | 68.7 MiB |
| `ail_alloc` (dense string-field text/prefix arrays and misc) | 54 | 331.1 MiB | 56.2 MiB |
| `parse_tree` (tree and operation storage) | 39 | 96.0 MiB | 48.0 MiB |
| `py_main` (stdin buffer) | 10 | 63.9 MiB | 32.0 MiB |
| `rebuild` (new pre-order vectors) | 58 | 128.0 MiB | 32.0 MiB |

By allocation size at that same instant (bucket is `floor(log2(bytes))`, so 64-128 MiB means one
or more blocks in that range): 64-128 MiB 72.0 MB; 32-64 MiB 201.3 MB; 16-32 MiB 208.8 MB;
8-16 MiB 10.9 MB.  Before the change the same profile was:

| site | live at peak |
|---|---:|
| `ail_slist_push` (string spines grown by doubling) | 192.0 MiB |
| `ail_alloc` | 124.9 MiB |
| `ail_numfield_list_append_slow` | 96.0 MiB |
| `ail_list_reserve` | 68.7 MiB |
| `rebuild` (four separate growth sites) | 128.0 MiB |
| `parse_tree` | 48.0 MiB |
| `py_main` | 32.0 MiB |

and the size buckets at the peak were 64-128 MiB 260.7 MB, 32-64 MiB 288.0 MB, 16-32 MiB 130.5 MB,
8-16 MiB 10.9 MB.  The old peak held several 3,000,000-element `list[str]` spines at once
(24 bytes an element) because a spine had been copied into a temporary and grown by doubling; the
new peak holds one such spine plus vectors that are about to be released.

## Per-node size against Rust

`T` has four lists.  AIL's `nm: list[str]` struct field is the dense packed form (`ail_pslist`):
an 8-byte prefix-sum entry per node plus the name text.  With 3,000,000 nodes and 10,935,168 name
bytes, an exact-size node is:

- AIL: `nm` 8 + name text 3.645 + `w` 8 + `dep` 8 + `par` 8 = **35.65 B/node** (plus the 27.9 MB
  stdin text, held by the program).  In the built tree the vectors grew by doubling, so the actual
  storage is `nm` prefix 33.55 MB + text 16.78 MB + three 33.55 MB int fields = 151.0 MB =
  **50.33 B/node**.
- Rust: name storage is a copy of the 27.9 MB tree line (9.29 B/node), `nm` `(u32,u32)` 8 B, `w`
  `u64` 8 B, and `ch` is `Vec<Vec<u32>>`: a 24 B `Vec` header every node plus the child ids =
  about **49-53 B/node** of persistent tree, before the input copy.

Measured peak RSS per node is 157 B/node for AIL after (450.2 MiB / 3M) and 107 B/node for Rust.
AIL's remaining excess is not its node layout but (a) `T` keeps `dep` and `par` for the whole run
where Rust recomputes pre-order/parent/depth per operation, and (b) `do_sort` still materialises a
`list[str]` key column (the 68.7 MiB spine above) while Rust compares names through an index.

## What changed

All in `AIL_CURRENT/python/pkg-v12`; no task source changed.

1. `cruntime.py`: new `ail_slist_reserve`, one exact `realloc` for a string list whose final length
   is known.  `pyfunc.py` emits it for a `list[str]` comprehension, and for an append loop whose
   range is known and whose target was emptied immediately before it (also for `list[int]` and
   `list[float]`); `ir/lower.py`/`ir/emit_c.py` add the same `list.reserve` operation to the IR.
2. `pyfunc.py` and `ir/lower.py`: a `list[str]` local is released at its last use, exactly like the
   numeric-list path.  This is what turns the old three simultaneous spines into one.

## Acceptance

- **stdout and exit code**: all public and hidden cases of all ten `lab/compare` tasks match the
  CPython reference (`run_task.py` per task; tree_fold 3 public + 52 hidden, rust too).  All builds
  stayed on the typed path.
- **Peak RSS**: tree_fold -157,168 KiB.  The other nine tasks: berth_sim -616 KiB, chain_relax 0,
  echo_pack +4 KiB, ledger_bin -256 KiB (full run with cases; -120 KiB without), rail_transfer 0,
  scar_life -124 KiB, tally_lang +4 KiB, term_rank -756 KiB, ticket_audit +4 KiB.  The +4 KiB
  entries are one page and their generated C is byte-identical or differs only by the new
  reserve/free; they are the measurement quantum, not a real rise.
- **Run icount**: not measurable on this runner.  `tools/icount` builds, but `perf_event_open`
  returns `EACCES` (`/proc/sys/kernel/perf_event_paranoid` is 4) and valgrind is not installed, so
  neither hardware nor callgrind instruction counts could be taken.  This is reported, not hidden:
  no instruction-count claim is made.  What was measured instead: tree_fold wall time 1.764 s vs
  1.875 s, 257 fewer allocation calls, and unchanged output on every case.
