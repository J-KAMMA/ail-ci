# AIL

AIL is a programming language with Python 3.12 syntax, including optional type annotations. It
compiles your program to a small native binary, so you can write Python-like code and ship a
standalone executable. A compiled AIL program prints what CPython prints, or the compiler refuses
the construct at compile time and tells you what to write instead.

## Install

```sh
pip install ailc
```

That installs the `ail` command. AIL needs Python 3.10 or newer (3.12 is recommended) and a C
compiler on `PATH`:

- **Linux:** `gcc` or `clang`; on Ubuntu/Debian install it with `sudo apt install gcc`, on Fedora
  with `sudo dnf install gcc`.
- **macOS:** the Xcode Command Line Tools provide `cc`; install them with
  `xcode-select --install`.
- **Windows:** use WSL 2 and the Linux instructions, or install MinGW-w64 with the UCRT gcc. If you have no C
  compiler, `pip install "ailc[zig]"` brings a `zig cc` (about 50 MB).

`ail check` type-checks without a C compiler. Check the whole setup with:

```sh
ail doctor --check
```

More detail, including checkout installs and troubleshooting, is in [docs/INSTALL.md](docs/INSTALL.md).

## A first program

Save this as `total.py`:

```python
def total(values: list[int]) -> int:
    result: int = 0
    for value in values:
        result += value
    return result


print("total:", total([10, 20, 12]))
```

It prints `total: 42`. Run it directly, or keep the executable:

```sh
ail run total.py
ail build total.py -o total
./total
```

Annotations are optional, but they let the compiler use the fast typed path. `ail run --strict`
refuses anything that would fall back to the slower general path and explains how to fix it.

## Integers

`int` is a signed 64-bit integer by default. A result that leaves int64 stops the program loudly
with an `OverflowError`; it never wraps silently. For CPython-style arbitrary-size integers, build
with `ail build --exact-int` (or `ail run --exact-int`, or set `AIL_EXACT_INT=1`). Exact integers
are slower.

## What is supported

- Python 3.12 syntax: functions, classes and dataclasses, methods, exceptions, loops,
  comprehensions, f-strings, list/dict/set/tuple, bytes and bytearray.
- A typed fast path and a slower general path. `--strict` builds only the typed path; `ail check`
  checks types without a C compiler.
- Text and binary files, `os` and `os.path`, and a growing standard-library subset that includes
  `sys`, `math`, `json`, `csv`, `re`, `heapq`, `bisect`, `collections`, `itertools`, `functools`,
  `random`, `datetime`, `decimal` and `statistics`.
- C FFI, the CPython hybrid, a language server (`ail lsp`), projects (`ail new`), a build cache,
  and debug builds with source lines (`ail build --debug`).

## What is not there yet

- No third-party packages: imports are limited to the standard-library modules AIL implements and
  your own modules. Constructs that are not built, such as `eval`, `exec`, `async def` and some
  `match` forms, are refused by name with a suggested rewrite.
- Python-syntax versions of the compare-lab programs do not yet reach the typed path; they run on
  the general path (much slower) or are refused. The compiler is not a complete Python
  implementation.
- Compile time is much slower than Rust's, and there is no typed parallelism without the GIL yet.
- The default integers are 64-bit; arbitrary-size integers need `--exact-int`.

## How AIL compares

The measured comparison is in [docs/COMPARISON.md](docs/COMPARISON.md). Against Rust, the report's
scorecards say:

- Peak RSS: AIL is lower on 0/4 tasks with data.
- Binary size: AIL is smaller on 10/10 tasks.
- Compile time: AIL is slower to compile on 10/10 tasks.
- Wall time: AIL is lower on 6/10 tasks.

So AIL wins on binary size and often on wall time, and loses on compile time and on peak memory
for the tasks with data. The page also compares AIL with the best other language, includes the
Python-syntax results, and lists every task, metric, win and loss.

## Learn more

- [docs/INSTALL.md](docs/INSTALL.md): setup on Linux, macOS and Windows.
- [docs/QUICKSTART.md](docs/QUICKSTART.md): a 10-minute tour with complete tested programs.
- [docs/tutorial.md](docs/tutorial.md): a longer tutorial, including refusals and the general path.
- [AIL_CURRENT/AIL_REFERENCE.md](AIL_CURRENT/AIL_REFERENCE.md): the core language reference.

## Development

This repository is the CI mirror of the compiler and its regression suite; development happens
elsewhere. Requirements: Python 3.10 or newer and `gcc` on `PATH`.

```sh
python3 tools/par_check.py            # whole suite, 8 modules at a time
python3 tools/par_check.py -j 4 test_ail_list_ops test_ail_check   # selected modules
```

`par_check.py` first checks the SHA-256 pins in `AIL_CURRENT/manifest.d/`. After editing a pinned
file or adding a test, `git add` the new files and refresh the pins with
`python3 tools/update_manifest.py`; `python3 tools/update_manifest.py --check` is what CI runs.

**Adding a test module.** Create `AIL_CURRENT/test_<name>.py` and a registration file
`AIL_CURRENT/tests.d/test_<name>.txt` that contains the module name on one line. Do not edit the
`LISTED_MODULES` tuple in `ail_check.py` or `MANIFEST.json`: `ail_check.MODULES` is the listed
tuple followed by the `tests.d` modules sorted by name, so `par_check.py`, `tools/ci_shards.py` and
the CI shards all see the union.

The workflow in `.github/workflows/tests.yml` splits the module list into 20 shards and runs them
in parallel on `ubuntu-24.04`.

## License

MIT OR Apache-2.0, at your option: see [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE).
