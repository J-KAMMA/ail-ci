# `xdrlib` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/xdrlib/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). Stdout and the exit status are compared;
stderr is not, because CPython 3.12 prints a `DeprecationWarning` for `import xdrlib`. The
programs take no arguments and use fixed values.

## Before

AIL had no model or bundled file for `xdrlib`, so every program was refused. First refusal line:

| program | default build | first refusal |
| --- | --- | --- |
| `01_uint_int_enum.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `02_bool_hyper.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `03_uhyper_max.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `04_float_double.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `05_strings_opaque.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `06_arrays.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `07_positions.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `08_done_eof.py` | refused | `not in the subset: xdrlib.Unpacker (not yet published in NAMES_library.json)` |
| `09_conversion_errors.py` | refused | `not in the subset: xdrlib.Packer (not yet published in NAMES_library.json)` |
| `10_record.py` | refused | `not in the subset: the method .pack_int() (on a value of unknown static kind)` |

Result before: **0 built, 0 typed, 10 refused**. The stdlib census recorded the same import
refusal for CPython's own `xdrlib.py` (`xdrlib.py:187:13: int64 literal out of range:
18446744073709551616`).

## After

`AIL_CURRENT/stdlib/xdrlib.py` is CPython 3.12's `Lib/xdrlib.py` as AIL source. Nine programs
build and match CPython in the default build and with `AIL_UNIFIED_FORCE=1`. Every one uses the
general path (the bundled `Error` is a user exception class, which the typed path does not build).

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_uint_int_enum.py` | general | general | yes |
| `02_bool_hyper.py` | general | general | yes |
| `03_uhyper_max.py` | general | general | no (loud stop beyond int64, see below) |
| `04_float_double.py` | general | general | yes |
| `05_strings_opaque.py` | general | general | yes |
| `06_arrays.py` | general | general | yes |
| `07_positions.py` | general | general | yes |
| `08_done_eof.py` | general | general | yes |
| `09_conversion_errors.py` | general | general | yes |
| `10_record.py` | general | general | yes |

Result after: **10 built, 0 typed, 0 refused; 9 build and match**. `03_uhyper_max.py` builds but
stops loudly at `unpack_uhyper()` of eight `ff` bytes, whose CPython value is `18446744073709551615`
(2**64 - 1, beyond int64):

```
OverflowError: integer overflow in << (ints are 64-bit; --exact-int gives exact ints)
```

Before that call it prints exactly what CPython prints, `7fffffffffffffff` for
`pack_uhyper(2**63 - 1)` and `9223372036854775807` for unpacking it. `pack_uhyper` of any int64
value is exact; only the unsigned value above int64 stops, and it stops loudly rather than wrapping.

## Module notes

* `io.BytesIO` is not built. A `Packer` keeps a list of `bytes` chunks and `get_buffer()` returns
  `b"".join(chunks)`, so `get_buffer()` still returns `bytes` with the same contents.
* `struct` is not built. Ints use `int.to_bytes`/`int.from_bytes`. Floats are encoded and decoded
  from IEEE-754 sign/exponent/fraction fields; the arithmetic uses only exactly representable
  powers of two, and single precision rounds to nearest with ties to even. `04_float_double.py`
  covers `pack_float(0.1)` (`0x3dcccccd`), doubles such as `1e300`, and `unpack_float`/
  `unpack_double`. A follow-up could build `struct` instead; the results are already exact for
  these cases, and a compiler change is not needed for the ten programs.
* Only `@staticmethod` and `@lru_cache` decorators are built, so the `@raise_conversion_error`
  decorator is inlined: each packing method checks its range and raises `ConversionError` with
  CPython's `struct.pack` text (`"'L' format requires 0 <= number <= 4294967295"`, ...).
* `0x10000000000000000` (2**64) is beyond int64. `unpack_hyper` tests the sign bit of the high
  word and computes the two's-complement magnitude, `-magnitude - 1`, which stays inside int64 and
  still yields `-9223372036854775808` for `0x8000000000000000`.
* Class-body aliases (`pack_enum = pack_int`, `get_buf = get_buffer`, ...) are refused by the
  compiler (`name 'get_buffer' is not defined`), so each alias is a one-line method that calls the
  canonical one. Same names, same signatures, same behaviour.

## Test notes

`python3 AIL_CURRENT/test_ail_std_xdrlib.py` passes (3 tests: 9 programs compared in both builds,
the beyond-int64 program checked for a loud stop, and the program inventory).  Probe programs in
`/tmp/probes/` (`xd_float`, `xd_int`, `xd_bytes`, `xd_values`, `xd_pow2`) match CPython in both
builds; they cover int widths and their error texts, hyper sign boundaries, zeros and signed
zeros, subnormals, infinities, nan, single-precision round-half-even ties, overflowing floats,
empty strings and arrays, and values reaching the packer through an argument, a list item, an
attribute and a dict value.

`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` are the required tests.
`test_ail_files` and `test_ail_corpus_findings3` pass.  `test_ail_safetynet` fails
`S4_generators_gc` (only the first line of its output is produced) in this runner; the same test
fails identically at the base commit `68eb00a`, without these changes, so it is a pre-existing
environmental failure, not an `xdrlib` regression.

## Follow-ups (out of scope: compiler files)

* Passing a bound method as a value is refused at run time by the merged/general path, in any
  class: `class P: def add(self, v): ...` then `f = p.add` raises
  `AttributeError: 'P' object has no attribute 'add'`. `06_arrays.py` and `09_conversion_errors.py`
  therefore pass `lambda v: p.pack_uint(v)` to `pack_list`/`pack_farray`, which still exercises the
  `pack_item` callback. A direct call `p.pack_uint(1)` works.
