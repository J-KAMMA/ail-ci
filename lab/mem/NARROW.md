# fbnarrow1: how much of tree_fold's peak is 8-byte ints that would fit in 32 bits

Measure-only. No compiler, runtime or C-compiler file was changed. Base `origin/integ`,
branch `job-fbnarrow1_rr1-11060457` (re-run of fbnarrow1; the first run's agent was not logged in).
Everything here comes from `lab/mem/narrow_census.py` and is reproduced in `lab/mem/NARROW.json`.

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

tree_fold, sites that hold at least 1 MiB at the peak (MiB; `n` is the largest `len()` seen at that site):

| list (site) | max n | min value | max value | narrowest width | MiB at peak |
|---|---:|---:|---:|---|---:|
| `compact: v_w` (new w) | 2,954,720 | 0 | 3,397,567 | int32 | 32.0 |
| `compact: v_dep` (new dep) | 2,954,720 | 0 | 62 | int8 | 32.0 |
| `compact: v_par` (new par) | 2,954,720 | 0 | 2,954,718 | int32 | 32.0 |
| `compact: v_mp` (old→new map) | 3,000,000 (capacity) | – | – | int32 | 22.9 |
| `rebuild: v_w` (new w) | 3,000,000 | 0 | 3,397,567 | int32 | 32.0 |
| `rebuild: v_dep` (new dep) | 3,000,000 | 0 | 62 | int8 | 32.0 |
| `rebuild: v_par` (new par) | 3,000,000 | 0 | 2,999,998 | int32 | 32.0 |
| `do_prune: ir5` (`keep`, 0/1) | 3,000,000 | 0 | 1 | int8 | 32.0 |
| runtime-internal (site 0) | – | – | – | – | 22.9 |
| **total tracked at the peak** | | | | | **269.8** |

The `w` rows are int32 *on this input only*; `fold` merges chains (`wt += t.w[j]`), so another input
can exceed int32. `dep` is bounded by tree height (62 observed), `par`/`idx`/`cs`/`ord`/`ni`/`mp`/`keep`
by `n < 2^31`. The peak of int-list bytes (269.8 MiB) falls in `compact` (the `prune` op), not in `sort`:
at the sort peak the reconstructed `w`/`dep`/`par` have not all been allocated yet, and `cs`, `idx`,
`sub`, `ord`, `ni` peak below that 269.8 MiB total.

Against rc1's 384 MiB of "list buffers", 269.8 MiB of int buffers is **70%**; the remainder is the
`list[str]` `nm` field (`ail_pslist`, 24 B/element ≈ 72 MiB at 3M) plus its sarena text and the string
sort-key columns, which are not `list[int]` and are outside (a). The tracked sum is a capacity figure
(the tracker sees `cap`, not resident pages), as in rc1.

Other programs, same method (full table in `NARROW.json`, 38 rows ≥ 1 MiB): berth_sim 260.7 MiB
(six 32 MiB ints, widths int8…int32), echo_pack 244.1 MiB, ledger_bin 186.0 MiB (two key columns are
int64: 4,294,949,410), rail_transfer 23.9 MiB, term_rank 27.0 MiB, ticket_audit 1.4 MiB, chain_relax
2.3 MiB, scar_life/tally_lang < 0.1 MiB, and the four pointer-graph rc programs (binarytrees, cfold,
deriv, linkedlist, objscan, rbtree) have no `list[int]` buffers at all.

## (b) Scratch copy with int32 buffers, measured against the plain build

The edit (`lab/mem/treefold_i32.patch`) gives the local index lists `mp`, `ord` and `ni` an
`int32_t *p` list type with its own push/get/set/reserve/free; every operation used on them is
covered (append, index read/write, `len`, reserve, free). It is a subset of the int32-fitting lists
in (a): the `w`/`dep`/`par` fields and the rebuild temporaries share the T struct and the runtime's
`int64_t*` views, and converting them was not finished inside the time budget.

tree_fold, N = 3,000,000, plain vs edited:

| | plain | int32 subset | change |
|---|---:|---:|---:|
| peak RSS, median of 3 (KiB) | 414,956 | 414,228 | **−0.18%** |
| run instructions, `Ir` at N=300k | 893,478,193 | 925,441,599 | **+3.58%** |
| `rss_phases.py` peak, default (MiB) | 405.7 | 404.6 | −1.1 |
| `rss_phases.py` peak, fixed threshold (MiB) | 369.4 | 369.4 | 0.0 |
| stdout | identical on all 55 public+hidden cases and on the perf input | | |

The default peak barely moves because glibc keeps the freed int64 blocks on the brk heap; the
fixed-threshold column (live set) shows the narrowed lists are not resident at the RSS peak, which is
the same thing (a) says — at the sort peak the narrowed temporaries are already freed. Instructions
rise because the narrowed path adds a cast and a second bounds-checked accessor in place of the
inlined int64 form.

## Go/no-go

**no-go** by the stated rule: peak RSS falls 0.18% (needs ≥ 10%) and run instructions rise 3.58%
(needs no worse than +1%). This is the rule applied to the measured subset; the census shows the
larger remaining opportunity is `dep`+`par` (128 MiB of the 269.8 MiB peak set), which the scratch
edit did not convert. fbnarrow2-4 should not start on this evidence.

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

fbnarrow3 must support append, index read/write (including negative-index normalisation is not used
here), `len`, `for x in`, `copy()`/`slice`, passing a narrowed list to a function, and — for `idx` —
`sort(key=...)` reading other narrowed lists inside the key. Any list that cannot be proven in range
must stay int64 (e.g. `w`, which `fold` can push past int32).

## Records

- Tracked builds: 16/16 matched the plain build; no wrong output was observed, so the stop rule was
  not triggered on output.
- (b) lowers peak RSS by 0.18%, below the 5% stop threshold: no-go, stop.
- `git diff --stat origin/integ` touches `lab/mem/` only (`NARROW.md`, `NARROW.json`,
  `narrow_census.py`, `treefold_i32.patch`).
