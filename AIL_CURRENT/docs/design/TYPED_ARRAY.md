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
  wanted; this module is deliberately smaller and does not answer that question (open question Q6 here).
- dtypes beyond D1: `bf16`, `uint8`, `int16`, `int64`, `bool`, complex. Refused by name (section 8).
- Shapes with more than two dimensions (open question Q5).
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
each one multiplies the lowering cases and the aliasing proofs (section 6) and no first target needs it (Q5).

## 3. Exact semantics

### 3.1 Float dtypes: f64, f32, f16

| question | rule |
| --- | --- |
| rounding | every element-wise op `x op y` gives `r_T(exact(x op y))` for `+ - * /` and `sqrt`: correctly rounded in `T`, ties to even. Nothing is fused: `a * b + c` is two ops, two roundings. f64 is IEEE binary64, f32 binary32 (24 bits), f16 IEEE binary16 (11 bits, exponent -14..15) |
| overflow | to `+inf` / `-inf` (IEEE). **Float dtypes never raise for overflow**, in arithmetic, casts or stores. `array('f', [1e300])` stores `inf` on CPython 3.12 too **[verified]**; `struct.pack('f', 1e300)` raises `OverflowError` instead **[verified]**, so the reference catches it (section 4.2) |
| division by zero | IEEE: `1/0 -> inf`, `-1/0 -> -inf`, `0/0 -> NaN`. This differs from Python's `float /` (which raises); it is the module's rule because SIMD and GPU code cannot raise per lane, and ML code expects it (open question Q2) |
| NaN | every NaN **produced** by an op, a cast, or a store of a Python float NaN is the **canonical quiet NaN with the sign bit clear**: f64 `0x7ff8000000000000`, f32 `0x7fc00000`, f16 `0x7e00`. Reason: x86 produces a NaN with the sign set for `inf - inf` (`fff8000000000000` on CPython here **[verified]**; `math.copysign(1, inf - inf)` is `-1.0`), arm64 produces it with the sign clear **[unverified]**, and a GPU may produce yet another; canonicalising makes the bits device-independent. Bits that arrive through `frombytes` or a C call are stored unchanged until an op touches them |
| NaN to Python | `a[i]` of a stored NaN gives the Python float the C conversion `(double)` gives. Under CPython the reference uses `struct.unpack('<f')`, which is that C cast; a signalling f32 NaN `7f800001` came back as `7ff8000020000000` (quieted, payload shifted) **[verified on x86-64]**; arm64 also quiets **[unverified]**. AIL does the same cast, so both agree on one machine |
| -0.0 | kept as IEEE: `-0.0 + -0.0 = -0.0`, `0.0 + -0.0 = 0.0`, `-(0.0) = -0.0`, `abs(-0.0) = 0.0`; `r_f16(-0.0)` is `0x8000` **[verified]** |
| subnormals | kept (gradual underflow) in all three dtypes, in arithmetic and conversion. f16: smallest `2^-24`, largest subnormal `2^-14 - 2^-24`; `2^-25` rounds to `0.0` (tie to even), anything above it to `2^-24` **[verified with `struct 'e'`]**. No flush-to-zero anywhere: the runtime never sets FTZ/DAZ, and a C callee that does is "trusted C" as in SEMANTICS.md section 48 |
| `sqrt` | correctly rounded. Negative input gives NaN (canonical), not `ValueError` (Q2) |
| `exp log tanh` | defined as `r_T(math.<f>(float(x)))`: CPython's libm result in binary64, rounded once to `T`. On one platform CPython and AIL call the same libm, so the bits agree; across platforms both follow that platform's libm, as plain `math.exp` already does. `log` of a negative is NaN, of zero `-inf` (IEEE, not `ValueError`). No vector libm (it gives other bits) except in the inexact mode (section 7) |
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
  `OverflowError: cannot convert float infinity to integer` **[texts verified]**, out of range raises `OverflowError`)
  or `'saturate'` (clamp; NaN becomes 0).
- **`astype` int to int**: `overflow='raise'` (default), `'saturate'` or `'wrap'`.
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

- `ta.dot(a, b)` is bit-for-bit `ta.sum(a * b)` with the products rounded to `A` (`r_A(a_i * b_i)` after widening to
  `A`); the fused native loop keeps no temporary array.
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
| f64 x f64, f32 x f32 | same dtype | `C[i,j]`: sequential `k` from 0, `acc = r(acc + r(A[i,k] * B[k,j]))`, `acc` starting at `-0.0`; `K = 0` gives `+0.0`. The natural CPU order (vectorise over `j`) and GPU.md's "tile over i, j, never split k" |
| f16 x f16 | f32 (default `acc`) | the exact sum of the exact products, rounded once to f32 (GPU.md 8.7). f16 products are exact in f32, and every product is an integer multiple of `2^-48`, so the reference adds Python ints and rounds once with integer code (section 4.2) |
| int8 x int8 | int32 | exact integer sum; `OverflowError` if a result leaves int32; order-free (so GPU cooperative matrix may be used under GPU.md 8.7's precondition) |
| int32 x int32 | int32 | exact, checked, order-free |

`ta.dot(row, col)` (blocked order) and a `1 x K` by `K x 1` `matmul` (sequential) are therefore different functions
for floats (open question Q4).

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
| **T1** | `ail_array.py` reference, all five dtypes, 1-D API of section 2 except FFI and matmul; `test_ail_array_ref.py` | the self-test of 4.3 passes on CPython 3.12 within its CI budget; the owner has answered Q1-Q3 (they change the reference) | T0 |
| **T2** | compiler: import pass, C runtime for **f64 and int32** 1-D, typed and general path, scalar loops (no SIMD work), errors, refusals of section 8 | differential tests of 9.2-9.3 and 9.7-9.9 pass in all build modes; size delta of a program using f64 arrays recorded | T1; IR core / typed path as today |
| **T3** | **f32, f16, int8**, `astype`, canonical NaN, software f16 conversion, wrapping/saturating ops, `exp log tanh sqrt` | exhaustive f16 tests (9.4) and the edge sets pass; optional: lift the `array('f')` refusal using the same f32 store rule (Q8) | T2 |
| **T4** | SIMD: vectorisable loops, int overflow flags with rescan, the 16-lane reductions, F16C in `x86-64-v3` | 9.6 neutrality passes; instruction counts (`tools/icount.c`) and RSS recorded per op family against the scalar T3 code and against C; no speed claim before that (`speed-claims`) | T3 |
| **T5** | FFI: arrays as `ptr`/`cptr` arguments, zero copy in AIL and in the shim | 9.10 passes; borrowed-pointer rule documented in AIL_REFERENCE_MORE | T2; FFI F4 (#209: same files `ail_ffi.py`, `ail_ffi_lower.py`) merged first; F3 if u64 lengths are used |
| **T6** | 2-D arrays, row broadcast, exact `matmul` (3.7) | CPython-equal on 3.7's cases incl. `K = 0`, int32 overflow, f16 exact sums; one MLP forward pass example matches the reference | T4 |
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

## 12. Open questions for the owner

- **Q1. Integer overflow.** int8/int32 `+ - *` raise `OverflowError` by default; wrap and saturate only through named
  functions (`ta.wrapping_add`, `ta.saturating_add`). numpy and C wrap silently. Is raising the right default?
- **Q2. Float errors.** Float arrays follow IEEE: `1/0` gives `inf`, `sqrt(-1)` and `log(-1)` give NaN, overflow gives
  `inf`, nothing raises. Plain Python floats raise in these cases. Is IEEE right for the module?
- **Q3. Sum order.** `ta.sum` and `ta.dot` use one fixed blocked order (16 lanes, blocks of 1024) so SIMD, threads and
  GPUs give the same bits. It is not Python's sequential order and not numpy's. Acceptable?
- **Q4. dot vs matmul.** `matmul` uses sequential `k` (GPU.md 8.7), `dot` uses the blocked order, so a `1 x K` matmul
  and a dot of the same numbers can differ in the last bit. Keep two orders, or make matmul blocked along `k` too?
- **Q5. Shapes.** 1-D, plus 2-D for matmul. Is that enough, or should general N-D arrays be planned now?
- **Q6. numpy.** This module is not numpy-compatible (no views, no mixed-dtype promotion, no masks). Is a separate
  numpy subset still wanted later (GPU.md Q5), or does this module replace that plan?
- **Q7. Name and delivery.** The module is `ail_array`, a file copied beside the program for CPython (as `ail_ffi.py`
  and `ail_cbuf.py` are today), later shipped in the `ail-lang` package at release. Is the name right?
- **Q8. `array('f')`.** The same f32 store rule can lift today's refusal of `array.array('f')` (storage only;
  arithmetic stays Python floats). Include it in T3?
