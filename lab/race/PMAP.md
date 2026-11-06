# fbpmap1: where parallel-map time goes

Measured by `python3 lab/race/pmap/run.py` on a 4-vCPU GitHub Actions runner, CPython 3.12.3, under a 1.5 GB address-space cap; wall time is the median of 5 runs and the runner is noisy (up to 3x between runs), so treat shares as the stable number and milliseconds as indicative.

The timed build is a scratch copy of each generated `program.c` with `ail_par_now()` stamps at block start/end (per worker), at the start of the doubling probe prefix, and around the serial result-list initialization. The compiler and the source are not edited. Every timed run's stdout was compared byte for byte with the plain build and with CPython.

`region_ms` is the `ail_par_run` wall time. `tail_ms` runs from the first empty block claim to the region end; `prefix_ms` is the probe prefix before `ail_par_go_wide`. `list_ms` is the serial `[0] * n` result-list build before the region. `blocks` is the number of completed blocks (`1` when the region stays sequential).

Instruction counts could not be measured on this runner: `tools/icount.c` reports `perf_event_open: Permission denied` (`/proc/sys/kernel/perf_event_paranoid` is 4) and `valgrind` is not installed, so there is no callgrind fallback. The wall-time medians below are the measurements this job can make.

## Idle tail, probe prefix, blocks and result list

| load | threads | region ms | wall ms | tail ms | tail share | prefix ms | prefix share | list ms | blocks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| par_collatz | 1 | 1302.234 | 1363.252 | 0.000 | 0.0% | 0.000 | 0.0% | 6.853 | 1 |
| par_collatz | 2 | 655.052 | 715.743 | 9.237 | 1.4% | 0.079 | 0.0% | 6.770 | 17 |
| par_collatz | 4 | 481.817 | 542.236 | 10.862 | 2.2% | 0.079 | 0.0% | 6.881 | 33 |
| uniform | 1 | 16.545 | 28.787 | 0.000 | 0.0% | 0.000 | 0.0% | 3.927 | 1 |
| uniform | 2 | 8.410 | 20.627 | 0.013 | 0.1% | 0.067 | 0.8% | 3.906 | 17 |
| uniform | 4 | 7.972 | 20.564 | 0.052 | 0.7% | 0.067 | 0.8% | 4.084 | 33 |
| ramp | 1 | 163.531 | 166.276 | 0.000 | 0.0% | 0.000 | 0.0% | 0.072 | 1 |
| ramp | 2 | 86.922 | 89.661 | 9.823 | 11.3% | 0.103 | 0.1% | 0.071 | 17 |
| ramp | 4 | 47.771 | 50.276 | 7.551 | 15.8% | 0.103 | 0.2% | 0.071 | 33 |
| heavy | 1 | 123.333 | 129.839 | 0.000 | 0.0% | 0.000 | 0.0% | 1.486 | 1 |
| heavy | 2 | 95.473 | 102.224 | 67.582 | 70.8% | 0.057 | 0.1% | 1.631 | 17 |
| heavy | 4 | 84.033 | 91.043 | 67.481 | 80.3% | 0.057 | 0.1% | 1.636 | 33 |
| tiny | 1 | 10.334 | 34.472 | 0.000 | 0.0% | 0.000 | 0.0% | 8.962 | 1 |
| tiny | 2 | 5.336 | 29.449 | 0.043 | 0.8% | 0.068 | 1.3% | 8.892 | 17 |
| tiny | 4 | 4.969 | 29.679 | 0.036 | 0.7% | 0.068 | 1.4% | 9.063 | 33 |

## Block timeline at 4 threads

Twenty equal bins of the region, from the first block start to the region end; each cell is `blocks/busy ms`.

| load | bins (start -> end) |
|---|---|
| par_collatz | 4/212.7 1/56.7 3/174.6 0/0.0 4/238.7 0/0.0 1/60.1 3/182.2 0/0.0 4/245.4 0/0.0 1/61.2 3/188.7 0/0.0 4/249.6 0/0.0 1/62.6 3/183.0 0/0.0 1/0.0 |
| uniform | 4/3.9 0/0.0 4/3.9 0/0.0 0/0.0 4/3.9 0/0.0 4/3.9 0/0.0 0/0.0 4/3.9 0/0.0 4/3.9 0/0.0 0/0.0 4/3.9 0/0.0 4/3.8 0/0.0 1/0.0 |
| ramp | 8/12.7 4/14.2 2/9.0 2/10.3 2/11.6 2/12.9 1/7.0 2/14.9 1/7.9 1/8.2 1/8.5 2/18.0 1/9.5 1/9.8 1/10.0 1/10.0 1/0.0 0/0.0 0/0.0 0/0.0 |
| heavy | 8/16.4 12/24.6 8/16.4 5/75.7 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 0/0.0 |
| tiny | 4/2.4 0/0.0 0/0.0 4/2.3 0/0.0 4/2.4 0/0.0 1/0.6 3/1.8 0/0.0 4/2.4 0/0.0 4/2.4 0/0.0 1/0.6 3/1.7 0/0.0 4/2.3 0/0.0 1/0.0 |

## par_collatz against races3

| threads | AIL wall, this job | races3 AIL | races3 C | races3 Rust |
|---:|---:|---:|---:|---:|
| 1 | 1363.3 | 1270.6 | 1082.0 | 923.5 |
| 2 | 715.7 | 885.7 | 701.6 | 588.4 |
| 4 | 542.2 | 602.6 | 527.8 | 424.6 |

The AIL column is this job's median of 5 runs of the same task and input (`N = 7,000,000`), with `AIL_THREADS` 1, 2 and 4; the input still says `W = 4`, so the worker cap is 4 and `AIL_THREADS` limits the pool. A separate local `lab/compare/run_task.py --task par_collatz --langs ail,c,rust --no-cases --icount none` run on the same runner at 4 threads gave AIL 474.9 ms, C 380.6 ms and Rust 311.0 ms (peak RSS 121956 / 29092 / 56704 KiB). The races3 numbers in the table are from `lab/race/SPEEDUP.md`, measured under a higher load average.

## Decisions

- guided chunk sizes: **go** (idle tail at least 10% of region wall time on 2 loads at 4 threads; rule needs at least 2).
- work-stealing deques (Chase-Lev): **no-go: no nesting** (1 program whose parallel region calls into another parallel region; rule needs at least 3).

Nested-region programs found: `lab/race/racy/nested_writes_outer.py`

## Files

- `lab/race/pmap/{par_collatz,uniform,ramp,heavy,tiny}.py`: the five loads.
- `lab/race/pmap/par_collatz.py` is a byte-for-byte copy of `lab/compare_par/src/par_collatz/typed.py`.
- `lab/race/pmap/run.py`: builds, instruments in /tmp, measures, writes these files.
