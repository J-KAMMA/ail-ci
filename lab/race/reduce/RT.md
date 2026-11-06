# fbred2: the reduction runtime (`PARRED`)

The runtime half of `docs/design/PAR_REDUCE.md`. The part is not wired to the compiler yet (fbred3), so
no program links it: `PARRED` is only pulled in when a program's part list names it.

## The part

`cruntime.py` part `PARRED`, `REQUIRES` `PAR` and `PARN`, placed after `PARN` in `ORDER`. No existing part
changed.

```c
typedef struct { __int128 s, mx, mn; } ail_red_part;      /* per accumulator and chunk */
void ail_par_reduce_run(ail_red_fn fn, void **args, int64_t lo, int64_t hi, ail_par_site *site, int64_t cap,
                        int64_t nacc, int64_t *acc, ail_red_rerun rerun);
/* fn(args, lo, hi, parts): the chunk's partial sum and largest / smallest prefix per accumulator
   rerun(args, lo, hi, acc): the sequential loop with the ordinary checked int64 add, from acc[] */
```

* Before going wide it does what `ail_par_run` does (too few iterations, one thread, a nested region:
  sequential; the timed doubling probe prefix through `site`), but every sequential part is `rerun`, so it
  raises exactly what the sequential loop raises.
* The rest is cut into `min(n, threads * 8)` contiguous chunks numbered in index order. The chunk table
  and the partials array are allocated once per call. `ail_par_go_wide` deals the chunks out (one PAR
  "iteration" is one chunk); `cap` is applied as `ail_par_run_n` does.
* A chunk runs under its own `ail_par_ctx`: a trap in `fn` goes through `ail_par_trap` /
  `ail_par_trap_value` to that context and is recorded **on the chunk** (code and message); chunks after
  the lowest failing one are skipped. Nothing reaches PAR's `fail_block`, so `go_wide` never raises here.
* The combine runs on the calling thread in chunk order from `B = acc[]`. The first chunk that failed, or
  for which `B + mx` or `B + mn` leaves int64 for some accumulator, is re-run alone by `rerun` from `B`
  (after the tables are freed): it stops at the iteration, with the text and through the path of the
  sequential checked add (`ail_die("OverflowError: integer overflow in + (ints are 64-bit; --exact-int
  gives exact ints)")`, or the body's own exception), with `acc[]` at the last prefix that fitted.
  Every other chunk adds its partial sums.
* A failed chunk is re-run rather than carried as `B + S_c`, so `fn` need not store its partials before a
  trap (it may keep them in registers). If a re-run does not repeat the recorded trap (impossible for the
  pure bodies the proof admits), the recorded one is raised.

## Differential test

`python3 AIL_CURRENT/test_ail_par_reduce_rt.py diff 20000 [tsan|asan]`. Cases are `model.py`'s
`rand_reduce_case` (seed 20261106) in three shapes: `acc += v`, `acc -= v`, `acc += v; neg -= w`; each case
also draws `cap` from {0, 2, 3, 5}, one of two `fn` variants (plain `__int128`, or an int64 running sum
that switches to `__int128` at the first chunk-local overflow), and the model's probe-prefix split. 1% of
the cases with 64+ items get a slow body and an empty site, so the runtime's own timed probe decides the
split. Each case runs in a forked child twice: the sequential checked loop, and `ail_par_reduce_run`; the
key is (exit status, stdout + stderr, `acc` after the run, the iteration where it stopped), with `acc` and
the iteration in shared memory.

| build | AIL_THREADS=1 | 2 | 4 | 16 |
|---|---|---|---|---|
| `-O2` | 0 / 20,000 | 0 / 20,000 | 0 / 20,000 | 0 / 20,000 |
| TSan (`-O1 -fsanitize=thread`) | 0 / 20,000 | 0 / 20,000 | 0 / 20,000 | 0 / 20,000 |
| ASan + UBSan (`-O1`, no recover) | 0 / 20,000 | 0 / 20,000 | 0 / 20,000 | 0 / 20,000 |

A sanitizer report changes the child's stderr and exit status, so it would count as a difference.
LeakSanitizer does not run: every child leaves through `_Exit`. Mutations caught on 2,000 cases at 4
threads: dropping the `mn` bound 106 differences, dropping the failed-chunk check 140, dropping the
partial sum 255 (all 0 at 1 thread, which never goes wide).

## Cost

No PMU on the runner (`perf_event_open: Permission denied`), so `valgrind --tool=callgrind` `Ir`, all
threads, on 1,000,000 terms of `acc += i % 1000` (`test_ail_par_reduce_rt.py cost` builds the harness):

| run | Ir | vs sequential |
|---|---|---|
| sequential checked loop | 15,224,654 | 1.000 |
| `ail_par_reduce_run`, AIL_THREADS=1 | 15,224,902 | 1.000 (target 1.15: met) |
| `ail_par_reduce_run`, AIL_THREADS=4 | 19,261,653 | 1.265 of the 1-thread run (target 1.05: **missed**) |

Where the instructions go at 4 threads: 98.65% is the chunk function `c_fn` (19.0M, about 19 per term
against 15 for the sequential loop); the pool, the combine and the re-runs are below callgrind's 1%
threshold. The 4 extra instructions per term are the two compare-and-moves that keep the largest and the
smallest prefix (`mx = t > mx ? t : mx; mn = ...`); the int64 running sum with its overflow branch costs
what the sequential checked add costs. The ratio falls as the body grows (the 4 instructions are fixed
per term), but for a one-line `acc += term(i)` the exact prefix bounds cost about 25%. Not tried in this
job: a conservative test with a cheaper per-term update (the test may fire falsely, since the re-run is
exact anyway, at the price of a bounded number of extra chunk re-runs).

## No program changes

`program.c` sha256 with `PYTHONHASHSEED=0 AIL_NO_CACHE=1 --debug-dir`, base tree (`HEAD~1`) against this
branch, on the 10 `lab/compare/src/*/typed.py` and the first 100 `lab/corpus/programs/**/*.py` (sorted):
0 differences in 110 (one, `deepseek-v4.1-flash-free/t172.py`, builds no `program.c` in either tree).
