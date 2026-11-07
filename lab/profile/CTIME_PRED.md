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
* the own time: the time inside the predicate body only.  The whole interval of a wrapped callee
  -- its key construction, its bookkeeping and its own recording included -- is subtracted from
  the caller, and a predicate's own recording is excluded from its own time.  The probe's
  instrumentation is therefore not charged to any predicate;
* `repr(result)` truncated to 200 characters (primitives kept as values).

A *repeat* is a call whose key was seen before.  A *changed* repeat is one whose answer differs
from the first answer for that key: the predicate reads state that changes during the build, and a
plain memo is wrong for it.  *Cacheable* seconds are the own time of repeats with an unchanged
answer.

Runs: the 10 `lab/compare/src/*/main.ail` builds **without `--debug-dir`**, i.e. the same normal
build pipeline as the `CTIME_FE` wall and own times, and the first 200 sorted
`lab/corpus/programs/*/*.py` in changed-repeat mode (11 of the 200 are refused by name, so they
make no calls).  All runs used `ulimit -v 1500000`.  The debug pipeline is used only by
`ccheck.py` (section 6), which measures C identity, not call counts.

The wrapper still inflates a predicate's own time (measured 0.8 to 12.9 microseconds per call,
`Ctx.type_of` to `_etype`), so the cacheable **fraction** `f = probe cacheable / probe own` is
applied to the real own time measured by `CTIME_FE.json`; the scale factor is exactly
`fe own / probe own`.  For a task whose
`CTIME_FE.json` row reports the predicate, the task's own ratio is used; otherwise the pooled
`fe own / probe own` fills the gap.  Because a fraction is scale-free, a predicate's cacheable
seconds on a task with a measured row cannot exceed that row's own time.  `n` and the repeats are
counted, not scaled.

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
| `_etype` | 513,296 | 470,714 | 91.7% | 90,900 | 124,164 | 215,064 | 1.1786 | 1.8120 | no |
| `_is_str_expr` | 430,695 | 388,999 | 90.3% | 771 | 11,335 | 12,106 | 0.7481 | 0.8524 | no |
| `_is_slist_expr` | 325,390 | 285,315 | 87.7% | 65 | 1,142 | 1,207 | 0.2402 | 0.2809 | no |
| `_map_kind` | 483,928 | 442,559 | 91.5% | 0 | 0 | 0 | 0.0965 | 0.1095 | **yes** |
| `_is_bytes_expr` | 108,028 | 90,062 | 83.4% | 810 | 1,104 | 1,914 | 0.1204 | 0.1498 | no |
| `_is_owned_bytes_call` | 443,701 | 398,373 | 89.8% | 0 | 0 | 0 | 0.1259 | 0.1415 | **yes** |
| `Ctx.type_of` | 1,044,004 | 1,038,181 | 99.4% | 403,929 | 394,526 | 798,455 | 0.0338 | 0.0475 | no |
| `_param_kinds` | 546 | 0 | 0.0% | 0 | 0 | 0 | 0.0000 | 0.0920 | **yes** |

Every cacheable row is at or below its own-time row: the largest, `_etype` 1.179 s of 1.812 s,
is a 65% fraction.  The four biggest rows (`_etype`, `_is_str_expr`, `Ctx.type_of`, and part of
`_is_slist_expr` / `_is_bytes_expr`) all change answers during the build: caching them plainly
would return a stale kind.  `_etype` alone changes 215k times over the 210 inputs.
`_param_kinds` has no repeats at all, so a cache there is pure lookup cost.

## 5. Per task: saving and projection

`saving` = cacheable seconds of the **eligible** predicates minus `L * calls` of those predicates.
`projection = 1 / (1 - saving / wall)`; `halved = 1 + (projection - 1) / 2`.  The last two columns
repeat the exercise for *all eight* predicates (including those with changed repeats), as an
upper bound that a plain cache cannot actually reach.

| task | wall s | saving (listed) s | projection | halved | saving (all) s | halved (all) |
|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 8.702 | 0.0817 | 1.0095 | 1.0047 | 1.0427 | 1.0681 |
| chain_relax | 1.433 | 0.0105 | 1.0074 | 1.0037 | 0.1443 | 1.0560 |
| echo_pack | 2.337 | 0.0241 | 1.0104 | 1.0052 | 0.4626 | 1.1234 |
| ledger_bin | 2.437 | 0.0089 | 1.0037 | 1.0018 | 0.1659 | 1.0365 |
| rail_transfer | 2.084 | 0.0042 | 1.0020 | 1.0010 | 0.0756 | 1.0188 |
| scar_life | 1.641 | 0.0037 | 1.0022 | 1.0011 | 0.0407 | 1.0127 |
| tally_lang | 2.495 | 0.0011 | 1.0004 | 1.0002 | 0.0303 | 1.0061 |
| term_rank | 2.351 | 0.0045 | 1.0019 | 1.0010 | 0.0818 | 1.0180 |
| ticket_audit | 3.584 | 0.0017 | 1.0005 | 1.0002 | 0.0581 | 1.0082 |
| tree_fold | 3.731 | 0.0056 | 1.0015 | 1.0007 | 0.0983 | 1.0135 |
| **pooled** | **30.795** | **0.146** | **1.0048** | **1.0024** | **2.200** | **1.0385** |

Eligible predicates total 928,175 calls; the lookup they add costs `1.25e-7 * 928,175 =
0.116 s` pooled, against 0.262 s of cacheable own time on the per-task scale (net 0.146 s,
0.474% of the pooled cold wall).  Even the unreachable all-predicate upper bound (2.619 s
cacheable, 0.419 s of lookup) only reaches 1.038x halved pooled.

## 6. Stop rule: the wrapper observes only

Ten cold builds of `lab/compare/src/*/main.ail` with and without the probe, same
`PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, `AIL_SERVER=0`, fresh `AIL_CACHE` and `--debug-dir`:
`sha256(program.c)` is identical for **10/10** tasks
(berth_sim `8007891e…`, chain_relax `865f18c0…`, echo_pack `8c63efc0…`, ledger_bin `c111f240…`,
rail_transfer `2943c242…`, scar_life `4e9492d8…`, tally_lang `0b28da4d…`, term_rank `5c5ed035…`,
ticket_audit `16def672…`, tree_fold `36cc65e7…`).  The probe's call and changed-repeat counts on
normal builds match the earlier normal-build probe run exactly; only the debug pipeline inflates
them (2-4x on tally_lang, ticket_audit and tree_fold), which is why this report uses normal
builds throughout.

`lab/profile/ccheck.py --base` records `sha256(program.c)`, `sha256(executable)` and the
`sha256` of the refusal text for the 10 `typed.py`, the 10 `main.py`, the first 200 sorted
`lab/corpus/programs/*/*.py` and `docs/design/alias_study/trans` when present (220 inputs in this
tree: 205 built, 15 refused by name).  `docs/design/alias_study/trans` is absent.  `--check`
re-runs all inputs and compares; the hashes live in `CTIME_PRED.json` under `byte_identity`.

## 7. Decision

**No-go.**  Under the go rule (halved projection at least 1.03x on at least 3 tasks), the eligible
predicates reach 1.0052x halved on their best task (echo_pack) and 1.0024x pooled.  No task
clears 1.03x, so ctpred2 does not build a predicate memo cache and the predicate line stops here.

The predicates with 0 changed repeats over all 210 inputs, ordered by cacheable seconds:
`_is_owned_bytes_call` (0.1259 s), `_map_kind` (0.0965 s), `_param_kinds` (0.0000 s, no repeats
-- a cache would be pure cost).  If the line is ever revisited, `_is_owned_bytes_call` and
`_map_kind` are the only safe keys; the cacheable total (0.262 s, 0.9% of the pooled cold wall)
is too small to pay for the lookup.

The four predicates ctimes2 priced highest -- `_etype`, `_is_str_expr`, `_is_slist_expr`,
`Ctx.type_of` -- are exactly the ones that answer differently for the same node and `Ctx` during a
build, so the plain memo ctpred2 was considering cannot serve them.
