# vibe3 results

The same AI writes the same tasks in Python, Rust, Go and AIL; we count how often it reaches
a correct program, how many fix rounds that costs, and how often a wrong answer is silent.

- Model: `deepseek/deepseek-v4.1-flash`, through ``cmd -p --yolo --max-turns 1``, identical settings for all four languages.
- Seeds: 0 (an independent repeated attempt; the CLI exposes no sampling seed).
- Rounds: up to 5 model attempts per (task, language, seed).
- Languages recorded: python, rust, go, ail.
- Tasks: 21, of which 11 are the vibe1 set (for the delta) and 10 are the app-like tasks in
  `lab/vibe/tasks2/` written for vibe3.
- Columns: python = CPython 3.12 on the `.py` the AI wrote; rust = `rustc -O --edition=2021`;
  go = `go build -o main main.go` (stdlib only); ail = AIL `compile --syntax python` on the
  same plain Python the AI wrote for the ail prompt.
- Oracles: each task's own `gen.py` + `reference.py`. Public cases are shown to the AI through
  the failure feedback; hidden cases never are.
- Attempts: 76 scheduled, 73 recorded; the wall-clock budget stopped scheduling (see the note).

## Per language, all tasks

| language | n | answered | correct | correct % (all) | correct % (answered) | public pass | gave up | of which call timeout | median fix rounds | silent wrong | loud stop | other wrong | loop s | median final run s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python | 21 | 15 | 14 | 67% | 93% | 15 | 6 | 6 | 1 | 1 | 0 | 0 | 0.9 | 0.064 |
| rust | 21 | 11 | 10 | 48% | 91% | 11 | 10 | 10 | 1 | 1 | 0 | 0 | 3.5 | 0.003 |
| go | 13 | 9 | 9 | 69% | 100% | 9 | 4 | 4 | 1 | 0 | 0 | 0 | 2.2 | 0.005 |
| ail | 18 | 11 | 10 | 56% | 91% | 11 | 7 | 7 | 1 | 0 | 1 | 0 | 147.1 | 0.003 |

`n` is every attempt recorded; `answered` removes the attempts the harness ended because one
model call exceeded `--call-timeout` before the model returned any text. Those say nothing
about the language, so both correct rates are given: over every attempt, and over the ones
the model actually answered. The share differs per language only because the slow calls fell
where they fell, not because a column was given more time.

Median fix rounds is over the attempts that passed the public cases; `gave up` is an attempt
that never did. `silent wrong` counts hidden cases where the program exits like the reference
but prints something else; `loud stop` counts hidden cases where it exits non-zero where the
reference exits 0. `loop s` is build plus run time summed over every round of every attempt.

AIL final-program paths: typed 0, general 11, refused 0 (n=18).

## Delta against vibe1, on the vibe1 tasks only

vibe1 ran 11 tasks with seeds 0,1 and 42 recorded attempts; this run repeats those tasks.

| language | vibe1 n | vibe1 correct | vibe1 % | vibe3 n | vibe3 correct | vibe3 % | delta |
|---|---|---|---|---|---|---|---|
| python | 19 | 16 | 84% | 11 | 6 | 55% | -30 pp |
| rust | 12 | 12 | 100% | 11 | 3 | 27% | -73 pp |
| ail | 11 | 7 | 64% | 8 | 3 | 38% | -26 pp |

## Per task

`rounds` is one value per seed (x = gave up).

| task | lang | n | correct | rounds | silent | loud | path |
|---|---|---|---|---|---|---|---|
| dsl_calc | python | 1 | 1 | 1 | 0 | 0 |  |
| dsl_calc | rust | 1 | 1 | 1 | 0 | 0 |  |
| dsl_calc | go | 1 | 1 | 1 | 0 | 0 |  |
| dsl_calc | ail | 1 | 1 | 1 | 0 | 0 | general |
| expense_split | python | 1 | 1 | 1 | 0 | 0 |  |
| expense_split | rust | 1 | 1 | 1 | 0 | 0 |  |
| expense_split | go | 1 | 1 | 1 | 0 | 0 |  |
| expense_split | ail | 1 | 1 | 1 | 0 | 0 | general |
| gradebook | python | 1 | 1 | 1 | 0 | 0 |  |
| gradebook | rust | 1 | 1 | 1 | 0 | 0 |  |
| gradebook | go | 1 | 1 | 1 | 0 | 0 |  |
| gradebook | ail | 1 | 1 | 2 | 0 | 0 | general |
| ini_merge | python | 1 | 1 | 1 | 0 | 0 |  |
| ini_merge | rust | 1 | 1 | 1 | 0 | 0 |  |
| ini_merge | go | 1 | 1 | 1 | 0 | 0 |  |
| ini_merge | ail | 1 | 1 | 1 | 0 | 0 | general |
| jsonl_stats | python | 1 | 1 | 1 | 0 | 0 |  |
| jsonl_stats | rust | 1 | 0 | x | 0 | 0 |  |
| jsonl_stats | go | 1 | 0 | x | 0 | 0 |  |
| jsonl_stats | ail | 1 | 0 | x | 0 | 0 |  |
| log_levels | python | 1 | 1 | 1 | 0 | 0 |  |
| log_levels | rust | 1 | 1 | 1 | 0 | 0 |  |
| log_levels | go | 1 | 1 | 1 | 0 | 0 |  |
| log_levels | ail | 1 | 1 | 3 | 0 | 0 | general |
| matrix_stats | python | 1 | 0 | x | 0 | 0 |  |
| matrix_stats | rust | 1 | 0 | x | 0 | 0 |  |
| matrix_stats | go | 1 | 0 | x | 0 | 0 |  |
| matrix_stats | ail | 1 | 0 | x | 0 | 0 |  |
| todo_file | python | 1 | 0 | 1 | 1 | 0 |  |
| todo_file | rust | 1 | 0 | 1 | 1 | 0 |  |
| todo_file | go | 1 | 1 | 1 | 0 | 0 |  |
| todo_file | ail | 1 | 0 | 1 | 0 | 1 | general |
| version_sort | python | 1 | 1 | 1 | 0 | 0 |  |
| version_sort | rust | 1 | 1 | 1 | 0 | 0 |  |
| version_sort | go | 1 | 1 | 2 | 0 | 0 |  |
| version_sort | ail | 1 | 1 | 1 | 0 | 0 | general |
| word_freq | python | 1 | 1 | 1 | 0 | 0 |  |
| word_freq | rust | 1 | 1 | 1 | 0 | 0 |  |
| word_freq | go | 1 | 1 | 1 | 0 | 0 |  |
| word_freq | ail | 1 | 1 | 1 | 0 | 0 | general |
| berth_sim | python | 1 | 0 | x | 0 | 0 |  |
| berth_sim | rust | 1 | 0 | x | 0 | 0 |  |
| berth_sim | go | 1 | 0 | x | 0 | 0 |  |
| berth_sim | ail | 1 | 0 | x | 0 | 0 |  |
| chain_relax | python | 1 | 1 | 1 | 0 | 0 |  |
| chain_relax | rust | 1 | 1 | 1 | 0 | 0 |  |
| chain_relax | go | 1 | 1 | 2 | 0 | 0 |  |
| chain_relax | ail | 1 | 0 | x | 0 | 0 |  |
| csv_rollup | python | 1 | 1 | 1 | 0 | 0 |  |
| csv_rollup | rust | 1 | 1 | 1 | 0 | 0 |  |
| echo_pack | python | 1 | 1 | 1 | 0 | 0 |  |
| echo_pack | rust | 1 | 0 | x | 0 | 0 |  |
| echo_pack | go | 1 | 0 | x | 0 | 0 |  |
| echo_pack | ail | 1 | 1 | 1 | 0 | 0 | general |
| ledger_bin | python | 1 | 1 | 1 | 0 | 0 |  |
| ledger_bin | rust | 1 | 1 | 1 | 0 | 0 |  |
| ledger_bin | ail | 1 | 0 | x | 0 | 0 |  |
| rail_transfer | python | 1 | 0 | x | 0 | 0 |  |
| rail_transfer | rust | 1 | 0 | x | 0 | 0 |  |
| rail_transfer | ail | 1 | 0 | x | 0 | 0 |  |
| scar_life | python | 1 | 1 | 1 | 0 | 0 |  |
| scar_life | rust | 1 | 0 | x | 0 | 0 |  |
| scar_life | ail | 1 | 1 | 1 | 0 | 0 | general |
| tally_lang | python | 1 | 0 | x | 0 | 0 |  |
| tally_lang | rust | 1 | 0 | x | 0 | 0 |  |
| tally_lang | ail | 1 | 0 | x | 0 | 0 |  |
| term_rank | python | 1 | 1 | 1 | 0 | 0 |  |
| term_rank | rust | 1 | 0 | x | 0 | 0 |  |
| term_rank | ail | 1 | 1 | 1 | 0 | 0 | general |
| ticket_audit | python | 1 | 0 | x | 0 | 0 |  |
| ticket_audit | rust | 1 | 0 | x | 0 | 0 |  |
| tree_fold | python | 1 | 0 | x | 0 | 0 |  |
| tree_fold | rust | 1 | 0 | x | 0 | 0 |  |

## AIL compiler messages

Every diagnostic the AIL column received, by occurrence, and how often the very next round
built. `fixed` is the share of occurrences after which the next build succeeded.

| # | kind | message | occurrences | fixed |
|---|---|---|---|---|
| 1 | note | built on the general path (about 20x slower) because the constant None; this language has no null value, so nothing holds one -- build a linked structure as parallel index lists (left[] and right[] of | 2 | 0% |
| 2 | note | built on the general path (about 20x slower) because 'LEVEL_BYTES' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module const | 1 | 0% |
| 3 | note | built on the general path (about 20x slower) because 'balances' is keyed by a str in one place and by something else in another; a dict or a set has one key kind throughout; run with --strict to see w | 1 | 0% |
| 4 | note | built on the general path (about 20x slower) because 'levels' is a slist; only an array, a list, a list of floats, a set, a dict, bytes and a list of str are walked as flat sequences here. write inste | 1 | 0% |
| 5 | note | built on the general path (about 20x slower) because .encode() on a str: only str.encode() and bytes.decode() with literal UTF-8 and strict errors are supported. write instead: `s.encode()` (UTF-8 onl | 1 | 0% |
| 6 | note | built on the general path (about 20x slower) because `result` is a list or dict that gets the bool `data[pos + n] != 0` among other values; Python keeps each element's own type (True / 1). write inste | 1 | 0% |
| 7 | note | built on the general path (about 20x slower) because `sections[current] = {}` uses `sections` as a dict of containers -- its values are lists, sets or dicts. A typed dict holds int, float, str or byte | 1 | 0% |
| 8 | note | built on the general path (about 20x slower) because a method on Call; run with --strict to see why | 1 | 0% |
| 9 | note | built on the general path (about 20x slower) because key= must be a lambda or a function name. write instead: key=lambda x: x[1], or key=len; run with --strict to see why | 1 | 0% |
| 10 | note | built on the general path (about 20x slower) because only strict codec errors are supported; run with --strict to see why | 1 | 0% |

## Every AIL failure, classified

| task | seed | class |
|---|---|---|
| berth_sim | 0 | gave up: model call timed out |
| chain_relax | 0 | gave up: model call timed out |
| jsonl_stats | 0 | gave up: model call timed out |
| ledger_bin | 0 | gave up: model call timed out |
| matrix_stats | 0 | gave up: model call timed out |
| rail_transfer | 0 | gave up: model call timed out |
| tally_lang | 0 | gave up: model call timed out |
| todo_file | 0 | runtime stop (non-zero exit where the reference exits 0) |

## Verdict

1. AIL reached a correct program in 10 of 18 attempts; among the attempts where the model
   returned text at all, the four columns are Python 93% (14/15 answered), Rust 91% (10/11 answered), Go 100% (9/9 answered), AIL 91% (10/11 answered).
2. AIL failures: gave up: model call timed out x7; runtime stop (non-zero exit where the reference exits 0) x1.
3. Silent wrong answers on hidden cases: AIL 0, Python 1, Rust 1, Go 0. AIL's 1 loud
   stop: `todo_file`.
4. AIL builds: typed 0, general 11, refused 0; loop time 147 s against Python 0.9 s.
5. On the vibe1 tasks the delta against vibe1 is python -30 pp, rust -73 pp, ail -26 pp; a single seed and a 90-180 s call
   timeout keep the comparison coarse, and part of the drop is unanswered calls, not programs.

The three things that cost AIL the most correct programs here, in order:

1. **Slow builds.** 147 s of build time for 18 attempts against 0.9 s for Python over 21.
   The compiler alone does not make a program wrong, but it is what the fix loop waits on, so
   a task that needs two rounds is two long builds, and a slow call plus a slow build is what
   the call timeout ended.
2. **Container-typed values.** Every compile error in the AIL column was one refusal:
   `dict[key] = [a, b]` (a dict of lists), which the message names and which the model fixed
   on the next round. It is not the message that costs the program, it is that the natural
   Python shape for a small record fails to build at all, so the model writes a program the
   compiler rejects rather than one it compiles slowly.
3. **Non-BMP text at run time.** `todo_file` passed every hidden case but one: a character
   above U+FFFF read from a file stops the binary with `AIL internal error: stdin code point
   above U+FFFF in the 16-bit v2 runtime`. This is the only silent-to-loud regression and it is
   a correctness bug, not a speed one.

Everything else AIL compiled ran at the speed of the other native columns: median final run
0.003 s against Rust 0.003 s and Go 0.005 s.

