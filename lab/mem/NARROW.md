# fbnarrow1: how much of tree_fold's peak is 8-byte ints that would fit in 32 bits

Measure-only. No compiler, runtime or C-compiler file was changed. Base `origin/integ`,
branch `job-fbnarrow1_rr1-11060751` (re-run of fbnarrow1; the first run's agent was not logged in).
Everything here comes from `lab/mem/narrow_census.py` and is reproduced in `lab/mem/NARROW.json`
(`census` and `emulate` sections).

## Method and limits

- 16/16 programs built through AIL's default path with `--debug-dir` (10 `lab/compare/src/*/typed.py`
  tasks, 6 `lab/rc/progs` programs): no general-path fallback, no build failure.
- In a **scratch copy** of each generated `program.c` only, every `ail_list_push`, `ail_list_reserve`,
  `ail_list_set`, direct `.p[.n++] =` append, `irN->p[i] =` store, list move
  (`ail_list_free(&A); A = B; B = (ail_list){0};`) and `ail_list_free` got a sequentially numbered
  site id inserted by the harness (text, never the compiler). Registration is also injected into the
  scratch copy's own `ail_list_push`/`ail_list_reserve`/`ail_list_free` bodies, so buffers allocated
  inside runtime helpers (`ail_list_copy`, keyed sort, …) are counted; they are attributed to a site
  when that site later touches the buffer, otherwise to site 0 ("runtime").
- Bookkeeping is per live **buffer pointer** (moves keep the pointer), so `t.w = w` and list returns
  do not lose bytes. Per site it records: number of buffers registered, largest `n`, smallest/largest
  stored value, store count, and the live list-buffer bytes at the peak of total list-buffer bytes.
  Width is the narrowest of int8/int16/int32/int64 that holds the observed `[min, max]`.
- The tracked build must print byte-identical stdout and the same exit status as the plain build.
  All 16 did (`match: true` in `NARROW.json`; tree_fold also on all 55 public+hidden cases plus perf).
- Peak RSS is `/usr/bin/time -v` "Maximum resident set size", median of 3, with
  `ulimit -v 1500000`. This runner has **no CPU PMU** (`/sys/bus/event_source/devices/cpu` is absent,
  `perf_event_open` has no hardware INSTRUCTIONS), so instruction counts are
  `valgrind --tool=callgrind` `Ir` on a 300,000-node input (not the 3M perf input), as the brief requires.
- tree_fold uses `gen.random_tree(random.Random(1), 3_000_000, chain=0.35)` plus the 17 perf ops
  (27,859,349 B input).

## (a) Bytes held by `list[int]` buffers at the peak, per list

tree_fold, the ten sites that hold bytes at the peak of total list-buffer bytes
(**292.67 MiB**; MiB; `n` is the largest `len()` seen at that site). Regenerated from the
`census` section of `NARROW.json`:

| list (site) | max n | min value | max value | narrowest width | MiB at peak |
|---|---:|---:|---:|---|---:|
| `parse_tree:(v_t) -> f_w` | 3,000,000 | 0 | 999,988 | int32 | 32.0 |
| `parse_tree:(v_t) -> f_dep` | 3,000,000 | 0 | 62 | int8 | 32.0 |
| `parse_tree:(v_t) -> f_par` | 3,000,000 | −1 | 2,999,998 | int32 | 32.0 |
| `rebuild:v_ord` | 3,000,000 | 0 | 2,999,999 | int32 | 32.0 |
| `rebuild:v_w` | 3,000,000 | 0 | 3,397,567 | int32 | 32.0 |
| `rebuild:v_dep` | 3,000,000 | 0 | 62 | int8 | 32.0 |
| `rebuild:v_par` | 3,000,000 | −1 | 2,999,998 | int32 | 32.0 |
| runtime-internal (site 0) | – | – | – | not measured | 22.89 |
| `rebuild:v_ni` | 3,000,000 | 0 | 2,999,999 | int32 | 22.89 |
| `do_sort:v__t5` | 2,999,999 | 1 | 2,999,999 | int32 | 22.89 |
| **total tracked at the peak** | | | | | **292.67** |

The peak is in the **sort/rebuild path**, not in `compact`: at that peak the `compact` locals and
`do_prune`'s `keep` site hold **0 bytes**, and the live set is `parse_tree`'s `w`/`dep`/`par` fields
plus `rebuild`'s `w`/`dep`/`par`/`ord`/`ni` and `do_sort`'s key column. `compact`/`prune` run later,
when those rebuild temporaries have been freed.

The `w` rows are int32 *on this input only*: `fold` merges chains (`wt += t.w[j]`), so another
input can exceed int32 (the 3.4M values in `rebuild:v_w` are already folded sums). `dep` is bounded
by tree height (62 observed; int32 is the provable bound, int8 is only this input's range), and
`par`/`idx`/`cs`/`ord`/`ni`/`mp`/`keep` by `n < 2^31`.

Against rc1's 384 MiB of "list buffers", 292.67 MiB of int buffers is **76.2%**. The remainder is
the `list[str]` `nm` field (`ail_pslist`, 24 B/element ≈ 68.7 MiB at 3M) plus its sarena text and the
string sort-key columns, which are not `list[int]` and are outside (a). The tracked sum is a capacity
figure (the tracker sees `cap`, not resident pages), as in rc1. **This is below the 80% done-check
for (a)**; the check is not met by this input.

Other programs, same method (39 rows ≥ 1 MiB in total, full table in `NARROW.json`):
berth_sim 260.67 MiB, echo_pack 244.14 MiB, ledger_bin 186.0 MiB (two key columns are int64:
4,294,949,410), term_rank 27.22 MiB, rail_transfer 23.95 MiB, ticket_audit 3.41 MiB, chain_relax
2.29 MiB, scar_life 0.03 MiB, tally_lang < 0.01 MiB, and the six pointer-graph rc programs
(binarytrees, cfold, deriv, linkedlist, objscan, rbtree) have no `list[int]` buffers at all.

## (b) Scratch copy with int32 buffers, measured against the plain build

The committed edit (`lab/mem/treefold_i32.patch`) gives an `int32_t *p` list type with its own
push/get/set/reserve/free to:

- the T struct fields `dep` and `par` (and their constructor/drop/move paths);
- the local `dep`/`par` temporaries in `compact`, `rebuild` and `fold`;
- `keep` (the `compact` 0/1 list), `mp`, `ord`, `ni` and `cs` (all index columns, `≤ n < 2^31`).

It deliberately leaves **every `w` list int64**, the T field and the `compact`/`rebuild`/`fold`
locals alike: `do_fold` accumulates `w[j]` into `wt` and pushes the sum, `sub` is a copy of that `w`,
and one sort-key column (`v__t11`, the negated folded `sub`) reaches −5.3e10 on the perf input, so no
bound smaller than int64 can be proven for any `w`-derived list. (The
earlier scratch edit that narrowed `f_w` was withdrawn: storing a folded weight in an int32 would
truncate silently on another input.)

tree_fold, N = 3,000,000, plain vs edited (from the `emulate` section of `NARROW.json`):

| | plain | int32 subset | change |
|---|---:|---:|---:|
| peak RSS, median of 3 (KiB) | 415,468 | 379,132 | **−8.75%** |
| run instructions, `Ir` at N=300k | 893,477,046 | 945,832,434 | **+5.86%** |
| `rss_phases.py` peak, default (MiB) | 406.2 | 370.3 | −35.9 |
| `rss_phases.py` peak, fixed threshold (MiB) | 369.4 | 335.1 | −34.3 |
| stdout | identical on all 55 public+hidden cases and on the perf input | | |

All 55 cases match (`cases: [...]`, `cases_match: true`) and the perf input matches
(`perf_match: true`). Instructions rise because the narrowed lists add a cast and a bounds-checked
accessor in place of the inlined int64 form.

## Go/no-go

**no-go** by the stated rule: peak RSS falls **8.75%** (needs ≥ 10%) and run instructions rise
**5.86%** (needs no worse than +1%). The drop is above the 5% stop threshold, so this is a measured
no-go rather than an early stop. fbnarrow2-4 should not start on this evidence: narrowing every
provably-int32 list (all of `dep`, `par`, `keep`, `mp`, `ord`, `ni`, `cs`) still leaves the `w`
columns int64, and the two live `w` sites (`parse_tree:(v_t)->f_w` and `rebuild:v_w`) account for
**64.0 MiB** of the 292.67 MiB peak set.

## Operations tree_fold applies to each narrowed list (fbnarrow3 requirements)

| list | append | index read | index write | len | `for x in` | sort / sorted | slicing / copy | passed to a function |
|---|---|---|---|---|---|---|---|---|
| `w` | yes (parse, compact, rebuild, fold) | yes (`subw`, total) | yes (`sub[t.par[i]] += sub[i]` on a copy) | yes | yes (`total`) | no | `t.w.copy()` | yes (`compact`, `rebuild`, T field) |
| `dep` | yes | yes (`do_print`, `do_cut`) | yes (`dep[j] -= 1`) | yes | no | no | no | yes (T field) |
| `par` | yes | yes (`subw`, `counts`, sort key) | yes (`par[j] = par[i]`) | yes | no | read as a sort key | `t.par.copy()` | yes (T field) |
| `idx` | comprehension | yes | no | yes | no | `idx.sort(key=lambda i: (par[i], -sub[i], nm[i], i))` | no | yes (`rebuild`) |
| `cs` | no | yes | yes (`cs[par[i]+1] += 1`, cumulative sum) | yes | no | no | `cs.copy()` (`pos`) | yes (`rebuild`) |
| `ord` | yes | yes (`ni[ord[k]] = k`) | no | yes | no | no | no | no |
| `ni` | `[0]*n` fill | yes | yes (`ni[ord[k]] = k`) | yes | no | no | no | no |
| `stack` | yes | yes (`stack[-1]`) | no | yes | no | no | no | no (pop returns) |
| `keep` | yes (`0/1` bool list) | yes (in `compact`) | no | yes | no | no | no | yes (`compact`) |
| `mp` | yes (`[0]*n`) | yes | yes (`mp[i] = …`) | yes | no | no | no | no |

fbnarrow3 must support append, index read/write (negative-index normalisation is not used here),
`len`, `for x in`, `copy()`/`slice`, passing a narrowed list to a function, and — for `idx` —
`sort(key=...)` reading other narrowed lists inside the key. **Any list that cannot be proven in
range must stay int64: in particular `w` (both the T field and every local), because `fold`
accumulates weights into it and can push it past int32.**

## Records

- Tracked builds: 16/16 matched the plain build; no wrong output was observed, so the stop rule was
  not triggered on output.
- (b) as committed: peak RSS −8.75% (≥ the 5% stop threshold but < the 10% go bar), instructions
  +5.86% (> the +1% bar) → no-go.
- (a) covers 292.67 / 384 MiB = 76.2% of rc1's list buffers, below the 80% done-check.
- `git diff --stat origin/integ` touches `lab/mem/` only (`NARROW.md`, `NARROW.json`,
  `narrow_census.py`, `treefold_i32.patch`).
