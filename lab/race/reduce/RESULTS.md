# fbred3: the reduction probes, measured

`docs/design/PAR_REDUCE.md` (fbred1) defined the exact shared-int reduction; fbred2 built the
runtime (`cruntime.PARRED`, `lab/race/reduce/RT.md`); fbred3 lowers the loop shape onto it. This
file records what moved and the measurements behind the done-check.

## What the compiler does now

* `parallel.py` (`_Body`) accepts `acc += e` / `acc -= e` on an int local of the enclosing
  function when the body touches `acc` nowhere else (no other store, no read), records
  `code -> '+' | '-'` in the loop's `.par` facts, and leaves every other refusal as it was.
  A body that also writes a list/bytearray element (`ys[i] = …`, `ys[i] += …`, an inner-loop
  `ys[i*K + j] = …`, conditional or aliased) stays refused in v1, as `PAR_REDUCE.md` requires:
  the re-run would repeat those writes, so the shape is approximated rather than exact.  The
  refusal names both and carries a `write instead:` line.
* `pyfunc._par_for` asks cruntime for the `PARRED` part; `pyfunc._par_outline` emits three things
  instead of one worker: the chunk function (`ail_red_fn`, per accumulator a `__int128` partial sum
  and its largest/smallest prefix, so a chunk-local overflow is not a trap), the re-run function
  (`ail_red_rerun`, the same loop with the ordinary checked add and `acc[]` updated after every
  step), and the call `ail_par_reduce_run(...)`. The call site keeps the accumulators in `_arK[]`
  and writes them back to the enclosing locals, so a read after the loop sees the sequential value.
* `typedpar.py` is unchanged: `sum(ex.map(f, xs))` and `sum(pool.map(f, xs))` already lower through
  `_ail_pmap` and are already exact (the map completes, in order, before the left-to-right checked
  sum, so a map exception after the overflow index wins over the overflow, as in the sequential
  map). Verified with p10/p14/p15 and with the extra `sum(map)` probes below.
* Scope in v1: the lowering is enabled on the Python surface only (`AIL_SURFACE=python`), so the
  AIL-surface `parallel for` keeps its old `t += i` refusal (`test_ail_parallel_for`). A float
  accumulator, an accumulator read in the body, a mixed `+=`/`-=` and `parallel for` inside `try`
  are refused by name with a `write instead:` line.

## Probe status (16 probes, `lab/race/reduce/`)

Built with `python3 -B AIL_CURRENT/ail_chatgpt.py compile <p> --syntax python -o <exe>` and run at
`AIL_THREADS` 1, 2, 4 and 16, three runs each, against the twin's measured output (`EXPECTED.md`).

| probe | before | now |
|---|---|---|
| `p01_small_sum` | refused (shared int) | `4950`, rc 0 — matches the twin at all 12 runs |
| `p02_negative_sum` | refused | `-15550`, rc 0 — matches |
| `p03_prefix_overflows_total_fits` | refused | empty, rc 1, `OverflowError: integer overflow in +` — matches the twin |
| `p04_overflow_first` | refused | empty, rc 1, `OverflowError: ... +` — matches |
| `p05_overflow_last` | refused | empty, rc 1, `OverflowError: ... +` — matches |
| `p06_exception_before_overflow` | refused | empty, rc 1, `ZeroDivisionError: integer division or modulo by zero` — matches |
| `p07_exception_after_overflow` | refused | empty, rc 1, `OverflowError: ... +` — matches (the stop beats the later exception) |
| `p08_try_catches_overflow` | refused (`try`) | **still refused**, by name: `parallel for: parallel for cannot be inside try; write instead: put the loop in its own fn` |
| `p09_two_accumulators` | refused | `4950 -4950`, rc 0 — matches |
| `p10_sum_map_exception_after_overflow` | built, matched | unchanged: `caught ZeroDivisionError 0` / `0` — matches |
| `p11_n_zero` | refused | `7`, rc 0 — matches |
| `p12_n_one` | refused | `12`, rc 0 — matches |
| `p13_more_workers_than_items` | refused | `3`, rc 0 — matches |
| `p14_sum_map_basic` | built, matched | unchanged: `285` — matches |
| `p15_sum_pool_map` | built, matched | unchanged: `285` — matches |
| `p16_min_overflow` | refused | empty, rc 1, `OverflowError: ... +` — matches |

So 12 probes move from refused to exactly their twin: 12 probes x 4 thread counts x 3 runs = 144
probe runs, all matching. The 3 `sum(map)` probes were already matching and still do. `p08` is
outside v1 (a `try` around the loop; the accumulator lives in the `try` frame struct, not a plain
local) and is refused by name with a `write instead:` line.

## Additional probes (self-check, in /tmp)

| probe | covers | default build | twin |
|---|---|---|---|
| `p_arg` | accumulator start from a function argument | matches at 1/2/4/16, 3 runs | `1232` |
| `p_list` | start from `xs[0]`, `acc += xs[1]` | matches | `130 100 3` |
| `p_dict` | start from a dict value | matches | `7` |
| `p_attr` | start from an attribute | matches | `50` |
| `p_negs` | negative range, `-=` | matches | `-5` |
| `p_inner` | `+=` inside a nested inner loop | matches | `120` |
| `p_bigchunk` | 2000 items, overflow at a chunk boundary | matches (loud `OverflowError`) | rc 1 |
| `p_excmany` | 1000 items, overflow at 500, exception at 900 | matches (overflow wins) | rc 1 |
| `p_sumover` | `sum(ex.map(f, range(4)))`, every result `BIG` | matches (loud `OverflowError` at every thread count) | rc 1 |
| `p_float` | float accumulator | refused: "must be an int local ... write instead:" | - |
| `p_read` | `out[i] = acc` in the body | refused: "read before the body assigns it" | - |
| `p_mixed` | `acc += i` and `acc -= 1` | refused: "read before the body assigns it" | - |
| `p_lwrite` | `acc += i` and `ys[i] = i` (the v1 boundary) | refused: "'acc' is a reduction ... also writes 'ys' ... write instead:" | - |
| `p_lwrite_aug` | `acc += i` and `ys[i] += 1` | refused the same way | - |
| `p_lwrite_inner` | `acc += i` and `ys[i*10 + j] = i + j` | refused the same way | - |
| `p_lwrite_byte` | `acc += i` and `bs[i] = 7` on a bytearray | refused the same way | - |
| `p_lwrite_cond` | `if i < 5: ys[i] = i` and `acc += i` | refused the same way | - |
| `p_lwrite_alias` | `ys = xs`, `acc += xs[i]` and `ys[i] = i` | refused the same way | - |
| `p_only_write` | `ys[i] = i * 2`, no reduction | builds, matches | `198` |
| `p_readonly` | `acc += xs[i]`, no write | builds, matches | `200` |
| `p_callee_aug` | a called fn does `x += j` on its parameter | builds, matches | `90` |

`AIL_UNIFIED_FORCE=1` (the general path) refuses every `par_range` program, before and after this
job: the general path has no `par_range`. That is unchanged and is not a regression.

## `program.c` hashes

`PYTHONHASHSEED=0 AIL_NO_CACHE=1 --debug-dir` on the 10 `lab/compare/src/*/typed.py` and the first
100 `lab/corpus/programs/**/*.py` (sorted), this tree against `HEAD` before the change:
**109 identical, 0 different, 1 builds no `program.c` in either tree** — the same 110 as `RT.md`.

## Race suite

`python3 lab/race/run.py`: **silent races 0**, **safe matched 16 of 17**, **safe GIL-free 16 of 17**
(34 rows: 14 racy, 17 safe, 3 hybrid). The counts are unchanged from the base; the reduction is
reached by no racy or safe probe (they are AIL syntax or use `threading` globals).

## Tests

`python3 AIL_CURRENT/test_ail_par_reduce.py` (3 tests, includes 144 matching runs and the five
refusals), `test_ail_parallel_for` (6), `test_ail_typed_parallel` (16, TSan and ASan/UBSan
included), `test_ail_race_probes` (31, one expected failure) all pass. `test_ail_files` (18, one
skipped) and `test_ail_corpus_findings3` (2) pass. `test_ail_safetynet` fails `S4_generators_gc`
identically on the base tree (checked by running the same test from a `git archive HEAD` export),
so it is not a regression from this job.

## Lowering size

`pyfunc.py`: 73 insertions, 12 deletions — `_par_for` (+3: the `PARRED` part request and the
wording), `_par_outline` (the accumulator skip, the int-local type check, the chunk/re-run
emission and the call site), and the `_red_stmt` text rewriter (`acc += e` -> `__int128` prefix
update or checked add, 19 lines including its docstring). That is over the 40-line note in the
brief; the extra is the rewriter and the second worker's declarations, and nothing outside
`_par_for`/`_par_outline` changed. `parallel.py` is +31/-1, no other compiler file changed.
