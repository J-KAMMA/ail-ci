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
| `01_hex_basic.py` | general, match | general, match | match |
| `02_hex_sep.py` | general, match | general, match | match |
| `03_unhex.py` | general, match | general, match | match |
| `04_hex_errors.py` | general, match | general, match | match |
| `05_base64_encode.py` | general, match | general, match | match |
| `06_base64_decode.py` | general, match | general, match | match |
| `07_base64_strict.py` | general, match | general, match | match |
| `08_base64_errors.py` | general, match | general, match | match |
| `09_crc32.py` | general, match | general, match | match |
| `10_crc32_values.py` | general, match | general, match | match |
| `11_crc_big.py` | general, stops | general, stops | prints `18446744073709551621` / `871334697` |
| `12_checksum.py` | general, match | general, match | match |

The typed path cannot raise `TypeError` (its built-in exception set is `ValueError`, `RuntimeError`,
`OverflowError` and friends, but not `TypeError`), and CPython's `binascii` raises `TypeError` for a
wrong argument type, so the module builds on the general path in both modes; `AIL_UNIFIED_FORCE=1`
forces the same path. `11/12` build and match CPython in both builds. `11_crc_big.py` feeds
`crc32(data, 2**64 + 5)`; AIL ints are int64, so the program stops loudly:

```
OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)
```

The brief allows that ("print what CPython prints, or let the program stop if the value cannot be
held"). CPython truncates the value to 32 bits, so `crc32(b"abc", 2**64 + 5) == 871334697`.

## The module

`AIL_CURRENT/stdlib/binascii.py` provides `Error(ValueError)`, `Incomplete(Exception)`, `hexlify`,
`b2a_hex`, `unhexlify`, `a2b_hex`, `b2a_base64`, `a2b_base64` (with `strict_mode`), `crc32` (a
256-entry table, polynomial 0xEDB88320, written out at module level) and `crc_hqx` (CCITT,
polynomial 0x1021, bit-serial). `bytes` and `bytearray` are accepted everywhere; an ASCII `str` is
accepted only by `unhexlify`, `a2b_hex` and `a2b_base64`, as in CPython. `b2a_uu`, `a2b_uu`, `b2a_qp`
and `a2b_qp` are not provided and are listed as such in the module docstring.

The `a2b_base64` decoder follows CPython 3.12.3's C loop: padding is accepted and ignored in
non-strict mode, while `strict_mode=True` gives `Leading padding not allowed`,
`Only base64 data is allowed`, `Discontinuous padding not allowed`,
`Excess data after padding`, `Incorrect padding` and the
`number of data characters (N) cannot be 1 more than a multiple of 4` message. `crc32` and
`crc_hqx` mask their input value to 32 and 16 bits, as the C code's `unsigned_int(bitwise=True)`
argument does.

The argument handling follows CPython's C signatures. `sep` defaults to a private sentinel, so an
explicit `sep=b""` or `sep=""` raises `ValueError: sep must be length 1.` while an omitted `sep`
means "no separator"; a `bytearray` separator raises `TypeError: sep must be str or bytes.` and a
value with no length raises `TypeError: object of type 'X' has no len()`. Passing a `str`, a list or
another non-buffer to `hexlify`/`b2a_hex`/`b2a_base64`/`crc32`/`crc_hqx` raises
`TypeError: a bytes-like object is required, not 'X'`, while `unhexlify`/`a2b_hex`/`a2b_base64`
raise `TypeError: argument should be bytes, buffer or ASCII string, not 'X'` for the same input.
`newline` (`b2a_base64`) and `strict_mode` (`a2b_base64`) are keyword-only, and an extra positional
argument gives CPython's `... takes exactly 1 positional argument (N given)`.

Program `09_crc32.py` compares the chunked running CRC with `ZLIB_WHOLE = 3456913684`, the value
`zlib.crc32` returns for the same bytes (checked with CPython 3.12.3). The program cannot import
`zlib` itself: `zlib` needs the typed path, and this module cannot be built there because the typed
path has no `TypeError`. `12_checksum.py` exercises the same chunked/whole equality over a 4219-byte
payload.

## Bench (Appendix B)

`cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c` built, but every run
reported `perf_event_open: Permission denied`. The numbers below are therefore the median of five
wall-clock runs (Python `time.perf_counter`), not instruction counts, for the same source compiled
by AIL and run by `python3` (whose `binascii` is the C extension). The AIL program is the loop that
generates the LCG bytes plus the conversion; both sides run the same source.

| workload | AIL | `python3` |
| --- | --- | --- |
| `crc32` over 16 MiB of LCG bytes | 6.06 s | 3.05 s |
| `hexlify` of 4 MiB of LCG bytes | 2.86 s | 0.93 s |

Both print the same values (`05d1d756` and `8388608`). CPython wins because its `binascii` is the
hand-optimised C extension while this module's `crc32`/`hexlify` are AIL loops compiled to C.

## Follow-ups

* `11_crc_big.py` needs values beyond int64; exact big ints (`--exact-int`) would let `crc32`
  truncate them as CPython does. Left out of scope.
* `09_crc32.py` uses the `zlib.crc32` value as a literal because `zlib` requires the typed path and
  the exact `TypeError` texts keep this module on the general path. A typed-path `TypeError`
  (add `TypeError` to the typed exception set) would let the program import `zlib` again.
