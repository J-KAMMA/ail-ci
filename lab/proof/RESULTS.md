# RESULTS — what today's analyses already prove

Measured by `python3 lab/proof/census.py --jobs 2` over 306 programs (4958 functions): the 20
`lab/compare/src` programs, the 55 `lab/pyproof` programs, the first 200 `corpus/gdev` programs,
plus 31 `lab/race` probes for the race section.  Full records: `census.json`.  Design:
`docs/design/SAFETY_PROOF.md`.

1. **Ownership: 80.9% of reference-parameter RC pairs are already elided** — 1658 elided vs 392
   needed.  By corpus: compare 82.1% (230/280), pyproof 91.1% (814/894), gdev 70.1% (614/876).
2. **Bounds: 13.6% of the index sites in IR-lowered functions already have their check removed** —
   166 of 1221.  A further **4744 index sites sit in functions the IR never lowers** at all, so
   only 20.5% of syntactic index sites are even inside the proof.
3. **Races: 79 of the 123 shared-state accesses in parallel regions are classified safe, 25 refused
   by a named rule (D1/D3/D4), 19 unknown**; 17 fork-join shapes across the 31 programs are
   lowered lock-free, 14 fall back to the general path's lock (rule D5).
4. **Reach: only 1552 of 4958 functions (31.3%) are on the typed path**; 1703 (34.3%) are compiled
   on the general (boxed) path, where no proof applies, and 1703 are in programs both paths refuse.
5. **Top blockers** (2875 blocker instances over 4958 functions): general path 1703, program
   refused 580, IR lowering refused 233, parameter returned 145, then the bounds reasons below.

## Per corpus

| corpus | programs | functions | typed | boxed | ref-param functions | RC elided | RC needed | share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| compare | 20 | 363 | 220 | 143 | 120 | 230 | 50 | 82.1% |
| pyproof | 55 | 769 | 538 | 231 | 334 | 814 | 80 | 91.1% |
| gdev | 200 | 2123 | 794 | 1329 | 423 | 614 | 262 | 70.1% |
| all | 275 | 3255 | 1552 | 1703 | 877 | 1658 | 392 | 80.9% |

Per-function ownership, over functions that have at least one reference parameter:
fully proved (no RC pair left) / partly / none — compare 99 / 4 / 17, pyproof 294 / 2 / 38,
gdev 293 / 5 / 125; 675 typed functions have no reference parameter at all.

| corpus | index sites in IR functions | check removed | share | sites in functions outside the IR |
|---|---:|---:|---:|---:|
| compare | 308 | 120 | 39.0% | 1353 |
| pyproof | 3 | 2 | 66.7% | 1585 |
| gdev | 910 | 44 | 4.8% | 1806 |
| all | 1221 | 166 | 13.6% | 4744 |

Why a kept bound check stayed, by the `AIL_BCE_EXPLAIN` reason (functions, then the per-corpus
distribution): `index may be negative` 36 functions (85 / 1 / 986 records), `no length value of
this container` 54 (76 / 0 / 206), `no upper bound against a length` 26 (26 / 0 / 250), `list
length may change (length-changing op or unknown call)` 24 (19 / 0 / 226).  A record is one
(deduplicated) site the range pass left checked; the records outnumber the 1055 kept IR sites
because a site can be reported once per build attempt, so use the reason *mix*, not its total.

## Ranked blockers (all 14 reasons; counts are functions)

| # | reason | count | example |
|---:|---|---:|---|
| 1 | function on the general (boxed) path: no proof applies | 1703 | `lab/compare/src/ledger_bin/main.py:9 parse` |
| 2 | program refused by both paths | 580 | `lab/compare/src/chain_relax/main.py:5` (an int literal above int64) |
| 3 | function stays on the legacy emitter (IR refused) | 233 | `lab/compare/src/rail_transfer/typed.py:43 relax` (field of object-list kind) |
| 4 | parameter returned (or yielded) to the caller | 145 | `lab/compare/src/tally_lang/main.py:96 unary` (`self`) |
| 5 | index bound not proved: no length value of this container | 54 | `lab/compare/src/berth_sim/typed.py:11 fpush` |
| 6 | index bound not proved: index may be negative | 36 | `lab/compare/src/ledger_bin/typed.py:11 readvar` |
| 7 | index bound not proved: no upper bound against a length | 26 | `lab/compare/src/berth_sim/typed.py:33 main` |
| 8 | index bound not proved: list length may change | 24 | `lab/compare/src/berth_sim/typed.py:26 fpop` |
| 9 | parameter aliased into a second local name | 20 | `lab/compare/src/tally_lang/main.py:54 expr` (`self`) |
| 10 | no API: index sites of legacy-emitted functions are unreported | 31 | `lab/compare/src/ledger_bin/typed.py:48 main` (81 sites) |
| 11 | parameter stored into a field, list or dict | 14 | `lab/compare/src/rail_transfer/typed.py:13` (`h0`) |
| 12 | parameter stored into a container literal | 4 | `lab/compare/src/tally_lang/main.py:72 add` |
| 13 | function is an entry point or used as a value | 3 | `lab/compare/src/tally_lang/main.py:132 g` |
| 14 | parameter passed to a call that stores or forwards it | 2 | `examples/ffi/bindgen/zlib_gen.py:141` |

## Why functions are on the general path (ranked, functions affected)

| functions | typed-path refusal |
|---:|---|
| 186 | a format spec on a `Decimal` in an f-string (`__format__` is not built) |
| 164 | a dunder other than `__init__` (e.g. `Fraction.__float__`) |
| 156 | parameter declared `bool` but given a non-bool |
| 120 | a list of `str` given a non-str value |
| 108 | a generator expression saved as a value |
| 108 | `d.get(k)` with one argument where an `Optional` is needed |
| 76 | a parameter annotated `str` that a caller also supplies an int to |
| 67 | `collections` use not built (`Counter`, `defaultdict` with a lambda, ...) |
| 58 | `threading`/`queue`/`concurrent.futures` (general path by design) |

## Race section

31 programs (`lab/race/safe`, `lab/race/racy`) name a threading module.  17 fork-join shapes are
lowered to `_ail_par_range` (lock-free); 14 are refused and run under the general path's lock.
Of the shared-state accesses in the regions:

| classification | accesses |
|---|---:|
| safe (reads, distinct-shape element writes) | 79 |
| refused — D4 (str/bytes/object or attribute) | 4 |
| refused — D1 (shared scalar write) | 2 |
| refused — D5 (shape not lowered, whole region under the lock) | 14 constructs |
| unknown (a read in a refused region, no rule names it) | 19 |
