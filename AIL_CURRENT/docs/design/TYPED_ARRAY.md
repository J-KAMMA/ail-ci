# Typed arrays: the `ail_array` module (design only, 2026-10-30)

Design note for the declared-precision array module the owner approved on 2026-10-29 (GPU.md section 10, D1). Nothing
here is built yet. It sits in the modules/FFI stage of the roadmap; GPU.md section 8 (M1..M6) builds on it later.
Oracle: CPython 3.12 running the module's pure-Python reference implementation (section 4).

The rule, unchanged: **a program prints exactly what CPython prints, or it is refused at compile time by name**, with
file:line and a `write instead:` hint. For this module "what CPython prints" means: CPython 3.12 running the same
program with `ail_array.py`, the reference file, beside it. The module's arithmetic is defined by this note, the
reference implements exactly that definition, and AIL's native code must give the same bits.

Verification marks: **[verified 2026-10-30]** = checked while writing this note, in the `integ` tree (d68453f7) or with
a CPython 3.12.3 snippet in WSL (no AIL program was compiled); **[read, not run]** = follows from reading code;
**[unverified]** = from memory or inference, to be checked in the stage named.

## 0. Words

- *dtype*: one of the five element types `f64`, `f32`, `f16`, `int8`, `int32` (D1). Nothing else.
- *r_T(x)*: round the real number `x` to dtype `T`, round-to-nearest, ties to even, with gradual underflow
  (subnormals kept) and overflow to `+-inf` (section 3.1).
- *element-wise op*: an op whose output element `i` depends only on input elements `i` (no order question).
- *reduction*: an op over many elements whose float result depends on the order of the adds (section 3.5).
- *reference*: `AIL_CURRENT/ail_array.py`, plain CPython, no numpy, no C extension (section 4).
- *typed path / general path*: as in BIGINT.md sections 4 and 10.

## 1. Scope

### 1.1 In

1. A module `ail_array` with one array type, five dtypes, 1-D first and 2-D (row-major) for matrix multiply.
2. Construction, indexing, slicing, element-wise arithmetic, reductions, conversion to and from lists and bytes,
   dtype casts, with every result defined bit for bit (sections 2 and 3).
3. A pure-Python reference that runs on CPython 3.12 and is the oracle for every AIL test of the module (section 4).
4. Native lowering in AIL: unboxed C buffers, SIMD that cannot change a bit, fixed reduction order (section 5).
5. Passing arrays to C through the existing FFI without copying (section 6), so BLAS and later the GPU read them.
6. The opt-in inexact mode of D2 (section 7).

### 1.2 Out

- numpy compatibility (names, broadcasting rules, dtype promotion, views). GPU.md Q5 asks whether a numpy subset is
  wanted; this module is deliberately smaller and is not that subset (decision TA6: a numpy subset may come later).
- dtypes beyond D1: `bf16`, `uint8`, `int16`, `int64`, `bool`, complex. Refused by name (section 8).
- Shapes with more than two dimensions (decision TA5).
- Automatic differentiation, training, a model format.

### 1.3 What exists today

- `array.array` is built for the integer typecodes and `'d'` as a Python prelude whose elements are a list
  (`prelude_array.py`, injected by `smalllib5.run_array`). Typecodes `'f'`, `'u'`, `'w'` and `tobytes`, `frombytes`,
  `tofile`, `fromfile`, `buffer_info` are refused by name **[verified 2026-10-30]**. So no binary32 storage exists in
  user programs yet.
- `struct` and `memoryview` are not built for user programs: no lowering of `struct.pack`/`unpack` and no
  `memoryview` support in `pkg-v12`; `memoryview` appears only in `bigcap.py`'s builtin-name tables and in
  `pipeline.py`'s own ctypes code **[verified by grep 2026-10-30]**. How an `import struct` in a user program is
  reported today was not checked **[unverified]**. The test suites use `struct` only on the CPython side, as an
  oracle (`test_ail_float64_codec.py`, `test_ail_integer_codec.py`) **[verified]**.
- The FFI already has binary32 at the boundary: interface kinds `float32` and `float32_list` (SEMANTICS.md sections 48
  and 50) convert `list[float]` to a temporary `const float *` with finite-only checks, and `ail_ffi.py` has
  `ptr(T)` / `cptr(T)` over a `bytearray` / `bytes` for `c_float` and `c_double` **[verified]**. `ail_cbuf.py` reads
  and writes little-endian ints and doubles in a bytearray in plain Python that compiles natively **[verified]**.
- The C build uses `-ffp-contract=off` (no fused multiply-add) and `-fopenmp-simd` (a `#pragma omp simd` hint on flat
  float comprehensions), and keeps `-O2` without `-march` by default; `x86-64-v3` is opt-in only (owner decision
  2026-10-17) **[verified in `pyc.py`]**.

## 2. API

```python
import ail_array as ta

a = ta.array([1.0, 2.5, -0.0], ta.f32)     # from a list (copied)
z = ta.zeros(1024, ta.f16)                  # also ta.full(n, value, dtype), ta.arange(n, dtype) for ints
q = ta.frombytes(data, ta.int8)             # little-endian raw bytes (copied); a.tobytes() back
y = (a * 2.0 + a) / 3.0                     # element-wise, rounded to f32 after every op
s = ta.sum(y); m = ta.max(y); d = ta.dot(a, y)   # Python float results; fixed order (section 3.5)
h = y.astype(ta.f16); i = y.astype(ta.int32, rounding='nearest', overflow='saturate')
W = ta.zeros((64, 128), ta.f32); out = ta.matmul(x2d, W)     # 2-D from stage T6; also x2d @ W
```

### 2.1 Table

| group | names | notes |
| --- | --- | --- |
| dtypes | `ta.f64 ta.f32 ta.f16 ta.int8 ta.int32` | objects with `.name`, `.itemsize` (8, 4, 2, 1, 4); `repr` is the name |
| construction | `ta.array(values, dtype)`, `ta.zeros(shape, dtype)`, `ta.full(shape, value, dtype)`, `ta.arange(n, dtype)` (int dtypes), `ta.frombytes(data, dtype, shape=None)`, `a.copy()` | `values`: a list/tuple/iterable of int/float/bool, or a list of equal-length lists for 2-D; every value goes through the store rule (3.4) |
| size | `len(a)` (rows for 2-D), `a.shape` (tuple), `a.dtype` | arrays have a **fixed length**: no `append`/`extend`/`pop`/`insert` (section 8) |
| indexing | `a[i]`, `a[i] = x`, `A[i, j]`, `A[i, j] = x`, negative indices | `a[i]` returns a Python `float` (the element's exact value) or `int`; `IndexError: array index out of range` (`array.array`'s text **[verified]**) |
| slicing | `a[i:j:k]` (1-D), `A[i]` (a row), `A[i:j]` (rows) | **a copy**, like `list` and `array.array`; no views (section 6.1). `a[i:j] = b` needs the same dtype and length (`ValueError` otherwise) |
| element-wise | `+ - * /` (float dtypes), `+ - * // %` (int dtypes), unary `-`, `abs(a)`, `+= -= *= /= //= %=`, `ta.sqrt exp log tanh` (float), `ta.minimum ta.maximum ta.clip` | operands: two arrays of the same dtype and shape, or an array and a Python int/float/bool (3.6); 2-D adds a row broadcast `A + row` (T6) |
| int extras | `ta.wrapping_add/sub/mul`, `ta.saturating_add/sub` | the only way to get wrap or saturation (3.3) |
| reductions | `ta.sum(a, acc=None)`, `ta.dot(a, b, acc=None)`, `ta.min`, `ta.max`, `ta.argmin`, `ta.argmax` | float results are Python floats, int results exact Python ints (3.5) |
| matrix | `ta.matmul(A, B, acc=None)`, `A @ B`, `ta.transpose(A)` (copy), `a.reshape(shape)` (copy) | T6; section 3.7 |
| conversion | `a.tolist()`, `a.tobytes()`, `list(a)`, iteration, `a.astype(dtype, rounding='trunc', overflow='raise')` | `tobytes` is little-endian raw storage, NaN payloads included (3.1) |
| comparison | `a == b`, `a != b` | one `bool`, like `list`: same dtype, same shape, every element `==` (so NaN makes it False, `-0.0 == 0.0`); `<` etc. raise `TypeError`; arrays are unhashable |
| text | `repr(a)`, `str(a)` | `array([1.0, 2.5, -0.0], f32)`; each element is the `repr` of its Python float, so f32 `0.1` prints `0.10000000149011612`, exactly what `print(a[0])` prints |

Builtins that iterate (`sum(a)`, `min(a)`, `sorted(a)`, `max(a, key=...)`) keep CPython's meaning: they see Python
floats/ints one by one. So `sum(a)` is CPython's binary64 Neumaier sum of the widened elements, and `ta.sum(a)` is the
module's own sum (3.5). They are different functions and may print different digits; the docs say which is which.

### 2.2 Annotations and dtype in the type system

`ta.Array` is the class; `ta.Array[ta.f32]` is accepted as an annotation (the reference gives `Array` a
`__class_getitem__` that returns an alias CPython ignores at run time). The typed path needs the dtype of every array
value at compile time: it is taken from the construction call (`dtype` must then be a literal `ta.<name>`), from an
annotation, or from the whole-program parameter-kind propagation (SEMANTICS.md section 26). A value whose dtype is not
static goes to the general path, which dispatches on a dtype tag at run time (section 5.1).

### 2.3 Shape: 1-D first, then 2-D, N-D not planned

1-D covers element-wise chains, reductions, and the buffers C and BLAS read. 2-D (C order, contiguous, `shape =
(rows, cols)`) is added in T6 only because matrix multiply needs it (small-model inference, GPU.md 8.3). The only
broadcasts are `(r, c) op (c,)` (a bias row) and array-scalar. General N-D arrays, strides and views are not planned:
each one multiplies the lowering cases and the aliasing proofs (section 6) and no first target needs it (TA5).

## 3. Exact semantics

### 3.1 Float dtypes: f64, f32, f16

| question | rule |
| --- | --- |
| rounding | every element-wise op `x op y` gives `r_T(exact(x op y))` for `+ - * /` and `sqrt`: correctly rounded in `T`, ties to even. Nothing is fused: `a * b + c` is two ops, two roundings. f64 is IEEE binary64, f32 binary32 (24 bits), f16 IEEE binary16 (11 bits, exponent -14..15) |
| overflow | to `+inf` / `-inf` (IEEE). **Float dtypes never raise for overflow**, in arithmetic, casts or stores. `array('f', [1e300])` stores `inf` on CPython 3.12 too **[verified]**; `struct.pack('f', 1e300)` raises `OverflowError` instead **[verified]**, so the reference catches it (section 4.2) |
| division by zero | IEEE: `1/0 -> inf`, `-1/0 -> -inf`, `0/0 -> NaN`. This differs from Python's `float /` (which raises); it is the module's rule because SIMD and GPU code cannot raise per lane, and ML code expects it (decision TA2) |
| NaN | every NaN **produced** by an op, a cast, or a store of a Python float NaN is the **canonical quiet NaN with the sign bit clear**: f64 `0x7ff8000000000000`, f32 `0x7fc00000`, f16 `0x7e00`. Reason: x86 produces a NaN with the sign set for `inf - inf` (`fff8000000000000` on CPython here **[verified]**; `math.copysign(1, inf - inf)` is `-1.0`), arm64 produces it with the sign clear **[unverified]**, and a GPU may produce yet another; canonicalising makes the bits device-independent. Bits that arrive through `frombytes` or a C call are stored unchanged until an op touches them |
| NaN to Python | `a[i]` of a stored NaN gives the Python float the C conversion `(double)` gives. Under CPython the reference uses `struct.unpack('<f')`, which is that C cast; a signalling f32 NaN `7f800001` came back as `7ff8000020000000` (quieted, payload shifted) **[verified on x86-64]**; arm64 also quiets **[unverified]**. AIL does the same cast, so both agree on one machine |
| -0.0 | kept as IEEE: `-0.0 + -0.0 = -0.0`, `0.0 + -0.0 = 0.0`, `-(0.0) = -0.0`, `abs(-0.0) = 0.0`; `r_f16(-0.0)` is `0x8000` **[verified]** |
| subnormals | kept (gradual underflow) in all three dtypes, in arithmetic and conversion. f16: smallest `2^-24`, largest subnormal `2^-14 - 2^-24`; `2^-25` rounds to `0.0` (tie to even), anything above it to `2^-24` **[verified with `struct 'e'`]**. No flush-to-zero anywhere: the runtime never sets FTZ/DAZ, and a C callee that does is "trusted C" as in SEMANTICS.md section 48 |
| `sqrt` | correctly rounded. Negative input gives NaN (canonical), not `ValueError` (TA2) |
| `exp log tanh` | defined as `r_T(math.<f>(float(x)))`: CPython's libm result in binary64, rounded once to `T`. On one platform CPython and AIL call the same libm, so the bits agree; across platforms both follow that platform's libm, as plain `math.exp` already does. `log` of a negative is NaN, of zero `-inf` (IEEE, not `ValueError`); `exp` whose binary64 result overflows is `inf` (CPython's `math.exp(1000)` raises `OverflowError: math range error` **[verified]**, so the reference catches it; found in T1). No vector libm (it gives other bits) except in the inexact mode (section 7) |
| `minimum maximum clip` | element-wise; NaN in either operand gives NaN; `-0.0` is less than `0.0`. Order-independent on purpose (Python's `min(-0.0, 0.0)` returns the first argument **[verified]**; the module does not copy that position rule) |

### 3.2 Why "compute in binary64, round once" is exact

For `+ - * /` and `sqrt`, rounding the binary64 result again to a format with `p` bits is the same as rounding the
exact result once, whenever `53 >= 2p + 2` (the double-rounding theorem; Figueroa 1995 **[citation from memory,
unverified]**). f32 has `p = 24` (50 <= 53) and f16 `p = 11` (24 <= 53). f16 through f32 also holds (`24 >= 2*11 + 2`).
Checked while writing this note against an exact `fractions.Fraction` oracle (exact result, rounded with integer code,
ties to even, subnormals and overflow included): 60,000 random finite bit-pattern pairs each for f16 `+ - * /` via
binary64, the same via binary32, f32 `+ * /` via binary64, and 50,000 f32 `sqrt`: **0 mismatches [verified 2026-10-30;
a sample, not a proof; T1 runs the exhaustive f16 unary set and a larger sample]**. The theorem does **not** cover a
chain (`a*b + c` evaluated in binary64 and rounded once is a different result from two f32 ops), which is why every
module op rounds separately and nothing is fused.

### 3.3 Int dtypes: int8, int32

| question | rule |
| --- | --- |
| overflow of `+ - *`, unary `-`, `abs` | **raises `OverflowError`** at the first element (lowest index) whose exact result is outside the dtype: `OverflowError: int8 add overflow at index 3`. The result array is not created; for in-place ops (`a += b`) the elements before that index are already updated and the rest are not, as the loop `for i in range(n): a[i] += b[i]` would leave them |
| why raise, not wrap | (1) Python ints never wrap; a program ported from list code expects `100 + 100 == 200`, and a silent `-56` is the classic numpy bug the zero-silent-difference rule exists to rule out, even if the reference wrapped too. (2) It matches what the typed path already does for int64 (the loud stop, BIGINT.md section 4) and what `array('b', [200])` does (`OverflowError` **[verified]**). (3) The GPU design already handles int overflow by flag and replay (GPU.md 3.3), so the GPU can keep the same rule. (4) The check is cheap in SIMD: compute in a wider lane or test signs, OR the lane flags per vector, rescan only a flagged vector (5.2). (5) ML code that wants wrap or saturation says so: `ta.wrapping_add/sub/mul` (two's complement) and `ta.saturating_add/sub` (clamp to the range), the forms quantised inference uses **[unverified that these cover the target models; T6 checks]** |
| `//`, `%` | Python's floor division and modulo (the sign of `%` is the divisor's); `ZeroDivisionError: integer division or modulo by zero` (CPython's text **[verified]**) at the first zero divisor; int8 `-128 // -1` and int32 `-2^31 // -1` raise the overflow error |
| `/` on int arrays | `TypeError` ("use a.astype(ta.f64) / b.astype(ta.f64)"): no implicit int-to-float |
| store `a[i] = x` | `x` an int or bool in range; outside: `OverflowError: int8 value out of range: 200`; a float: `TypeError: 'float' object cannot be interpreted as an integer` (the text `array('i', [1.5])` gives **[verified]**) |

### 3.4 Stores, casts and Python scalars

- **Store of a Python float into a float array**: `r_T(x)`, overflow to inf, NaN canonical. An int is first `float(x)`
  (CPython's rule: correctly rounded to binary64, `OverflowError: int too large to convert to float` beyond it), then
  `r_T`. That is two roundings for large ints into f32/f16; it is the definition, and the reference does the same.
- **`astype` float to float**: `r_T`, overflow to inf, NaN canonical. f16 to f32/f64 and f32 to f64 are exact.
- **`astype` int to float**: exact int, rounded once (`float(int)` is exact for `|x| < 2^53`, so int8/int32 are rounded
  once). int8 to f16 is exact; int32 to f32 rounds (above `2^24`); int32 to f16 overflows to inf from 65520 on.
- **`astype` float to int**: `rounding='trunc'` (toward zero, like `int()`, default) or `'nearest'` (ties to even, like
  `round()`); `overflow='raise'` (default: NaN raises `ValueError: cannot convert float NaN to integer`, inf raises
  `OverflowError: cannot convert float infinity to integer` **[texts verified]**, out of range raises
  `OverflowError: int8 cast overflow at index 4` at the first such index) or `'saturate'` (clamp; NaN becomes 0).
  `overflow='wrap'` is a `ValueError` for float sources.
- **`astype` int to int**: `overflow='raise'` (default, same text), `'saturate'` or `'wrap'`.
- In T1 a 2-D shape (`ta.zeros((2, 3), ...)`) raises `ValueError` naming stage T6, and 3-D or more raises the
  `1-D and 2-D` error; `order='any'` on `ta.min`/`ta.max` raises `ValueError` at run time in the reference (the
  compiler refuses it by name, section 8).
- **Array op Python scalar**: section 3.6.

### 3.5 Reductions: one fixed order

A float sum depends on the order. Sequential order (Python's) cannot use SIMD lanes or threads; a free order makes the
bits depend on the machine. So the module fixes one order that maps onto any SIMD width dividing 16, onto threads, and
onto GPU work groups, and the reference implements exactly that order.

`ta.sum(a)` for a float dtype `T` with accumulator dtype `A` (default `A = T`, except f16 whose default is `A = f32`;
`acc=ta.f64` or `acc=ta.f32` may widen, never narrow):

1. Each element is converted to `A` exactly (widening is exact).
2. The array is cut into **blocks of 1024 elements** (the last may be shorter).
3. Inside a block there are **16 lanes**, each starting at `-0.0` (the exact identity of IEEE addition, so empty lanes
   change nothing and the sum of `[-0.0]` is `-0.0`). Element `k` of the block goes to lane `k % 16`, added in index
   order with `r_A` after every add. The 16 lanes are then combined pairwise: `l[i] = r_A(l[i] + l[i+w])` for
   `w = 8, 4, 2, 1`, `i < w`. The block value is `l[0]`.
4. Blocks `[lo, hi)` are combined by `S(lo, hi) = block(lo)` if `hi - lo == 1`, else `r_A(S(lo, lo+p) + S(lo+p, hi))`
   with `p` the largest power of two below `hi - lo`.
5. The empty array gives `+0.0`. The result is returned as a Python float (the `A` value, widened exactly).

Properties: a fixed function of the values and `n` only; SSE/NEON (4 x f32), AVX2 (8), AVX-512 (16) and a GPU sub-group
of 16 all produce it with no extra work; threads take whole subtrees of blocks. It is **not** CPython's
`sum(a.tolist())` (Neumaier, sequential: `sum([0.1] * 10)` prints `1.0`, `sum([-0.0])` prints `0.0` **[verified]**)
and not numpy's pairwise sum; users who want Python's result call the builtin `sum(a)`, which stays exactly CPython's.

- `ta.dot(a, b)` is the fixed-order sum of the products `r_A(a_i * b_i)` (operands widened to `A` first); the fused
  native loop keeps no temporary array. When `A = T` (f32, f64 by default) that is bit-for-bit `ta.sum(a * b)`; for
  f16 (default `A = f32`) it is not, because `a * b` rounds the products to f16 (clarified in T1).
- `ta.min` / `ta.max`: NaN if any element is NaN (canonical); `-0.0 < 0.0`; `ValueError` on an empty array (CPython
  3.12's `min()` text: `min() iterable argument is empty` **[verified]**). Order-independent, so any lane or thread
  split is exact.
- `ta.argmin` / `ta.argmax`: the **lowest index** holding the min/max value under the same order (`-0.0` and `0.0` are
  different values here); the first NaN's index if there is one.
- **Int reductions** (`sum`, `dot`, `min`, `max`) are exact Python ints and order-free. Native code accumulates int8 and
  int32 in int64: `|sum| <= 2^31 * n < 2^63` while `n < 2^32` elements; `dot` of int32 can exceed int64 (`2^62 * n`),
  so it uses `__builtin_add_overflow` and a cold big-int path (BIGINT.md) **[read, not run: an int32 `dot` result
  above int64 is rare; it falls back, it is never wrong]**.

### 3.6 Mixed dtypes and promotion

- **Array op array of different dtypes: `TypeError`** (`ail_array: f32 + f16: dtypes differ; write a.astype(ta.f16) or
  b.astype(ta.f32)`). No implicit promotion between arrays: every precision change is written in the program. Shapes
  that differ: `ValueError: ail_array: shapes differ: (3,) and (4,)`.
- **Array op Python float**, float array: the scalar is stored to `T` first (3.4), then the op runs in `T`. So
  `a_f16 * 0.1` multiplies by `r_f16(0.1) = 0.0999755859375`. (numpy 2's "weak scalar" rule keeps the same dtype
  **[unverified that its bits match]**.)
- **Array op Python int**, float array: the int is stored to `T` (3.4). Int array: the int must fit the dtype
  (`OverflowError: int8 value out of range: 300`), then the op runs with overflow checks.
- **Array op Python float, int array: `TypeError`** (write `a.astype(...)`).
- `bool` is an int (0/1) everywhere, as in Python.
- Results of int `+ - * // %` stay in the dtype (checked); reductions of ints return Python ints.

### 3.7 Matrix multiply (T6), consistent with GPU.md 8.7

| inputs | result | definition |
| --- | --- | --- |
| f64 x f64 | f64 | **built (T6, 2026-10-30).** `C[i, j] = ta.dot(A[i], B[:, j])` bit for bit: the products `r(A[i,k] * B[k,j])` are added along `k` in the **one fixed order** below. K = 0 gives `+0.0` |
| f32 x f32 | f32 | the same order with `r = r_f32` (not built yet) |
| f16 x f16 | f32 (default `acc`) | the exact sum of the exact products, rounded once to f32 (GPU.md 8.7). f16 products are exact in f32, and every product is an integer multiple of `2^-48`, so the reference adds Python ints and rounds once with integer code (section 4.2). Not built yet |
| int8 x int8 | int32 | exact integer sum; `OverflowError` if a result leaves int32; order-free (so GPU cooperative matrix may be used under GPU.md 8.7's precondition). Not built yet |
| int32 x int32 | int32 | exact, checked, order-free. Not built yet |

**The exact order of one output element (f64).** For `K` products `p_k = r(A[i,k] * B[k,j])` (each rounded to binary64; `k = 0..K-1`):

1. cut `k` into **blocks of 1024** (`[0, 1024)`, `[1024, 2048)`, ...; the last may be shorter);
2. inside a block of length `L` there are **16 lanes**, each starting at `-0.0`; the product with block-local index `u` is added to lane `u % 16`, in increasing `u`, one rounding per add (`lane = lane + p`);
3. the lanes are combined **8-4-2-1**: `l[i] = l[i] + l[i+w]` for `w = 8, 4, 2, 1` and `i < w` (so `((l0+l8)+(l4+l12)) + ((l2+l10)+(l6+l14))` and so on, exactly 3.5); the block value is `l[0]`;
4. the block values `b_0 .. b_{n-1}` are combined by `S(lo, hi) = b_lo` when `hi - lo == 1`, else `S(lo, lo+p) + S(lo+p, hi)` with `p` the largest power of two below `hi - lo`;
5. `K = 0` gives `+0.0`; a NaN result is the canonical NaN (a NaN product or an `inf - inf` anywhere makes the sum NaN).

This is the order of `ta.dot` (3.5) with the row of `A` and the column of `B` as the two vectors, so `ta.matmul(A, B)[i, j]` equals `ta.dot(A[i], B[:, j])` and a `1 x K` by `K x 1` matmul is `ta.dot`. Nothing in it depends on `M`, `N`, the loop nest, the SIMD width, the thread count or the device: a lane never mixes two columns of the output, so an implementation may tile over `i` and `j` as it likes, may vectorise over `j` (16 lanes of one element are independent of the lanes of the next element) or over the 16 lanes of one element, and must not split `k` or reassociate it. No fused multiply-add (the product is rounded before it is added): `-ffp-contract=off` on the CPU, `NoContraction` in SPIR-V. A missing lane (the short last group of a block) is the identity `-0.0`, so an implementation that pads a short group with `-0.0` is exact; padding with `+0.0` is not (`-0.0 + 0.0 = +0.0`).

This replaces the first draft of this table (sequential `k` from 0 with one accumulator): owner decision 2026-10-30, TA4 below. Sequential `k` cannot use the 16 lanes and differs from `dot` in the last bit; the fixed tree costs one extra block-sized lane set and gives one answer on every device.

### 3.8 2-D arrays (T6)

`Array` has a second shape, `(rows, cols)`, row-major and contiguous (a 1-D array has `shape == (n,)`). All of it is defined by the reference; the native lowering builds **f64 only** in this stage (an int32 2-D array is refused by name, the reference accepts every dtype).

- **Construction**: `ta.zeros((r, c), dt)`, `ta.full((r, c), x, dt)`, `ta.array([[...], [...]], dt)` (a non-empty list of lists; rows of different lengths are `ValueError: ail_array: array(): rows differ in length (2 and 1)`). `(n,)` is the same as `n`. Dimensions are checked in order, each with the 1-D texts (`negative length -1`, `a length must be an int, not float`); more than two dimensions: `ail_array has 1-D and 2-D arrays; shape (2, 3, 4)`. Zero dimensions are allowed: `(0, 3)`, `(3, 0)`, `(0, 0)` hold no elements and keep their shape.
- **Annotation**: `ta.Matrix[ta.f64]` (`ta.Array[...]` is the 1-D annotation). Values are `ta.Array`.
- **Indexing**: `M[i, j]` (two ints, negative allowed, `IndexError: array index out of range` checked for `i` and then `j`), `M[i]` (a 1-D **copy** of row `i`), `M[a:b:c]` (a 2-D **copy** of the selected rows, columns kept). `M[i, j] = x` stores with the 1-D store rule; `M[i] = row` copies a 1-D array of `cols` elements (`ValueError: ail_array: row assignment needs a 1-D array of 3 elements, not shape (4,)`). Slices with a slice in the second position (`M[0, 1:2]`) are `TypeError: ail_array: a 2-D array takes M[i, j] (two ints), M[i] or M[a:b]`; assigning into a slice of rows is `TypeError: ail_array: slice assignment into a 2-D array is not built; assign one row at a time`. There are no views: a slice or a row never aliases the matrix.
- **`.shape`, `len`, `.T`**: `M.shape == (rows, cols)`, `len(M) == rows`, `M.T` is a new transposed array (a 1-D array has no `.T`: `ValueError: ail_array: .T needs a 2-D array, not a 1-D one`). `.copy()`, `.tolist()` (list of rows), `.tobytes()` (row-major), `==` (same dtype, same shape, same values), iteration (yields rows) and `repr` (`array([[1.0, 2.0], [3.0, 4.0]], f64)`) follow.
- **Element-wise operations** use the 1-D rules on the flat data: the same rounding, NaN, IEEE division and in-place semantics. The two operands of an array-array operation must have the **same shape**; `(2, 3) + (3,)` is `ValueError: ail_array: shapes differ: (2, 3) and (3,)` (the row broadcast of 2.3 is not built; write the loop over rows). This covers `+ - * /` (and `// %` on int arrays), unary `-`, `abs`, `sqrt exp log tanh`, `minimum maximum clip`, `astype` and the in-place forms.
- **Reductions** (`sum dot min max argmin argmax`) take 1-D arrays; a 2-D argument is `ValueError: ail_array.sum(): 2-D arrays are not built here; reduce one row: ta.sum(M[i])`. `ta.matmul` is the 2-D product.
- **`ta.matmul(A, B)`**, both 2-D f64: `A` is `(m, k)`, `B` is `(k, n)`, the result is `(m, n)` with the order of 3.7. Errors, in this order: not two arrays: `TypeError: ail_array.matmul() needs two ail_array.Array values`; either not 2-D: `ValueError: ail_array.matmul(): needs two 2-D arrays, not shapes (3,) and (2, 3)`; dtypes differ: the standard `TypeError: ail_array: f64 matmul f32: dtypes differ; write a.astype(ta.f32) or b.astype(ta.f64)`; not f64: `TypeError: ail_array.matmul(): only f64 arrays are built in this version, not f32`; inner sizes differ: `ValueError: ail_array: matmul: shapes (2, 3) and (4, 5) do not match: 3 != 4`. The `@` operator is not defined on arrays (decision TA4: `dot` and `matmul` are separate functions).

## 4. The reference implementation

### 4.1 Shape of the file

`AIL_CURRENT/ail_array.py`, beside `ail_ffi.py` and `ail_cbuf.py`, copied next to the program for CPython runs, like
those two. Plain Python 3.12 standard library only: `struct`, `math` (no numpy). One class `Array` with
`__slots__ = ('_dt', '_shape', '_buf')`; `_buf` is a `bytearray` holding the elements **in the native layout**
(little-endian, C order), so `tobytes` is `bytes(_buf)`, `frombytes` is a copy, and the FFI shim hands the same
bytearray to ctypes without copying (section 6.3). Reads use `struct.unpack_from('<%d%s' % (n, code), buf)` (codes
`d f e b i`); `memoryview(buf).cast('e')` and `cast('f')` also work on 3.12 **[verified]**.

### 4.2 How each result is made bit-identical

- **Float element-wise ops**: unpack to Python floats (exact), compute each element with the Python float op (binary64,
  correctly rounded), then store with `r_T`. Exact by section 3.2. `/` checks for a zero divisor itself and returns the
  IEEE value instead of letting Python raise; `sqrt` and `log` check the domain the same way.
- **`r_T` for f32/f16**: `struct.pack_into('<%df' % n, ...)` on the whole list (fast path); if it raises
  `OverflowError`, the elements are packed one by one and an element that raises becomes `copysign(inf, x)`.
  `struct` raises exactly for values that round to infinity: the largest binary64 below `2^128 - 2^103` packs to
  `0x7f7fffff` and the halfway value itself raises; `65519.99999999999` packs to f16 `0x7bff` and `65520.0` raises
  **[verified at those boundaries; T1 tests every exponent]**. NaNs are replaced by `float('nan')` (bits
  `7ff8000000000000` on CPython **[verified]**) before packing, which packs to `0x7fc00000` / `0x7e00` **[verified]**:
  the canonical NaNs.
- **Int ops**: Python ints (exact), then a range check that raises with the module's text at the first bad index;
  wrapping/saturating forms compute exactly and then wrap (`((x + 2^(b-1)) % 2^b) - 2^(b-1)`) or clamp.
- **Reductions**: the block/lane/tree order of 3.5 written as plain loops, `r_A` after every add (`r_A` of one value is
  a one-element `struct` round trip, or nothing for f64).
- **f16 matmul**: products as exact ints (mantissa times mantissa, exponents tracked), summed as Python ints, then one
  correctly rounded conversion to f32 written with integer arithmetic (not `float()` then `struct`, which would round
  twice).
- **`exp log tanh`**: `math.exp` etc., then `r_T`.

### 4.3 How the reference itself is checked

The reference is the oracle, so it gets its own oracle (T1, `test_ail_array_ref.py`, CPython only): an independent
implementation of `r_T` on `fractions.Fraction` (exact value, integer rounding, ties to even, subnormals, overflow)
checks every f16 value through every unary op and cast (65,536 inputs), sampled pairs for binary ops (random bit
patterns plus the edge set: `+-0`, smallest/largest subnormal and normal, `1 +- ulp`, powers of two, halfway cases,
`inf`, NaN), every int8 pair for `+ - * // %` (65,536 pairs), and int32 edges. The reduction order is checked against a
second, recursive implementation written from the text of 3.5, not from the first.

### 4.4 Cost of the reference

It is slow: a Python loop per element. Batched `struct` calls help for stores, not for the ops. Tests keep arrays at
or below about 10^5 elements in CPython runs **[unverified cost; T1 measures it]**. Speed of the reference does not
matter beyond CI time; it is never what AIL compiles.

## 5. Lowering in AIL

### 5.1 Recognition and representation

`import ail_array` (or `from ail_array import ...`) is recognised by the front end like `array` is today (an import
pass in the `smalllib5` style), but lowered to a C runtime, not to a Python prelude: a per-element prelude would be as
slow as the reference. The C value is `{uint8_t *p; int64_t n; int64_t rows, cols; int32_t dtype; ...}` with `p`
64-byte aligned, owned and freed like `ail_flist` **[read, not run: exact ownership hooks chosen in T2]**.

- **Typed path**: the dtype is a compile-time fact (2.2), so every op is a direct call or an inlined loop for that
  dtype, with no tag test.
- **General path**: a boxed kind (a GC object with the same struct inside and the dtype as a field) so an array can sit
  in a list, a dict or an object; ops switch on the dtype once per call, not per element.
- Programs that do not import `ail_array` get byte-identical C (the same gate idea as `biggate.py`); the runtime is
  split with `-ffunction-sections` / `--gc-sections` so a program that uses only f64 does not carry f16 code.

### 5.2 Element-wise code

Each op is a plain C loop over the buffer: f64 and f32 use C `double` and `float` arithmetic (correctly rounded on
x86-64 SSE2 and arm64 **[unverified for arm64: no arm64 runner here]**); f16 is converted to f32, computed in f32, and
rounded back (exact by 3.2). With `-ffp-contract=off` and without `-ffast-math` GCC may vectorise these loops but may
not reassociate or fuse, so vectorised and scalar code give the same bits **[GCC's documented flag meaning, unverified
per version; T4 tests both]**. NaN canonicalisation is one compare and one select per vector. The int overflow check
computes in a wider type (int8 in int16, int32 in int64) or by sign tests, ORs a flag per vector, and on a flagged
vector rescans it in scalar code to find the first index and raise.

**f16 conversion**: the default x86-64 target (`-O2`, no `-march`) has no F16C instructions; `x86-64-v3` (opt-in) has
F16C **[unverified: from the psABI level list]**. So the default build converts f16 in software (integer bit
operations: exponent rebias, rounding of the dropped mantissa bits with ties to even, subnormals, overflow to inf),
and the `v3` build may use `vcvtph2ps` / `vcvtps2ph` with round-to-nearest-even. Both must pass the exhaustive f16
tests. GCC's `_Float16` arithmetic is not used (its excess-precision rules vary by flag and version **[unverified]**);
only explicit conversions are.

### 5.2a Fusing a chain (built, branch array-fuse, 2026-10-30)

Code: `Fuser` in `python/pkg-v12/ailarray.py`, `_ail_ta_bsum` and the unrolled `_ail_taf_fsum_s/_d` in `prelude_ailarray.py`;
tests `test_ail_array_fuse.py`, cases `array_fuse_cases/`.

T2 lowered `a * b + a` to one call per operation: a pass over memory and a new array for each. Now a tree of f64 operations is one
generated function with one loop:

| form | generated | notes |
| --- | --- | --- |
| `+ - * /`, unary minus, `abs`, `minimum`, `maximum`, `clip`, with arrays or scalars, 1 to 256 operations | `_ail_taf_fu<N>` (loop in `_ail_taf_fk<N>`) | a single operation too |
| `a += tree`, `a -= tree`, `a *= tree`, `a /= tree` | `_ail_taf_fi<N>` | the loop reads and writes `a`; element k only reads element k, so aliasing is safe |
| `ta.sum(tree)` | `_ail_taf_fs<N>` | the tree is computed one block of 1024 into a scratch array that `_ail_ta_bsum` adds in the order of 3.5 |
| `ta.dot(x, y)`, a tree on either side | `_ail_taf_fd<N>` | the scratch array holds the products, which are rounded before the adds |

Why the bits are T2's: the same binary64 operations in the same order (`-ffp-contract=off`); T2 makes a NaN canonical after every
operation, and every fused operation returns a NaN for a NaN operand, so one canonicalisation at the end gives the same bits (a tree
that ends in `minimum`/`maximum`/`clip` needs none: it returns a NaN only through its explicit canonical NaN); `x / y` is IEEE,
y == 0 goes through the same `_ail_ta_fdiv0` and never raises (TA2); sums and dots do not canonicalise per element for the same
reason, only the result; the shape checks come first, in T2's order and text. A tree with an operand that is a call, a subscript or
anything but a name, constant or attribute chain is not fused as a whole (the operands would be evaluated before a check that used
to come first); only its top operation is. A `ta.dot` whose second operand is such an expression is left to T2. int32 is untouched.
The NaN equivalence is tested exhaustively on `array_fuse_cases/grid.py` (14 special values in all triples, 48 patterns of two
operations, scalar patterns, sums, dots, in-place), with specials planted at lane and block boundaries in `reduce.py`.

Lane indexing: the sixteen lanes are sixteen locals and the loop takes sixteen elements per pass, so there is no `% 16`; the short
tail adds element j of the last group to lane j, which is the lane `(k - s) % 16` gave.

What the IR needs (found by measuring): a function that returns an array is not compiled by the IR (the legacy emitter is 2 to 3
times the instructions), so the loop is a kernel that returns a `list[float]` or nothing; an int parameter of a function that is
not inlined becomes a tagged int and slows every index, so kernels take their length from `len()`; `list` parameters are read-only.

Measured with `tools/icount.c` (instructions per repetition, user space, WSL, `-O2 -ffp-contract=off`), RSS from `/usr/bin/time`.
"C" is hand-written `-O2` with the same order of operations (and, for sums, the lane order of 3.5).

| op | n | T2 before | after | C |
| --- | --- | --- | --- | --- |
| `a*b+a` | 64K | 2.25M | 0.744M | 0.721M |
| | 1M | 35.7M | 11.9M | 11.5M |
| | 10M | 340M | 119M | 110M |
| Horner 4 (8 ops) | 64K | 8.9M | 1.14M | 1.11M |
| Horner 16 (32 ops) | 64K | 35.7M | 2.71M | 2.69M |
| | 10M | 5,440M | 419M | 410M |
| Horner 32 (64 ops) | 1M | 1,141M | 77.0M | 76.5M |
| Horner 64 (128 ops) | 1M | 2,282M | 144M | 144M |
| `a + b` (one op) | 64K | 1.14M | 0.611M | 0.590M |
| `a / b + a` | 64K | 3.45M | 1.09M | 0.721M |
| clip chain | 64K | 7.5M | 1.95M | 0.94M (C ignores -0.0) |
| `abs(a - b) * a` | 64K | 4.15M | 1.07M | 0.786M |
| `w += b * 1e-9` | 64K | 1.66M | 0.673M | 0.655M |
| `ta.sum(a)` | 64K | 640k | 117k | 269k (lane array) / 91k (16 locals) |
| | 1M | 9.9M | 1.50M | 4.3M / - |
| `ta.dot(a, b)` | 64K | 706k | 187k | 302k / 161k |
| `ta.sum(a * b)` | 64K | 1.76M | 0.660M | 0.662M |
| `ta.dot(a, b * a)` | 64K | 1.82M | 0.922M | 0.695M |

Peak RSS: Horner 16 at 1M 297 MB before, 57 MB after; Horner 64 at 1M 1,065 MB before, 57 MB after; at 10M Horner 16 2.8 GB before,
535 MB after (four input arrays and a result are 460 MB of that); Horner 32 at 10M took 5.1 GB before (Horner 64 at 10M would need
about 10 GB and was not run: it does not fit this machine, and that is the finding). C is lower in the RSS column only because
its bench holds fewer arrays.

Binary size of one-function programs (bytes, T2 before / after): `a*b+a` 31,584 / 31,688; `a+b` 31,584 / 31,688; Horner 16 52,200 /
31,568; `ta.sum(a) + ta.dot(a, b)` 40,400 / 68,784 (the unrolled lanes cost about 28 KB: three 16-lane bodies, plain sum, plain
dot and `_ail_ta_bsum`, each compiled twice by the IR for the guarded and the checked loop); a mix of chain, division, abs, in-place,
clip, sum and dot 49,392 / 57,800. A program that only fuses chains gets smaller as the chain grows; one that sums gets bigger.

### 5.3 SIMD is an optimisation that cannot change a bit

SIMD is allowed exactly where the scalar definition is order-free: element-wise ops, min/max, int reductions. For
float sums it is allowed because the definition (3.5) already has 16 lanes; the SIMD code is that definition, not a
re-association of a sequential sum. The vector width is chosen by the build (SSE2 4 x f32 by default, AVX2 8 in
`x86-64-v3`, NEON 4 on arm64), always a divisor of 16, so every width gives the same lanes. No horizontal-add
instruction is used in an order other than the 8-4-2-1 tree of 3.5.

### 5.4 Threads

Element-wise ops and reductions over large arrays may be split across threads once the GIL-free typed parallelism stage
exists (the "Replace Rust" plan): split points are block boundaries and subtrees of 3.5, so the result does not depend
on the thread count. In-place int ops that may raise run on one thread (the "prefix updated" rule of 3.3 is
sequential) or in two passes (check, then write) **[design choice for T8, cost unmeasured]**.

### 5.5 Python loops over elements keep binary64

`for i in range(n): out[i] = a[i] * b[i] + c[i]` with f32 arrays is **Python float code**: `a[i]` is a binary64 value,
the expression is computed in binary64 (two binary64 roundings), and only the store rounds to f32. AIL lowers exactly
that: loads widen, arithmetic is `double`, the store is `r_f32`. Lowering this loop to f32 arithmetic would be a silent
difference (one f32 rounding per op is not the same as binary64 then one rounding). The fast, f32-per-op form is the
array expression `out = a * b + c`. The docs and the refusal hints point to it.

### 5.6 2-D arrays and `matmul` on the CPU (built, branch array-matmul, 2026-10-30)

Code: `_AilTAM` (rows `r`, columns `c`, and `v`, the row-major data as an `_AilTAF`) and the `_ail_tam_*` functions of
`python/pkg-v12/prelude_ailarray.py`; kind `'MF'` in `ailarray.py`; tests `test_ail_array_t6.py`, cases `array_t6_cases/`. A
program that uses no 2-D array gets the same text as before (the prelude is shaken by use). Every element-wise operation of a 2-D
array is the 1-D function on `.v` (so the bits are T2's, in place included) behind a shape check with the reference's text; this
is not fused (5.2a is 1-D). `M.shape` is the tuple `(M.r, M.c)` written inline, so it needs a name (`r, c = m.shape`), and a
tuple used as a value (`print(m.shape)`) is a program the typed path refuses to compile (it runs on the general path, with the
build's note), as any tuple is.

`ta.matmul(A, B)` is one kernel, `_ail_tam_mmk`, that takes the two data lists and three lists that carry `m`, `k`, `n` as their
lengths, and returns the result list. It copies `B` transposed once, tiles `j` in groups of 32 (a tile of the transposed `B` stays in
cache while every row of `A` passes over it), and for each `(i, j)` runs the order of 3.7: per block of 1024 sixteen lanes held in
sixteen locals, 16 products per loop pass, the short tail of a block staged in a 16-element list with `-0.0` in the lanes it does not
reach (adding `-0.0` is the identity, so the tail is exact and the 16 add statements need no branches), the 8-4-2-1 tree, and the
tree over blocks (`_ail_ta_tree`, the one `ta.sum` uses) when `k > 1024`. The tiling and the transposed copy move no element's
order. What the IR needed, found by measuring: lists as parameters and a returned list (a function that returns an object, or takes
a list it writes, is built by the legacy emitter, 20x more instructions in the first try); `m`, `k`, `n` from `len()` (an int read
from a list element or a parameter is a tagged int and every index through it costs a dozen instructions); no name holding a
product of two lengths (`i * k` is written inside the subscript: 25.7 became 15.9 instructions per multiply-add); one name per
loop variable.

Measured with `tools/icount.c` (user-space instructions of the whole process, WSL, `-O2 -ffp-contract=off`, default build, typed path),
the matrix fill and the final sum subtracted by running the same program without the product. "C naive" is a triple loop in C
`-O2` with the order of 3.7 (`lane[(k - s) % 16] += a[i][k] * b[k][j]`, `B` read with stride); "C locals" is the best C we wrote
(`B` transposed, sixteen scalar locals, the loop of the AIL kernel). Instructions per multiply-add:

| m x k x n | multiply-adds | AIL | C naive | C locals | CPython reference |
| --- | --- | --- | --- | --- | --- |
| 128 x 128 x 128 | 2.10M | 15.9 | 11.8 | 3.4 | - |
| 256 x 256 x 256 | 16.8M | 15.1 | 10.9 | 2.8 | - |
| 64 x 2048 x 64 (two blocks) | 8.4M | 14.3 | 10.2 | 2.5 | - |
| 33 x 17 x 29 (tails) | 16K | 37.8 | 23.3 | 10.4 | - |
| 32 x 32 x 32 / 64 x 64 x 64 | 33K / 262K | - | - | - | 2,955 / 2,528 |

All outputs (the sum of every element printed with `repr`) equal in the AIL build and both C programs. So the AIL kernel costs about
1.3x to 1.5x the instructions of the naive C and 4.5x to 5.5x those of the best C, and 165x to 195x fewer than the reference under
CPython. The gap to the best C is the code the IR emits around every list read (a bounds test and, for a sum of indices, an overflow
test: about 5 instructions per operand) and the lane locals it spills; the same cost makes `ta.dot` 23.5 instructions per element
here (`ta.dot` of two 65,536-element arrays, 20 repetitions). Vectorising over `j` (a lane block of one element is independent of the
next element's) is the way to the C locals' number and is not built; it is an optimisation that cannot change a bit (5.3), and
`speed-claims` applies before anyone says it is faster. No speed claim is made here beyond the table.

### 5.7 The GPU kernel for `matmul`: the contract (not built; GPU.md 6.2 to 6.5 and M5/M6)

The device side has to produce the bits of 3.7, so what it may and may not do is fixed here, before the code:

- **One invocation per output element** (or per tile of elements): the invocation for `(i, j)` runs the order of 3.7 along `k` in
  one thread of control: blocks of 1024, sixteen lane accumulators `l0 .. l15` started at `-0.0`, element `u` of a block into lane
  `u % 16`, the 8-4-2-1 tree, the tree over blocks, `+0.0` for `K = 0`, canonical NaN at the store. Tiling over `i` and `j` (shared
  memory, several elements per invocation) is free; splitting `k` over invocations or sub-group lanes is not (it would add a
  reduction in another order). 16 lanes per element are 16 registers of one invocation, not 16 invocations.
- **No fused multiply-add**: every product is a `NoContraction` `OpFMul` whose result is added by a separate `OpFAdd` (also
  `NoContraction`); the emitter of GPU.md G2 must decorate it, and G3's self-test has to show that the
  device honours it (a device that fuses `a * b + c` fails the matmul-specific operand set below and is kept on the CPU).
- **The short tail** of a block adds nothing to the lanes it does not reach (equivalently `-0.0`, 3.7); the kernel must not add
  `+0.0`.
- **64-bit integer index arithmetic** avoids `OpSRem`/`OpSMod` on NVIDIA driver 580 (`a - (a / d) * d` instead); the matmul kernel
  needs only `i * K + k` style products and one division by the constant 16 (a shift), so it should not need either.
- **G3 self-test operand sets for matmul** (run once per device, before the first launch; a mismatch with the CPU emulation keeps the
  device off): (1) `K = 17`, `1025` with `a_k * b_k` chosen so that only the lane order gives the CPU's bits (alternating `1e16`,
  `1`, `-1e16`); (2) products that overflow to `inf` and cancel to NaN (`inf - inf` in one lane); (3) `-0.0` products only (the
  identity lanes); (4) subnormal products (flush-to-zero devices fail); (5) a product pair that differs in the last bit when
  fused. Every set is compared with `_ail_tam_mmk` on the CPU by the 3.7 order.
- **Cost model entry (G4/G7)**: operations `2 * K` per output element (one multiply, one add), `M * N` elements; transfer bytes
  `8 * (M * K + K * N)` in and `8 * M * N` out, counted whether or not the data is already resident. `auto` launches when
  `2 * M * N * K` flops divided by the measured device rate plus the transfer time beats the measured CPU time of the kernel above;
  `--gpu` must never make a program slower, so a shape under the break-even stays on the CPU and a device that fails the
  self-test is never used. Constants come from measurements on the laptop iGPU, lavapipe and Colab (G7), not from this note.
- **Fallback**: no loader, no device, `AIL_GPU=0`, a failed self-test or a failed launch all run the CPU kernel; the result is the
  same bits by construction.

## 6. Aliasing, layout and the FFI boundary

### 6.1 Sharing semantics

- An array is a mutable object with Python's sharing: `b = a` names the same array, and passing it to a function
  passes the object (the language's sharing rule, owner decision 2026-10-15).
- Every constructor, slice, `copy`, `astype`, `reshape`, `transpose` and `tolist` **copies**. There are no views, so
  two different arrays never share memory and an element-wise op never meets a partial overlap. `a += a` and `a * a`
  are exact overlap, which element-wise code handles (each element is read before it is written).
- `ta.array(xs, T)` copies the list; later changes to `xs` do not reach the array, as with `array.array`.

### 6.2 Layout

Contiguous, little-endian, C order (row-major for 2-D), element size 8/4/2/1/4 bytes, the buffer 64-byte aligned in
AIL (the reference's bytearray has CPython's alignment, which only matters to C callees, section 6.3). Fixed length:
the data pointer of an array never moves while the array lives. Big-endian targets are not supported (there are none
today).

### 6.3 Passing buffers to C and BLAS

- `ail_ffi`'s `ptr(T)` / `cptr(T)` annotations accept an `ail_array.Array` whose dtype matches `T`: `c_double` for f64,
  `c_float` for f32, `c_int8` for int8, `c_int32` for int32, and `c_uint16` for f16 (ctypes has no half type
  **[unverified]**, and C has no portable one). The C side gets `a.p` with no copy; `length("a", T)` passes the element
  count. A mismatched dtype is a compile-time refusal when the dtype is static and the shim's `TypeError` otherwise.
- Under CPython the shim passes `(ctypes.c_char * nbytes).from_buffer(a._buf)` (zero copy there too), so a C function
  that writes into the array gives the same bytes in both worlds. Values C writes (NaN payloads, signalling NaNs) are
  stored as they are (3.1).
- The pointer is **borrowed for the call** (as for bytearrays today, SEMANTICS.md section 50): a C library that keeps
  it after returning is outside the contract. The fixed length means it cannot dangle during the call.
- **BLAS** (`cblas_sgemm`, `cblas_dgemm`) is reached through `@extern` like any library. Its result is defined by the
  library, not by this module, so a BLAS call is outside the CPython-vs-reference comparison; its tests compare with the
  same library called from CPython through ctypes (GPU.md 8.1). AIL never replaces `ta.matmul` with a BLAS call unless
  the inexact mode asks for it (section 7).
- The GPU (G1..G6, M2, M4) reads and writes the same buffers: an array is the "contiguous typed buffer" GPU.md 1.1
  needs, and its dtype tells the kernel emitter which rounding to apply.

## 7. Inexact mode (D2)

Exact is the default. Some fast forms cannot be exact: a BLAS `sgemm`, a matmul whose `k` is split, FMA contraction,
vector libm, f16 accumulation in f16 hardware units, GPU cooperative matrix on f32. D2 allows them only with **both**:

1. the compile flag `--inexact-arrays` (env `AIL_INEXACT_ARRAYS=1`), and
2. a marker at the use: the keyword `order='any'` on the call (`ta.matmul(A, B, order='any')`, `ta.sum(a,
   order='any')`, `ta.dot(...)`), or a module comment `# ail: inexact-arrays` that applies it to every module call in
   that file. The reference accepts `order='any'` and computes the exact result (CPython has no other).

The compiler prints a note naming each place it used an inexact form (`prog.py:41: note: ta.matmul uses BLAS sgemm
(order='any'; result may differ from the reference in the last bits)`). With the marker but without the flag, the
call stays exact and the compiler notes `order='any' ignored: build without --inexact-arrays is exact`: no output
differs, so this is a note, not a refusal. Tests of the inexact forms run in a separate suite and compare with the
exact reference within a stated bound per op (for a sum: `|got - exact| <= gamma_n * sum|x_i|` with
`gamma_n = n*u/(1-n*u)`, `u` the unit roundoff of `A`; for matmul the same per output element with `K`), never with
bit equality, and never as part of the zero-silent-difference suite.

## 8. Refused by name

Each is a compile-time refusal with file:line and a `write instead:` hint, and each has a test. Where CPython would
raise at run time with the reference (a wrong dtype mix, a shape mismatch), AIL raises the same error at run time
instead of refusing, because the program may catch it.

| construct | message (shape) |
| --- | --- |
| a dtype outside D1 (`ta.bf16`, `ta.uint8`, `ta.int16`, `ta.int64`, `ta.bool_`) | `ail_array has f64, f32, f16, int8, int32; write instead: ta.int32 (or a list)` |
| `append`, `extend`, `insert`, `pop`, `remove`, `resize` | `ail_array arrays have a fixed length; write instead: ta.zeros(n) and index, or a list` |
| views: `memoryview(a)`, the buffer protocol, `struct.pack_into(..., a, ...)` | `ail_array exposes bytes through a.tobytes() / ta.frombytes(); write instead: ...` |
| element-wise comparisons `a < b`, boolean masks, fancy indexing `a[[0, 2]]`, `a[mask]` | `not built in ail_array; write instead: a loop, or ta.minimum/ta.maximum/ta.clip` (a later stage if needed) |
| `**`, float `//` and `%`, bitwise `&`, `\|`, `^`, `<<`, `>>` on arrays | `not built; write instead: a loop over a.tolist()` |
| 3-D and higher shapes | `ail_array has 1-D and 2-D arrays; write instead: a 2-D array with a computed row index` |
| a 1-D array where `ta.matmul` needs 2-D, or a broadcast other than `(r, c) op (c,)` | raises the reference's `ValueError` at run time (not a refusal) |
| an array passed to `ptr(c_double)` with a static f32 dtype | `f32 array passed as c_double *; write instead: cptr(c_float) or a.astype(ta.f64)` |
| `order='any'` on a function that has no inexact form | `ta.min has no inexact form; drop order='any'` |
| a typed-only build (`AIL_NO_GENERAL=1`) with an array whose dtype is not static | `dtype of 'a' is not known at compile time; write instead: ta.array(xs, ta.f32) with a literal dtype` |
| `import numpy` | unchanged (numpy is not built; GPU.md 1.2) |

## 9. Testing

1. **Reference self-test** (T1, CPython only, section 4.3). Runs in one ordinary shard, no compiler.
2. **Differential**: each test program uses the module on dozens of inputs (many cases per binary: gcc time per build
   dominates, as in the other modules) and is run by CPython 3.12 with `ail_array.py` beside it and by AIL in the
   default build, the general (forced) build and the IR build; stdout and exit code must be equal. Outputs print
   `a.tobytes().hex()` as well as `repr`, so every bit is compared, NaN payloads included.
3. **Edge sets**: per dtype `+-0`, subnormal limits, `1 +- ulp`, halfway cases, the largest finite and the first
   overflow, `inf`, NaN, int min/max and `min // -1`; and per reduction `n` = 0, 1, 15, 16, 17, 1023, 1024, 1025, 2049
   (lane and block boundaries).
4. **Exhaustive f16** in the native build: one C test binary converts and operates on all 65,536 f16 values (unary ops,
   casts both ways) and a fixed set of 2^20 pairs, compared with tables the reference writes once per test run.
   Run in both the default build and `x86-64-v3` (software conversion vs F16C).
5. **Property tests** (seeded, deterministic): `a + b == b + a` bit for bit, `x * 1 == x`, `astype` round trips that
   must be exact (f16 -> f32 -> f16), `ta.sum` equal to the second reduction implementation, int wrap/saturate
   identities, `frombytes(a.tobytes()) == a` on bits.
6. **SIMD neutrality**: the same programs built with SIMD off (`-fno-tree-vectorize`) and on, and with
   `x86-64-v3`; outputs must be equal byte for byte. This is the `optimization-adoption` rule: output identity proven
   against the reference on long inputs, not per op.
7. **Errors**: every raise (overflow at index k, zero division, dtype and shape mismatch, NaN cast) with its text and
   index, and the in-place "prefix updated" state after a caught error.
8. **Refusals**: one case per row of section 8; the same program without the refused line builds and matches.
9. **No cost**: programs without the import keep byte-identical C.
10. **FFI** (T5): a C source that writes and reads each dtype through `ptr`/`cptr`; CPython with the ctypes shim and
    AIL must print the same bytes.
11. **Inexact suite** (T7): separate module, tolerance comparisons only.
12. **CI time**: the reference run is the slow part. Budget: under 2 minutes of runner time added in total, spread over
    the shards by `tools/ci_shards.py`, arrays of at most about 10^5 elements in CPython runs, the exhaustive f16 work
    in C **[unverified budget; T2 and T3 measure]**.

## 10. Stages

Each stage is one PR, tested as in section 9, and leaves programs without the import byte-identical. Core compiler
stages run as one sequential line (the "split core fixes" rule).

| stage | content | done means | depends on |
| --- | --- | --- | --- |
| **T0** | this note | merged into `integ` | - |
| **T1** | `ail_array.py` reference, all five dtypes, 1-D API of section 2 except FFI and matmul; `test_ail_array_ref.py` | the self-test of 4.3 passes on CPython 3.12 within its CI budget; follows decisions TA1-TA3 | T0 |
| **T2** | compiler: import pass, C runtime for **f64 and int32** 1-D, typed and general path, scalar loops (no SIMD work), errors, refusals of section 8 | differential tests of 9.2-9.3 and 9.7-9.9 pass in all build modes; size delta of a program using f64 arrays recorded | T1; IR core / typed path as today |
| **T3** | **f32, f16, int8**, `astype`, canonical NaN, software f16 conversion, wrapping/saturating ops, `exp log tanh sqrt` | exhaustive f16 tests (9.4) and the edge sets pass; the `array('f')` refusal is lifted using the same f32 store rule (TA8) | T2 |
| **T4** | SIMD: vectorisable loops, int overflow flags with rescan, the 16-lane reductions, F16C in `x86-64-v3` | 9.6 neutrality passes; instruction counts (`tools/icount.c`) and RSS recorded per op family against the scalar T3 code and against C; no speed claim before that (`speed-claims`) | T3 |
| **T5** | FFI: arrays as `ptr`/`cptr` arguments, zero copy in AIL and in the shim | 9.10 passes; borrowed-pointer rule documented in AIL_REFERENCE_MORE | T2; FFI F4 (#209: same files `ail_ffi.py`, `ail_ffi_lower.py`) merged first; F3 if u64 lengths are used |
| **T6** | 2-D arrays (built for f64: 3.8) and exact `matmul` (3.7, built for f64, CPU: 5.6); the row broadcast, f32/f16/int matmul and the GPU kernel (GPU.md 6.2 to 6.5) are later | CPython-equal on 3.7's cases incl. `K = 0`, lane and block boundaries and planted specials; an MLP forward pass example matches the reference | T4 |
| **T7** | inexact mode (D2): flag, `order='any'`, notes, BLAS `sgemm`/`dgemm` via `@extern`, tolerance suite | notes printed at every use; tolerance tests pass; BLAS results equal the same BLAS through ctypes; this is the array half of GPU.md M1 | T5, T6 |
| **T8** (optional) | threads over blocks (5.4) | outputs equal for 1..N threads; measured | T4; GIL-free typed parallelism |
| GPU | M2 (fused element-wise chains over arrays), M4 (array kernels), M5/M6 (matmul) | as GPU.md 8.6 | T3/T6 here, and G1-G6 for the device side (G2 SPIR-V ops, G3 runtime, G4 error replay for int overflow, G5 correctly rounded `/` and `sqrt`: f32 `/` on a GPU is not correctly rounded **[unverified per driver]**, G6 reductions with the order of 3.5) |

## 11. Risks

- **The reference is slow**, so CI can only use small arrays; bugs that need large `n` (block trees with many levels)
  are tested through the second reduction implementation in C-sized runs, not through CPython.
- **Different digits from numpy and PyTorch.** The fixed sum order and the raise-on-overflow rule are the module's
  own; users comparing with numpy will see last-bit differences in sums and errors where numpy wraps. This is by
  design, but it will be reported as a bug.
- **Default x86-64 has no F16C**: f16 in the default build is software conversion on every load and store, likely
  slow **[unmeasured]**; the fast f16 path needs the `x86-64-v3` opt-in build.
- **Canonical NaN and overflow checks cost** a compare and select per vector; small, but unmeasured (T4).
- **Exact matmul without FMA** reaches only a part of a tuned BLAS's speed on FMA hardware **[unmeasured]**; the fast
  BLAS path is the inexact mode, which most ML users may end up using.
- **The double-rounding argument** rests on a theorem and a 60k-pair sample here; T1 must make the f16 part exhaustive
  and keep a large f32 sample.
- **libm functions differ by platform** (`exp` on glibc vs macOS): both CPython and AIL follow the platform, so tests
  on one platform cannot catch a cross-platform difference; that is the same position plain `math.exp` is in today.
- **Scope creep toward numpy.** Each request for masks, views, N-D or broadcasting widens the lowering and the aliasing
  proofs; the stages hold the line at section 2.
- **Two names for "sum"** (`sum(a)` vs `ta.sum(a)`) with different digits may confuse users; only the docs help.

## 12. Owner decisions (2026-10-30)

The owner accepted every recommendation of the first draft on 2026-10-30. There are no open questions left in this
note; the decisions were questions Q1..Q8 of that draft.

- **TA1 (was Q1). Integer overflow raises.** int8/int32 `+ - *` (and unary `-`, `abs`) raise `OverflowError` by
  default; wrap and saturate only through the named functions `ta.wrapping_*` / `ta.saturating_*` (section 3.3).
- **TA2 (was Q2). IEEE for float arrays.** `1/0` gives `inf`, `sqrt(-1)` and `log(-1)` give NaN, overflow gives `inf`;
  float arrays never raise for these (section 3.1).
- **TA3 (was Q3). The fixed sum order.** `ta.sum` and `ta.dot` use the 16-lane, 1024-block order of section 3.5; the
  builtin `sum(a)` keeps CPython's meaning.
- **TA4 (was Q4). `dot` and `matmul` stay separate functions**, and (owner, 2026-10-30) **one order for both**: the 16-lane,
  1024-block order of 3.5 along `k`, so `matmul` of a row and a column equals `ta.dot` and every device can reproduce it
  (section 3.7). The first draft said sequential `k` for `matmul`; that is withdrawn. A fast device-dependent matmul is the
  explicit opt-in of D2 only (not built).
- **TA5 (was Q5). 1-D and 2-D first**; N-D is not planned now.
- **TA6 (was Q6). A numpy subset may come later**, as separate work; this module is not it.
- **TA7 (was Q7). The name is `ail_array`**, a file beside the program for CPython, later in the `ail-lang` package.
- **TA8 (was Q8). T3 lifts the `array('f')` refusal** with the same f32 store rule (storage only; arithmetic stays
  Python floats).
