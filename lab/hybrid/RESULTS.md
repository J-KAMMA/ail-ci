# CPython hybrid correctness check

Run 2026-11-03 on the hybrid from `ail_cpython_hybrid.py` (schema `ail.cpython_hybrid/2`), checked against CPython 3.12.3. Each program was built into a fresh temporary directory and run with the same stdin and arguments; stdout, exit status and the last stderr line were compared, with a 60-second timeout per run.

The 10 compare-lab programs use the performance case and arguments from `lab/compare/run_task.py` (`make_case(..., smoke=False)`). The 30 corpus programs are the first 30 `lab/corpus/programs/*/t*.py` sorted by path, with stdin from `/dev/null`.

## Results

| program | native functions | Python functions | match |
| --- | --- | ---: | --- |
| `compare/berth_sim` | - | 1 | yes |
| `compare/chain_relax` | - | 3 | yes |
| `compare/echo_pack` | - | 4 | yes |
| `compare/ledger_bin` | - | 2 | yes |
| `compare/rail_transfer` | - | 1 | yes |
| `compare/scar_life` | - | 3 | yes |
| `compare/tally_lang` | - | 4 | yes |
| `compare/term_rank` | - | 2 | yes |
| `compare/ticket_audit` | - | 4 | yes |
| `compare/tree_fold` | - | 3 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t001.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t003.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t004.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t005.py` | - | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t008.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t009.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t010.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t012.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t014.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t015.py` | - | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t016.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t017.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t018.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t054.py` | - | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t055.py` | - | 4 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t065.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t067.py` | - | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t069.py` | - | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t078.py` | - | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t079.py` | reverse_words | 2 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t080.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t081.py` | - | 3 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t087.py` | - | 3 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t094.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t095.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t098.py` | - | 3 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t100.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t103.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t104.py` | - | 1 | yes |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t107.py` | - | 1 | yes |

**40/40 programs match CPython.** 1 function(s) were accelerated across the 40 programs.

## Mismatches

None.

## Functions kept in Python by the safety filters

These functions were reported by the analysis but not accelerated; the reason is the `_select`/`_unsafe_body` refusal (the same reason was already enforced before this check).

| program | function | reason |
| --- | --- | --- |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t005.py` | `longest_strictly_increasing_run` | indexing can raise |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t055.py` | `is_prime` | division or power can raise |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t055.py` | `next_prime` | a call can raise or have side effects |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t079.py` | `distinct_char_count` | a call can raise or have side effects |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t081.py` | `is_palindrome` | indexing can raise |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t087.py` | `compress` | a call can raise or have side effects |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t087.py` | `decompress` | a call can raise or have side effects |

## Wall time on the 10 compare-lab tasks

Milliseconds. `python` is `python3 main.py`, `hybrid` is `python3 DIR/<stem>_run.py`, `standalone` is the binary from `ail_chatgpt.py compile --syntax python` (with `--exact-int` for `rail_transfer` and `chain_relax`), all on the performance input. `berth_sim` and `chain_relax` are the median of 3 timed runs; the rest are one timed run (the 80-minute budget did not allow the median of 5 the task asks for). Every run used `ulimit -v 1500000`, so a run that the cap kills is recorded as a note rather than a time.

| task | python | hybrid | standalone | note |
| --- | ---: | ---: | ---: | --- |
| berth_sim | 16693.9 | 16691.5 | n/a | standalone out of memory under 1.5 GB (peak RSS 9.2 GB without the cap) |
| chain_relax | 11022.3 | 11150.0 | 103774.1 | |
| echo_pack | n/a | n/a | 4143.9 | CPython and hybrid `MemoryError` under 1.5 GB; standalone fits |
| ledger_bin | 22665.6 | 22128.2 | n/a | standalone out of memory |
| rail_transfer | 561.5 | 548.6 | 891.3 | |
| scar_life | 5457.8 | 5044.4 | n/a | standalone `OverflowError` (int64; needs `--exact-int`) |
| tally_lang | 11231.8 | 11005.8 | n/a | standalone compile refused (in the subset check, not the hybrid) |
| term_rank | 7842.3 | 7780.3 | n/a | standalone out of memory |
| ticket_audit | 7514.7 | 7430.1 | n/a | standalone out of memory |
| tree_fold | 17257.6 | 17258.6 | n/a | standalone compile refused (`re` with a non-literal pattern) |

The hybrid is within a few percent of CPython on every task, which is expected: none of these functions passed the typed-path selection, so the hybrid runs the same Python code with the extension imported but unused.

## Instruction counts

Unavailable. `tools/icount.c` compiled, but its self-test exited 1: `perf_event_open: Permission denied`.

## `program.c` stability against `origin/integ`

`--debug-dir DIR/program.c` from a standalone build of each `main.py`, HEAD against a worktree at `origin/integ` (`095e0321`), same flags. All 10 agree.

| task | result |
| --- | --- |
| berth_sim | identical (`sha256:3da23d92d9e048f8`) |
| chain_relax | identical (`sha256:279a6748fc3ef4c9`) |
| echo_pack | identical (`sha256:f4ce1d5d242e2620`) |
| ledger_bin | identical (`sha256:7493f9754a4350dc`) |
| rail_transfer | identical (`sha256:b32b281c91289715`) |
| scar_life | identical (`sha256:69041e7eabf9449f`) |
| tally_lang | identical refusal, no `program.c` on either tree (general path cannot build this `main.py`) |
| term_rank | identical (`sha256:6956fb33949c90b4`) |
| ticket_audit | identical (`sha256:9b763de5e4222ea9`) |
| tree_fold | identical refusal, no `program.c` on either tree (`re` with a non-literal pattern) |
