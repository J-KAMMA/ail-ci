# job job-fbred2-11061500  started 2026-11-06T06:05:51Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model claude/opus 2.1.310 (Claude Code)]
The new `PARRED` runtime part gives 0 differences against the sequential checked loop, but it misses the 4-thread cost target: 1.265x instead of 1.05x. Two commits (`3834de5`, `093fbfc`), nothing pushed. The brief asked for pushes, a PR against `integ` and CI, but the job rules forbid pushing, so there is no PR and the 20 `shard` checks have not run.

**What's built**
- `PARRED` in `cruntime.py`, after `PARN`, requiring `PAR` and `PARN`. No existing part was edited, and nothing links it until fbred3 wires up the compiler.
- `ail_par_reduce_run` cuts the range into contiguous chunks in index order and hands them to PAR's pool. A trap in a chunk goes through `ail_par_trap` and is recorded on that chunk, not on `fail_block`.
- The combine runs in chunk order on the calling thread. It reruns the first chunk that failed or whose prefix bounds leave int64, so the stop uses the sequential text and path: `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)`, or the body's own exception.
- One change from the brief's sketch: a failed chunk is rerun instead of carrying its partial sum forward. That way `fn` doesn't have to store its partials before a trap.

**Results**
| Check | Result |
|---|---|
| Differential test, 20,000 cases from `model.py`'s generator, at 1, 2, 4 and 16 threads | 0 differences |
| Same, TSan build | 0 differences |
| Same, ASan/UBSan build | 0 differences |
| Mutations (2,000 cases, 4 threads): drop min bound / drop failed-chunk check / drop partial sum | 106 / 140 / 255 differences |
| `program.c` hash, base vs. this branch, 10 compare tasks + first 100 corpus programs | 0 differences of 110 (`t172` builds in neither tree) |

The sanitizer runs did not include leak checking: each forked child exits through `_Exit`, so LeakSanitizer never runs.

**Cost:** the runner has no PMU (`perf_event_open` was denied), so these are callgrind `Ir` counts on 1M terms of `acc += i % 1000`:
- **1 thread:** 15,224,902 against 15,224,654 for the sequential loop, so 1.000x (target 1.15x, met). At 1 thread the runtime simply runs the sequential loop.
- **4 threads:** 19,261,653, which is **1.265x** the 1-thread run (target 1.05x, missed). 98.65% of it is in the chunk function. Tracking the largest and smallest prefix costs about 4 extra instructions per term, and the share shrinks as the loop body gets heavier.
- `RT.md` records the miss and a cheaper approach I haven't tried.

**Tests:** `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_parallel_for`, `test_ail_typed_parallel` and the new `test_ail_par_reduce_rt` all pass on the final code. Under the 1.5 GB memory cap, `test_ail_typed_parallel` (its sanitizer tests couldn't reserve memory) and one `test_ail_safetynet` program failed. Both pass when rerun without the cap.

**Probes** (in `/tmp/probes`), all as expected since no compiled program changes:
- `p01_small_sum_twin`, `p09_two_accumulators_twin` and `p14_sum_map_basic` match CPython.
- `big_twin` stops at int64 with the loud `OverflowError`, as AIL is meant to.
- `p01_small_sum` raises `NameError` under CPython because `par_range` doesn't exist there.

The manifest is updated and `--check` passes. I didn't add a DEVLOG entry: the job rules ask for one, but the brief says not to edit `DEVLOG.md`, so I followed the brief.
[claude subtype=success turns=39 out_tokens=45775]

## review 0
[model claude/sonnet 2.1.310 (Claude Code)]
The change does what it claims, except for the 4-thread cost target, which the worker already reported as missed.

**What the change does:** it adds a `PARRED` runtime part to `cruntime.py`. Nothing in the compiler references it yet. It also adds a C harness test and `RT.md`. The runtime cuts the range into contiguous chunks and gives each an int128 partial sum with its largest and smallest prefix. It combines them in order, and it re-runs the first chunk that failed or whose prefix leaves int64, so the stop uses the sequential text. This matches the report.

**Claims**
- **`PARRED` added, no existing part edited:** verified from the diff. The cruntime hunk is one insertion plus the `ORDER`/`SOURCE`/`REQUIRES` entries.
- **Unrelated programs unchanged:** verified on my one probe, `/tmp/rprobes/a.py`. `program.c` is byte-identical between HEAD and the base (`/tmp/base`). I did not rerun the 110-program hash check.
- **`test_ail_par_reduce_rt` and `test_ail_safetynet` pass:** verified on HEAD, 0 failed.
- **0 differences on 20,000 cases at 1, 2, 4 and 16 threads, plus TSan and ASan/UBSan:** unverified. I did not repeat the long differential run, but the harness module passes. I read the combine logic and found no gap: failed-chunk reruns, the min and max bound checks, and the skipping of chunks after a failure are all consistent.
- **Cost at 1 thread (1.000x) and 4 threads (1.265x vs the 1.05x target):** unverified. The miss is stated in `RT.md`, as the task allows.
- **No push, no PR, no CI:** consistent with the job rules. The 20 `shard` checks have not run.

**Not applicable:** the task is not a speed task, and no benchmark or example program was edited.

**Unverified**
- Hand-written probes of the int64 boundary, the empty range and `lo < 0`. I wrote only one probe, not the five allowed.
- Probes of mutation or aliasing through list, attribute or dict values. These need the compiler wiring, which is fbred3.
- The gdev instruction counts. Nothing links `PARRED` into any program, so I expect no change.

**Pre-existing:** none observed.

VERDICT: ACCEPT
[claude subtype=success turns=8 out_tokens=2669]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T07:57:13Z
