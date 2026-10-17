# LLM-written Python corpus: CPython versus AIL

A large set of small, deterministic stdin-to-stdout tasks, one Python program per task and model written by
free LLMs, and a differential check of each program: CPython 3.12 is the oracle, AIL (default path and
`AIL_IR=1`) is compared against it. No expected outputs exist anywhere; the point is to learn

* which Python features LLM-written programs use that AIL refuses by name (what to support next), and
* whether AIL ever runs such a program and prints something different (a bug).

## Layout

| path | content |
|---|---|
| `tasks.py`, `inputs_lib.py`, `make_tasks.py` | task descriptions, seeded input generators, the script that writes `tasks/` |
| `tasks/tNNN/` | `task.json` (id, category), `prompt.md` (the exact prompt), `in0..in2.txt` (stdin; small, medium, larger) |
| `generate.py` | asks an OpenCode model for one program per task (first reply only, 5 minute limit, empties recorded) |
| `programs/<model>/tNNN.py` | the extracted programs; `status.jsonl` records ok / empty / no-code / timeout per task |
| `check.py` | the differential check (copy of the `lab/fuzz` classification logic) |
| `results/results.jsonl` | one record per program x mode x input |
| `summarize.py`, `RESULTS.md` | counts per class and category, ranked refusal reasons, list of findings |
| `findings/` | every DIFF, crash and timeout with program, input, both outputs and `reproduce.sh`; minimal versions in `findings/min/` |

## Rerun

Python 3.12 is required (the input generators use nested f-string quotes).

```sh
cd lab/corpus
python3 make_tasks.py                      # regenerates tasks/ (deterministic)
# generation (free models, one request at a time per model; the models may run concurrently)
OPENCODE_BIN=/path/to/opencode python3 generate.py opencode/glm-5.3-flash-free --budget 21600
OPENCODE_BIN=/path/to/opencode python3 generate.py opencode/deepseek-v4.1-flash-free --budget 21600
# check (one process at a time; resumable)
python3 check.py --ail /path/to/ail_chatgpt.py
python3 summarize.py
```

Under WSL with the Windows CLI set `OPENCODE_BIN` to the `.exe` and `OPENCODE_DATA` to a Windows directory
for the CLI's own state; `generate.py` forwards it through `WSLENV`. `generate.py` shuffles the task order
with a fixed seed so every category is covered even when the time budget ends early.

## Classes

`same`, `refused` (compile-time refusal, exit 3, a named reason), `overflow` (declared 64-bit `int`),
`DIFF` (silent difference in stdout or exit code), `crash`, `timeout`, `skipped` (CPython timed out,
printed too much, or printed different output under two hash seeds). A program is classed `refused` if its
compile was refused; otherwise by the worst class over its three inputs. Only stdout and the exit code are
compared, not stderr text.

## State of this corpus

499 tasks were defined. The free tier stopped serving requests (\"free tier can only be used from within
OpenCode\") about 1.5 hours into generation, so only the first answers exist: see `RESULTS.md`, section
Generation, for the counts. `python3 generate.py MODEL --redo-empty` asks the missing ones again once the
service answers; `check.py` then only processes programs it has not seen. The AIL compiler used was a fixed
snapshot of one build, so all results come from the same version; rerun `check.py` against a newer build
into another `--out` directory to compare.

`findings/min/` holds hand-minimised reproductions (one directory per root cause, with `info.json`
saying what each mode does); `reduce.py` is the automatic line-deleting reducer used as a first step.
