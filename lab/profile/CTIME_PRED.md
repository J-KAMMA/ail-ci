# ctpred1: the cacheable fraction of the `pyfunc` type/kind predicates

Base: export of `staging:integ` (task commit `aea334f`). Measurement only: no compiler file is
edited, and the probe does not change the generated C (section 6).

The question is the number ctimes2 could not measure (`lab/profile/CTIME_CUT.md`): of the own
time the `pyfunc` predicates spend, how much is a repeat of an earlier call **on the same node
and arguments that returns the same answer**?  That is the only part a memo cache can remove.

## 1. The price carried from ctimes2 (speed-claims rule)

| measure | value |
|---|---:|
| predicate own time, pooled 10 compare tasks (`CTIME_FE.md`) | 6.731 s |
| pooled cold wall (`CTIME_FE.md`) | 30.795 s |
| share | 21.9% |
| full Amdahl bound | 1.280x |
| halved (repo rule) | 1.123x |
| tasks at or above 1.10x halved | berth_sim 1.200, chain_relax 1.205, echo_pack 1.320, ledger_bin 1.108 |

That bound assumes the predicates become **free**.  A cache removes only repeated calls with an
unchanged answer and adds a lookup to every call, so the real projection is
`1 / (1 - (f * own - L * n) / wall)`, halved, where `f` is the cacheable fraction of predicate
own time, `n` the number of calls and `L` the lookup cost.

## 2. How it was measured

`lab/profile/pred_probe.py` wraps eight predicates from outside, in the compiler child process,
through a `sitecustomize` in a temp directory (`pyfunc.py` untouched): `_etype`, `_is_str_expr`,
`_is_slist_expr`, `_map_kind`, `_is_bytes_expr`, `_is_owned_bytes_call`, `Ctx.type_of` and
`_param_kinds`.  Per call it records

* a key: `id()` of each non-primitive argument (AST node, `Ctx`, function) plus the value of each
  primitive one, so `type_of` keys on `(id(ctx), name)` and the predicates on `(id(node), id(ctx))`;
  every object is kept alive for the run, so ids are not reused;
* the own time (nested calls subtracted from the enclosing call, the cProfile convention);
* `repr(result)` truncated to 200 characters (primitives kept as values).

A *repeat* is a call whose key was seen before.  A *changed* repeat is one whose answer differs
from the first answer for that key: the predicate reads state that changes during the build, and a
plain memo is wrong for it.  *Cacheable* seconds are the own time of repeats with an unchanged
answer.

Runs: the 10 `lab/compare/src/*/main.ail` builds and the first 200 sorted
`lab/corpus/programs/*/*.py` (11 of the 200 are refused by name, so they make no calls).  All runs
used `ulimit -v 1500000`.

The wrapper inflates a predicate's own time (a few microseconds per call), so the cacheable
**fraction** `f = cacheable / probe own` is applied to the real per-task own time from
`CTIME_FE.json`; for a task where the row is not in the top 25 the predicate's pooled
`FE own / probe own` ratio fills the gap.  `n` and the repeats are counted, not scaled.

## 3. Lookup cost

`timeit`, dict keyed by `id(node)` (`d.get((id(node), id(ctx)))`, 2,000,000 iterations, best of 5):

| form | ns/call |
|---|---:|
| prebuilt key `d.get(k)` | 32.1 |
| `d[k]` | 29.3 |
| build key then `d.get(k2)` | 124.9 |
| `d.get((id(node), id(ctx)))` | 123.6 |

**L = 1.25e-7 s per call** (key construction included), used below.

## 4. Per predicate (10 compare tasks)

`calls`, `repeats`, `changed` are pooled over the ten tasks; `changed (200 corpus)` adds the corpus
programs; `cacheable s` is on the `CTIME_FE` own-time scale; `FE own` is the pooled
`CTIME_FE.json` top-row own time.  A predicate is **eligible** only when it has 0 changed repeats
over all 210 inputs.

| predicate | calls | repeats | repeat share | changed | changed (200 corpus) | changed (210) | cacheable s | FE own s | eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:--:|
| `_etype` | 622,726 | 570,104 | 91.6% | 96,810 | 124,164 | 220,974 | 1.159 | 1.812 | no |
| `_is_str_expr` | 469,022 | 417,615 | 89.0% | 800 | 11,335 | 12,135 | 0.739 | 0.852 | no |
| `_is_slist_expr` | 353,534 | 304,000 | 86.0% | 65 | 1,142 | 1,207 | 0.239 | 0.281 | no |
| `_map_kind` | 530,263 | 479,080 | 90.4% | 0 | 0 | 0 | 0.124 | 0.110 | **yes** |
| `_is_bytes_expr` | 116,013 | 94,680 | 81.6% | 879 | 1,104 | 1,983 | 0.149 | 0.150 | no |
| `_is_owned_bytes_call` | 489,358 | 431,750 | 88.2% | 0 | 0 | 0 | 0.161 | 0.141 | **yes** |
| `Ctx.type_of` | 1,122,902 | 1,115,802 | 99.4% | 428,396 | 394,526 | 822,922 | 0.081 | 0.048 | no |
| `_param_kinds` | 546 | 0 | 0.0% | 0 | 0 | 0 | 0.000 | 0.092 | **yes** |

The four biggest rows (`_etype`, `_is_str_expr`, `Ctx.type_of`, and part of `_is_slist_expr` /
`_is_bytes_expr`) all change answers during the build: caching them plainly would return a stale
kind.  `_etype` alone changes 221k times over the 210 inputs.  `_param_kinds` has no repeats at all,
so a cache there is pure lookup cost.

## 5. Per task: saving and projection

`saving` = cacheable seconds of the **eligible** predicates minus `L * calls` of those predicates.
`projection = 1 / (1 - saving / wall)`; `halved = 1 + (projection - 1) / 2`.  The last two columns
repeat the exercise for *all eight* predicates (including those with changed repeats), as an
upper bound that a plain cache cannot actually reach.

| task | wall s | saving (listed) s | projection | halved | saving (all) s | halved (all) |
|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 8.702 | 0.0810 | 1.0094 | 1.0047 | 1.0430 | 1.0681 |
| chain_relax | 1.433 | 0.0100 | 1.0070 | 1.0035 | 0.1446 | 1.0561 |
| echo_pack | 2.337 | 0.0242 | 1.0105 | 1.0052 | 0.4635 | 1.1237 |
| ledger_bin | 2.437 | 0.0089 | 1.0037 | 1.0018 | 0.1674 | 1.0369 |
| rail_transfer | 2.084 | 0.0043 | 1.0021 | 1.0010 | 0.0745 | 1.0185 |
| scar_life | 1.641 | 0.0048 | 1.0029 | 1.0015 | 0.0415 | 1.0130 |
| tally_lang | 2.495 | 0.0038 | 1.0015 | 1.0008 | 0.0315 | 1.0064 |
| term_rank | 2.351 | 0.0048 | 1.0021 | 1.0010 | 0.0829 | 1.0183 |
| ticket_audit | 3.584 | 0.0056 | 1.0016 | 1.0008 | 0.0490 | 1.0069 |
| tree_fold | 3.731 | 0.0099 | 1.0027 | 1.0013 | 0.0908 | 1.0125 |
| **pooled** | **30.795** | **0.157** | **1.0051** | **1.0026** | **2.190** | **1.038** |

Eligible predicates total 1,020,167 calls; the lookup they add costs `1.25e-7 * 1,020,167 =
0.1275 s` pooled, against 0.285 s of cacheable own time.  Even the unreachable all-predicate upper
bound (2.651 s cacheable, 0.463 s of lookup) only reaches 1.038x halved pooled.

## 6. Stop rule: the wrapper observes only

Ten cold builds of `lab/compare/src/*/main.ail` with and without the probe, same
`PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, `AIL_SERVER=0`, fresh `AIL_CACHE` and `--debug-dir`:
`sha256(program.c)` is identical for **10/10** tasks
(berth_sim `8007891e…`, chain_relax `865f18c0…`, echo_pack `8c63efc0…`, ledger_bin `c111f240…`,
rail_transfer `2943c242…`, scar_life `4e9492d8…`, tally_lang `0b28da4d…`, term_rank `5c5ed035…`,
ticket_audit `16def672…`, tree_fold `36cc65e7…`).

## 7. Decision

**No-go.**  Under the go rule (halved projection at least 1.03x on at least 3 tasks), the eligible
predicates reach 1.005x halved on their best task (echo_pack) and 1.003x pooled.  No task clears
1.03x, so ctpred2 does not build a predicate memo cache and the predicate line stops here.

The predicates with 0 changed repeats over all 210 inputs, ordered by cacheable seconds:
`_is_owned_bytes_call` (0.161 s), `_map_kind` (0.124 s), `_param_kinds` (0.000 s, no repeats — a
cache would be pure cost).  If the line is ever revisited, `_is_owned_bytes_call` and `_map_kind`
are the only safe keys; the cacheable total (0.285 s, 0.9% of the pooled cold wall) is too small
to pay for the lookup.

The four predicates ctimes2 priced highest — `_etype`, `_is_str_expr`, `_is_slist_expr`,
`Ctx.type_of` — are exactly the ones that answer differently for the same node and `Ctx` during a
build, so the plain memo ctpred2 was considering cannot serve them.
