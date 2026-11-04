# pyperf lab: ten plain-Python kernels through AIL

Ten programs in `bench/`, each the algorithm of a pyperformance benchmark,
written as ordinary Python 3.12 with no AIL-specific spelling.  `run.py` builds
each one with the default command, classifies the build (typed, general or
refused), compares stdout and the exit status with CPython 3.12 at the default
size, and takes the median of three wall times.  `RESULTS.md` holds the table
from the last run; the matching programs are also exercised by
`AIL_CURRENT/test_ail_pyperf_lab.py` at a small size.

## Programs

| program | algorithm | default size | small size |
|---|---|---|---|
| `nbody.py` | sun and four gas giants, symplectic steps | 400000 steps | 200 |
| `fannkuch.py` | Fannkuch redux, Johnson-Trotter permutations | n = 10 | 8 |
| `spectral_norm.py` | power iteration on the infinite spectral-norm matrix | n = 700 | 60 |
| `nqueens.py` | count all n-queens placements | n = 13 | 7 |
| `float_bench.py` | sqrt/sin/cos/exp/log chain in double precision | 5 000 000 steps | 20 000 |
| `richards.py` | Richards scheduler: task control blocks, packets, priorities | 250 000 packets | 2 000 |
| `raytrace.py` | three spheres, Lambert plus Phong, one ray per pixel | 800 x 800 | 16 x 16 |
| `generators.py` | generator pipeline plus recursive tree walk | 20 000 000 values | 50 000 |
| `scimark_sor.py` | red-black successive over-relaxation, omega 1.25 | 200 x 200, 400 sweeps | 40 x 40 |
| `scimark_fft.py` | iterative radix-2 Cooley-Tukey FFT | 2048 points, 400 transforms | 256, 400 |

Every program takes the size from `sys.argv[1]` when it is given and otherwise
uses the default above (the sweep counts in `scimark_sor` and `scimark_fft`
are part of the benchmark, so only the grid or transform size comes from the
argument).  Output is one or a few deterministic lines: integers or floats
printed with `"%.9f"`.

## Runner

```sh
python3 lab/pyperf/run.py                 # build, compare, time (writes results.json/.md here)
python3 lab/pyperf/run.py --small         # small sizes only, no timing
python3 lab/pyperf/run.py --unified       # also build with AIL_UNIFIED_FORCE=1, compare stdout
python3 lab/pyperf/run.py --only nbody    # one program
python3 lab/pyperf/run.py --out DIR       # write results elsewhere
```

The build runs in a scratch directory with `AIL_NO_CACHE=1`, one program at a
time, a 300 s timeout and `RLIMIT_AS` at 1.5 GB.  `path` is `typed` when the
build has no fallback note, `general` when stderr carries `note: ... built on
the general path ...` (that line is kept verbatim in `note`), and `refused`
when the compiler exits non-zero (its first line is kept in `note`).

Instruction counts come from `tools/icount.c`, built as its header comment
says.  It needs `perf_event_open`; when that is denied the runner records
`"icount": {"available": false, "note": "perf_event_open denied: ..."}` and
leaves the instruction columns empty, so only wall time is reported.

Wall time is the median of three runs of each binary at the default size.
The AIL general path is about twenty times slower than CPython, which is what
the wall columns show; the wall time of a program that does not match is still
recorded.

`RESULTS.md` is written by hand from the runner's markdown table and records
the date, the commit, the CPU, and the first refusal or fallback line of every
program that is not typed.
