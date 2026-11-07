# vibe2: three surfaces on the vibe1 tasks — results

Date: 2026-11-07. Harness: `lab/vibe/run.py` (extended, vibe1 arms unchanged). Tasks: the ten
`lab/compare/tasks/*` plus `csv_rollup` (11 tasks, 3 public + 6–88 hidden cases each). One file per
attempt, up to 5 fix rounds, compiler/runtime/public-test messages fed back verbatim; hidden cases
run only after every public case passes.

## Arms

| arm | surface | prompt note |
|---|---|---|
| `python` | CPython 3.12 | "Python 3.12" |
| `rust` | rustc -O --edition=2021 | "Rust 2021, std only" |
| `ail` | AIL Python syntax | `lab/vibe/AIL_FOR_AI.md` |
| `ail-strict` | AIL Python syntax | `lab/vibe2/STRICT_SPEC.md` (annotate everything, int64, refusals + rewrites) |
| `ail-new` | AIL-N (`lab/vibe2/NEW_SURFACE.md`) | translated mechanically to AIL Python by `lab/vibe2/translate.py` (line map kept), then compiled with AIL |

## Models and cut

- **Run:** `deepseek-v4.1-flash` (the free model this worker runs on), effort `low`.
- **Second free model named but not run:** `reflection/beam:free`. A one-line call via the same CLI
  returned text, so it is available; the run was **cut to one model and one seed** (seed 0) for
  budget. The harness now keys `results.json` by `(task, lang, seed, model)` and writes `summary`
  and `ail_errors` per model, so a second model can be appended without overwriting this one.
- `--call-timeout 240`, `-j 2`. Seed = an independent repeated attempt; the CLI exposes no
  sampling seed.

## Main table (deepseek-v4.1-flash, seed 0, n = 11 tasks per arm)

| arm | correct % | public % | median attempts (correct) | median fix rounds | silent-wrong | loud-stop | build+run s | reply tokens / correct | model timeouts | typed / general / refused |
|---|---|---|---|---|---|---|---|---|---|---|
| python | **81.8** (9) | 81.8 | 1 | 0 | 0 | 0 | 0.4 | 17,365 | 2 | – |
| rust | **63.6** (7) | 63.6 | 1 | 0 | 0 | 0 | 3.1 | 12,759 | 4 | – |
| ail | **72.7** (8) | 72.7 | 1 | 0 | 0 | 0 | 157.8 | 19,056 | 3 | 0 / 8 / 0 |
| ail-strict | **54.5** (6) | 63.6 | 1 | 0 | 0 | 1 | 81.1 | 22,378 | 4 | 2 / 5 / 0 |
| ail-new | **45.5** (5) | 45.5 | 2 | 1 | 0 | 0 | 102.8 | 29,452 | 6 | 0 / 5 / 0 |

"Correct" = every public and every hidden case matched CPython. `build+run s` is the harness's
`loop_seconds` (compilation + test runs); it **excludes model latency**, which is the larger cost.
`typed/general/refused` is the AIL build path of the submitted program.

**The dominant failure in every arm is the 240 s model-call timeout**, not a wrong program. Among
attempts that returned text, the arms are close:

| arm | completed attempts | correct among completed | correct % raw |
|---|---|---|---|
| python | 9 | 9 | 100.0 |
| rust | 7 | 7 | 100.0 |
| ail | 8 | 8 | 100.0 |
| ail-strict | 7 | 6 | 85.7 |
| ail-new | 5 | 5 | 100.0 |

## Per-task detail

`C` = correct, `T` = model call timed out (no program produced), `p` = public passed, hidden failed,
`x` = public failed.

| task | python | rust | ail | ail-strict | ail-new |
|---|---|---|---|---|---|
| berth_sim | C | T | T | T | C |
| chain_relax | C | C | C | C | T |
| csv_rollup | C | C | C | C | C |
| echo_pack | C | C | C | T | C |
| ledger_bin | C | C | C | C | T |
| rail_transfer | T | T | T | C | C |
| scar_life | C | C | C | C | C |
| tally_lang | T | C | T | T | T |
| term_rank | C | C | C | C | T |
| ticket_audit | C | T | C | p | T |
| tree_fold | C | T | C | T | T |

The only program-level failure in a non-`ail-new` arm: `ail-strict` `ticket_audit` passed all 3
public cases and 87/88 hidden cases, then **loud-stopped** on hidden `random4` (exit 6, expected 0)
— a rules/logic failure, not a build failure. No arm produced a silent-wrong result.

## `ail-new`: surface vs program logic

- **Surface-caused final failures: 0 of 6.** All six failed `ail-new` attempts ended because the
  model call timed out; none was caused by the translator or a syntax refusal.
- One surface error appeared and was **recovered**: `rail_transfer` round 1 returned
  `line 33: 'best' is a let binding and cannot be reassigned; declare it with var`; the message was
  fed back and round 2 passed all public and hidden cases. This exercises the fixed surface-error
  path end to end (before the fix this reply crashed the evaluator and recorded nothing).
- `ail-new` needed one more attempt on the programs it solved (median 2 attempts vs 1) and cost the
  most tokens per correct program (29,452 vs 12,759 for Rust).

## Compiler-message fix rates (AIL arms, per normalized message)

`results.json` records 25 compiler-message occurrences over 21 distinct normalized messages: 24
general-path notes (20 distinct messages) and one AIL-N surface error.

| kind | occurrences | fixed on next round | message (short) |
|---|---|---|---|
| note | 2 | – | `dict[int, list[int]]` annotation (`idx`): no typed rule |
| note | 2 | – | `Tree.weights` field type `array` unsupported |
| note | 2 | – | `sold[ev] = set()`: dict of containers |
| note | 2 | – | list parameter is read-only (`h.append()`) |
| note | 1 | – | `'ALLOWED'` read before assigned |
| note | 1 | – | `dict[bytes, int]` annotation (`counts`): no typed rule |
| note | 1 | – | list parameter is read-only (`parent`) |
| note | 1 | – | `Tree.subtree_weights` must take plain positional arguments |
| note | 1 | – | tuple used where a single value is needed |
| note | 1 | – | `format()` is not a builtin |
| note | 1 | – | class list comprehensions unsupported |
| note | 1 | – | comparing a str with a number |
| note | 1 | – | `normalize` returns bytes on one path, a number on another |
| note | 1 | – | `ord()`: crossing between a str and a code point |
| note | 1 | – | `parse_codes`: return paths disagree on a class instance |
| note | 1 | – | `parse_qty` returns a tuple on one path, a value on another |
| note | 1 | – | `parse_qty`: return paths disagree on a class instance |
| note | 1 | – | returning a set where the function returns a number |
| note | 1 | – | typed dict parameters are read-only |
| note | 1 | – | `unpack_data` returns a class on one path, something else on another |
| surface | 1 | 1.0 | `let` reassignment (`rail_transfer`) |

Every general-path line begins "built on the general path", so all 24 occurrences are `note`s, not
errors; the earlier version of this table mislabeled three of them (`Tree.weights`, the dict of
containers, `format()`) because it matched "unsupported"/"refuses" inside the message text. The
harness attributes a fix rate only to `error` and `surface` entries, so the note rows carry no fix
rate; the single surface error was fixed on the next round (1/1).

## Decision table (what the numbers support; no decision taken)

1. **`ail-new` beats `ail-strict` by more than the seed-to-seed spread on correct % or
   silent-wrong → change the surface.** Not supported. With one seed there is no seed-to-seed
   spread to compare; raw correct % is lower for `ail-new` (45.5 vs 54.5), and on completed
   attempts it is higher (100 vs 85.7, n = 5 vs 7). Neither difference is established as larger
   than noise.
2. **`ail-strict` reaches Rust's correct % → the gap is rules and messages; keep Python syntax.**
   Not supported. `ail-strict` 54.5 % vs Rust 63.6 % raw, 85.7 % vs 100 % on completed attempts.
3. **Neither → list the top 3 failure causes per arm.**
   - `python`: model call timeout (2); no program failures.
   - `rust`: model call timeout (4); no program failures.
   - `ail`: model call timeout (3); no program failures.
   - `ail-strict`: model call timeout (4); hidden loud stop (`ticket_audit`, exit 6 vs 0); no
     build refusals.
   - `ail-new`: model call timeout (6); one recovered surface error (`let` reassignment); no
     program-logic failure, no build refusal.

**Reading:** the surfaces did not fail the programs in this run — the 240 s call timeout did. The
data neither shows a surface win for `ail-new` nor a rule/message win for `ail-strict`; the syntax
question is not settled by one seed with this latency confound. A decisive run needs more seeds, the
second model, and a larger `--call-timeout` (or a latency-normalized metric) so that timeouts do not
mask program outcomes.

## Files

- `results.json` — the 55 rows (5 arms × 11 tasks × 1 model × seed 0), with `summary` and
  `ail_errors` keyed by model. `meta.started` is the first recorded completion in `run-flash.log`
  (10:24:28Z; the process start was not logged), `meta.last_completed` is 11:55:50Z, and
  `completed_attempts`/`scheduled_attempts` are 55 (one per row). Two `ail-new` rows (`berth_sim`,
  `echo_pack`) have no `program` field: their source was not retained by the earlier invocation,
  so the reference was cleared and `program_note` says so; the three retained `.nw` programs
  reproduce 0 failures.
- `translate.py`, `test_translate.py` — AIL-N translator and its CPython/AIL round-trip tests.
- `STRICT_SPEC.md`, `NEW_SURFACE.md` — the two prompt notes.
- `run-flash.log`, `run-flash2.log`, `run-flash3.log` — run logs.
