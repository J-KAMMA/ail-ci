# lab/compare_rival

AIL against the tools that actually compete with it: the Python compilers **Nuitka, Cython, mypyc and Codon**
(and Mojo, when it installs without an account). The existing `lab/compare` table has C, Rust, Go, Nim and
CPython; this lab answers a narrower question: does AIL still win any column against compilers of the same
source language?

## Sources (the same rule as compare-lab)

| tool | source | how it is built |
|---|---|---|
| `ail` | `src/<task>/typed.py` | `ail compile --syntax python` (the compare-lab AIL column) |
| `ail-py` | `src/<task>/main.py` | `ail compile --syntax python` |
| `cython-main` | `src/<task>/main.py` | `cython --embed -3`, then gcc against `python3-config --embed` |
| `cython-typed` | `src/<task>/typed.py` | the same, with `AIL_CURRENT` on `PYTHONPATH` for `from ail import ...` |
| `nuitka` | `src/<task>/main.py` | `python -m nuitka --onefile` |
| `mypyc` | `src/<task>/typed.py` | `python -m mypyc typed.py` plus a 3-line launcher |
| `codon` | `src/<task>/typed.py` | `codon build -release` |

`typed.py` imports the pure-Python `ail` runtime (`AIL_CURRENT/ail.py`); mypyc gets a `.pyi` stub for it in
the build directory and loads the real module at run time, so AIL's sources are never changed.

A refusal is a result: the first error line is kept in `results.json` and `RESULTS.md`. A tool that needs a
syntax-only patch gets one under `patches/<tool>/<task>/` and the row is marked `patched`; no algorithm or
data structure is changed, and AIL's sources are never touched. No patch was needed for this run.

## Measurement

`run.py` reuses `lab/compare/run_task.py`: the perf input and every public/hidden case come from the task's
`gen.py`, the oracle is its `reference.py`, wall time is the median of 5 runs, peak RSS is `/usr/bin/time -v`,
instructions are callgrind Ir (or `perf_event_open` when the runner exposes it), and each tool gets one cold
build in a fresh directory that also holds its caches (compile time, build disk, artifact size). The one
difference from compare-lab is one cold build instead of three: a Nuitka onefile build takes minutes.

"Single exe" means the artifact is one file that runs without the source tree. Cython's `--embed` binary is
one file but links `libpython3.12`; mypyc leaves a CPython extension module that needs the interpreter and the
`ail` runtime module, so it is not standalone.

## Safety

`safety/*.py` are five probes (int64 overflow, index out of range, negative index past the start, division by
zero, 100000-level recursion). Every tool builds and runs each one; stdout and exit status are compared with
CPython. A compiled program that exits 0 with a different answer is counted as **silently wrong**.

## Running

Everything is installed outside the repository (versions in `toolchains.env`):

    python3 -m venv /tmp/rival-venv
    /tmp/rival-venv/bin/pip install -r <(printf 'cython==3.3.1\nmypy==2.4.1\nnuitka==4.3.4\nsetuptools==75.8.0\n')
    curl -fsSL https://github.com/exaloop/codon/releases/download/v0.20.6/codon-linux-x86_64.tar.gz \
      | tar xz -C /tmp/codon --strip-components=1     # Codon v0.20.6, Apache-2.0 (repo LICENSE)

`compare-rival.yml` in this directory is the proposed workflow (one job per task, manual dispatch); it is not
under `.github/` because workers cannot push workflow files.

    python3 lab/compare_rival/run.py                       # all ten tasks and the safety probes
    python3 lab/compare_rival/run.py --tasks tree_fold --tools nuitka,cython-main
    python3 lab/compare_rival/run.py --safety

Results go to `results.json`; the tables go to `RESULTS.md`.

## Mojo

Not measured. Modular's installer asks for an account and an interactive licence, which the brief rules out
(no account, no secrets). The table says so.
