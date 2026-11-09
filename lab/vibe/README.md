# lab/vibe

The vibe-coding benchmark: the same AI writes the same tasks in Python, Rust, Go and AIL, and we
compare how often it ends with a correct program, how many fix rounds it needs, and how many wrong
answers are silent. The tasks are the ten compare-lab tasks plus `csv_rollup` (the vibe1 set) and
the ten app-like tasks written for vibe3 in `tasks2/`.

- `run.py` — the harness. It asks a model CLI for one file, builds and runs the task's public
  cases, sends the compiler or runtime error (or the first diff) back, up to 5 rounds, then runs
  the hidden cases. Every round is recorded in `results.json`.
- `AIL_FOR_AI.md` — the short language brief the model gets for the AIL column (at most 40
  lines: AIL is Python syntax, annotations help, it compiles to a binary, what it refuses and
  how the errors look).
- `results.json` — machine-readable results and the per-language summary.
- `RESULTS.md` — the report.
- `programs/` — the final file of each attempt, for audit.
- `vibe.yml` — a proposed repeatable workflow (kept here, not under `.github/`).

## Languages

| column | what runs |
|---|---|
| python | CPython 3.12 on the `.py` file the AI wrote |
| rust   | `rustc -O --edition=2021` on the `.rs` file the AI wrote |
| go     | `go build -o main main.go` (standard library only) on the `.go` file the AI wrote |
| ail    | AIL (`compile --syntax python`) on the plain Python the AI wrote for the ail prompt |

The task's own `reference.py` is the oracle. Public and hidden cases come from the task's
`gen.py`, the same cases `lab/compare/run_task.py` uses. Perf inputs are never run.

## Model

`run.py` calls a model CLI non-interactively and uses the same model and settings for all three
languages. It never reads or writes an API key: `cmd` takes `COMMAND_CODE_API_KEY` from the
environment, as the runner sets it.

    python3 lab/vibe/run.py --langs python --seeds 3 --minutes 90

Use `--cli opencode` for `opencode run`, or `--cli claude` (or `VIBE_CLI=claude`) for the Claude Code CLI
(`claude -p --tools ""`, one text-only turn; pass `--model claude-haiku-5-5`; run model calls with `--jobs 1`).
vibe3 (RESULTS3.md) used the claude adapter; Go is found on PATH (user-local `~/opt/go/bin`). `--effort` is passed to `cmd` as `--effort`.
`--jobs` is capped at 2, per the lab load rule.

## Numbers

Per attempt: `correct` (public and hidden), `public_pass`, `rounds_used` (attempts; max 5),
`gave_up`, `silent_wrong` (hidden case, same exit code as the reference, different output),
`loud_stop` (hidden case exits non-zero where the reference exits 0), `loop_seconds` (build plus
run time over all rounds) and `final_run_seconds` (public cases in the last round). For AIL the
final build's path is `typed`, `general` or `refused`, and the compiler messages the model got
are counted with whether the next round's build got past them.
