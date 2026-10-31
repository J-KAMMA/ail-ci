# lab/compare

Language comparison: AIL against C, Rust, Go, Nim and CPython on ten programs, measured on a GitHub runner
(`compare-lab` workflow, manual). Timing on a laptop is too noisy to use, so the laptop only runs the smoke check.

- `src/<task>/main.{ail,c,rs,go,nim,py}`: the ten "novel task" programs of `experiments/llm-compare` (round 4 of the
  2026-10-14 run; every one of them passed that run's hidden tests and perf check). `main.ail` is the AIL source, `main.py`
  the CPython source; the `ail-py` column compiles that same `main.py` with AIL (`compile --syntax python`).
- `tasks/<task>/`: `spec.md`, `gen.py` (inputs; the perf case is used) and `reference.py` (the CPython oracle).
- `run_task.py`: builds and measures one task in every language, writes `result-<task>.json`.
- `merge.py`: tables (AIL first, ratio vs the best other language per metric) and one JSON.

Smoke check, any languages that are installed: `python3 lab/compare/run_task.py --task chain_relax --smoke --out /tmp/r.json`
(`--langs ail,c,python` limits it; `--smoke` uses a tiny public example instead of the perf input and times one run).

Compile-time note: the AIL compiler is Python, so a build also pays for loading it. `run_task.py` does not set
`PYTHONDONTWRITEBYTECODE` for the builds: the compiler's own bytecode is written beside its sources by the first (strict probe)
build, as a pip install ships it, and the timed cold builds (fresh `AIL_CACHE` and `TMPDIR`) reuse it. For the number without
bytecode run `PYTHONDONTWRITEBYTECODE=1 python3 tools/compile_phases.py <source>`; that tool also splits a build into the Python
front end and the gcc phases.

Full measurement (one command; manual trigger only, at most 4 task jobs at once):

    gh workflow run compare-lab -R J-KAMMA/ail-ci --ref integ            # all ten tasks
    gh workflow run compare-lab -R J-KAMMA/ail-ci --ref integ -f tasks='tree_fold tally_lang'

Each program also runs on every public and hidden case of its task (`gen.py`) and is compared with `reference.py`. Wall time is
the median of 5 runs; instructions come from callgrind (or perf_event if the runner has the counter). Toolchain versions are
pinned in `toolchains.env` and verified by `check_tools.py`; the report ends with a per-task scorecard (W/L per column) for
both AIL columns and shows whether each AIL build took the typed or the general path (and the compiler's fallback note).
