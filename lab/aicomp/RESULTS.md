# Where AIL stands on AI compute today (measurement only)

Measured 2026-11-09T07:59:27Z on the job runner. No compiler or runtime code was changed; this lane only adds
`lab/aicomp/`. One algorithm and one dtype per row; all columns run single-threaded
(`OMP_NUM_THREADS=1`, `torch.set_num_threads(1)`). Wall is the median of 5 process runs,
CPU is the median child `user+sys` time, RSS is the maximum child `ru_maxrss`.

Environment:

- CPU: AMD EPYC 9V74 80-Core Processor (4 logical CPUs)
- Python 3.12.3, gcc: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- NumPy: 2.5.4, BLAS: {"detection method": "pkgconfig", "found": true, "include directory": "/opt/_internal/cpython-3.12.13/lib/python3.12/site-packages/scipy_openblas64/include", "lib directory": "/opt/_internal/cpython-3.12.13/lib/python3.12/site-packages/scipy_openblas64/lib", "name": "scipy-openblas", "openblas configuration": "OpenBLAS 0.3.34.106.0  USE64BITINT DYNAMIC_ARCH NO_AFFINITY SkylakeX MAX_THREADS=64", "pc file directory": "/project/.openblas", "version": "0.3.34.106.0"}
- PyTorch: 2.5.1+cpu, MKL True, oneDNN True, threads 1
- GPU: **no Vulkan device on this runner** (`libvulkan.so.1` present, but `/usr/share/vulkan/icd.d` is absent;
  `/dev/dri` entries: ['/dev/dri/card1'], which is not usable without an ICD). Even with a device, today's GPU path
  covers marked loops only; `ta.matmul` has no GPU kernel
  (TYPED_ARRAY.md 5.7 and GPU.md 8.7 are design, not built).

Data are deterministic: `value(i, salt) = ((i*1664525 + 1013904223 + salt*2654435761) mod 2**32) / 2**32`.
The error column is the maximum relative difference from NumPy over the reported aggregate checks
(`total`, `abs`, `maxabs`) and the maximum absolute difference over three sampled elements. The
checks themselves use a sequential `float64` sum in every column, so they compare the data, not a
different summation order; full outputs are not compared element by element.

## Process start-up floor (median wall)

| column | start-up |
| --- | ---: |
| AIL | 0.57 ms |
| C | 0.53 ms |
| CPython | 13.4 ms |
| NumPy | 61.4 ms |
| PyTorch | 1066 ms |

## matmul 256 f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 14.7 | 0.015 | 14.9 | 3.52x | 2.32e-16 | 2.84e-14 |
| NumPy | 67.5 | 0.067 | 37.3 | 16.15x | 0 | 0 |
| PyTorch | 1051 | 1.051 | 285.9 | 251.73x | 0 | 0 |
| C | 4.18 | 0.004 | 14.9 | 1.00x | 2.21e-16 | 1.42e-14 |
| CPython | 1577 | 1.577 | 18.6 | 377.68x | 2.21e-16 | 1.42e-14 |

best: C

## matmul 1024 f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 690.1 | 0.690 | 49.2 | 5.14x | 4.14e-16 | 5.68e-14 |
| NumPy | 134.4 | 0.134 | 80.3 | 1.00x | 0 | 0 |
| PyTorch | 1179 | 1.181 | 351.6 | 8.78x | 1.52e-15 | 1.14e-13 |
| C | 215.4 | 0.215 | 25.7 | 1.60x | 1.52e-15 | 8.53e-14 |

best: NumPy

## matmul 2048 f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 5354 | 5.353 | 193.3 | 11.10x | 2.22e-16 | 1.71e-13 |
| NumPy | 482.5 | 0.482 | 204.3 | 1.00x | 0 | 0 |
| PyTorch | 1699 | 1.699 | 444.8 | 3.52x | 3.67e-16 | 1.02e-12 |
| C | 4452 | 4.452 | 97.7 | 9.23x | 5.51e-16 | 9.66e-13 |

best: NumPy

## elementwise 10m f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 152.2 | 0.152 | 383.0 | 1.00x | 0 | 0 |
| NumPy | 419.0 | 0.419 | 490.9 | 2.75x | 0 | 0 |
| PyTorch | 2596 | 2.596 | 736.3 | 17.06x | 0 | 0 |
| C | 181.6 | 0.181 | 306.9 | 1.19x | 0 | 0 |
| CPython | 10147 | 10.125 | 1351.8 | 66.69x | 0 | 0 |

best: AIL

## sum 10m f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 34.5 | 0.034 | 78.0 | 1.00x | 0 | 0 |
| NumPy | 133.0 | 0.133 | 261.9 | 3.85x | 0 | 0 |
| PyTorch | 1338 | 1.338 | 581.7 | 38.77x | 0 | 0 |
| C | 49.2 | 0.049 | 78.0 | 1.42x | 1.35e-10 | 0 |
| CPython | 2276 | 2.275 | 393.2 | 65.93x | 0 | 0 |

best: AIL

## softmax 1024 f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 45.0 | 0.045 | 18.3 | 2.80x | 1.93e-16 | 8.67e-19 |
| NumPy | 89.7 | 0.089 | 81.0 | 5.58x | 0 | 0 |
| PyTorch | 1180 | 1.179 | 355.5 | 73.33x | 0 | 8.67e-19 |
| C | 16.1 | 0.016 | 18.3 | 1.00x | 4.44e-16 | 3.47e-18 |
| CPython | 554.7 | 0.554 | 100.4 | 34.49x | 0 | 0 |

best: C

## mlp f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 28.4 | 0.028 | 15.1 | 1.64x | 8.61e-16 | 4.44e-16 |
| NumPy | 76.7 | 0.076 | 46.0 | 4.43x | 0 | 0 |
| PyTorch | 1124 | 1.124 | 293.8 | 64.95x | 6.89e-16 | 4.44e-16 |
| C | 17.3 | 0.017 | 15.1 | 1.00x | 5.13e-16 | 6.66e-16 |

best: C

## transformer f64

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 4.77 | 0.005 | 15.1 | 1.95x | 2.83e-16 | 6.66e-16 |
| NumPy | 64.0 | 0.064 | 34.9 | 26.25x | 0 | 0 |
| PyTorch | 1066 | 1.066 | 289.4 | 437.45x | 4.25e-16 | 1.11e-16 |
| C | 2.44 | 0.002 | 15.1 | 1.00x | 1.37e-16 | 1.11e-16 |

best: C

## matmul 256 f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 4.67 | 0.005 | 15.1 | 1.88x | 3.73e-07 | 2.29e-05 |
| NumPy | 66.8 | 0.067 | 37.0 | 26.92x | 0 | 0 |
| PyTorch | 1071 | 1.071 | 288.2 | 431.34x | 3.73e-07 | 3.05e-05 |
| C | 2.48 | 0.002 | 15.1 | 1.00x | 6.22e-08 | 0 |

best: C

## matmul 1024 f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 121.8 | 0.122 | 17.2 | 1.24x | 6.91e-10 | 4.58e-05 |
| NumPy | 113.7 | 0.113 | 76.8 | 1.16x | 0 | 0 |
| PyTorch | 1147 | 1.146 | 326.6 | 11.68x | 7.41e-08 | 1.53e-05 |
| C | 98.2 | 0.098 | 15.1 | 1.00x | 2.22e-07 | 7.63e-05 |

best: C

## matmul 2048 f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 829.5 | 0.829 | 65.2 | 2.54x | 1.97e-07 | 1.83e-04 |
| NumPy | 326.5 | 0.326 | 183.0 | 1.00x | 0 | 0 |
| PyTorch | 1557 | 1.556 | 428.5 | 4.77x | 2.96e-07 | 1.22e-04 |
| C | 865.3 | 0.865 | 49.7 | 2.65x | 7.88e-07 | 3.97e-04 |

best: NumPy

## elementwise 10m f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 323.1 | 0.323 | 382.9 | 2.80x | 0 | 0 |
| NumPy | 407.8 | 0.408 | 414.7 | 3.54x | 0 | 0 |
| PyTorch | 2606 | 2.606 | 660.1 | 22.62x | 0 | 0 |
| C | 115.2 | 0.115 | 154.3 | 1.00x | 0 | 0 |

best: C

## sum 10m f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 60.7 | 0.060 | 39.8 | 1.80x | 0 | 0 |
| NumPy | 129.7 | 0.129 | 262.0 | 3.85x | 0 | 0 |
| PyTorch | 1370 | 1.369 | 581.7 | 40.63x | 1.00e-07 | 0 |
| C | 33.7 | 0.033 | 40.0 | 1.00x | 3.20e-06 | 0 |

best: C

## softmax 1024 f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 114.5 | 0.114 | 15.1 | 9.60x | 2.07e-07 | 0 |
| NumPy | 87.7 | 0.088 | 77.2 | 7.35x | 0 | 0 |
| PyTorch | 1131 | 1.131 | 332.6 | 94.81x | 6.92e-08 | 2.33e-10 |
| C | 11.9 | 0.012 | 15.1 | 1.00x | 5.18e-07 | 4.66e-10 |

best: C

## mlp f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 12.8 | 0.013 | 15.1 | 1.21x | 5.51e-07 | 4.47e-07 |
| NumPy | 74.5 | 0.074 | 43.3 | 7.05x | 0 | 0 |
| PyTorch | 1077 | 1.077 | 293.5 | 102.00x | 2.02e-07 | 6.56e-07 |
| C | 10.6 | 0.010 | 15.1 | 1.00x | 1.38e-07 | 4.62e-07 |

best: C

## transformer f32

| column | wall ms | CPU s | peak RSS MB | x best | max rel err vs NumPy | max sample abs err |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIL | 5.57 | 0.005 | 15.1 | 2.53x | 5.05e-09 | 5.96e-08 |
| NumPy | 63.0 | 0.063 | 34.8 | 28.66x | 0 | 0 |
| PyTorch | 1048 | 1.048 | 291.8 | 476.74x | 5.10e-09 | 1.49e-08 |
| C | 2.20 | 0.002 | 15.1 | 1.00x | 7.37e-08 | 1.79e-07 |

best: C

## AIL against the best column, sorted

| case | AIL ms | best column | best ms | AIL / best |
| --- | ---: | --- | ---: | ---: |
| matmul_2048_f64 | 5354 | NumPy | 482.5 | 11.10x |
| softmax_1024_f32 | 114.5 | C | 11.9 | 9.60x |
| matmul_1024_f64 | 690.1 | NumPy | 134.4 | 5.14x |
| matmul_256_f64 | 14.7 | C | 4.18 | 3.52x |
| elementwise_10m_f32 | 323.1 | C | 115.2 | 2.80x |
| softmax_1024_f64 | 45.0 | C | 16.1 | 2.80x |
| matmul_2048_f32 | 829.5 | NumPy | 326.5 | 2.54x |
| transformer_f32 | 5.57 | C | 2.20 | 2.53x |
| transformer_f64 | 4.77 | C | 2.44 | 1.95x |
| matmul_256_f32 | 4.67 | C | 2.48 | 1.88x |
| sum_10m_f32 | 60.7 | C | 33.7 | 1.80x |
| mlp_f64 | 28.4 | C | 17.3 | 1.64x |
| matmul_1024_f32 | 121.8 | C | 98.2 | 1.24x |
| mlp_f32 | 12.8 | C | 10.6 | 1.21x |
| sum_10m_f64 | 34.5 | AIL | 34.5 | 1.00x |
| elementwise_10m_f64 | 152.2 | AIL | 152.2 | 1.00x |

## What AIL could not write

- The attention **core** of the transformer block (Q/K/V, scores, row softmax, P@V, residual) is
  expressible with `ta.matmul`, `.T` and a row loop. The **full** block is not: there is no
  layer norm (no `mean`/`var`, and `ta.sum`/`ta.max` take 1-D arrays only), no 2-D row
  broadcast, no fused softmax, and no vector-matrix `dot`; every row operation is a manual
  loop that copies the row out and writes it back.
- 2-D f32 element-wise operations and 2-D reductions are refused by name; the f32 MLP and
  transformer rows therefore use 1-D row operations on the rows of 2-D f32 matrices.
- There is no torch-like API: `TORCH_COMPAT.md` is a design note and no `ail_torch` module
  exists in this tree.
- `ta.matmul` is CPU-only. The GPU/SPIR-V path is opt-in and covers marked loops, not array
  operations; no GPU matmul kernel is built.

## Self-check

Small versions of every generated AIL program were built with both the default and the
unified build and compared with CPython by `lab/aicomp/probes.py`; every probe matched
CPython stdout (see the report). No compiler behaviour was changed.

## Verdict

1. **Gap 1: matmul_2048_f64** is 11.10x the best column (NumPy, 5354 ms vs 482.5 ms). What it would take: a blocked SIMD/AVX2 kernel that keeps the fixed lane order, or a BLAS FFI behind the explicit inexact opt-in; estimate: 1-2 weeks for the kernel, 2-4 days for the BLAS wiring (estimate).
2. **Gap 2: softmax_1024_f32** is 9.60x the best column (C, 114.5 ms vs 11.9 ms). What it would take: a fused, vectorised f32 exp/sum kernel and row-level threads; estimate: 1-2 weeks (estimate).
3. **Gap 3: matmul_1024_f64** is 5.14x the best column (NumPy, 690.1 ms vs 134.4 ms). What it would take: a blocked SIMD/AVX2 kernel that keeps the fixed lane order, or a BLAS FFI behind the explicit inexact opt-in; estimate: 1-2 weeks for the kernel, 2-4 days for the BLAS wiring (estimate).
4. Context: the MLP and attention rows are already at or near the best wall because their
   matrices are small; the pure-Python columns there mostly measure interpreter start-up
   (PyTorch ~1.0 s, NumPy ~0.06 s, AIL ~0.0006 s), not kernel speed.
5. Overall: AIL is exact by default and competitive on f64 reductions and element-wise
   chains, but it is behind BLAS/SIMD on large matmul and behind plain C on f32 exp/reduction;
   the full transformer block is not expressible yet.
