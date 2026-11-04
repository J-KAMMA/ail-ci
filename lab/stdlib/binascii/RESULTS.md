# `binascii` coverage

Twelve realistic programs using the CPython 3.12 `binascii` module, built with the default command
`python3 AIL_CURRENT/ail_chatgpt.py compile X.py -o X.out` and with `AIL_UNIFIED_FORCE=1`.
`typed` means that build used the typed path; `general` means it fell back to the general path (the
build log names the reason); `refused` means the build stopped.

## Before (integ 2adbd4e)

There is no `binascii` module on the base, so all twelve are refused at the import. The first
refusal line (default build) is below; `0/12` built and matched.

| program | result | first refusal |
| --- | --- | --- |
| `01_hex_basic.py` | refused | `not in the subset: import of 'binascii' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: binascii.hexlify (not yet published in NAMES_library.json)` |
| `02_hex_sep.py` | refused | same, `general path: binascii.hexlify (not yet published in NAMES_library.json)` |
| `03_unhex.py` | refused | same, `general path: binascii.unhexlify (not yet published in NAMES_library.json)` |
| `04_hex_errors.py` | refused | same, `general path: a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `05_base64_encode.py` | refused | same, `general path: binascii.b2a_base64 (not yet published in NAMES_library.json)` |
| `06_base64_decode.py` | refused | same, `general path: binascii.a2b_base64 (not yet published in NAMES_library.json)` |
| `07_base64_strict.py` | refused | same, `general path: a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `08_base64_errors.py` | refused | same, `general path: a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `09_crc32.py` | refused | same (no general-path clause: the program also imports `zlib`, which needs the typed path) |
| `10_crc32_values.py` | refused | same, `general path: binascii.crc32 (not yet published in NAMES_library.json)` |
| `11_crc_big.py` | refused | same, `general path: binascii.crc32 (not yet published in NAMES_library.json)` |
| `12_checksum.py` | refused | same, `general path: binascii.crc32 (not yet published in NAMES_library.json)` |

The common prefix, verbatim from `01_hex_basic.py`, is:

```
lab/stdlib/binascii/01_hex_basic.py:1:1: not in the subset: import of 'binascii' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: binascii.hexlify (not yet published in NAMES_library.json)
```

## After (this branch)

`AIL_CURRENT/stdlib/binascii.py` is new AIL code; `import binascii` in a program's own directory
or `AIL_PATH` still wins, and the bundled copy is searched last. Both builds were run on the same
sources; stdout and the exit status were compared with `python3` 3.12.3.

| program | default | forced | CPython |
| --- | --- | --- | --- |
| `01_hex_basic.py` | general, match | typed, match | match |
| `02_hex_sep.py` | general, match | typed, match | match |
| `03_unhex.py` | general, match | typed, match | match |
| `04_hex_errors.py` | typed, match | typed, match | match |
| `05_base64_encode.py` | general, match | typed, match | match |
| `06_base64_decode.py` | general, match | typed, match | match |
| `07_base64_strict.py` | general, match | typed, match | match |
| `08_base64_errors.py` | general, match | typed, match | match |
| `09_crc32.py` | typed, match | typed, match | match |
| `10_crc32_values.py` | typed, match | typed, match | match |
| `11_crc_big.py` | typed, stops | typed, stops | prints `18446744073709551621` / `871334697` |
| `12_checksum.py` | typed, match | typed, match | match |

`11/12` build and match CPython in both builds. `11_crc_big.py` feeds `crc32(data, 2**64 + 5)`;
AIL ints are int64, so the program stops loudly:

```
OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)
```

The brief allows that ("print what CPython prints, or let the program stop if the value cannot be
held"). CPython truncates the value to 32 bits, so `crc32(b"abc", 2**64 + 5) == 871334697`.

## The module

`AIL_CURRENT/stdlib/binascii.py` provides `Error(ValueError)`, `Incomplete(Exception)`, `hexlify`,
`b2a_hex`, `unhexlify`, `a2b_hex`, `b2a_base64`, `a2b_base64` (with `strict_mode`), `crc32` (a
256-entry table, polynomial 0xEDB88320, written out at module level) and `crc_hqx` (CCITT,
polynomial 0x1021, bit-serial). `bytes`, `bytearray` and, where CPython accepts it, an ASCII `str`
are accepted. `b2a_uu`, `a2b_uu`, `b2a_qp` and `a2b_qp` are not provided and are listed as such in
the module docstring.

The `a2b_base64` decoder follows CPython 3.12.3's C loop: padding is accepted and ignored in
non-strict mode, while `strict_mode=True` gives `Leading padding not allowed`,
`Only base64 data is allowed`, `Discontinuous padding not allowed`,
`Excess data after padding`, `Incorrect padding` and the
`number of data characters (N) cannot be 1 more than a multiple of 4` message. `crc32` and
`crc_hqx` mask their input value to 32 and 16 bits, as the C code's `unsigned_int(bitwise=True)`
argument does.

One intentional corner: the typed path refuses a `None` default, so `hexlify`/`b2a_hex` spell the
"no separator" default as `sep: bytes = b""`. As a result an explicit `sep=b""` is treated as "no
separator", where CPython raises `ValueError: sep must be length 1.` (an explicit non-empty
separator of the wrong length still raises).

## Bench (Appendix B)

`cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c` built, but every run
reported `perf_event_open: Permission denied`. The numbers below are therefore the median of five
wall-clock runs (`/usr/bin/time -f %e`), not instruction counts, for the same source compiled by
AIL and run by `python3` (whose `binascii` is the C extension). The AIL program is the loop that
generates the LCG bytes plus the conversion; both sides run the same source.

| workload | AIL | `python3` |
| --- | --- | --- |
| `crc32` over 16 MiB of LCG bytes | 0.06 s | 0.42 s |
| `hexlify` of 4 MiB of LCG bytes | 0.02 s | 1.62 s |

Both print the same values (`ca40f48b` and `8388608`). The AIL side wins here because the byte
generation is a compiled loop; CPython's per-byte interpreter overhead dominates its C `crc32` and
`hexlify` calls.

## Follow-ups

* `11_crc_big.py` needs values beyond int64; exact big ints (`--exact-int`) would let `crc32`
  truncate them as CPython does. Left out of scope.
* Explicit `sep=b""` behaves as "no separator" (see above); the typed path cannot take a `None`
  default.
