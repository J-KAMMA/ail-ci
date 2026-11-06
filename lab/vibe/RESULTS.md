# vibe1 results

Benchmark of the same model writing the same tasks in Python, Rust and AIL.

- Model: `deepseek-v4.1-flash` through `cmd` (`--effort low`), identical settings for all three languages.
- Seeds: 0, 1 (an independent repeated attempt; the CLI exposes no sampling seed).
- Tasks: 11 (`berth_sim, chain_relax, csv_rollup, echo_pack, ledger_bin, rail_transfer, scar_life, tally_lang, term_rank, ticket_audit, tree_fold`).
- Rounds: up to 5 model attempts per (task, language, seed).
- Columns: python = CPython 3.12 on the `.py` the model wrote; rust = `rustc -O --edition=2021`; ail = AIL `compile --syntax python` on the plain Python it wrote.
- Oracles: each task's own `gen.py` + `reference.py`; public cases are shown to the model, hidden cases are not.
- Attempts: 66 scheduled, 42 recorded (the wall-clock budget stopped scheduling; see the note below).

## Per language

| language | n | correct | correct % | public pass | gave up | median fix rounds | silent wrong | loud stop | other wrong | loop s | final run s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| python | 19 | 16 | 84% | 16 | 3 | 1 | 0 | 0 | 0 | 1.0 | 0.91 |
| rust | 12 | 12 | 100% | 12 | 0 | 1 | 0 | 0 | 0 | 5.3 | 0.04 |
| ail | 11 | 7 | 64% | 8 | 3 | 1 | 0 | 1 | 0 | 111.2 | 0.02 |

Median fix rounds is over the attempts that passed the public cases. `loop s` is build plus run time summed over every round of every attempt.

AIL final-program paths: typed 0, general 8, refused 0 (n=11).

## Per task

Rows are grouped by task and language; `rounds` lists one value per seed (x = gave up).

| task | lang | n | correct | rounds | silent | loud | path |
|---|---|---|---|---|---|---|---|
| berth_sim | python | 2 | 2 | 1,1 | 0 | 0 |  |
| berth_sim | rust | 2 | 2 | 1,1 | 0 | 0 |  |
| berth_sim | ail | 1 | 1 | 2 | 0 | 0 | general |
| chain_relax | python | 2 | 2 | 1,1 | 0 | 0 |  |
| chain_relax | rust | 1 | 1 | 1 | 0 | 0 |  |
| chain_relax | ail | 1 | 0 | x | 0 | 0 |  |
| csv_rollup | python | 1 | 1 | 1 | 0 | 0 |  |
| csv_rollup | rust | 1 | 1 | 1 | 0 | 0 |  |
| csv_rollup | ail | 1 | 1 | 1 | 0 | 0 | general |
| echo_pack | python | 2 | 2 | 1,1 | 0 | 0 |  |
| echo_pack | rust | 1 | 1 | 1 | 0 | 0 |  |
| echo_pack | ail | 1 | 1 | 1 | 0 | 0 | general |
| ledger_bin | python | 2 | 2 | 1,1 | 0 | 0 |  |
| ledger_bin | rust | 1 | 1 | 1 | 0 | 0 |  |
| ledger_bin | ail | 1 | 1 | 1 | 0 | 0 | general |
| rail_transfer | python | 2 | 1 | 1,x | 0 | 0 |  |
| rail_transfer | rust | 1 | 1 | 1 | 0 | 0 |  |
| rail_transfer | ail | 1 | 0 | x | 0 | 0 |  |
| scar_life | python | 2 | 1 | x,1 | 0 | 0 |  |
| scar_life | rust | 1 | 1 | 1 | 0 | 0 |  |
| scar_life | ail | 1 | 1 | 1 | 0 | 0 | general |
| tally_lang | python | 1 | 1 | 1 | 0 | 0 |  |
| tally_lang | rust | 1 | 1 | 1 | 0 | 0 |  |
| tally_lang | ail | 1 | 0 | 1 | 0 | 1 | general |
| term_rank | python | 2 | 2 | 1,1 | 0 | 0 |  |
| term_rank | rust | 1 | 1 | 1 | 0 | 0 |  |
| term_rank | ail | 1 | 1 | 1 | 0 | 0 | general |
| ticket_audit | python | 2 | 2 | 1,2 | 0 | 0 |  |
| ticket_audit | rust | 1 | 1 | 1 | 0 | 0 |  |
| ticket_audit | ail | 1 | 1 | 1 | 0 | 0 | general |
| tree_fold | python | 1 | 0 | x | 0 | 0 |  |
| tree_fold | rust | 1 | 1 | 1 | 0 | 0 |  |
| tree_fold | ail | 1 | 0 | x | 0 | 0 |  |

## AIL compiler errors

The ten most common compiler errors/notes the model received, and how often the next round built after that message.

| kind | message | occurrences | fixed next round | rate |
|---|---|---|---|---|
| note | cannot tell the type of element 0 of this tuple (an empty list or a value of unknown type); give it a name with an annotation | 3 | 0 | 0.00 |
| note | built on the general path (about 20x slower) because '_ail_l1l' is bound from popping rows of 1 fields in one place and 5 in another; a captured row has one arity, the same rule an ordinary list of records already follow | 1 | 0 | 0.00 |
| error | built on the general path (about 20x slower) because `accounts[rid] = [name, initial, True]` uses `accounts` as a dict of containers -- its values are lists, sets or dicts. A typed dict holds int, float, str or bytes val | 1 | 0 | 0.00 |
| error | built on the general path (about 20x slower) because `positions.get(key)` with one argument needs Optional values (s8): prove `key in positions` and read `positions[key]`, or pass the missing row as a second argument. Or | 1 | 0 | 0.00 |
| note | built on the general path (about 20x slower) because `{'type': 'when', 'line': lineno, 'bod...` mixes bools and numbers; Python keeps each value's own type and a number would print as 1 / 0. write instead: make every ope | 1 | 0 | 0.00 |
| error | built on the general path (about 20x slower) because class list comprehensions are unsupported; run with --strict to see why | 1 | 0 | 0.00 |
| error | built on the general path (about 20x slower) because comparing a str with a number; str and bytes are separate types here and a str is never a number -- this is refused by name rather than answered. write instead: compar | 1 | 0 | 0.00 |
| note | built on the general path (about 20x slower) because make_term returns bytes on one path and a number on another; run with --strict to see why | 1 | 0 | 0.00 |
| error | built on the general path (about 20x slower) because while-else is unsupported. write instead: a flag set before the loop, `done = True` when the loop ends normally, and `if done:` after it; run with --strict to see why | 1 | 0 | 0.00 |
| error | not in the subset: sys.stdin.buffer: only sys.stdin.read(), sys.stdin.readline() and sys.exit(<int>) are supported, and only as calls; sys.stdin.buffer used as a value is not (the general path could not build this progra | 1 | 1 | 1.00 |


### Shortfall and method notes

- Seed 0 is complete for all 11 tasks in all three languages. Seed 1 is partial: python 8/11,
  rust 1/11, ail 0/11. The wall-clock budget stopped scheduling, and the run kept only two
  attempts in flight; this is the cut the task allows ("cut seeds to 2 if the budget runs short").
- A model call that exceeded 300 s ends that attempt as "gave up". Three AIL attempts
  (`chain_relax`, `rail_transfer`, `tree_fold` seed 0) and three Python attempts
  (`scar_life` and `tree_fold` seed 0, `rail_transfer` seed 1) hit it; the model sometimes
  streams hundreds of KB of reasoning on the simulation tasks.
- One AIL measurement was re-run after the harness fix: `compile -o` refuses to overwrite an
  existing binary, so every fix round used to fail with `error: output already exists`. With the
  output removed before each build, `echo_pack` builds on round 1 (it had used all 5 rounds and
  was recorded as refused), and `tally_lang`'s new draw is wrong on one hidden case (loud stop).
- `ail_errors` counts what the model actually saw in this run; the "output already exists" rows
  from the old build are gone.

### Self-check probes

Run with `bash .agent/cmp.sh /tmp/probes/<p>.py "$PWD"` unless noted; every probe matched CPython
or was refused by name.

| probe | behaviour | result |
|---|---|---|
| `dictview.py` `x = d.items()` | default build | builds, same stdout; `--strict` refuses by name |
| `property_dec.py` `@property` | typed build | builds (also `--strict`), prints `3`, same stdout |
| `deco.py` custom decorator | both builds | refused by name: "only @staticmethod ... @cache are supported" |
| `multi.py` multiple inheritance | both builds | refused by name: "multiple inheritance in class C" |
| `lru.py`, `static.py` | both builds | build, same stdout |
| `gen.py`, `withyield.py`, `withyield2.py` | default build | build, same stdout; `--strict` refuses generators by name |
| `bigint.py` `1 << 200`, `overflow.py` int64 max + 1 | compile | refused by name, exit 2 |
| `overflow_argv.py` runtime `MAX + 1` | run | `OverflowError`, exit 1 |
| `sock.py`, `csvt.py` | both builds | build, same stdout (general path) |

## Verdict

1. AIL did not get the model to a correct program more often here: seed-0 correct is Python 9/11,
   Rust 11/11, AIL 7/11.
2. Silent-wrong was 0 in all three columns, so AIL's loud stops had nothing to convert; the single
   loud stop is AIL on `tally_lang` (hidden case exits non-zero where CPython exits 0).
3. AIL's builds cost 111 s against 1 s for CPython, and every AIL program that built took the
   general path (0 typed, 8 general, 0 refused): the annotations the model wrote did not reach it.
4. The AIL give-ups were 300 s call timeouts, not refusals; with the rebuild fixed, `echo_pack`
   builds first try.
5. The sample is one model over two seeds (seed 1 only 9/33 rows), so this is a first observation,
   not a ranking; on it, AIL is the weakest column.
