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
