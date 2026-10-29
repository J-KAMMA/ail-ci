# Installing AIL

AIL compiles a subset of Python 3.12 to C and builds a small native executable with your C
compiler. The compiler is the `AIL_CURRENT/` directory of this repository. There is no installer
yet: you run it from a git checkout.

Checked on 2026-10-30 on Ubuntu 24.04 under WSL 2 (AMD Ryzen 7 8840U), Python 3.12.3,
gcc 13.3.0. Other platforms are described below with what is and is not checked.

## Requirements

- **Python 3.12.** AIL matches its output against CPython 3.12, so use 3.12 to compare
  results. The compiler itself refuses to run on Python older than 3.10.
- **A C compiler.** AIL uses `$PIPE_CC` if set, otherwise the first of `cc`, `clang`, `gcc` on
  `PATH`. Builds are optimised with `-O2`.
- **git**, to get the code.

No Python packages are needed.

### Linux

Install Python 3.12 and gcc from your distribution. On Ubuntu 24.04 both are in the default
repositories:

```sh
sudo apt install python3 gcc git
```

This is the platform the full test suite runs on (`ubuntu-24.04` on GitHub Actions). A
representative subset of the tests also runs on Linux arm64.

### macOS

Install Python 3.12 and the Xcode Command Line Tools (`xcode-select --install`), which provide
`cc` (Apple clang). The repository's `platforms` CI workflow runs a representative subset of the
tests on macOS 14 (arm64) with `PIPE_CC` set to that `cc`; it does not run the full suite.
`--static` is refused on macOS (Apple ships no static C library). This guide was not run on a Mac.

### Windows

Two options:

- **WSL 2 (recommended).** Install an Ubuntu distribution, open its shell and follow the Linux
  steps. This guide was checked this way.
- **Native, with MinGW-w64.** The `platforms` CI workflow runs a representative subset of the tests
  on `windows-latest` with Python 3.12 and the MSYS2 UCRT64 gcc
  (`pacman -S mingw-w64-ucrt-x86_64-gcc`, with `C:\msys64\ucrt64\bin` on `PATH`) and
  `PYTHONUTF8=1`. Use `python` or `py -3` in place of `python3`. This guide was not run on
  native Windows.

## Get the code

```sh
git clone https://github.com/J-KAMMA/ail-ci.git ~/ail-ci
cd ~/ail-ci
```

### pip install

Not available. This repository has no `pyproject.toml` or `setup.py`, so pip cannot install it.
Tried in a fresh venv on 2026-10-30:

```text
$ python3 -m venv /tmp/ailvenv
$ /tmp/ailvenv/bin/python -m pip install --no-build-isolation /home/bluec/pub/wt-docs
ERROR: Directory '/home/bluec/pub/wt-docs' is not installable. Neither 'setup.py' nor 'pyproject.toml' found.
```

(`/home/bluec/pub/wt-docs` was a checkout of this repository.) `ail-lang` is also not on PyPI
yet. `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md` describes `pip install ail-lang` and an `ail`
command; those belong to a package that has not been published, and they do not work from this
checkout.

## Check the setup

From the checkout:

```sh
python3 AIL_CURRENT/ail_chatgpt.py doctor
```

It prints JSON. On the machine above:

```text
{
  "python": "3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]",
  "platform": "Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39",
  "python_supported": true,
  "c_compiler": "/usr/bin/cc",
  "c_compiler_configured": "/usr/bin/cc",
  "c_compiler_available": true,
  "source_root": "/home/bluec/pub/wt-docs/AIL_CURRENT",
  "external_model_required_for_selftest": false
}
```

`python_supported` and `c_compiler_available` must both be `true`. To also compile and run a
small program, add `--check`; a working setup ends with:

```text
  "build_check": {
    "status": "passed",
    "phase": "run",
    "message": "Representative SDK compile/runtime check passed"
  }
}
```

and exit status 0.

## A first compile

The compiler can be run from any directory. To keep commands short, define a shell function
(bash or zsh; adjust the path if you cloned elsewhere):

```sh
ailc() { python3 ~/ail-ci/AIL_CURRENT/ail_chatgpt.py "$@"; }
```

Make a work directory and a program:

```sh
mkdir -p ~/ail-tutorial && cd ~/ail-tutorial
echo 'print("Hello, AIL!")' > hello.py
```

Compile and run it:

```text
$ ailc compile hello.py -o hello
{"output": "/home/bluec/ail-tutorial/hello", "bytes": 16192, "sha256": "bd9bd02b429a6b681aec9344bdc4a482ee3b369680f710f7601f688b7c460b49"}
$ ./hello
Hello, AIL!
```

On success `compile` prints one JSON line (output path, size in bytes, SHA-256); your path and
hash will differ. Continue with [the tutorial](TUTORIAL.md).

## Troubleshooting

- **`"c_compiler_available": false`** in `doctor`: no C compiler was found. Install `gcc`
  (Linux, WSL, MinGW) or the Xcode Command Line Tools (macOS), or set `PIPE_CC` to a compiler.
- **`"python_supported": false`**, or an error saying Python 3.10 or newer is required: run the
  commands with a newer `python3`.
- **`ail_chatgpt.py: error: output already exists`** (exit 2): `compile` never overwrites the
  `-o` file. Delete it or choose another name.
- **`not in the subset: ...`** (exit 3): the program uses something AIL does not build. The
  message names it and usually gives `file:line:col` and a `write instead:` line. See
  [the tutorial](TUTORIAL.md#3-a-refusal).
- **`import of 'numpy' is not available`** (exit 2): only the standard library modules AIL
  implements, and your own modules, can be imported. Third-party packages cannot.
- **`note: ... built on the general path (about 20x slower)`**: not an error. The program was
  built and behaves like CPython, but on the slower path. Add `--strict` to see why and how to
  fix it.
- **`check` says `no def found`** for a script with no function: `check` needs at least one
  `def`. `compile` builds such a script normally.
- **`hash mismatch: NAME`** from the test tools: a file pinned in `AIL_CURRENT/MANIFEST.json`
  changed. Run `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
