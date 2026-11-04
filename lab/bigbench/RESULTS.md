# bigbench1: exact big-int programs, AIL `--exact-int` vs CPython 3.12

Date: 2026-11-04. Branch: `job-bigbench1-11041237`, base `f3d82a9` (staging export of `integ`).

Five Python-syntax programs in this directory are compiled with

    python3 -B AIL_CURRENT/ail_chatgpt.py compile PROG.py --syntax python --exact-int -o OUT

and run against `python3 PROG.py`.  All five print exactly what CPython prints (stdout and
exit code 0).

## Measurement method

`tools/icount.c` needs `perf_event_open`, which this runner refuses
(`/proc/sys/kernel/perf_event_paranoid = 4`, and changing it needs root; `sudo` is not
available to the job).  Following Appendix B, the ratio is therefore the **median wall time of
9 runs** (stdout to `/dev/null`), not an instruction ratio.  Peak RSS is `/usr/bin/time -v`
("Maximum resident set size").  The AIL number is the AIL binary; the CPython number is
`python3 PROG.py`.  Times are milliseconds; lower is better.  `--exact-int` set
`AIL_NO_CACHE=1` for the compile-time column.

## Builds

All five take the **general path** (`note: ... built on the general path`); none is refused.

| program | route | reason |
|---|---|---|
| pidigits.py | general | `main()` needs the tagged-int lowering, which does not cover it: builder locals |
| fib_big.py | general | module code can need an int beyond int64 (`10 ** 40`) |
| fact_mod.py | general | module code can need an int beyond int64 (a call of `math.factorial`) |
| powmod.py | general | module code can need an int beyond int64 (`10 ** 50`) |
| collatz_big.py | general | module code can need an int beyond int64 (`2 ** 300`) |

## Before the core change

| program | AIL compile s | binary B | AIL ms | CPython ms | AIL/CPython | AIL RSS KB | CPython RSS KB | output |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| pidigits.py | 3.77 | 125616 | 265.8 | 206.6 | 1.286 | 11112 | 10672 | equal |
| fib_big.py | 2.37 | 103760 | 33.9 | 42.4 | 0.799 | 10616 | 10308 | equal |
| fact_mod.py | 3.33 | 134168 | 21.4 | 23.3 | 0.920 | 10248 | 10488 | equal |
| powmod.py | 3.11 | 142168 | 1305.0 | 1226.3 | 1.064 | 10452 | 10168 | equal |
| collatz_big.py | 2.80 | 112808 | 121.4 | 75.5 | 1.607 | 10264 | 10384 | equal |

Geomean of the AIL/CPython ratios: **1.1009**.

## Profile (step 3, before the change)

`perf record` and `valgrind --tool=callgrind` are both unavailable here (no `valgrind`
package, `perf_event_open` denied).  The AIL binaries were rebuilt with
`AIL_EXTRA_CFLAGS=-pg` and profiled with `gprof`; several runs were merged with
`GMON_OUT_PREFIX` to get enough samples.

The two worst ratios are `collatz_big` (1.607) and `pidigits` (1.286).

`pidigits` (10 merged runs, 2.19 s sampled):

| % | routine |
|---:|---|
| 66.67 | `ail_bn_mul_school` |
| 14.16 | `ail__dbl_mag` |
| 5.94 | `ail_bn_sub` |
| 5.94 | `ail_bn_add` |
| 2.74 | `ail_big_alloc` |

`collatz_big` (20 merged runs, 2.37 s sampled):

| % | routine |
|---:|---|
| 20.68 | `ail__dbl_mag` |
| 20.68 | `main` |
| 19.83 | `ail__slow_obj` |
| 6.33 | `ail_big_alloc` |
| 5.91 | `ail_big_divmod` |

In `collatz_big` the big-int arithmetic is a small part of the time (allocation and the
generic operator slow paths dominate); `ail_bn_mul_school` is 1.69 %.  In `pidigits` the
schoolbook multiply is the clear hot core routine, and its operands are mostly a big value
times a one-limb counter (`q*k`, `(2*q+r)*l`, `t*l`, `q*(7*k+2)`, `r*l`), so the general
`nb == 1` inner loop pays for a zeroing `memset` and a read-modify-write of the output.

### RSS growth with run length

The general-path runtime does keep memory proportional to the biggest values.  Running the
same spigot for N digits (AIL binary, `/usr/bin/time -v`):

| digits | AIL wall s | AIL RSS KB | CPython RSS KB |
|---:|---:|---:|---:|
| 500 | 0.01 | 10892 | 10664 |
| 1000 | 0.05 | 10984 | 10664 |
| 2000 | 0.18 | 11024 | 10776 |
| 4000 | 0.80 | 11660 | 10912 |
| 8000 | 3.16 | 12672 | 11184 |

AIL RSS grows by about 1.8 MB from 500 to 8000 digits (CPython: about 0.5 MB).  This is a
finding only; memory ownership was not changed in this job.

## The core speed-up

`AIL_CURRENT/python/pkg-v12/bigint_core.py`, `ail_bn_mul_school`: a single-limb multiplier
(`nb == 1`) now takes one pass that writes the output limbs directly, without the
`memset(o, 0, ...)` and without the read-modify-write of `o[i + j]` in the general loop.
The limb base, the Karatsuba threshold, the decimal conversion and every printed value are
unchanged.  The general `nb >= 2` path is byte-for-byte the old loop, so a case the fast
path cannot handle keeps the old route.

## After the core change

| program | AIL compile s | binary B | AIL ms | CPython ms | AIL/CPython | AIL RSS KB | CPython RSS KB | output |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| pidigits.py | 3.82 | 125616 | 187.4 | 206.6 | 0.907 | 11112 | 10672 | equal |
| fib_big.py | 2.35 | 103760 | 33.8 | 42.4 | 0.797 | 10740 | 10308 | equal |
| fact_mod.py | 3.37 | 134168 | 19.1 | 23.3 | 0.820 | 10128 | 10488 | equal |
| powmod.py | 3.09 | 142168 | 1277.2 | 1226.3 | 1.042 | 10300 | 10168 | equal |
| collatz_big.py | 2.79 | 112808 | 121.5 | 75.5 | 1.609 | 10488 | 10384 | equal |

Geomean of the AIL/CPython ratios: **0.9990**, down from **1.1009** (a **9.3 %**
improvement).  No program got slower by more than 1 %: the largest change is
`collatz_big` at +0.1 %, and `powmod` improved by about 2 %.

## Tests

* `python3 -B -m unittest -q test_ail_bigint.CoreLimbs` (C core against CPython): OK.
* `python3 tools/par_check.py -j 2 test_ail_bigint`: **ok, 458 s, 0 failed**.
* The five programs were rebuilt after the change and their stdout compared byte-for-byte
  with `python3`; 5/5 equal, exit code 0.

## Notes / limits

* `perf_event_open` is denied on this runner, so the table uses wall time (Appendix B
  fallback) rather than instructions.
* No compiler files outside the allowed list were edited.  `bigcap.py`, `biggate.py`,
  `cruntime.py`, `tint_typed.py`, `bigint_obj.py` and the Appendix A rule 8 files are
  untouched.
