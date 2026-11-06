# RESULTS — what today's analyses already prove

Measured by `python3 lab/proof/census.py --jobs 2` over 275 program records (3255 function
records) from the three corpora, plus 31 `lab/race` probes for the race section.  Ten `main.py`
are listed by both the compare and the pyproof corpus, so the 275 records cover 265 distinct
non-race files.  Full records: `census.json`.  Design: `docs/design/SAFETY_PROOF.md`.

1. **Ownership: 80.9% of reference-parameter RC pairs are already elided** — 1658 elided vs 392
   needed.  By corpus: compare 82.1% (230/280), pyproof 91.1% (814/894), gdev 70.1% (614/876).
2. **Bounds: 13.6% of the index sites in IR-lowered functions already have their check removed** —
   166 of 1221.  A further **4744 index sites sit in functions the IR never lowers** at all, so
   only 20.5% of syntactic index sites are even inside the proof.
3. **Races: 79 of the 158 distinct shared-state accesses in parallel regions are classified safe;
   of the 79 refused, 19 are named by a rule (D4 6, D1 11, D3 2) and 60 are unknown.**  14 fork-join
   shapes are refused by D5, covering 16 worker functions; 17 shapes are lowered lock-free.
4. **Reach: of 3255 function records, 907 (27.9%) are on the typed path, 1703 (52.3%) are boxed and
   645 (19.8%) belong to programs both paths refuse.**  1552 records are not boxed (47.7%), but 645
   of those are in programs that never compiled: 907 is the real typed-path reach.
5. **Top blockers** (counts are functions affected; a function may carry more than one reason):
   boxed 1703, program refused 645, legacy emitter 252, parameter returned 145, index may be
   negative 106, no length value 77, no upper bound 59, length may change 49, no-index-api 47,
   aliased 20, stored into a field 14, container literal 4, entry point 3, passed to a call 2.
   **2875 of 3255 functions are not fully proved.**

## Per corpus

`typed path` = not boxed in a program that built; `refused programs` = every function of a program
both paths refuse (those records carry `boxed: false`, because nothing was built).  The three
columns partition the function records.

| corpus | programs | functions | typed path | boxed | refused programs | ref-param fns | RC elided | RC needed | share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| compare | 20 | 363 | 118 | 143 | 102 | 120 | 230 | 50 | 82.1% |
| pyproof | 55 | 769 | 64 | 231 | 474 | 334 | 814 | 80 | 91.1% |
| gdev | 200 | 2123 | 725 | 1329 | 69 | 423 | 614 | 262 | 70.1% |
| all | 275 | 3255 | 907 | 1703 | 645 | 877 | 1658 | 392 | 80.9% |

Ownership is measured by `ir.borrow.analyze` over every record that is not boxed (1552), including
the 645 from refused programs, because that analysis is an AST analysis and answers independently
of whether a program builds.  Per-function ownership, over the 877 records that have at least one
reference parameter: fully proved / partly / none — compare 99 / 4 / 17, pyproof 294 / 2 / 38,
gdev 293 / 5 / 125.  The other 675 records have no reference parameter at all.

| corpus | index sites in IR functions | check removed | share | sites in functions outside the IR |
|---|---:|---:|---:|---:|
| compare | 308 | 120 | 39.0% | 1353 |
| pyproof | 3 | 2 | 66.7% | 1585 |
| gdev | 910 | 44 | 4.8% | 1806 |
| all | 1221 | 166 | 13.6% | 4744 |

Why a kept bound check stayed, by the `AIL_BCE_EXPLAIN` reason (records, then the per-corpus
distribution): `index may be negative` 1072 (85 / 1 / 986), `no length value of this container`
282 (76 / 0 / 206), `no upper bound against a length` 276 (26 / 0 / 250), `list length may change
(length-changing op or unknown call)` 245 (19 / 0 / 226).  A record is one (deduplicated) site the
range pass left checked.  The 1875 records are not the 1055 kept IR sites: **792 of them belong to
functions with no IR record** (legacy-emitted or no-index), so those reasons come from failed IR
attempts of functions the IR never lowered; the other 1083 are attributed to function names that do
have an IR record, but `AIL_BCE_EXPLAIN` is keyed by function name and accumulates retries, so they
neither sum to nor subdivide the 1055 kept sites.  Use the reason *mix* only.

## Ranked blockers (functions affected, not instances)

Each non-boxed function is counted once per distinct reason it carries, so the column sums to more
than the 1172 non-boxed functions with a blocker.  Boxed functions are one row of their own; their
other blockers are not part of this ranking (they are still in `census.json`).

| # | reason | count | example |
|---:|---|---:|---|
| 1 | function on the general (boxed) path: no proof applies | 1703 | `lab/compare/src/ledger_bin/main.py:9 parse` |
| 2 | program refused by both paths | 645 | `lab/compare/src/chain_relax/main.py:5 parse` (an int literal above int64) |
| 3 | function stays on the legacy emitter (IR refused) | 252 | `lab/compare/src/rail_transfer/typed.py:43 relax` (field of object-list kind) |
| 4 | parameter returned (or yielded) to the caller | 145 | `lab/compare/src/tally_lang/main.py:96 unary` (`self`) |
| 5 | index bound not proved: index may be negative | 106 | `lab/compare/src/berth_sim/typed.py:11 fpush` (3 sites) |
| 6 | index bound not proved: no length value of this container | 77 | `lab/compare/src/berth_sim/typed.py:11 fpush` (6 sites) |
| 7 | index bound not proved: no upper bound against a length | 59 | `lab/compare/src/berth_sim/typed.py:33 main` (9 sites) |
| 8 | index bound not proved: list length may change | 49 | `lab/compare/src/berth_sim/typed.py:26 fpop` (5 sites) |
| 9 | no API: index sites of legacy-emitted functions are unreported | 47 | `lab/compare/src/ledger_bin/typed.py:48 main` (81 sites) |
| 10 | parameter aliased into a second local name | 20 | `lab/compare/src/tally_lang/main.py:54 expr` (`self`) |
| 11 | parameter stored into a field, list or dict | 14 | `lab/compare/src/rail_transfer/typed.py:13 __init__` (`h0`) |
| 12 | parameter stored into a container literal | 4 | `lab/compare/src/tally_lang/main.py:72 add` (`self`) |
| 13 | function is an entry point or used as a value | 3 | `lab/compare/src/tally_lang/main.py:132 g` (`self`) |
| 14 | parameter passed to a call that stores or forwards it | 2 | `examples/ffi/bindgen/zlib_gen.py:141` (`buf`) |

## Why functions are on the general path (ranked, functions affected)

Computed by `census.boxed_reasons()`: every boxed function is grouped by the one
`pyc.last_fallback_reason` its program recorded (the compiler records one reason per program, not
per function), first matching group wins.  `other` is the remainder, and the exact string stays in
`census.json` under that program's `fallback`.

| functions | typed-path refusal |
|---:|---|
| 273 | other (a reason not in the named groups) |
| 214 | a dunder other than `__init__` |
| 198 | a `Decimal` format spec in an f-string |
| 188 | a `bool` parameter given a non-bool |
| 126 | a list of `str` given a non-str value |
| 113 | a generator expression saved as a value |
| 109 | `d.get(k)` with one argument where an Optional is needed |
| 69 | a `str` parameter a caller also supplies an int to |
| 62 | a scalar `None`/Optional value |
| 58 | a `statistics` function not built |
| 54 | `collections` use not built |
| 45 | a set/dict element needing `__eq__`/`__hash__` |
| 43 | an annotation this compiler has no rule for |
| 42 | a struct-list comprehension not built |
| 35 | a module-level constant that is not numeric |
| 34 | the iterator protocol not built |
| 27 | a list parameter that is read-only |
| 13 | `yield`/generators not built |

## Race section

31 programs (`lab/race/safe`, `lab/race/racy`) name a threading module.  17 fork-join shapes are
lowered to `_ail_par_range` (lock-free).  14 shapes are refused by D5 and run under the general
path's lock; 16 worker functions of those refused shapes were found, and only there can accesses be
classified.  D5 is a count of *shapes*, never of accesses.

| classification | accesses |
|---|---:|
| safe (reads, distinct-shape element writes) | 79 |
| refused — D4 (str/bytes/object or attribute) | 6 |
| refused — D1 (shared scalar write) | 11 |
| refused — D3 (append/resize) | 2 |
| refused — no rule names it (`unknown`) | 60 |
| **refused total** | **79** |
| **distinct accesses (safe + refused)** | **158** |
