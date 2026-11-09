# aicore1: an MLP forward pass and an attention block in AIL

Job aicore1 (2026-11-09). Programs in this directory:

- `mlp.py`: batch 64, 784 -> 512 -> 10, relu, f32. Inputs and weights come from one 32-bit LCG
  (`s = (1664525*s + 1013904223) % 2**32`, `value = (s / 2**32 - 0.5) * scale`), seed 1, filled in the order
  x, w1, b1, w2, b2. Prints the row-major sum of the output (each row with `ta.sum`), two elements and two argmaxes.
- `attn.py`: seq 128, dim 64, one head, f32: `softmax(Q K^T / sqrt(64)) V` with the max-subtracted softmax.
  Q, K, V from the same LCG, seed 7. Prints the sum of the output, two output elements and one probability.
- `mlp_np.py`, `attn_np.py`: the same programs with NumPy (for its output and its timing only).

Reference = the same `.py` file run by CPython 3.12 with `AIL_CURRENT/ail_array.py` beside it
(`PYTHONPATH=AIL_CURRENT python3 lab/aicore1/mlp.py`).

## 1. Census (before this job, integ c02f3d4f3)

Both programs are written the way the torch/NumPy user writes them (`ta.matmul(x, w1) + b1`, `ta.maximum(h, 0.0)`,
`ta.max(s, axis=1, keepdims=True)`, `ta.exp(s - m)`, `e / ta.sum(e, axis=1, keepdims=True)`, `k.T`).

| program | AIL compile | CPython + reference |
| --- | --- | --- |
| `mlp.py` (f32) | refused: `mlp.py:32: element-wise operations and reductions on a 2-D f32 array are not built (2-D f64 has them)` | `ValueError: ail_array: shapes differ: (64, 512) and (512,)` (no row broadcast) |
| `mlp.py` with f64 | refused: `a 2-D array and a 1-D or int32 array (a row broadcast is not built)` | same ValueError |
| `attn.py` (f32) | refused: the same 2-D f32 element-wise refusal (`* (1/sqrt d)`) | `TypeError: max() got an unexpected keyword argument 'axis'` |
| `attn.py` with f64 | refused: `ta.max(axis=...) is not a parameter it takes` | same TypeError |

What was missing, and why:

1. **Element-wise operations on 2-D f32 arrays** (`+ - * /`, scalars, `-`, `abs`, `exp sqrt log tanh`,
   `minimum maximum clip`): job fdarr2 built 2-D f32 construction, indexing, `.T` and `matmul` only.
2. **Broadcasting a row / a column**: `(64, 512) + (512,)` (bias) and `(128, 128) - (128, 1)` (softmax). The design
   (TYPED_ARRAY 2.3) planned the row broadcast; neither the reference nor the compiler had it.
3. **Row-wise reductions** (`max` and `sum` along an axis, with the dimension kept): not in the API at all.
4. Already there: `ta.matmul` for f32 (fixed order of 3.7), `M.T`, `M[i]`, `ta.sum/argmax` of a 1-D f32 row,
   `math.sqrt` on a scalar.

Not needed for these two programs and still missing: `@`, `ta.softmax`, `mean`, int8/f16 2-D, N-D.

## 2. What was added (step 2)

- **Broadcasting (1-D/2-D)**: an array-array `+ - * /` (and `ta.minimum/maximum`) where one side is 2-D uses NumPy's
  rule restricted to two dimensions: a 1-D `(n,)` operand is a row `(1, n)`; each dimension must be equal or 1 on one
  side, and the side with 1 is repeated. Same dtype required (the existing `dtypes differ` TypeError comes first), a
  shape that does not broadcast keeps the `ValueError: ail_array: shapes differ: (a) and (b)` text. In place
  (`M += row`) keeps the left shape. Two 1-D arrays still need equal lengths (no change). Exact by construction: the
  repeat is a copy, then the same-shape operation runs, so every element has the bits of the 1-D operation.
- **Axis reductions** (2-D f64/f32): `ta.sum(M, axis=, keepdims=)`, `ta.min/ta.max(M, axis=, keepdims=)`,
  `ta.argmin/ta.argmax(M, axis=)` (int32 result). `axis` is 0 or 1 (or -2, -1); `ta.sum(M, axis=1)[i]` is
  `ta.sum(M[i])` bit for bit, i.e. each row is summed in the one fixed order of TYPED_ARRAY 3.5 (16 lanes, blocks of
  1024, tree) with the dtype as accumulator (f32 for f32; f16 sums to f32). `axis=0` reduces each column the same way.
  `keepdims=True` gives `(r, 1)` / `(1, c)`. `acc=`/`order=` with `axis=` are refused by name.
- **2-D f32 element-wise**: every operation above is the 1-D f32 operation on the row-major data, so the f32 rounding
  rules (one rounding per op, IEEE division, canonical NaN; `exp` is `r_f32(libm exp in binary64)`) are unchanged.

Both programs now compile on the typed path and print the reference's bytes (section 3 has the numbers).

| program | AIL output = CPython + reference | NumPy 2.2.6 (Windows) output |
| --- | --- | --- |
| `mlp.py` | `-9.1396434754133224`, `-0.082242131233215332`, `-0.084551580250263214`, `8 4` | `-9.13964669033885`, `-0.082242026925086975`, `-0.084551602602005005`, `8 4` |
| `attn.py` | `-86.309193223714828`, `-0.074540652334690094`, `-0.013285044580698013`, `0.006452921312302351` | `-86.309192895889282`, `-0.074540644884109497`, `-0.013285058550536633`, `0.0064529217779636383` |

NumPy differs in the last digits because its sgemm uses another summation order (and FMA), and its `exp` is
NumPy's own; AIL's digits are the fixed-order ones and equal CPython + the reference.

## 3. Speed (CPU, typed path)

Programs: `bench_mlp.py` / `bench_attn.py` (AIL, default build), `mlp.c` / `attn.c` (plain C, naive loops, sequential
sums, `gcc -O2`), `mlp_np.py` / `attn_np.py` (NumPy 2.2.6, Windows Python 3.13 on the same laptop; WSL has no NumPy).
Each program times one forward pass inside itself (the fill is outside the timer): 21 passes for the MLP, 101 for
attention, median taken; each program run 5 times, the median of the 5 medians reported. Laptop: Inspiron 14 5445,
WSL2, timing noisy (runs within one set spread up to about 15%; one NumPy run was 5x its median). Instructions:
`tools/icount.c`, user space, (the program with R passes minus the program with 0 passes) / R.

The AIL output is bit-identical to CPython + the reference in every row (the checksums above); C and NumPy are not
(other order, NumPy also FMA and its own exp).

| forward pass | AIL before step 3 | AIL after step 3 | C naive -O2 | NumPy, default threads | NumPy, 1 thread |
| --- | --- | --- | --- | --- | --- |
| MLP 64x784x512x10, wall | 9.19 ms | **3.20 ms** | 66.1 ms | 0.56 ms | 1.20 ms |
| MLP, instructions | 82.0M | 47.8M | 181.7M | - | - |
| attention 128x64, wall | 7.57 ms | **0.430 ms** | 0.641 ms | 0.254 ms | 0.142 ms |
| attention, instructions | 58.9M | 6.95M | 6.77M | - | - |

Ratios after step 3: MLP AIL is 20.7x faster than naive C, 5.7x slower than NumPy (multi-threaded BLAS) and 2.7x slower
than NumPy on one thread. Attention: 1.49x faster than naive C, 1.7x slower than NumPy, 3.0x slower than NumPy on one
thread. (C naive MLP is slow because its inner loop reads `w1` with a stride of 2 KiB.)

What step 3 changed, largest gap first (attention was 11x slower than naive C; per-op instruction counts on 128x128 f32):

| op | before | after | change |
| --- | --- | --- | --- |
| `M - col`, `M / col` (broadcast) | 11.6M each | 0.15M | the repeat copy is a C kernel (`ailz_bc`), was a byte loop |
| `ta.max(M, axis=1, keepdims=True)` | 10.1M | 0.25M | row min/max kernel (`ailz_rext`), was a row copy + f64 view per row |
| `ta.sum(M, axis=1, keepdims=True)` | 8.8M | 0.07M | row sums with the existing fixed-order reducer (`ailz_rsum`) |
| `k.T` (128x64) | 5.7M | 0.07M | transpose kernel (`ailz_tr`), was a byte loop |
| `ta.exp(M)` | 4.3M | 1.36M | `(float)exp((double)x)` in C (`ailz_fn`), the same definition as the f64 path; was three passes through an f64 copy |
| `ta.maximum(M, 0.0)` (64x512) | 4.9M | (in the 47.8M) | min/max kernel (`ailz_pick`), was three passes through an f64 copy |
| `ta.matmul` f32 | 1 output at a time | 2 outputs per pass | `ailz_block2`: two columns share the loads of the row, columns tiled; each output runs `ailz_block`'s operations in its order |

Every kernel has a plain-Python definition in the prelude (CPython and the general path run it); the typed path calls
the C. All are moves, comparisons, or one binary64 libm call rounded once, or the existing 3.5 order, so no output bit
changes (array_ai_cases match in the default, forced and typed builds; the f32 matmul cases of test_ail_array_core and
test_ail_array_f32native, including the scalar `-DAILZ_SCALAR` build, still pass).

## 4. What is still missing / next

- **The matmul is the gap to NumPy.** The f32 kernel is 4-wide SSE (the default build has no AVX; `x86-64-v3` is
  opt-in by owner decision), no FMA (the fixed order forbids it), one thread. The inner loop is 31 instructions per 32
  multiply-adds, but the whole MLP matmul costs 1.77 instructions per multiply-add (transposing `B` with 4-byte
  `memcpy`s, the per-output lane tree). Next: a blocked transpose, 4-column blocking with AVX under a runtime CPU
  check (needs an owner decision: the default stays SSE2), threads over output tiles (the order does not depend on them).
- `ta.exp` uses binary64 `exp` per element (83 instructions each); a vector f32 exp would change bits, so it belongs to
  the opt-in inexact mode (TYPED_ARRAY 7), not the default.
- 2-D f64 axis reductions and broadcasts still use the Python-written loops (correct, slower); 2-D int32 element-wise
  is still refused; `@`, `ta.softmax`, `mean`, N-D, f16/int8 2-D are not built.
- Not measured: peak RSS, compile time.
