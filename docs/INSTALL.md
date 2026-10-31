# Installing AIL

AIL compiles a subset of Python 3.12 to C and builds a small native executable with your C
compiler. You install it as the Python package `ail-lang`, which gives you the `ail` command.

> `ail-lang` is **not published on PyPI yet**. Until it is, install it from a checkout of this
> repository (below). The commands are the same after publishing, minus the clone.

Checked on 2026-10-31 on Ubuntu 24.04 under WSL 2 (Python 3.12.3, gcc 13.3.0): `pip wheel`, a
fresh virtual environment, `pip install` of the wheel, then `ail run` of a hello world and of a
typed program, and every sample of [the tutorial](tutorial.md). The macOS and native Windows
steps below were not run by hand; CI covers a subset of the tests there (see "Platforms").

## Requirements

- **Python 3.10 or newer, 3.12 recommended.** AIL matches its output against CPython 3.12, so use
  3.12 to compare results. The package has no Python dependencies.
- **A C compiler** on `PATH`: AIL uses `$PIPE_CC` if set, otherwise the first of `cc`, `clang`,
  `gcc`; failing those, a `zig cc` (`$AIL_ZIG`, `zig` on `PATH`, or the `ziglang` wheel from
  `pip install "ail-lang[zig]"`, about 50 MB). `ail check` needs no C compiler.
- **git**, to get the code until the package is published.

## Linux

On Ubuntu 24.04 (the platform the full test suite runs on) everything is in the default
repositories. `python3-venv` is a separate package there and is easy to miss:

```sh
sudo apt install python3 python3-venv python3-pip gcc git
git clone https://github.com/J-KAMMA/ail-ci.git
python3 -m venv ~/.venvs/ail
~/.venvs/ail/bin/pip install ./ail-ci
~/.venvs/ail/bin/ail doctor --check
```

Put `~/.venvs/ail/bin` on your `PATH` (or `source ~/.venvs/ail/bin/activate`) to type just `ail`.
On Fedora use `sudo dnf install python3 gcc git`. `pip install .` and `pip wheel .` both work;
only a wheel is built (there is no sdist).

First program:

```sh
echo 'print("Hello, AIL!")' > hello.py
ail run hello.py                  # compile to a temporary executable and run it
ail build hello.py -o hello       # keep the executable
./hello
```

A typed program, built so that it must stay on the fast path:

```sh
cat > fib.py <<'EOF'
def fib(n: int) -> int:
    a: int = 0
    b: int = 1
    for _ in range(n):
        a, b = b, a + b
    return a


print(fib(50))
EOF
ail run --strict fib.py           # 12586269025
```

Continue with [the quickstart](QUICKSTART.md) or [the tutorial](tutorial.md).

## macOS

Install Python 3.12 (python.org or Homebrew: `brew install python@3.12`) and the Xcode Command
Line Tools, which provide `cc` (Apple clang):

```sh
xcode-select --install
git clone https://github.com/J-KAMMA/ail-ci.git
python3 -m venv ~/.venvs/ail
~/.venvs/ail/bin/pip install ./ail-ci
~/.venvs/ail/bin/ail doctor --check
```

`--static` is refused on macOS (Apple ships no static C library). Libraries built with
`ail build --lib` are `.dylib` files.

## Windows

Two options:

- **WSL 2 (recommended).** In an administrator PowerShell run `wsl --install -d Ubuntu-24.04`,
  open the Ubuntu shell and follow the Linux steps there. Keep your files inside the Linux file
  system (`~`), not under `/mnt/c`: it is much faster and avoids line-ending problems.
- **Native, with MinGW-w64 or Zig.** Install Python 3.12 and a C compiler, then in PowerShell:

  ```powershell
  winget install MSYS2.MSYS2                  # then, in the MSYS2 UCRT64 shell:
  pacman -S mingw-w64-ucrt-x86_64-gcc
  $env:Path = "C:\msys64\ucrt64\bin;$env:Path"
  git clone https://github.com/J-KAMMA/ail-ci.git
  py -3 -m venv $HOME\ail-venv
  & $HOME\ail-venv\Scripts\pip install .\ail-ci
  & $HOME\ail-venv\Scripts\ail doctor --check
  ```

  Alternatively `pip install ".\ail-ci[zig]"` brings a `zig cc` and needs no MinGW. Set
  `PYTHONUTF8=1` for UTF-8 output. Native Windows is a supported CI target for a subset of the
  tests, not the full suite.

## Platforms

| Platform | State |
|---|---|
| Linux x86-64 (Ubuntu 24.04) | full test suite in CI; this guide was run here |
| Linux arm64 | representative subset in CI |
| macOS 14 arm64 | representative subset in CI |
| Windows (MinGW-w64, `windows-latest`) | representative subset in CI |

## Without installing (from the checkout)

The package only bundles the compiler sources, so you can also run them in place:

```sh
python3 AIL_CURRENT/ail_chatgpt.py doctor --check
python3 AIL_CURRENT/ail_chatgpt.py compile hello.py -o hello
```

(`compile` here is `ail build` in the installed command.) Use this when you work on the compiler
itself; the test tools live in `tools/`.

## Check the setup

```sh
ail doctor            # report only
ail doctor --check    # also compiles and runs a small program
```

`doctor` prints JSON. `python_supported` and `c_compiler_available` must both be `true`, and
with `--check` a working setup ends with `"build_check": {"status": "passed", ...}` and exit
status 0. `ail cache stats|path|clear` manages the per-user build cache (`$AIL_CACHE`, else the
platform cache directory).

## Troubleshooting

- **`The virtual environment was not created successfully ... ensurepip is not available`**
  (Debian/Ubuntu): `sudo apt install python3-venv`. For pip itself: `sudo apt install python3-pip`.
  `error: externally-managed-environment` means pip refuses to touch the system Python: use a
  virtual environment as above (or `pipx install ./ail-ci`).
- **`ail: no C compiler found`**, or `"c_compiler_available": false` in `doctor`: install `gcc`
  (`sudo apt install gcc`, `sudo dnf install gcc`, MinGW), the Xcode Command Line Tools on macOS,
  or `pip install "ail-lang[zig]"`; or set `PIPE_CC=/path/to/cc`. `PIPE_CC` must resolve on `PATH`.
- **`ail: command not found`** after installing: the virtual environment's `bin` directory
  (`Scripts` on Windows) is not on `PATH`; call it by full path or activate the environment.
- **`"python_supported": false`**, or an error saying Python 3.10 or newer is required: use a
  newer `python3`.
- **`error: output already exists`** (exit 2): `ail build` never overwrites the `-o` file. Delete
  it or choose another name.
- **`not in the subset: ...`** (exit 3): the program uses something AIL does not build. The
  message names it and usually gives `file:line:col` and a `write instead:` line. See
  [the tutorial](tutorial.md#a-refusal).
- **`import of 'numpy' is not available`** (exit 2): only the standard library modules AIL
  implements, and your own modules, can be imported. Third-party packages cannot.
- **`note: ... built on the general path (about 20x slower)`**: not an error. The program was
  built and behaves like CPython, but on the slower path. Add `--strict` to see why and how to
  fix it ([tutorial](tutorial.md#3-the-general-path-the-note-and---strict)).
- **`build cache disabled (owned by another user ...)`**: the cache directory belongs to someone
  else; set `AIL_CACHE` to a directory you own. Builds still work without the cache.
- **`hash mismatch: NAME`** from the test tools (checkout only): a file pinned in
  `AIL_CURRENT/manifest.d/` changed. Run `python3 tools/update_manifest.py`, then
  `python3 tools/update_manifest.py --check`.
- **pip says `Directory ... is not installable`**: you are in a directory without
  `pyproject.toml`; install from the repository root (`pip install ./ail-ci`).
