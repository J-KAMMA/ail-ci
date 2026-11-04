# `ta.matmul` 256x256 f64 on the CPU: AIL vs C vs CPython

Programs (this directory):

- `matmul256.py` — AIL (Python syntax), built with `python3 -B AIL_CURRENT/ail_chatgpt.py compile
  lab/array/matmul256.py -o OUT --syntax python --debug-dir DIR` (default build, typed path; `--strict` also
  accepts it and prints no `built on the general path` note).
- `matmul256.c` — the same fill and the same order, `gcc -O2 -ffp-contract=off -o matmul256 lab/array/matmul256.c`.
  (`-ffp-contract=off` keeps the products rounded before the add; the x86-64 baseline has no FMA, but the
  flag makes that independent of `-march`.)
- `matmul256_ref.py` — CPython 3.12, the same fill and order as a pure-Python triple loop.

Both 256x256 matrices are filled row-major from one 32-bit LCG continued from `a` into `b`:
`s = (1664525*s + 1013904223) % 2**32`, `value = s / 2**32`, seed 1.

## Sum order

`ta.matmul` uses the fixed order of `TYPED_ARRAY.md` 3.5/3.7: element `k` of a dot goes to lane `k % 16`
(lanes start at `-0.0`), blocks are 1024 products, then the 8-4-2-1 tree over the lanes and a power-of-two
tree over the blocks. `K = 256` is one block, so each output element is 16 lanes of 16 products each followed
by the 8-4-2-1 tree. No FMA. The C program uses exactly that (`lane[k % 16] += a[i][k] * b[k][j]`, `b` read
with stride, then `w = 8, 4, 2, 1`), and the reference does the same. The printed checksum is the row-major
sequential sum of all 65536 output elements in all three programs.

The three programs print the same four lines, byte for byte:

```
4196337.4013470374
60.538415881530057
69.781509893807595
71.126957885982307
```

(the sum of every element with `%.17g`, then `c[0,0]`, `c[1,2]`, `c[255,255]`).

## Measurements

Runner: GitHub Actions, 4 cores, Linux container. Wall time is the median of 5 runs (`date +%s%N` around
the process, output to a file).

| program | wall, median of 5 | ratio to AIL |
| --- | --- | --- |
| AIL, typed path | 18 ms | 1.00x |
| C, `gcc -O2 -ffp-contract=off` (naive, `B` strided) | 32 ms | 1.78x slower |
| CPython 3.12, pure-Python triple loop | 1453 ms | 80.7x slower |

Instructions (icount) could not be recorded on this runner: `tools/icount.c` builds, but `perf_event_open`
returns `EACCES` and, after `sudo sysctl -w kernel/perf_event_paranoid=1`, `ENOENT`; `perf stat` reports
"No supported events found" — the container exposes no hardware PMU. Per the brief, the table above uses
the median of 5 wall times instead.

The AIL kernel beats the naive C here because the C reads `B` with stride 2 KiB (one cache line per
access), while `_ail_tam_mmk` copies `B` transposed once and tiles `j` in groups of 32; the tiling and the
copy do not change any element's order.
