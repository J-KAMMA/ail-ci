# vibe3 results

The same AI writes the same tasks in Python, Rust, Go and AIL; we count how often it reaches
a correct program, how many fix rounds that costs, and how often a wrong answer is silent.

- Model: `claude-haiku-5-5` through the Claude Code CLI (`claude -p --tools "" --no-session-persistence`, one text-only
  turn per call, calls strictly one at a time), identical settings for all four languages.
  **This is not vibe1's model** (vibe1 used a free DeepSeek model through opencode), so the
  delta against vibe1 below is confounded by the model change; judge the four-language
  comparison inside this run, not the delta.
- Seeds: 0, 1 (an independent repeated attempt; the CLI exposes no sampling seed).
- Rounds: up to 5 model attempts per (task, language, seed).
- Languages recorded: python, rust, go, ail.
- Tasks: 21, of which 11 are the vibe1 set (for the delta) and 10 are the app-like tasks in
  `lab/vibe/tasks2/` written for vibe3.
- Toolchains: CPython 3.12, rustc -O, go1.27.3 (installed user-locally from go.dev), AIL = `AIL_CURRENT` of this branch.
- Columns: python = CPython 3.12 on the `.py` the AI wrote; rust = `rustc -O --edition=2021`;
  go = `go build -o main main.go` (stdlib only); ail = AIL `compile --syntax python` on the
  same plain Python the AI wrote for the ail prompt.
- Oracles: each task's own `gen.py` + `reference.py`. Public cases are shown to the AI through
  the failure feedback; hidden cases never are.
- Attempts: 168 recorded (21 tasks x 4 languages x 2 seeds); nothing was cut.

## Per language, all tasks

| language | n | answered | correct | correct % (all) | correct % (answered) | public pass | gave up | of which call timeout | median fix rounds | silent wrong | loud stop | other wrong | loop s | median final run s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python | 42 | 42 | 40 | 95% | 95% | 42 | 0 | 0 | 1.0 | 1 | 0 | 1 | 16.1 | 0.105 |
| rust | 42 | 42 | 40 | 95% | 95% | 42 | 0 | 0 | 1.0 | 0 | 0 | 7 | 30.2 | 0.004 |
| go | 42 | 42 | 40 | 95% | 95% | 42 | 0 | 0 | 1.0 | 2 | 0 | 0 | 22.7 | 0.009 |
| ail | 42 | 42 | 34 | 81% | 81% | 42 | 0 | 0 | 1.0 | 0 | 6 | 7 | 712.2 | 0.004 |

`n` is every attempt recorded; `answered` removes the attempts the harness ended because one
model call exceeded `--call-timeout` before the model returned any text. Those say nothing
about the language, so both correct rates are given: over every attempt, and over the ones
the model actually answered. The share differs per language only because the slow calls fell
where they fell, not because a column was given more time.

Median fix rounds is over the attempts that passed the public cases; `gave up` is an attempt
that never did. `silent wrong` counts hidden cases where the program exits like the reference
but prints something else; `loud stop` counts hidden cases where it exits non-zero where the
reference exits 0. `loop s` is build plus run time summed over every round of every attempt.

AIL final-program paths: typed 2, general 40, refused 0 (n=42).

## Delta against vibe1, on the vibe1 tasks only

vibe1 ran 11 tasks with seeds 0,1 and 42 recorded attempts; this run repeats those tasks.

| language | vibe1 n | vibe1 correct | vibe1 % | vibe3 n | vibe3 correct | vibe3 % | delta |
|---|---|---|---|---|---|---|---|
| python | 19 | 16 | 84% | 22 | 21 | 95% | +11 pp |
| rust | 12 | 12 | 100% | 22 | 21 | 95% | -5 pp |
| ail | 11 | 7 | 64% | 22 | 20 | 91% | +27 pp |

## Per task

`rounds` is one value per seed (x = gave up).

| task | lang | n | correct | rounds | silent | loud | path |
|---|---|---|---|---|---|---|---|
| dsl_calc | python | 2 | 2 | 1,1 | 0 | 0 | , |
| dsl_calc | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| dsl_calc | go | 2 | 2 | 1,1 | 0 | 0 | , |
| dsl_calc | ail | 2 | 1 | 1,1 | 0 | 1 | general,general |
| expense_split | python | 2 | 2 | 1,1 | 0 | 0 | , |
| expense_split | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| expense_split | go | 2 | 2 | 1,1 | 0 | 0 | , |
| expense_split | ail | 2 | 2 | 1,2 | 0 | 0 | general,general |
| gradebook | python | 2 | 2 | 1,1 | 0 | 0 | , |
| gradebook | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| gradebook | go | 2 | 2 | 1,1 | 0 | 0 | , |
| gradebook | ail | 2 | 2 | 2,2 | 0 | 0 | general,general |
| ini_merge | python | 2 | 2 | 1,1 | 0 | 0 | , |
| ini_merge | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| ini_merge | go | 2 | 2 | 1,1 | 0 | 0 | , |
| ini_merge | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| jsonl_stats | python | 2 | 2 | 1,1 | 0 | 0 | , |
| jsonl_stats | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| jsonl_stats | go | 2 | 0 | 1,1 | 2 | 0 | , |
| jsonl_stats | ail | 2 | 0 | 3,2 | 0 | 2 | general,general |
| log_levels | python | 2 | 2 | 1,1 | 0 | 0 | , |
| log_levels | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| log_levels | go | 2 | 2 | 1,1 | 0 | 0 | , |
| log_levels | ail | 2 | 2 | 2,3 | 0 | 0 | general,general |
| matrix_stats | python | 2 | 2 | 1,1 | 0 | 0 | , |
| matrix_stats | rust | 2 | 1 | 1,1 | 0 | 0 | , |
| matrix_stats | go | 2 | 2 | 1,1 | 0 | 0 | , |
| matrix_stats | ail | 2 | 1 | 1,1 | 0 | 0 | general,general |
| todo_file | python | 2 | 1 | 1,1 | 1 | 0 | , |
| todo_file | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| todo_file | go | 2 | 2 | 1,1 | 0 | 0 | , |
| todo_file | ail | 2 | 0 | 3,1 | 0 | 2 | general,general |
| version_sort | python | 2 | 2 | 1,1 | 0 | 0 | , |
| version_sort | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| version_sort | go | 2 | 2 | 1,1 | 0 | 0 | , |
| version_sort | ail | 2 | 2 | 2,1 | 0 | 0 | general,general |
| word_freq | python | 2 | 2 | 1,1 | 0 | 0 | , |
| word_freq | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| word_freq | go | 2 | 2 | 1,1 | 0 | 0 | , |
| word_freq | ail | 2 | 2 | 1,1 | 0 | 0 | typed,general |
| berth_sim | python | 2 | 2 | 1,1 | 0 | 0 | , |
| berth_sim | rust | 2 | 2 | 2,1 | 0 | 0 | , |
| berth_sim | go | 2 | 2 | 1,1 | 0 | 0 | , |
| berth_sim | ail | 2 | 2 | 2,1 | 0 | 0 | general,typed |
| chain_relax | python | 2 | 1 | 1,1 | 0 | 0 | , |
| chain_relax | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| chain_relax | go | 2 | 2 | 1,1 | 0 | 0 | , |
| chain_relax | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| csv_rollup | python | 2 | 2 | 1,1 | 0 | 0 | , |
| csv_rollup | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| csv_rollup | go | 2 | 2 | 1,1 | 0 | 0 | , |
| csv_rollup | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| echo_pack | python | 2 | 2 | 1,1 | 0 | 0 | , |
| echo_pack | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| echo_pack | go | 2 | 2 | 1,1 | 0 | 0 | , |
| echo_pack | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| ledger_bin | python | 2 | 2 | 1,1 | 0 | 0 | , |
| ledger_bin | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| ledger_bin | go | 2 | 2 | 1,1 | 0 | 0 | , |
| ledger_bin | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| rail_transfer | python | 2 | 2 | 1,1 | 0 | 0 | , |
| rail_transfer | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| rail_transfer | go | 2 | 2 | 1,1 | 0 | 0 | , |
| rail_transfer | ail | 2 | 2 | 1,2 | 0 | 0 | general,general |
| scar_life | python | 2 | 2 | 1,1 | 0 | 0 | , |
| scar_life | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| scar_life | go | 2 | 2 | 1,1 | 0 | 0 | , |
| scar_life | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| tally_lang | python | 2 | 2 | 1,1 | 0 | 0 | , |
| tally_lang | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| tally_lang | go | 2 | 2 | 1,1 | 0 | 0 | , |
| tally_lang | ail | 2 | 1 | 1,3 | 0 | 1 | general,general |
| term_rank | python | 2 | 2 | 1,1 | 0 | 0 | , |
| term_rank | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| term_rank | go | 2 | 2 | 1,1 | 0 | 0 | , |
| term_rank | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |
| ticket_audit | python | 2 | 2 | 1,1 | 0 | 0 | , |
| ticket_audit | rust | 2 | 1 | 1,1 | 0 | 0 | , |
| ticket_audit | go | 2 | 2 | 1,1 | 0 | 0 | , |
| ticket_audit | ail | 2 | 1 | 1,1 | 0 | 0 | general,general |
| tree_fold | python | 2 | 2 | 1,1 | 0 | 0 | , |
| tree_fold | rust | 2 | 2 | 1,1 | 0 | 0 | , |
| tree_fold | go | 2 | 2 | 1,1 | 0 | 0 | , |
| tree_fold | ail | 2 | 2 | 1,1 | 0 | 0 | general,general |

## AIL compiler messages

Every diagnostic the AIL column received, by occurrence, and how often the very next round
built. `fixed` is the share of occurrences after which the next build succeeded; it is only meaningful for
errors, since a `note` is printed on a build that worked and is never sent back to the model.

| # | kind | message | occurrences | fixed |
|---|---|---|---|---|
| 1 | error | not in the subset: json.loads(s): the type of the result is not declared here; write the type down: `data: dict[str, int] = json.loads(s)` (the types are int, float, str, bool, list[T], list[list[T]], | 2 | 100% |
| 2 | error | not in the subset: only strict codec errors are supported (the general path could not build this program either); general path: bytes.decode() with the error handler 'surrogateescape' on the general p | 2 | 100% |
| 3 | error | not in the subset: 'bal' is keyed by a str in one place and by something else in another; a dict or a set has one key kind throughout (the general path could not build this program either); general pa | 1 | 100% |
| 4 | error | not in the subset: 'out' is appended both a str and a non-str value; a list of str holds one kind of value throughout, exactly like a plain list of numbers -- keep it to one kind, or build two separat | 1 | 100% |
| 5 | error | not in the subset: 's' is a parameter and cannot be reassigned (the general path could not build this program either); general path: name 'Exception' is not defined | 1 | 100% |
| 6 | error | not in the subset: `items[vid] = [parts[2], False]` uses `items` as a dict of containers -- its values are lists, sets or dicts. A typed dict holds int, float, str or bytes values (an int-keyed dict o | 1 | 0% |
| 7 | error | not in the subset: `stats.get(name)` with one argument needs Optional values (s8): prove `name in stats` and read `stats[name]`, or pass the missing row as a second argument. Original refusal: only st | 1 | 100% |
| 8 | error | not in the subset: set(...) of str or bytes keys in a function built on the typed path; an unannotated set of str/bytes keys is left to the general path -- move it to a function of its own, or annotat | 1 | 100% |
| 9 | note | built on the general path (about 20x slower) because 's' is annotated str in the source, but the caller also supplies int; refusing rather than silently choosing one. write instead: indexing or iterat | 3 | 0% |
| 10 | note | built on the general path (about 20x slower) because comparing a str with a number; str and bytes are separate types here and a str is never a number -- this is refused by name rather than answered. w | 3 | 0% |

## Every AIL failure, classified

| task | seed | class |
|---|---|---|
| dsl_calc | 0 | runtime stop (non-zero exit where the reference exits 0) |
| jsonl_stats | 0 | runtime stop (non-zero exit where the reference exits 0) |
| jsonl_stats | 1 | runtime stop (non-zero exit where the reference exits 0) |
| matrix_stats | 0 | wrong output (exit status differs) |
| tally_lang | 0 | runtime stop (non-zero exit where the reference exits 0) |
| ticket_audit | 0 | wrong output (exit status differs) |
| todo_file | 0 | runtime stop (non-zero exit where the reference exits 0) |
| todo_file | 1 | runtime stop (non-zero exit where the reference exits 0) |

## Verdict

1. Correct programs (all public + hidden cases), 2 seeds x 21 tasks: Python 40/42, Rust 40/42, Go 40/42, AIL 34/42.
   Nobody gave up in any language; with this model the languages differ mostly in the first compile.
2. Fix rounds: Python and Go passed the public cases on round 1 in every attempt, Rust in all but one. AIL needed a
   second or third round in 12 of 42 attempts: 9 began with a compile refusal, 3 with a run-time failure on a public case
   (`UnboundLocalError ... heappush` in rail_transfer, `ValueError: re: the group did not take part in the match (None
   is not built)` in version_sort, a wrong output in berth_sim that Rust also produced).
3. Silent wrong answers on hidden cases: Python 1, Go 2, Rust 0, AIL 0. AIL stopped loudly 6 times where the
   CPython reference answers (int64 overflow in 4 attempts, a non-BMP character in 2); Go wrapped int64 silently twice.
4. Loop and run time: AIL final programs ran as fast as Rust (median 0.004 s vs 0.004 s) but 40 of 42 took the
   general path (about 20x slower than typed), and the AIL build loop cost 712 s against Python 16.1 s, Go 22.7 s,
   Rust 30.2 s over the same 42 attempts.

The three things that cost AIL correct programs, in order:

1. **int64 overflow stops (4 attempts, 3 tasks).** AIL's default is 64-bit ints with a loud `OverflowError`; the hidden
   cases expect CPython-sized integers at the boundary. Examples: `dsl_calc` `int64_edges` (`push 9223372036854775807`,
   `push 1`, `add`) stops with `OverflowError: integer overflow in +`; `jsonl_stats` sums amounts to 9223372036854775808;
   `tally_lang` multiplies 4294967295 * 4294967295. This is the owner-chosen int64 default working as designed (loud,
   never silent). Python passes because ints are unbounded; Go fails the same jsonl_stats case but silently (wraps).
2. **A runtime bug on non-BMP text (2 attempts, `todo_file`).** An emoji (3 x U+1F600 in `add 2 ...`) read from input stops
   the binary with `AIL internal error: decode: a code point above U+FFFF in the 16-bit v2 runtime`. The model cannot
   work around it and the message does not say how. It also hit a public case of `log_levels` seed 1 (fixed in round 3).
3. **Compile refusals that burn a round and a long rebuild (every AIL attempt that needed more than one round).**
   Examples: `json.loads(s): the type of the result is not declared here; write the type down` (jsonl_stats, both seeds);
   `items[vid] = [parts[2], False]` uses `items` as a dict of containers (todo_file); `bytes.decode(..., "surrogateescape")`
   (only strict codec errors are supported). All 10 refusals named the construct; 9 of 10 were fixed by the next build from
   the message alone, the 10th (dict of containers) one round later. Also 40 of 42 final programs landed on the general
   path (about 20x slower), signalled by 60 `note:` lines the model never sees.

Not AIL-specific: the other two AIL failures (`matrix_stats` seed 0, `ticket_audit` seed 0) are spec misreads that the Rust
column made identically (same hidden cases fail), so they are the model, not the language.

## What is and is not comparable

- **Model changed from vibe1.** vibe1: free DeepSeek via opencode; vibe3: `claude-haiku-5-5`. The vibe1 delta table mixes the
  model change with every compiler change since 2026-11-06 and cannot attribute the difference to AIL.
- **Two seeds, not three** (time budget). Seeds are independent repeated attempts, not sampling seeds. With 42 attempts per
  language one attempt is 2.4 percentage points; differences of one or two attempts are noise.
- **The model is strong here.** Python, Go and Rust all reach 95%; this task set barely separates them. A harder or
  larger set would be needed to see language differences beyond the first compile and the int64/unicode edges.
- Final run times are for tiny inputs, so they measure process start, not throughput. The speed claim is carried by the
  compare lab, not by this benchmark.
- The AIL column got `AIL_FOR_AI.md` (37 lines, unchanged). Facts it lacks, from the failures above: `json.loads` needs an
  annotated target; non-BMP text is not supported at run time; ints that can exceed int64 stop the program.
- The first vibe3 attempt (deepseek via Command Code, partial) is kept as `results3-deepseek-partial.json` and
  `RESULTS3-deepseek-partial.md`; it is not mixed into these numbers.

