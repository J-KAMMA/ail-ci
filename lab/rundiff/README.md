# lab/rundiff

The census for `ail run --diff` (`docs/CLI.md`, `packaging/ail_lang/cli.py`): every program is built
once and run twice, natively and under CPython, with the same input, and the command reports whether
they agree.

`RESULTS.md` is the output of `census.py` and is committed with the job; regenerate it with:

    python3 lab/rundiff/census.py                 # both sets, rewrites RESULTS.md
    python3 lab/rundiff/census.py --compare       # only lab/compare/src/*/main.py public cases
    python3 lab/rundiff/census.py --corpus 50     # only the first 50 corpus/gdev programs
    python3 lab/rundiff/census.py --json rows.json

The two sets:

- `lab/compare/src/*/main.py`: the ten language-comparison programs, each on every **public** case of
  its task's `gen.py`, run as the task runs it (stdin when the task reads stdin, the case's arguments
  otherwise);
- the first 50 `corpus/gdev/*.py` programs in name order, with no arguments and empty stdin.

The outcomes are the command's own (`agree`, `differ`, `loud stop by design`, `timeout: …`). A
**differ** means the compiler and CPython disagree on the same input: it is a bug list for the
compiler, and this directory does not fix them.
