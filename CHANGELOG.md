# Changelog

All notable changes to AIL are recorded here. This is the first release; version numbers are set by
the project owner.

## 0.1.0 - 2026-11-03

The first release of `ailc`, the AIL compiler and the `ail` command. It is built from the exported
`integ` tree and the entries in [DEVLOG.md](DEVLOG.md).

### Features

- AIL source is Python 3.12 syntax, with optional type annotations. Programs are compiled to C and
  then to a small standalone native executable with the system C compiler.
- Two code paths: a typed fast path, and a general path for programs the typed path cannot take.
  The compiler prints a `note:` when it falls back; `--strict` refuses the fallback instead and
  lists every blocker with a suggested rewrite.
- `ail run`, `ail build`, `ail check`, `ail doctor`, projects (`ail new`), a build cache, debug
  builds with source lines (`--debug`), and a language server (`ail lsp`).
- Core Python data types and control flow: functions, classes and dataclasses, methods,
  exceptions, loops, comprehensions, f-strings, `list`, `dict`, `set`, `tuple`, `bytes` and
  `bytearray`.
- Text and binary file I/O, `os` and `os.path`, and a standard-library subset including `sys`,
  `math`, `json`, `csv`, `re`, `heapq`, `bisect`, `collections`, `itertools`, `functools`,
  `random`, `datetime`, `decimal`, `statistics`, `string`, `shlex`, `graphlib`, `numbers` and
  `array`.
- C FFI, the CPython hybrid, typed arrays, and AIL-only built-ins through `from ail import ...`.
- Packaging as the PyPI distribution `ailc`, with the `ail` command, install checks on Linux,
  macOS and native Windows, and an optional `zig cc` fallback (`pip install "ailc[zig]"`).
- Documentation for a first-time user: installation, quickstart, tutorial, core reference, and the
  published compare-lab comparison.

### Correctness

- A compiled program prints exactly what CPython 3.12 prints, or the compiler refuses the
  construct at compile time with `file:line:col` and a `write instead:` hint.
- `int` is int64 by default. Arithmetic that leaves the range stops with `OverflowError` instead of
  wrapping; literals and constant expressions outside int64 are refused with a hint.
- An uncaught exception exits with status 1. An explicit `raise` prints CPython's exception name and
  message; a runtime fault such as division by zero, an index error or a missing dict key prints a
  message without the exception name. A `--debug` build adds the source line (`raised near
  file:line`).  Beginner mistakes such as an undefined name, a missing argument or a method without
  `self` now carry a compile-time position and often a "did you mean" suggestion.
- List `count`/`index` hoists now wait for every earlier operand that can raise or change the list,
  preserving Python's evaluation order in those cases.
- Fixed CPython-parity defects in `same_file`, path errors (`ENOTDIR`, empty paths), closed binary
  files, astral `jscharat`, frozenset module constants, shadowed builtins and repeated `from ail`
  aliases.
- Repaired the macOS SDK export under `/var` symlinks and the Windows tutorial artifact path, so
  wheel installs and the tutorial samples run on all supported CI platforms.

### Performance

- The typed path emits plain C with no interpreter, giving small binaries and competitive wall
  time on the compare-lab tasks; the general path is used only when needed.
- Loop-block list locals and field-loop snapshots are freed at last use, reducing peak memory on
  the string-heavy `tree_fold` workload.
- `decimal` uses native int64 coefficients when they fit, with large speedups on coefficient-heavy
  arithmetic.
- An opt-in front-end cache (`AIL_FE_CACHE=1`) and a resident compile server reduce repeated
  compile work; the server starts in the background and falls back to the ordinary path.
- Exact integers (`--exact-int`) use arbitrary precision at a cost of roughly 20x on arithmetic.

### Known limitations

- Python-syntax versions of the compare-lab programs do not yet reach the typed path: they run on
  the general path (about 20x slower) or are refused.
- Not all of Python or its standard library is implemented. Third-party packages cannot be
  imported, and constructs such as `eval`, `exec`, `async def` and some `match` forms are refused
  by name.
- The default integers are signed 64-bit; arbitrary-size integers require `--exact-int`.
- Compile time is much slower than Rust's, and peak memory is higher on the compare-lab tasks with
  data. Typed parallelism without the GIL is not available yet.
- The licence is MIT OR Apache-2.0, at your option. Publishing and tagging are done by the project
  owner.
