# FFI examples

These four programs call real C libraries through `ail_ffi`. Each file is plain Python: `python3` runs it
through the ctypes implementation in `AIL_CURRENT/ail_ffi.py`, and the compiler reads the same `@extern` stubs and
builds a native executable that makes the C calls directly. The declarations are checked against the system header
when compiling, so a wrong prototype is a compile error.

`AIL_CURRENT/test_ail_ffi_examples.py` runs every example both ways and requires the same stdout and exit status.
It skips an example, naming the missing header or library, when the runner does not provide it.

## Building and running

From the repository root:

```sh
export PYTHONPATH="$PWD/AIL_CURRENT"
python3 examples/ffi/zlib_check.py
python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi/zlib_check.py -o /tmp/zlib_check
/tmp/zlib_check
```

`lib=` on a stub is the library for `-l` (`lib="z"` is `-lz`); `link("m", "z")` at module level names libraries
for every stub of the file that has no `lib=`.

## `zlib_check.py`

`crc32` and `adler32` of three byte strings, then `compress2` and `uncompress` round trip a longer buffer. The
stubs show borrowed `bytes` input, a writable `bytearray` output, `length(...)` for a buffer length, and
`ptr(c_ulong)` for the out-length:

```python
@extern(header="zlib.h", symbol="crc32")
def c_crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...

@extern(header="zlib.h", symbol="compress2")
def c_compress2(dest: bytearray, dest_len: ptr(c_ulong), src: bytes,
                n: length("src", c_ulong), level: c_int) -> c_int: ...
```

The `n` parameter is not in the Python call: the call supplies `len(buf)` or `len(src)`. The out-length lives in a
`bytearray(8)` and is read back by shifting its bytes.

## `libm_math.py`

`cbrt`, `hypot`, `fma` and `frexp` over six values that include `-0.0`, `inf` and the subnormal `5e-324`. It shows
the float annotations, the `ptr(c_int)` out-exponent, and printing with `repr()`:

```python
link("m")

@extern(header="math.h", symbol="frexp")
def c_frexp(x: c_double, e: ptr(c_int)) -> c_double: ...
```

## `libc_text.py`

`strlen` through `c_char_p`, `strtol` in base 16 and 36, and `toupper` applied over a `bytearray`. One parse is
`int64`'s edge (`7fffffffffffffff` base 16); one is below `int64`, where `strtol` saturates and sets `ERANGE`:

```python
@extern(header="string.h", symbol="strlen")
def c_strlen(s: c_char_p) -> c_size_t: ...

@extern(header="stdlib.h", symbol="strtol", trust=True)
def c_strtol(s: c_char_p, end: ptr(c_void_p), base: c_int) -> c_long: ...

@extern(header="stdlib.h", symbol="strtol", trust=True,
         check="negative", errno=True)
def c_strtol_checked(s: c_char_p, end: ptr(c_void_p), base: c_int) -> c_long: ...
```

`trust=True` is needed because `strtol`'s second parameter is a `char **`, which the stub annotation cannot spell;
the header is still included, but its prototype is not compared with the stub. The checked declaration uses
`check="negative"` with `errno=True`: the saturated negative result is a failure, and the program prints
`[Errno 34] Numerical result out of range`.

## `sqlite_count.py`

An in-memory SQLite database owned by a `Handle("sqlite3", free="sqlite3_close")`. The program creates a table,
inserts 1,000 rows in one transaction through `sqlite3_exec`, then reads `SELECT count(*), sum(v)` through
`sqlite3_prepare_v2`, `sqlite3_step`, `sqlite3_column_int64` and the statement handle's `sqlite3_finalize`:

```python
Db = Handle("sqlite3", free="sqlite3_close")
Stmt = Handle("sqlite3_stmt", free="sqlite3_finalize")

@extern(header="sqlite3.h", trust=True)
def sqlite3_open(path: c_char_p, out: ptr(c_void_p)) -> c_int: ...
```

`ptr(c_void_p)` is the `void **` out-parameter; `Db.adopt(out)` takes the pointer out of the bytearray. `close()`
calls the free function once, and the statement is closed before the database.

## What is not supported yet

These are the limits declared in the `ail_ffi.py` docstring; both the compiler and the ctypes shim refuse the same
shapes.

* Every parameter and the return need an annotation (`-> None` for void). `bytes`, `bytearray` and `length` cannot
  be results.
* Integers are range checked for the declared C width. `bytes` is borrowed for the call and never copied;
  `bytearray` may be written by C, its length cannot change, and a compiled program copies it in and out around
  the call.
* `ptr(T)` / `cptr(T)` cover integer, `c_double`, `c_float` and `c_bool` element types; a buffer that is not a
  whole number of `T` is a `ValueError`.
* `c_char_p` / `c_mut_char_p` are UTF-8, NUL-terminated copies; an embedded NUL is an error. A `c_char_p` result
  is copied and decoded, and NULL gives `""`.
* A struct passed by pointer is a bytearray laid out by hand with the C offsets, and its stub needs `trust=True`
  because the exact-prototype check cannot spell the struct. The same applies to a prototype that names a
  pointer type the stub cannot spell, such as `strtol`'s `char **`.
* A bare `c_void_p` is an int (`0` is NULL) and the program owns the lifetime. A `Handle(name, free=...)` owns the
  pointer, frees it exactly once at `close()` (or when it is left open at program exit, newest first), and refuses
  arithmetic on the handle and passing it into a parallel worker.
* Callbacks must name a module-level `def`; a lambda, a closure, a method or a variable is refused. `retain=True`
  and `threads=True` are refused. A call from another thread or after the C call returned aborts the program. A
  callback's `on_error=` is required unless its return is `None`. A compiled program copies a bytearray in and out
  around the whole call, so the callback sees the bytearray as it was before the call.
* `check="negative"` and `check="minus1"` on an unsigned result never fire, so a compiled program refuses them;
  `check="allones"` is the unsigned `(T)-1`.
* `--no-ffi` refuses every declaration.
* `errno=True` reads errno right after the call and raises `OSError(errno, strerror)`: `str(e)` is
  `[Errno N] text` and `e.errno` is N. In a compiled program `e.errno`, `e.strerror` and `str(e)` are built only
  on a name bound by `except OSError as e` (or one of the five errno classes AIL has); another class is refused by
  name. A bare `OSError("x")` has no errno there: reading it raises `RuntimeError`, where CPython gives `None`.
* A `uint64` result above `int64` is a loud stop on the legacy emitter (the owner decision is exact u64 FFI with
  an argument range check).
* A compiled program frees an unclosed handle at program exit (or at `close()`), not when the last reference
  drops; the two differ only if the C library's free function does something the program can observe earlier.
