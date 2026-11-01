# int64 constants in the default build (2026-11-01)

A Python-syntax program in the default mode has signed 64-bit ints (`docs/design/BIGINT.md`, section 15). A value that needs
a big int statically is refused by name with the line and the `--exact-int` hint; `compile --exact-int` / `AIL_EXACT_INT=1`
is the exact (arbitrary precision) mode. This note records the int64 constants behind the refusal for all 34 modules of
the compiler census at `pyfront.fold_int_constants` and classifies each use. It is the reference for the rule: **admit a constant only when the
value that reaches the program provably fits int64; never wrap or change the type silently.**

## 1. Where the refusal comes from

The first refusal is usually `a constant integer expression overflows int64` from `pyfront.fold_int_constants`
(`python/pkg-v12/pyfront.py`). It evaluates a purely integer constant expression exactly and refuses when the *result* does
not fit `[-2**63, 2**63 - 1]`. An out-of-int64 intermediate whose final result fits is already folded, not refused:
`(1 << 64) - (1 << 64) + 5`, `(1 << 63) - 1`, `-(1 << 63)`, `0 & ((1 << 64) - 1)` and `255 & ((1 << 64) - 1)` all build.

A literal outside int64 is refused as `the integer literal ... does not fit in a 64-bit signed integer`; a big value in a
module, class or default position can also be named by `ail_chatgpt.py` as `int64 constant expression out of range`.
Every default-mode refusal names the source line and ends with the `--exact-int` hint.

## 2. The safe subset that already builds

These are the only big-constant shapes the default mode admits. They all have an int64 result *before* code generation:

| shape | example | why it is safe |
| --- | --- | --- |
| a mask applied to an int64 constant | `5 & ((1 << 64) - 1)`, `0xFF & (1 << 64) - 1` | the outer expression folds to `5` / `255`, which fits |
| a mask that itself fits int64 | `x & 0x7FFFFFFFFFFFFFFF`, `x & 0xFFFFFFFF` | the result is bounded by a nonnegative int64 mask |
| a big intermediate with an int64 result | `(1 << 64) >> 64`, `(1 << 64) - (1 << 64)`, `-2**63` | the folded result is checked, not the intermediate |
| the int64 boundaries | `-(1 << 63)`, `(1 << 63) - 1` | they denote `INT64_MIN` / `INT64_MAX`, which fit |

These are covered by `test_ail_i64_constants.py` and match CPython on the default and forced-general builds.

## 3. Patterns that stay refused

| pattern | actual constants | why it is not admitted |
| --- | --- | --- |
| all-ones mask on a value | `x & 0xFFFFFFFFFFFFFFFF`, `x & ((1 << 64) - 1)`, `value &= (1 << 64) - 1` | for a negative int64 `x`, CPython's result is above `INT64_MAX`; removing the mask would be a silent wrap, and the signed result is not provable from the source |
| FNV/hash multiplier | `0xcbf29ce484222325` = `14695981039346656037`, the signed spelling `-3750763034362895579` | a stored multiplier is out of int64; the signed spelling only fits when the surrounding arithmetic is a documented wrapping algorithm, which is not a static property of the constant |
| high-bit sentinels | `1 << 63`, `0x8000000000000000`, `-(1 << 64)` | the sentinel value itself is out of int64, and it is stored or used in arithmetic, not only compared |
| decimal thresholds | `10 ** 30`, `10 ** 99` | the threshold is evaluated and compared as a Python int; it is not an int64 value |
| range bounds | `-(1 << 63) <= x < (1 << 63)`, `0 <= x < (1 << 64)` | the comparison result fits, but the bound is out of int64, the operand's type/range is not proven at this stage, and changing the operator or the bound type changes float and user-class comparisons |
| census/test fixtures | `2 ** 63`, `2 ** 64`, `2 ** 70`, `2 ** 100`, `10 ** 400`, `12345678901234567890` | they deliberately exercise the boundary, a refusal, or exact mode; they are not programs that should become int64 |

Consequently, `x & ((1 << 64) - 1)` stays a compile-time refusal even for a call with a positive argument: the compiler
does not prove the argument nonnegative, and a run-time stop would differ from CPython's printed big integer. The exact
mode builds it and prints CPython's value, including for negative inputs.

## 4. Census table

The census compiles each module with the default Python syntax and records the first refusal. The line is in the original
source; `refused` means the module still needs exact mode or a source rewrite for a different reason. No compiler behavior
was changed by this note; the table records the current state.

| module | constants (line) | use | verdict |
| --- | --- | --- | --- |
| `ail_chatgpt.py` | `1 << 63` (92, 870, 2980, 4052, 4511, 4637); `1 << 64` (1942, 1951); `10 ** 99` (4347) | int64 range checks, power routing, diagnostic text | refused; every value is a bound or a display threshold |
| `ail_ffi.py` | `1 << 64` (322, 412, 752) | unsigned handle/pointer range `0 <= value < 2**64` | refused; the value is an arbitrary Python int at that point |
| `ail_ffi_lower.py` | `1 << 63` (602, 1939); `10 ** 30` (609); `1 << 64` (1164) | FFI constant range checks, `ULL`/`LL` suffix choice, message length threshold | refused; the FFI lowering has its own wide-u64 path, but the front end cannot admit the literal in default mode |
| `ail_modules.py` | `1 << 63` (1364) | module constant int64 range check | refused |
| `ail_syntax.py` | `1 << 63` (769); `2 ** 63` (1988) | constant-folder result check, `sys.maxsize` fallback | refused; the folder value itself is checked |
| `benchmark_current_rows.py` | `1 << 63` (105, 111) | running-total range check | refused |
| `bigcap.py` | `1 << 63` (26, 450, 451) | `_I64` sentinel, local-proof bounds | refused; `_I64` is stored and used in arithmetic |
| `enumlib.py` | `1 << 63` (178) | flag value must fit 63 bits | refused |
| `gpu_spirv.py` | `1 << 64` (95); `1 << 63` (37, 313) | i64 word masking, sign-bit constant | refused; the mask and the sign bit are unsigned 64-bit patterns |
| `jsonrt.py` | `2 ** 64` (1039, 1043) | Ryu table generation, low/high word split | refused; the table itself is arbitrary precision |
| `modtables.py` | `1 << 63` (85) | scalar literal range | refused |
| `module_object.py` | `1 << 63` (67) | int constant range | refused |
| `pyboxed.py` | `0x8000000000000000` (1303); `1 << 63` (1330, 1331, 1416, 1420, 1421) | boxed int range and sign checks | refused |
| `pyboxed2.py` | `0x8000000000000000` (5485); `1 << 63` (5666, 5667, 5896) | same boxed-int checks | refused |
| `pyc.py` | `1 << 63` (817, 939, 1252) | literal/constant range checks | refused |
| `pyfront.py` | `1 << 63` (142, 143, 459, 460, 1237, 1268, 1313) | folder bounds and power bases | refused |
| `pyfunc.py` | `1 << 63` (649, 650, 2066, 2068, 7206, 9700, 9708, 9832, 10665, 13023, 13039, 13404, 13502, 13821, 13822, 25916, 35969, 36388); `2 ** 63` (23045) | range checks in the typed emitter | refused |
| `readonly_bytes_scalar.py` | `1 << 63` (49, 53) | constant-expression range | refused |
| `unified.py` | `1 << 63` (57, 2844) | constant range | refused |
| `test_ail_array_ref.py` | `10 ** 30` (311), `10 ** 400` (316) | test data | refused by design |
| `test_ail_bigint.py` | `2 ** 63`/`2 ** 64`/`2 ** 70`/`2 ** 100`/`2 ** 1024` (37-41) | big-int vectors | refused by design |
| `test_ail_ffi_f3a.py` | `1 << 63` (93, 99, 100) | FFI boundary vectors | refused by design |
| `test_ail_files.py` | `2 ** 64` (385) | file-size vector | refused by design |
| `test_ail_freestanding.py` | `1 << 63` (138), `1 << 64` (298) | freestanding vectors | refused by design |
| `test_ail_instruction_gap.py` | `2 ** 63` (751, 758) | instruction-gap vectors | refused by design |
| `test_ail_int64_default.py` | `1 << 63`/`1 << 100`/`2 ** 70` (28, 29, 330, 344) | the int64 boundary matrix | refused by design |
| `test_ail_json_fast.py` | `-2 ** 63 - 1`/`2 ** 63` (293), big decimal strings (294) | JSON number vectors | refused by design |
| `test_ail_numeric_binding_boundaries.py` | `2**63` (34, 37) | binding boundary vectors | refused by design |
| `test_ail_range_checks.py` | `1 << 63` (359) | range-check vector | refused by design |
| `test_ail_stdlib_batch1.py` | `2 ** 63` (423, 436) | stdlib vectors | refused by design |
| `test_ail_stdlib_batch3.py` | `2 ** 63` (110, 131, 133, 728) | stdlib vectors | refused by design |
| `test_ail_stdtop1.py` | `2 ** 63`/`2 ** 64`/`2 ** 65`/`2 ** 70`/`2 ** 100`/`10 ** 19`/big decimal (343, 407, 412, 442) | decimal vectors | refused by design |
| `test_ail_stdtop3.py` | `2 ** 70` (136) | decimal vector | refused by design |
| `test_ail_tint.py` | `2 ** 63`/`2 ** 64` (34-46, 80, 90, 91, 304) | tint vectors | refused by design |

The test modules are listed so the census is complete; they are not candidates for the safe subset. A test that needs a
big value either runs in exact mode or asserts the named refusal.

## 5. Reproducing the census

The first refusal for a module can be produced compile-only, without a C compiler, by the same preparation and typed attempt
used by `lab/census/fallback_census.py`:

```
PYTHONPATH=AIL_CURRENT/python/pkg-v12 python3 lab/census/fallback_census.py --jobs 2 -o /tmp/census.jsonl \
    AIL_CURRENT/ail_ffi.py AIL_CURRENT/python/pkg-v12/bigcap.py
```

`test_ail_i64_constants.py` is the small regression suite for this note: it checks representative hash, mask, sentinel and
threshold refusals with the hint, the safe folded/mask shapes above, and the exact-mode result for the same programs.
