# AIL user guide

This guide is for AIL 0.1. It shows small programs, and every code sample in it is built by the
compiler and run by `AIL_CURRENT/test_ail_guide.py`; its stdout is compared byte for byte with
CPython 3.12. The sample style is the one used by [the tutorial](../tutorial.md).

Read [INSTALL.md](../INSTALL.md) first for a working setup and a C compiler.

## Chapters

1. [Typed code, the general path, and integers](01-typed-and-general.md): annotations, the typed
   path, the general-path note, `--strict`, int64 overflow, and exact big ints.
2. [Text, bytes, and files](02-text-bytes-files.md): strings, formatting, bytes, stdin, files, and
   `sys.argv`.
3. [Errors and exit status](03-errors-and-exit.md): `try`/`except`/`else`/`finally`, raising and
   catching errors, user exception classes, `sys.exit`, and uncaught errors.
4. [Modules and C](04-modules-and-c.md): standard modules that build today, plus one `ail_ffi`
   call into libm.

## Where to read more

- [The tutorial](../tutorial.md): a 20-minute tour with the same sample style.
- [INSTALL.md](../INSTALL.md): setup on Linux, macOS and Windows (WSL).
- `AIL_CURRENT/AIL_REFERENCE.md`: the short core reference.
- `AIL_CURRENT/AIL_REFERENCE_MORE.md`: longer sections, including strict mode, the standard
  library, FFI and export.
