# Embedding AIL as a C library

`AIL_CURRENT/ail_embed.py` turns a typed-path Python-syntax module into a static
library, a shared library (`--shared`) and a header:

```sh
python3 -B AIL_CURRENT/ail_embed.py build examples/embed/fib/mod.py -o build/fib
cc -O2 -pthread -Ibuild/fib examples/embed/fib/test.c build/fib/libfib.a -lm -o build/fib/test
build/fib/test

python3 -B AIL_CURRENT/ail_embed.py build examples/embed/fib/mod.py -o build/fib --shared
python3 -B examples/embed/fib/use_ctypes.py --lib build/fib/libfib.so

cd examples/embed/fib/rust && cargo build --release --offline && cargo run --release --offline
```

The same module is called by three hosts and each prints what CPython prints:
the C `test.c`, the Rust binary under `rust/`, and `use_ctypes.py` through
`lib<name>.so`.

The library name is `__ail_name__` from the module, or the source file stem when
that assignment is absent.  The module names its exports in a plain Python list:

```python
__ail_name__ = "fib"
__ail_export__ = ["fib", "gcd", "sum_line"]
```

The build refuses an export whose name is not defined, whose name is reserved by
the ABI, or whose generated C is on the general path.  A fallback build is never
silently exported: the tool stops and names the functions.

## ABI version 1

`<name>_init(void)` returns 0 and resets the saved error.  `<name>_shutdown(void)`
releases the saved error.  `const char *<name>_last_error(void)` returns
`"<ExcName>: <message>"` after a failed call, or `""` before any failure.  The
pointer is valid until the next call.

Every export `<fn>` becomes `int <name>_<fn>(...)`.  The parameters are, in
Python order:

| Python | C argument |
| --- | --- |
| `int` | `int64_t` |
| `bool` | `bool` |
| `float` | `double` |
| `str` | `const char *`, `size_t` (UTF-8 bytes) |
| `bytes` | `const char *`, `size_t` (raw bytes) |

The result travels through an extra out parameter at the end:

| Python | C result |
| --- | --- |
| `int` | `int64_t *out` |
| `bool` | `bool *out` |
| `float` | `double *out` |
| `str` | `char *out, size_t cap, size_t *len` |
| `bytes` | `char *out, size_t cap, size_t *len` |

For `str` and `bytes`, at most `cap` bytes are written and `*len` is always the
true length.  The length is the whole value, so embedded NUL bytes are
preserved.

Every export returns one of these status codes:

| status | meaning |
| --- | --- |
| 0 | success |
| 1 | Python exception; see `<name>_last_error()` |
| 2 | the result did not fit in `cap`; `*len` holds the required size |

An `int64` overflow inside an export is status 1 with an `OverflowError` in
`last_error`, never a wrapped value.  Only typed-path functions can be exported;
the general path is refused by name.

## Threads

Every export takes one process-wide lock, so calls from several threads are
serialised: a second call waits for the first one to return.  This is the same
rule as the general-path runtime's interpreter lock (`python/pkg-v12/threadrt.py`
gives one AIL lock with CPython's GIL semantics); a typed-path library has no
lock of its own, and its exception stack, arena and saved error are globals, so
the wrapper supplies that lock.  `init` and `shutdown` take it too.

`last_error()` reads that shared error without the lock.  It is valid until the
next call on any thread, so a caller that needs the text while other threads are
calling exports must serialise those reads itself.

The test builds `fib` and runs 2 pthreads x 500 iterations (`test.c`-style
checks inside each thread); 1000/1000 results are correct.  The same program
under `gcc -fsanitize=thread` (library and test both instrumented through
`--cc "gcc -fsanitize=thread"`) reports no data race and 1000/1000 correct.  With
the lock calls removed from the wrapper, ThreadSanitizer reports 8 races on
`ail_exc_top`, `ail_exc_cleanup`, `ail_embed_in_call`, `ail_embed_saved_*` and
`ail_embed_error`, which is what the lock prevents.

A ThreadSanitizer binary reserves a huge address space, so the sanitizer run is
skipped when the process has a virtual-memory cap (`ulimit -v`); the plain
two-thread run always runs.

## What the generated C looks like

The probe used by `ail_embed.py` is
`ail_chatgpt.py compile SRC -o EXE --debug-dir DIR`; `DIR/program.c` is then
adapted as follows.

* A typed function keeps its Python name and gets a direct C prototype, for
  example `int64_t fib(int64_t v_n);` or
  `ail_str transform(ail_str v_text);`.  `bool` is carried as `int64_t` in the
  generated signature; `str`/`bytes` are the `ail_str`/`ail_bytes` structs.
* A general-path function instead appears as
  `static ail_st pfu_<name>(ail_ctx *cx, ...)`.  That shape is what the tool
  uses to refuse an export by name.
* A returned `str`/`bytes` is copied into an owned allocation before the
  function's temporary arena is released; the wrapper copies it to the caller's
  buffer and frees that allocation.
* The typed path has no explicit runtime init: its state is static and
  zero-initialized.  `main` is the only process entry point.  The wrapper
  renames it to `ail_embed_unused_main`, includes `program.c`, and calls the
  typed functions directly.
* Exceptions use the generated `jmp_buf` stack.  The wrapper installs one
  handler around each call, so a Python exception or an int64 trap becomes a
  status and a `last_error` string instead of terminating the host process.

## Callers

Each example directory holds three callers:

| file | how it calls |
| --- | --- |
| `test.c` | links `lib<name>.a` with `gcc -O2` |
| `rust/` | `build.rs` runs `ail_embed.py`, emits `rustc-link-search`/`rustc-link-lib`, and `src/main.rs` declares the exports in `extern "C"` (no crates) |
| `use_ctypes.py` | `ctypes.CDLL` on `lib<name>.so`; builds it with `--shared` unless `--lib` names one |

`use_ctypes.py` calls the library and, in the same process, imports `mod.py`
directly, comparing every value with the plain-Python result before printing the
line.  `rust/build.rs` finds the repository root by walking up from
`CARGO_MANIFEST_DIR` until it sees `AIL_CURRENT/ail_embed.py`; `AIL_PYTHON`
overrides the interpreter it runs.

## Examples

| directory | exports | checks |
| --- | --- | --- |
| `fib/` | `fib`, `gcd`, `sum_line` | int values, negative modulo, int64 overflow at `fib(93)` |
| `transform/` | `transform` | `str` result in a caller buffer, empty result, status 2 |
| `wordcount/` | `word_count` | a text buffer with explicit length |
| `raiser/` | `checked_div`, `require_positive` | status 1 and exact `ValueError` text |

Each `expected.txt` is CPython's stdout for that example's `mod.py`.  All three
callers print the same lines; `AIL_CURRENT/test_ail_embed.py` builds each form,
runs the three of them plus the two-thread test, and compares the output.
