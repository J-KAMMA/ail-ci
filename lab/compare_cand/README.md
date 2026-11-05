# lab/compare_cand: candidate compare-lab task

This directory holds one candidate task, `csv_rollup`, for the language comparison in `lab/compare`.
It is deliberately separate from `lab/compare/`: the ten-task table and everything under
`lab/compare/` are unchanged, and the owner decides later whether the candidate joins
`lab/compare/src/`. A second candidate, `log_scan` (an access-log summary CLI), lives beside it with
the same layout.

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
input (4,000,000 rows, 89 MB). Wrap it in `ulimit -v 1500000`: the `ail-py` column peaks near
640 MB and CPython near 450 MB. Build the table with:

    python3 lab/compare/merge.py /tmp/cand-results --json /tmp/cand.json

## Reusing `lab/compare/run_task.py`

`run_task.py` binds its paths at import time, on line 41:

    HERE = Path(__file__).resolve().parent

so it cannot be pointed at another directory by changing the working directory. `run.py` loads it
with `importlib`, sets `module.HERE = lab/compare_cand` **before** calling `main()`, and also
re-sets the derived `REPO` and `AIL`. `REPO` and `AIL` would be correct anyway because
`lab/compare_cand` and `lab/compare` sit at the same depth, but they are reassigned explicitly.
Everything else in `run_task.py` that depends on the directory (`load_task`, `make_case`,
`make_check_cases`, `reference_outputs` and `read_pins`) reads `HERE` at call time. No file under
`lab/compare/` is edited.

## AIL paths and probes

`typed.py` builds on the **typed** path (`compile --strict` accepts it). `main.py` is the plain
CPython source used for the `python` column and for `ail-py`; its AIL build falls back to the
**general** path with this note:

    note: lab/compare_cand/src/csv_rollup/main.py:29:9: built on the general path (about 20x slower)
    because the constant None; this language has no null value, so nothing holds one ...
    run with --strict to see why

Both files run the same one-pass algorithm (scan the bytes, hash map keyed by the pair, sort the
groups); they differ only in spelling:

- `typed.py` is annotated (`dict[str, int]`, `list[int]`, `bytes`, `-> int`) and uses `ail`'s
  `read_stdin_bytes`/`write_stdout_bytes`, string group keys (`region + ' ' + product`), and
  parallel index lists for the groups and regions.
- `main.py` is unannotated, uses `sys.stdin.buffer.read()`/`sys.stdout.write`, a dict keyed by
  `(region, product)` byte tuples, and `None` for a failed number parse (the cause of the general
  path).

Both scan the input with an index loop instead of `bytes.split` / `bytes.find`. That is a memory
and speed fix, not an algorithm change: `bytes.split(b'\n')` on the 4M-row perf input made the
compiled `ail-py` build peak at 1.39 GB and die with `AIL internal error: out of memory` under a
1.5 GB limit, and `bytes.find` in the compiled typed build is quadratic in the buffer (10k rows
0.32 s, 40k rows 5.37 s, 160k rows never finished), while the index scan is linear (40k rows
0.02 s, 400k rows 0.27 s, 4M rows 3.9 s).

## Integer probes (not part of the cases)

`qty * price` and the sums stay inside int64 for every input the spec allows (|qty| <= 1000,
price <= 10^7, and the perf input's sums are bounded). Beyond int64, AIL stops loudly in both the
default build and with `AIL_UNIFIED_FORCE=1`; it never prints a wrong number:

| probe (in `/tmp/probes/`) | CPython | AIL default | AIL `AIL_UNIFIED_FORCE=1` |
|---|---|---|---|
| `overflow_int64.py` (`4000...000 + 4000...000`, `* 4`) | prints 8000000000000000000 / 16000000000000000000, exit 0 | compile error: `int64 constant expression out of range`, exit 1 | same compile error, exit 1 |
| `overflow_argv.py` (args `4000000000000000000 4`) | prints both lines, exit 0 | prints the sum, then `OverflowError: integer overflow in *`, exit 1 | same, exit 1 |
| `overflow_parse.py` (`int('99999999999999999999')`) | prints the big value, exit 0 | compile error: `int64 constant expression out of range`, exit 1 | same, exit 1 |
| `parse_argv.py` (`int(argv[1])` with a 20-digit value) | prints the big value, exit 0 | `OverflowError: integer overflow in int()`, exit 1, no stdout | same, exit 1 |

The comparisons were run with `bash ~/tools/cmp.sh` (which passes no arguments, so the constant
forms) and by compiling `overflow_argv.py` / `parse_argv.py` with `ail_chatgpt.py compile --syntax
python` once per build. The task's own validation turns every out-of-range field into a bad line
before any multiplication, so the task programs never reach the overflow.
