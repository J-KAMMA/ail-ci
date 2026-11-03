# SPEC1: an opcode-specialized evaluator for `tally_lang` (measurement, 2026-11-02)

Status: **measurement only; no compiler or runtime change landed.** The task's stop rule is
"if the measured gain on `tally_lang` is below 1.2x, stop and report, and do not land the code".
The only prototype above 1.2x removes AIL's bounds and recursion checks, so it is not a legal
general compiler rule; the safe pieces together reach about 1.08x. Details and numbers below.

Base: `job-spec1-11030015` at `435d59c` (`staging:integ`). Machine: GitHub Actions runner,
4 logical x86-64 cores, 16 GB, gcc 13.3.0, CPython 3.12.3. Times are medians of 5 or more runs;
paired ratios alternate base and variant and take the median of the per-round ratio. A difference
below 3% is called a tie. The runner was shared with other agents, so absolute times move between
tables; only paired ratios and same-run comparisons are used for conclusions.

## 1. Profile first

`perf record` and `tools/icount.c` are both denied on this runner (`/proc/sys/kernel/
perf_event_paranoid` is 4 and `perf_event_open: Permission denied`); there is no
`valgrind`/callgrind. As in `docs/design/BEAT_C.md`, the fallback is `gprof` on the compiler's
generated C rebuilt with `-pg -g`:

```sh
python3 lab/beatc/profile.py --tasks tally_lang --runs 2 --out /tmp/spec1/profile.json
```

Raw results are kept as `lab/beatc/results/spec1-profile-tally.json`,
`lab/beatc/results/spec1-profile-echo.json` and `lab/beatc/results/spec1-measure.json`.

Two pinned-core runs on the perf input (`wall 4.21 s` under `-pg`, so shares only):

| function / line | share | removal bound `1/(1-s)` |
| --- | ---: | ---: |
| `ev` (the evaluator, whole function) | 83.9% | 6.2x |
| `ev` line 8105: `p.n_a[i]` span get | 8.1% | 1.09x |
| `ail_list_span_get` line 5173 (bounds compare) | 7.6% | 1.08x |
| `ail_list_span_get` line 5178 (load after check) | 6.9% | 1.07x |
| `ail_list_span_get` other lines in `ev` | 6.6% | 1.07x |
| `ev` line 8100: `++ail_depth` recursion check | 6.4% | 1.07x |
| `ev` line 8103: `p.n_op[i]` span get | 5.6% | 1.06x |
| `py_run__try1` (statement loop) | 16.1% | 1.19x |
| `py_run__try1` line 8290: arena `keep_roots` | 5.4% | 1.06x |
| `ev` line 8101: list pointer load | 4.5% | 1.05x |
| `ev` line 8107: `op == 100` compare | 5.1% | 1.05x |

Summed from the line table, the numeric-list span work (`ail_list_span_get`, its pointer/count
loads and the `p.n_*[i]` sites) is about 25% of the run, the recursion-depth bookkeeping about
6%, and the statement loop about 16%. The generic things named in the brief are therefore not
dict/str lookups or callbacks here: `tally_lang` builds on the typed path, and its cost is array
indexing, bounds checks, recursion and dispatch. That matches `BEAT_C`'s 0.65 share estimate for
`ev`, though the profiled whole-function share is larger (83.9%).

## 2. Prototype: what a specialization can and cannot remove

All prototypes were hand-edits of a `/tmp` copy of the generated `dbg/program.c`; the source tree
was not changed. `base` is the compiler's C with its normal `-O2` flags.

| variant | what it changes | 1-core median ms | paired gain | admissible? |
| --- | --- | ---: | ---: | --- |
| base | compiler output | 1556.8 | 1.000 | yes |
| `pop` | `popcnt` loop -> `__builtin_popcount` | 1519.0 | 1.027 | **yes**, a general idiom rule |
| `cache` | one shared span check for `n_op`/`n_a` when their counts are equal; same for `n_b` | 1463.1 | 1.054 | yes, bounds checks kept |
| `bounds` | direct `p->f_*[i]` in `ev` (checks removed) | 1360.2 | 1.139 | **no**, out-of-range reads become UB |
| `max` | `bounds` + no `ail_depth` + `pop` + no loop `keep_roots` | 1194.3 | 1.305 | **no**, removes recursion limit and arena resets |
| C reference | `gcc -O2 -std=c11` | 1147.5 | 1.36 vs base AIL | — |

The measured safe reach is the important result: `cache` (a safe one-check-per-index change)
is 1.054x; `pop` is 1.027x; together about 1.08x. That is far below `BEAT_C`'s assumed 40% of
the 2.86x bound (1.74x), and below the 1.2x stop rule. Even the **unsafe** `max` prototype is
still 4% slower than C (1194 ms vs 1148 ms), so deleting every runtime safety check would not
win this task.

`max` and `base` produce byte-identical stdout and exit status on all 76 `tally_lang` cases
(public, hidden, and the perf case) from `gen.py` against `reference.py`; the same is true of
`cache` and `pop`. That proves the edits are output-preserving on these cases, not that `max` is
a legal implementation: a program with an out-of-range index or a deeper recursion chain would
observe the missing checks.

`keep_roots` on its own made no measurable difference (paired 1.002); it only contributes to
`max` through code-layout/register effects. That is why the table does not treat it as an
independent safe win.

## 3. `echo_pack`

Profile (`lab/beatc/profile.py`, 2 runs): `pack` 92.6%, `ail_tab_order_append` 1.4%,
`ail_tab_hput` 1.4%, `ail_tab_hash_rearray` 1.4%. Lines: `ail_tab_hslot` about 46% across three
sites, `ail_bytes_get` 12.5%, `pack` 11.1%. Its hot path is the generic int-key hash table and
byte indexing, not an opcode evaluator.

Baseline on the same runner, median of 5 pinned-core runs:

| implementation | wall ms | peak RSS KiB | output |
| --- | ---: | ---: | --- |
| AIL default | 1077.4 | 354300 | reference, identical |
| C `-O2 -std=c11` | 613.4 | 178728 | reference, identical |

AIL/C is 1.76x here. The C reference uses a direct-mapped 2^20 table that overwrites head
entries and never resolves collisions; AIL must preserve a real `dict[int, int]` with insertion
order. Specializing the hash for `int` keys would not remove that algorithmic difference, and
the primary `tally_lang` result already stops the job, so no `echo_pack` prototype was landed.
Both builds matched the reference output on the perf input (`correct: true` in
`lab/beatc/results/spec1-measure.json`).

## 4. Cost of the prototype

No code landed, so the shipped cost is zero: generated C, binary, RSS, compile time and build
disk are identical to the base commit. For the record, the `/tmp` prototypes cost:

| item | base | `max` prototype |
| --- | ---: | ---: |
| generated C lines | 8824 | 8781 |
| binary bytes | 74648 | 74656 (+8) |
| gcc time (s) | 1.24 | 1.23 |
| peak RSS KiB (perf run) | 1492 | 1492 |
| AIL build time (s, empty cache) | 4.06 | 4.06 |

## 5. Decision and limitations

The task's stop rule applies: the admissible (safe and general) gain is about 1.08x, below 1.2x,
so **the code is not landed**. The documentation and measurements are the deliverable. The
unreachable part is not a missing tweak to a helper: the generated evaluator is already an
`if` chain that GCC turns into a jump table for binary opcodes, and the remaining cost is the
parallel int-list representation plus its bounds and recursion checks. Removing those needs an
index-range or read-only-field proof that the front end does not have, or a different node
layout, which is an algorithmic change, not specialization.

Not verified: instruction counts (hardware counter and callgrind both unavailable), the full
test suite (the task says not to run it locally), and the ten-task public/hidden matrix for a
landed build (there is no landed build). The 76-case `tally_lang` equality check and the
`measure.py` correctness bits were run and are reported above.
