# lab/compare_cand: candidate compare-lab task

This directory holds one candidate task, `csv_rollup`, for the language comparison in `lab/compare`.
It is deliberately separate from `lab/compare/`: the ten-task table and everything under
`lab/compare/` are unchanged, and the owner decides later whether the candidate joins
`lab/compare/src/`.

Layout:

- `tasks/csv_rollup/spec.md`: the task.
- `tasks/csv_rollup/gen.py`: public, hidden and perf cases (`STDIN = True`).
- `tasks/csv_rollup/reference.py`: the CPython oracle.
- `src/csv_rollup/`: `main.c`, `main.rs`, `main.go`, `main.py`, `typed.py`.
- `toolchains.env`: a symlink to `../compare/toolchains.env`.
- `run.py`: loads `../compare/run_task.py` as a module, rebinds its task root to this directory, and
  calls `main()`.
- `RESULTS.md`: the measured table and the AIL path notes.

## Running

    python3 lab/compare_cand/run.py --task csv_rollup --smoke --out /tmp/r.json --langs python
    python3 lab/compare_cand/run.py --task csv_rollup --langs python,ail,ail-py --no-cases --out /tmp/r.json
    python3 lab/compare_cand/run.py --task csv_rollup --out /tmp/r.json

The last command checks every public and hidden case in every column and then measures the perf
input (4,000,000 rows). Build the table with:

    python3 lab/compare/merge.py /tmp/cand-results --json /tmp/cand.json

## Reusing `lab/compare/run_task.py`

`run_task.py` binds `HERE` at import time:

    HERE = Path(__file__).resolve().parent

`run.py` therefore loads it with `importlib`, sets `module.HERE` to `lab/compare_cand` **before**
calling `main()`, and also re-sets the derived `REPO` and `AIL` paths. `REPO` and `AIL` happen to be
correct already because `lab/compare_cand` and `lab/compare` are at the same depth, but they are
reassigned explicitly. No file under `lab/compare/` is edited.

## AIL paths and probes

`typed.py` builds on the typed path (`compile --strict` accepts it). `main.py` is the plain CPython
source used for the `python` column and for `ail-py`; its AIL build falls back to the general path
with this note:

    note: .../main.py:11:9: built on the general path (about 20x slower) because 'NAME' is read before it is assigned

Only the spelling differs between `main.py` and `typed.py` (annotations, string group keys, and a
manual byte scan instead of `bytes.split`/tuples); the algorithm is the same one-pass hash map and
sort.

`qty * price` beyond int64 was probed outside the task's ranges (with the range checks removed in a
throwaway /tmp program): CPython prints the exact big integer, while the AIL build stops loudly on
int64 overflow instead of printing a wrong number. The probe is not part of the cases. With the
task's own validation, out-of-range fields are counted bad before any multiplication, so the task
programs never reach that overflow.
