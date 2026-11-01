# `struct` stdlib coverage

Build command for every row: `ail_chatgpt.py compile X.py --syntax python` (default mode, CPython 3.12 oracle).
`general` means the default build fell back to the general (boxed) path and the program ran successfully; its
stdout and exit code match CPython.

| # | program | result | first typed-path message / refusal |
|---|---------|--------|-------------------------------------|
| 1 | `binary_header.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 2 | `network_packet.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 3 | `sensor_samples.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 4 | `fixed_records.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 5 | `string_fields.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 6 | `flags_alignment.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 7 | `error_paths.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 8 | `struct_class.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 9 | `from_imports.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 10 | `buffer_offsets.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 11 | `byte_orders.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |
| 12 | `tlv_protocol.py` | general | module-level `_STRUCT_NATIVE` dict (see below) |

12 built, 0 refused. The typed path refuses the prelude's module-level format table, and the default build
then builds the general path. The first message is the same for all twelve (line 22 is the injected prelude):

```
note: X.py:22:1: built on the general path (about 20x slower) because '_STRUCT_NATIVE' is a module-level dict
that a function cannot read: a module-level table must be a non-empty literal whose keys are all ints, all strs
or all bytes (or tuples of ints / strs) and whose values are all one kind -- no empty one, no computed one, no
bool, and no name bound twice or changed at module level. write instead: build it in main()
(`_struct_native: dict[str, int] = {...}`) and pass it to the functions that read it as a parameter, or build it
inside the one function that reads it; run with --strict to see why
```

## Built

`struct.calcsize`, `pack`, `unpack`, `pack_into`, `unpack_from`, `iter_unpack`, `Struct` (including
`Struct(format=...)`, `.format`, `.size`, `.pack`, `.unpack`, `.pack_into`, `.unpack_from`, `.iter_unpack`) and
`struct.error`; `from struct import ...` with aliases; `@ = < > !` byte orders, native alignment and trailing
padding of `@`; whitespace and repeat counts in a format; `x c b B ? h H i I l L q Q n N e f d s p`; empty
formats and zero-length `s`/`p`; 8/16/32/64-bit integer ranges and their `struct.error` texts; `f`/`d`/`e`
IEEE 754 packing and unpacking; start/negative offsets and the `pack_into` / `unpack_from` buffer messages.

## Follow-ups (out of scope here)

1. Typed path: the prelude's format tables are module-level dicts. Moving them into the parsing function (or
   spelling them as if-chains) should let the typed path build these programs instead of the 20x slower general
   path. No program is refused because of it.
2. A `Struct` method with fixed arguments before a starred tail, e.g. `s.pack_into(buf, 0, *values)`, still
   reaches the general path's starred-call restriction:
   `general path: a starred (*args) call argument (only print(*xs), zip(*rows), and a call to a def f(*args) or
   a fixed-arity def with no defaults are modelled)`. The module forms `struct.pack(fmt, *values)` and
   `struct.pack_into(fmt, buf, off, *values)` are lowered and work.
3. `struct.iter_unpack` / `Struct.iter_unpack` return a list in this build, not CPython's one-pass iterator:
   `for ... in ...` and `list(...)` match, but `next(...)` raises `TypeError` and `len(...)` succeeds where
   CPython has no `len`.
4. Unsigned 64-bit unpack (difference `C?-job-std_struct-11012058-2`): with the default int64 build, a `Q`, `P`,
   `L` or `N` field at or above 2^63 stops with
   `OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)` (exit 1, stdout kept),
   where CPython returns `9223372036854775808`. This is the declared int64 rule, not silent wrapping; the same
   program with `--exact-int` matches CPython. Values below 2^63 and all signed fields match in the default build.
