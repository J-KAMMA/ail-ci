# Rust crates called from Python syntax

Three small crates in this directory are usable from an ordinary Python file:

| crate | C entry point | what it shows |
| --- | --- | --- |
| `fnvhash/` | `uint64_t fnv1a64(const uint8_t *p, size_t n)` | an exact `u64` result and a 1 MB borrowed input |
| `textstat/` | `int32_t stats(const uint8_t *p, size_t n, uint64_t *out)` | a negative result mapped to `ValueError`, and a `ptr(c_uint64)` out-parameter |
| `rle/` | `intptr_t rle_encode(const uint8_t *src, size_t n, uint8_t *dst, size_t room)` | a writable `bytearray` and an explicit capacity |

Each crate has no dependencies, `crate-type = ["cdylib", "staticlib"]`, `panic = "abort"`, a hand-written
header (because `cbindgen` may not be installed), and a `main.py`.  `ail_cargo.py` builds the crate and writes
the cdylib (for CPython's `ctypes`), the staticlib (for the compiled AIL program), the header, the `@extern`
stubs and cargo's `native-static-libs` line.

## Build and run one crate

From the repository root:

```sh
python3 AIL_CURRENT/ail_cargo.py build examples/crate/fnvhash \
    -o examples/crate/fnvhash/out --header examples/crate/fnvhash/fnvhash.h
cp examples/crate/fnvhash/main.py examples/crate/fnvhash/bigbuffer.py examples/crate/fnvhash/out/
```

The generated `fnvhash_ffi.py` links `./libfnvhash.a` because a compiled AIL program links the staticlib.
CPython must load the cdylib, so make the `.so` copy for the `python3` run and restore the `.a` copy before
compiling:

```sh
cd examples/crate/fnvhash/out
cp fnvhash_ffi.py fnvhash_ffi.a.py
sed 's|\./libfnvhash\.a|./libfnvhash.so|' fnvhash_ffi.a.py > fnvhash_ffi.py
PYTHONPATH=/path/to/repo/AIL_CURRENT python3 -B main.py
cp fnvhash_ffi.a.py fnvhash_ffi.py
PYTHONPATH=/path/to/repo/AIL_CURRENT python3 -B /path/to/repo/AIL_CURRENT/ail_chatgpt.py \
    compile --exact-int main.py -o main.out
./main.out
```

`fnvhash` needs `--exact-int`: its empty-string hash is `14695981039346656037`, above `2**63` (see the
limitations below).  `textstat` is built with `--check stats=negative:ValueError`; `rle` needs no flags:

```sh
python3 AIL_CURRENT/ail_cargo.py build examples/crate/textstat -o examples/crate/textstat/out \
    --header examples/crate/textstat/textstat.h --check stats=negative:ValueError
python3 AIL_CURRENT/ail_cargo.py build examples/crate/rle -o examples/crate/rle/out \
    --header examples/crate/rle/rle.h
```

`AIL_CURRENT/test_ail_examples_crate.py` performs this build/run/compare for all three crates and requires
equal stdout and exit status on CPython and in the AIL binary.

## Measurements

`make_input.py` writes a deterministic 10 MB buffer (`b"a"` repeated) to the path given on its command line
(or `input.bin`).  Each crate has a `bench.py` that reads that file, calls the crate and prints one line.
The times are wall time, median of three, on the GitHub Actions runner:

```sh
python3 examples/crate/make_input.py /tmp/crate_input.bin
```

| crate | AIL binary bytes | AIL wall time | `python3` wall time |
| --- | ---: | ---: | ---: |
| `fnvhash` | 36,488 | 13.6 ms | 49.3 ms |
| `textstat` | 5,425,640 | 12.4 ms | 48.4 ms |
| `rle` | 36,928 | 25.9 ms | 50.6 ms |

The binary size is the `bench.py` executable used for the timing.  The example `main.py` binaries are
27,736 (`fnvhash`), 5,442,352 (`textstat`) and 37,016 (`rle`) bytes.  `textstat` is large because the Rust
standard library's Unicode tables come with `str::split_whitespace` and `str::chars`; the C ABI is still
tiny.  The same three functions are easy to write in plain Python (a hash loop, a text counter and a run
encoder), so the crate is worth it only when the Rust code is already there or is much faster than a Python
loop.

## Limitations found in this lane

These are defects in files this job may not edit (`ail_ffi.py`, `ail_ffi_lower.py`); the examples work
around them.

1. A `uint64_t` result above `int64` is a runtime stop in the default build:

   ```
   OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)
     raised near fnvhash_ffi.py:10
   ```

   `--exact-int` fixes a call with a literal argument, but a call whose `bytes` argument is a runtime value
   still converts through `int64` and stops even with the flag:

   ```
   OverflowError: integer overflow in a conversion to int64 (ints are 64-bit; --exact-int gives exact ints)
     raised near fnvhash_ffi.py:10
   ```

   Reproducer: put `print(fnv1a64(b""))` after `data = b"a" * 1048577` and compile with `--exact-int`.
   The first call then fails, while the same call alone prints the exact value.  `fnvhash/bigbuffer.py`
   keeps the runtime-value call in a separate module, which leaves `main.py`'s literal calls on the exact
   path.

2. Iterating over a tuple of `bytes` values and passing the element to a `bytes` stub parameter is refused:

   ```
   not in the subset: 'p' is annotated bytes in the source, but the caller also supplies int; refusing
   rather than silently choosing one.
   note: main.py:13: iterating over a tuple
   ```

   Reproducer: `for data in (b"", b"a"): print(fnv1a64(data))`.  The examples print each call directly.

3. A `bytearray` cannot be passed to a function whose parameter is annotated `bytes`; the compiler requires
   an explicit snapshot:

   ```
   passing a bytearray to the bytes parameter 'data' of read_u64() would copy it ... bind bytes(data) first
   ```

   The examples call `bytes(out)` before reading the out-buffer.  `fnvhash` also needs `--exact-int`; the
   other two crates compile without it.
