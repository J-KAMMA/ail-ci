# `struct` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/struct/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). Every program prints fixed values and
takes no command-line arguments. The bundled module is `AIL_CURRENT/stdlib/struct.py`.

## Before

`AIL_CURRENT/stdlib/struct.py` did not exist, so `import struct` reached CPython's C module
through the general path and every attribute use was refused. First refusal line of each program:

| program | first refusal |
| --- | --- |
| `01_byte_orders.py` | `class.pack (not yet published in NAMES_library.json)` |
| `02_repeat_and_counts.py` | `class.calcsize (not yet published in NAMES_library.json)` |
| `03_int_codes.py` | `class.calcsize (not yet published in NAMES_library.json)` |
| `04_long_codes.py` | `class.calcsize (not yet published in NAMES_library.json)` |
| `05_bool_char_bytes.py` | `class.pack (not yet published in NAMES_library.json)` |
| `06_roundtrip_mixed.py` | `class.calcsize (not yet published in NAMES_library.json)` |
| `07_calcsize.py` | `class.calcsize (not yet published in NAMES_library.json)` |
| `08_pack_into_unpack_from.py` | `class.pack_into (not yet published in NAMES_library.json)` |
| `09_iter_unpack.py` | `class.pack (not yet published in NAMES_library.json)` |
| `10_struct_class.py` | `class.Struct (not yet published in NAMES_library.json)` |
| `11_int64_edges.py` | `class.pack (not yet published in NAMES_library.json)` |
| `12_errors_range.py` | `a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `13_errors_buffer_args.py` | `a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `14_floats.py` | `class.calcsize (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 typed, 14 refused**.

## After

Twelve programs build and match CPython's stdout and exit status in the default build and with
`AIL_UNIFIED_FORCE=1`. Every one uses the general path: the bundled module raises its own
`struct.error`, which the typed path does not model. `11_int64_edges.py` stops loudly on the
`Q` value `2**64 - 1` because AIL ints are int64; `14_floats.py` stops with the module's
`NotImplementedError` because the float codes are not built.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_byte_orders.py` | general | general | yes |
| `02_repeat_and_counts.py` | general | general | yes |
| `03_int_codes.py` | general | general | yes |
| `04_long_codes.py` | general | general | yes |
| `05_bool_char_bytes.py` | general | general | yes |
| `06_roundtrip_mixed.py` | general | general | yes |
| `07_calcsize.py` | general | general | yes |
| `08_pack_into_unpack_from.py` | general | general | yes |
| `09_iter_unpack.py` | general | general | yes |
| `10_struct_class.py` | general | general | yes |
| `11_int64_edges.py` | general | general | no: loud stop at `Q = 2**64 - 1` |
| `12_errors_range.py` | general | general | yes |
| `13_errors_buffer_args.py` | general | general | yes |
| `14_floats.py` | general | general | no: `NotImplementedError: struct: float formats are not built yet` |

Result after: **14 built, 0 typed, 0 refused; 12 build and match**. The target was at least 11.

`11_int64_edges.py` prints its first eight lines exactly as CPython, then
`OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)` while
unpacking `>Q` of `b"\xff" * 8`; CPython prints `18446744073709551615`. A `Q`/`N` value above
int64 cannot be represented, so a loud stop is the honest result (Appendix A rule 1).

## Notes

- Byte order for the native prefix (`@`, and `=`) is little-endian, the x86-64 Linux host. There
  is no compiler operation that reads `sys.byteorder` (the typed path refuses it as a plain value),
  so the module states the assumption in `_parse`.
- Packing/unpacking a float raises `NotImplementedError`; exact IEEE-754 `e`/`f`/`d` conversion
  is not in the module, as the task allows.
- `iter_unpack` validates the buffer at call time (as CPython does), then returns a generator.
- `n`/`N` are accepted only with the native prefix, matching CPython (`"=n"` is a bad char).
- The module was also run under CPython with `sys.path` pointing at `AIL_CURRENT/stdlib`: its
  output equals the real `struct` for programs 01-13; 14 differs only because of the planned
  floats refusal.
