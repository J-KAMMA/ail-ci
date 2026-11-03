# arena1 S4: packed append-only `list[str]` locals

Status: implemented and verified; **not landed** because this runner still peaks above the 350 MB
acceptance bar.  The remaining gap is attributed below.

## Result

`tree_fold`, N = 3M, actual perf input (27,877,476 B), default glibc, `/usr/bin/time -v`:

| | base `06de59e` | S4 | change |
|---|---:|---:|---:|
| peak RSS | 440,188 KiB (430 MiB) | 414,220 KiB (405 MiB) | -25,968 KiB (-5.9%) |
| wall | 1.75 s | 1.42 s | -0.33 s |
| minor faults | 194,030 | 135,599 | -58,431 |
| generated C bytes | 86,288 | 86,336 | +48 |

`tools/rss_phases.py --n 3000000` (default / fixed-threshold peaks, MiB):

| build | parse | stats | sort | later ops | peak |
|---|---:|---:|---:|---:|---:|
| base | 129.8 | 152.8 | 429.8 | 447.8 | **447.8** |
| S4 | 129.8 | 152.7 | 404.5 | 405.1 | **405.1** |
| base, `mmap_threshold=131072` | 129.8 | 152.7 | 372.4 | 374.3 | 374.3 |
| S4, `mmap_threshold=131072` | 129.9 | 152.7 | 369.2 | 369.3 | **369.3** |

The sort phase drops 25.3 MiB.  With the fixed threshold it drops only 3 MiB because the base peak
there is already a different live set.

All ten `lab/compare` tasks, all 55/26/32/57/55/24/53/75/43/91 public+hidden cases, match CPython /
`reference.py`; every task stays on the typed path.

| task | RSS base | RSS S4 | Δ KiB | wall base ms | wall S4 ms | Δ ms |
|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 246,096 | 243,664 | -2,432 | 2,374.0 | 2,501.8 | +127.8 |
| chain_relax | 3,896 | 3,896 | 0 | 1,255.9 | 1,256.1 | +0.2 |
| echo_pack | 354,276 | 354,272 | -4 | 1,030.9 | 979.8 | -51.1 |
| ledger_bin | 342,292 | 337,620 | -4,672 | 860.9 | 833.2 | -27.7 |
| rail_transfer | 28,752 | 28,756 | +4 | 68.3 | 67.0 | -1.3 |
| scar_life | 17,540 | 17,548 | +8 | 30,124.5 | 30,055.6 | -68.9 |
| tally_lang | 1,496 | 1,496 | 0 | 1,530.6 | 1,532.9 | +2.3 |
| term_rank | 161,528 | 161,228 | -300 | 2,262.9 | 2,249.8 | -13.1 |
| ticket_audit | 254,684 | 254,688 | +4 | 1,712.1 | 1,676.1 | -36.0 |
| tree_fold | 441,240 | 414,200 | -27,040 | 1,773.0 | 1,427.7 | -345.3 |

The berth_sim wall difference is within the spread of repeated runs (new 2,450.5/2,513.7/2,514.4
vs base 2,365.8/2,375.9/2,507.0 ms).  `+4`/`+8` KiB is the page quantum.  All generated C except
tree_fold's packed locals and reserves is unchanged or differs only by the new free/reserve.

## What changed

- `cruntime.py`: `ail_pslist_move` (free the slot, take the local, zero the local) and
  `ail_pslist_reserve` (exact offsets plus a text-capacity hint).
- `pyfunc.py`: `_mark_packed_str_lists` chooses a local that starts as `[]`, is only appended to,
  measured with `len`, and stored once into a `list[str]` field as its last mention.  Appends use
  `ail_pslist_push`; a builder or a field element is pushed directly (no sarena copy); the store
  uses `ail_pslist_move`; declaration, cleanup and unwind use `ail_pslist_free`.
- Step 3's reserve runs for packed locals too, including loops with `if`/`continue`, with the
  field text length as the hint when every append reads the same field.

## Residual attribution (why this is not ≤350 MB here)

The generated `do_sort` still contains
`ail_slist_snapshot(&v__sarena, (v_t)->f_nm)` for `let nm = t.nm`, i.e. S2's row-4 snapshot
(about 72 MB of 24 B views plus the text copy) is present in this base.  The task description says
steps 1-3 are merged, but the generated C shows the snapshot, so the S2 read-only field alias did
not reach this checkout.  The responsive file, `MEM_TREEFOLD.md`, prices S2 at 83 MB and S4's sort
phase at 332 MB only with S2 present.  Without it the sort phase cannot reach 350 MB: S4 removes
the rebuild-local spine, but the snapshot and the str key column (`_ail_sk1_c2`, another 72 MB)
remain, and the default heap peak in this runner is 405 MiB.  This is therefore a base/integration
gap, not a failure of the S4 packed-local path; doing S5 would not remove the snapshot or key
column either.

## Tests and probes

- `AIL_CURRENT/test_ail_arena1s4.py` (registered by `tests.d/test_ail_arena1s4.txt`): 8 tests
  covering the rebuild/compact/fold shapes, builder views, same-field append, empty column,
  non-ASCII, stays-`slist` cases (element read, iteration, sort, return, after-store read, two
  fields, passed to a function), the exception/unwind path, CPython + legacy + IR + forced builds,
  and an ASan/UBSan/LeakSanitizer run.
- Targeted modules: `test_ail_arena1s4`, `test_ail_slist_reserve`, `test_ail_element_views`,
  `test_ail_field_views`, `test_ail_string_field_mutation`, `test_ail_str_comprehension_move`,
  `test_ail_ir_s3`; required: `test_ail_safetynet`, `test_ail_files`,
  `test_ail_corpus_findings3`.  `par_check -j 2`: all green (5 modules, then 3 modules).
- Probe `/tmp/probes/arena1s4.py` matched CPython on the default and `AIL_UNIFIED_FORCE=1` builds.
