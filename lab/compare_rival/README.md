# lab/compare_rival

AIL against the tools that actually compete with it: the Python compilers **Nuitka, Cython, mypyc and Codon**
(and Mojo, when it installs without an account), plus the **PyPy** interpreter. The existing `lab/compare`
table has C, Rust, Go, Nim and CPython; this lab answers a narrower question: does AIL still win any column
against compilers of the same source language?

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
| `pypy` | `src/<task>/main.py` | nothing: `pypy3 -B main.py`, PyPy 7.3.23 (Python 3.11.15) |

`typed.py` imports the pure-Python `ail` runtime (`AIL_CURRENT/ail.py`); mypyc gets a `.pyi` stub for it in
the build directory and loads the real module at run time, so AIL's sources are never changed.

PyPy is the one row that compiles nothing, and it is the row that matters most for the owner's question
("is AIL clearly faster than PyPy on real Python code"). It gets two wall-time columns because its JIT needs
warm-up:

- **wall ms**: the median of 5 fresh processes, exactly like every other row. It includes interpreter start-up
  and the JIT compiling the hot loops from cold.
- **warm5 ms**: the 5th run **inside one process** (`pypy_warm.py`), timed around `exec` of the
  already-compiled source with a fresh globals dict, a fresh stdin over the same bytes and its own stdout
  file. That is what a long-lived process (a server, a notebook) sees.  The 5th run's stdout and exit status
  are checked against the same `reference.py`, so a warm run that computes something else cannot pass
  silently.

`compile s` is `-` for PyPy (nothing is compiled); its build-disk cell is the **interpreter install** and is
marked `interpreter` (`interpreter: true` in `results.json`), not a build artifact. `single exe` is `no`.

A refusal is a result: the first error line is kept in `results.json` and `RESULTS.md`. A tool that needs a
syntax-only patch gets one under `patches/<tool>/<task>/` and the row is marked `patched`; no algorithm or
data structure is changed, and AIL's sources are never touched. No patch was needed for this run.

## Measurement

`run.py` reuses `lab/compare/run_task.py`: the perf input and every public/hidden case come from the task's
`gen.py`, the oracle is its `reference.py`, wall time is the median of 5 runs, peak RSS is `/usr/bin/time -v`,
instructions are callgrind Ir (or `perf_event_open` when the runner exposes it), and each tool gets one cold
build in a fresh directory that also holds its caches (compile time, build disk, artifact size).

It does **not** use compare-lab's settings unchanged. The reductions are deliberate and are repeated in the
`settings` object of `results.json` and above the tables in `RESULTS.md`:

- one cold build instead of `BUILD_RUNS=3` (a Nuitka onefile build takes minutes);
- `RUN_TIMEOUT` 180 s instead of 1500 s, so a rival slower than 3 minutes is recorded as `timeout`, not a number;
  two rival rows are measured that way and would have a value under `run_task.py`'s timeout;
- `CASE_TIMEOUT` 30 s instead of 120 s;
- `CALLGRIND_TIMEOUT` 120 s instead of 7000 s;
- instructions are skipped when the wall time exceeds 4 s (callgrind is 50-100x slower);
- the public/hidden cases have a 240 s per-tool budget; unreached cases count as not matched.

The consequence is in the tables, not hidden: 59 of the 70 rows have `-` for instructions (37 of the 48 builds
that succeeded), and the instruction verdict rests on n=1. Restoring the reference timeouts means re-measuring
all ten tasks, not just regenerating the report. The two `timeout` rows are `cython-typed` on `scar_life` and
`tree_fold`.

"Single exe" means the artifact is one file that runs without the source tree. Cython's `--embed` binary is
one file but links `libpython3.12`; mypyc leaves a CPython extension module that needs the interpreter and the
`ail` runtime module, so it is not standalone.

## Safety

`safety/*.py` are five probes (int64 overflow, index out of range, negative index past the start, division by
zero, 100000-level recursion). Every tool builds and runs each one; stdout and exit status are compared with
CPython. The classification is the one `classify()` implements:

- `same as CPython`: same exit status and same stdout;
- `stops loudly`: non-zero exit that still reproduces a non-empty prefix of CPython's stdout;
- `stops loudly (stdout differs)`: non-zero exit whose stdout does not match that prefix (usually buffered away);
- `silently wrong output`: zero exit with a different answer — the number that matters most;
- `crash (signal N)`: killed by a signal.

## Running

Everything is installed outside the repository (versions in `toolchains.env`):

    python3 -m venv /tmp/rival-venv
    /tmp/rival-venv/bin/pip install -r <(printf 'cython==3.3.1\nmypy==2.4.1\nnuitka==4.3.4\nsetuptools==75.8.0\n')
    curl -fsSL https://github.com/exaloop/codon/releases/download/v0.20.6/codon-linux-x86_64.tar.gz \
      | tar xz -C /tmp/codon --strip-components=1     # Codon v0.20.6, Apache-2.0 (repo LICENSE)
    . lab/compare_rival/toolchains.env
    curl -fsSL -o pypy.tar.bz2 "$PYPY_TARBALL"
    echo "$PYPY_SHA256  pypy.tar.bz2" | sha256sum -c -
    mkdir -p /tmp/pypy && tar xjf pypy.tar.bz2 -C /tmp/pypy   # PyPy 7.3.23 / Python 3.11.15, MIT
    export PYPY=/tmp/pypy/pypy3.11-v7.3.23-linux64/bin/pypy3

`downloads.python.org/pypy` publishes no `.sha256` beside the tarball (checked 2026-11-08: `.sha256`,
`.md5`, `.b2sum`, `.asc` and `SHA256SUMS` are all 404, and there is no GitHub release asset). The pin in
`toolchains.env` is therefore the digest this job **downloaded and unpacked**, recorded so a re-upload is
detected rather than trusted; it is not a signature. The digest is
`16f9f56e82d1f4ec95a324c1a8cacfd78afc7f0656c0a809a18725ef4391453a`, and the unpacked tree is 154 MB --
that is the PyPy build-disk cell.

`compare-rival.yml` in this directory is the proposed workflow (one job per task, manual dispatch); it is not
under `.github/` because workers cannot push workflow files.

    python3 lab/compare_rival/run.py                       # all ten tasks and the safety probes
    python3 lab/compare_rival/run.py --tasks tree_fold --tools nuitka,cython-main
    python3 lab/compare_rival/run.py --safety

Results go to `results.json`; the tables go to `RESULTS.md`.

## Mojo

Not measured. Modular's installer asks for an account and an interactive licence, which the brief rules out
(no account, no secrets). The table says so.
