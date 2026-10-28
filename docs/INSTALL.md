# Installing and running AIL

AIL compiles a typed subset of Python (and its own block syntax) to C. The compiler is in
`AIL_CURRENT/`; it needs Python to run and a C compiler to build an executable.

This guide was checked on Ubuntu 24.04 (the GitHub Actions runner), with Python 3.12.3 and
gcc 13.3.0. The macOS and Windows notes at the end are short pointers, not tested by this
repository's CI.

## Requirements

- **Python 3.10 or newer.** The test suite refuses older versions.
- **A C compiler on `PATH`.** CI uses `gcc`; AIL also looks for `cc` and `clang`.
- **git**, to get the code.

## Get the code

```sh
git clone https://github.com/J-KAMMA/ail-ci.git
cd ail-ci
```

Run the commands below from the repository root.

## Check the setup

```sh
python3 AIL_CURRENT/ail_chatgpt.py doctor
```

`doctor` prints JSON. For this guide's Linux runner it reported `python_supported: true`,
`c_compiler_available: true`, and the compiler path `/usr/bin/cc`. To also compile and run a
representative program, use:

```sh
python3 AIL_CURRENT/ail_chatgpt.py doctor --check
```

A working setup ends with `"status": "passed"`, `"phase": "run"`, and exit code 0.

## Compile and run a first program

The quickstart's hello program is at `AIL_CURRENT/language_examples/quickstart/hello.py`.
Check it without building C:

```sh
python3 AIL_CURRENT/ail_chatgpt.py check --syntax python AIL_CURRENT/language_examples/quickstart/hello.py
```

Compile it, then run the executable:

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --syntax python AIL_CURRENT/language_examples/quickstart/hello.py -o hello
./hello
```

The program prints:

```text
Hello, AIL!
```

`compile` prints a small JSON summary on success and writes the executable named by `-o`.
Continue with [the quickstart](QUICKSTART.md).

## Common problems

- **`Python 3.10 or newer is required`** — the running `python3` is too old. Use a newer
  interpreter and run the commands with it.
- **`c_compiler_available: false`** — no C compiler was found. `doctor` shows the path it
  checked. Install `gcc` (the package is called `gcc` on Ubuntu/Debian), or point `PIPE_CC` at
  a compiler.
- **`hash mismatch: NAME`** — a file pinned in `AIL_CURRENT/MANIFEST.json` changed. Run
  `python3 tools/update_manifest.py` and then `python3 tools/update_manifest.py --check`.
- **`error: output already exists`** — `compile` will not overwrite the executable. Choose a new
  `-o` name or remove the old file.
- **`not in the subset` or a `write instead:` line** — the program uses something outside the
  typed subset. The message names the construct and shows a supported rewrite. See
  [the quickstart](QUICKSTART.md).

## macOS

Install Python 3.10 or newer and the Xcode Command Line Tools
(`xcode-select --install`) so that `cc`/`clang` are available, then use the same commands.
This repository's CI has not run macOS.

## Windows via WSL

Install WSL 2 with an Ubuntu distribution, open its shell, and follow the Linux steps above
inside WSL. This guide has not been run on native Windows.
