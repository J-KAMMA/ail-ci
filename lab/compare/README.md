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
