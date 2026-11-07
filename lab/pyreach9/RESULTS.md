# pyreach9 census: why plain Python still falls to the general path

Date: 2026-11-07. Branch: `job-pyreach9-11071331`. Tree: `0ec0443` (export of `staging:integ`).
The compiler was not changed; this lane measures and designs only.

## Method

`lab/pyreach9/census.py` builds every program twice in its own temp directory with
`AIL_NO_CACHE=1`, on the branch tree:

1. `compile --syntax python --strict --json` — a strict build either passes (path **typed**)
   or refuses with exit 3 and prints the full blocker list (`ail.strict/1`, produced by
   `python/pkg-v12/strictmode.py::collect`). `--exact-int` is passed for the compare
   `chain_relax` and `rail_transfer` programs, the flags `run_task.py` uses.
2. the default build — **general** when it prints “built on the general path”, otherwise
   **refused**. A parse-stage failure (exit 2) is refused even by the strict build.

Corpora, fixed order and seed:

| corpus | source | programs |
|---|---|---:|
| compare | `lab/compare/src/*/main.py` | 10 |
| vibe | every `*.py` under `lab/vibe/programs` (the AI-written Python and AIL programs; both are plain Python to this compiler) | 24 |
| gdev | 100 of `corpus/gdev/*.py`, `random.Random(20261107).sample` of the sorted list | 100 |

`lab/pyreach9/classify.py` maps every blocker to one reason (ordered patterns over
`construct :: why :: function`) and counts, per reason, the programs touched, the programs
whose blocker list contains *only* that reason (**sole**), and the blocker instances. The
full per-program classification is `lab/pyreach9/programs.txt`; the raw record for all 134
programs is `lab/pyreach9/census.jsonl`.

Caveat that matters for every sole count: `strictmode` stops when it cannot locate a
refusal and reports `strict_incomplete`. **41 of the 97 non-typed programs have an
incomplete blocker list**, so “sole” is exact only for the other 56. The table gives both
`sole` (all) and `sole-c` (complete lists only); the ranking uses `sole`, as the task asks.

## Paths

| corpus | typed | general | refused |
|---|---:|---:|---:|
| compare | 2 | 6 | 2 |
| vibe | 0 | 19 | 5 |
| gdev | 35 | 56 | 9 |
| **all** | **37** | **81** | **16** |

The two typed compare programs are `berth_sim` and `echo_pack`; the other eight are on the
general path or refused, matching `lab/roof/RESULTS.md`. **No AI-written program
(`lab/vibe`) reaches the typed path.** The five vibe refusals are `berth_sim/python-0`
(the injected `array` prelude), both `chain_relax` seeds (int64 literal), and
`tally_lang/python-0` / `scar_life/python-1` (other blockers). `rail_transfer/python-0`
also carries the `array` prelude but builds on the general path.

## Reasons, ranked by programs whose only remaining blocker is the reason

`progs` = general/refused programs with at least one such blocker; `sole` = programs whose
whole blocker list is this reason; `sole-c` = the same restricted to complete lists;
`blk` = blocker instances; `c/v/g` = corpus split of `progs`.

| # | reason | progs | sole | sole-c | blk | c/v/g |
|---:|---|---:|---:|---:|---:|---|
| 1 | generated-prelude | 16 | **5** | 1 | 128 | 2/4/10 |
| 2 | int64-literal | 4 | **3** | 3 | 4 | 2/2/0 |
| 3 | parameter-readonly | 4 | **3** | 1 | 5 | 0/1/3 |
| 4 | generator-yield | 4 | **3** | 3 | 5 | 0/0/4 |
| 5 | unsupported-module | 21 | **2** | 0 | 32 | 3/3/15 |
| 6 | tuple-unpack | 16 | 2 | 2 | 37 | 1/7/8 |
| 7 | mixed-container | 15 | 2 | 2 | 19 | 3/4/8 |
| 8 | none-optional | 12 | 2 | 1 | 29 | 3/3/6 |
| 9 | comprehension | 7 | 2 | 1 | 7 | 0/1/6 |
| 10 | dict-of-containers | 18 | 1 | 0 | 24 | 3/4/11 |
| 11 | value-kind-lost | 14 | 1 | 1 | 37 | 0/9/5 |
| 12 | other (long tail) | 11 | 1 | 1 | 12 | 1/2/8 |
| 13 | generic-annotation | 11 | 1 | 1 | 14 | 0/0/11 |
| 14 | class-dunders | 10 | 1 | 1 | 43 | 1/1/8 |
| 15 | class-shape | 6 | 1 | 1 | 8 | 0/3/3 |
| 16 | numeric-kind | 4 | 1 | 1 | 4 | 0/0/4 |
| 17 | str-number-compare | 2 | 1 | 1 | 2 | 0/2/0 |
| — | module-level-constant | 13 | 0 | 0 | 18 | 1/6/6 |
| — | mixed-return-kind | 10 | 0 | 0 | 10 | 1/7/2 |
| — | bytes-str-methods | 9 | 0 | 0 | 16 | 2/6/1 |
| — | unsupported-builtin | 5 | 0 | 0 | 7 | 1/0/4 |
| — | str-number-concat | 4 | 0 | 0 | 4 | 1/3/0 |
| — | slice-for-number | 4 | 0 | 0 | 11 | 0/3/1 |
| — | annotation-caller-conflict | 2 | 0 | 0 | 2 | 0/0/2 |
| — | buffer-io | 2 | 0 | 0 | 2 | 0/2/0 |
| — | bytes-sequence-param | 2 | 0 | 0 | 23 | 0/2/0 |
| — | records-annotation | 2 | 0 | 0 | 2 | 0/0/2 |
| — | tuple-holds | 2 | 0 | 0 | 2 | 1/1/0 |
| — | nested-def-in-loop | 1 | 0 | 0 | 10 | 1/0/0 |
| — | exceptions, key-argument, while-else | 1 each | 0 | 0 | 1 each | |

## The sole-blocked programs

| reason | programs |
|---|---|
| generated-prelude | `vibe/berth_sim/ail-0.py`, `vibe/berth_sim/python-0.py`, `vibe/rail_transfer/python-0.py`, `gdev/g01_008.py` (datetime), `gdev/g11_002.py` (deque) |
| int64-literal | `compare/chain_relax/main.py`, `vibe/chain_relax/python-0.py`, `vibe/chain_relax/python-1.py` |
| parameter-readonly | `gdev/g04_010.py`, `gdev/g08_002.py`, `gdev/g08_034.py` |
| generator-yield | `gdev/g16_000.py`, `gdev/g16_006.py`, `gdev/g16_038.py` |
| unsupported-module | `gdev/g03_032.py` (statistics), `gdev/g21_022.py` (json) |
| tuple-unpack | `gdev/g00_008.py`, `gdev/g10_008.py` |
| mixed-container | `gdev/g03_016.py`, `gdev/g03_036.py` |
| none-optional | `vibe/echo_pack/ail-0.py`, `gdev/g11_034.py` |
| comprehension | `vibe/scar_life/ail-0.py`, `gdev/g04_018.py` |
| dict-of-containers | `gdev/g01_026.py` |
| value-kind-lost | `gdev/g05_022.py` |
| generic-annotation | `gdev/g00_004.py` |
| class-dunders | `gdev/g13_012.py` |
| class-shape | `gdev/g14_006.py` |
| numeric-kind | `gdev/g09_006.py` |
| str-number-compare | `vibe/csv_rollup/ail-0.py` |
| other | `gdev/g14_022.py` (itertools.groupby) |

Note that `g01_008.py` (datetime), `g11_002.py` (deque), `berth_sim/python-0.py` and
`rail_transfer/python-0.py` (array) are sole *because* the only blockers are in the
injected prelude: their user code is already in the subset. `berth_sim/ail-0.py` is also
sole `generated-prelude`, but its blocker is a compiler-generated lowering name
(`_ail_l1l` bound with two arities), not a prelude module, so typing the prelude does not
move it.

## AI-typical vs corpus-typical

Rates are programs per corpus: vibe has 24 programs, gdev 100, compare 10, so a reason on
6 vibe programs is 25% of that corpus; the same 6 on gdev is 6%.

**AI-typical** (vibe rate ≫ gdev rate):

| reason | vibe | gdev | what the AI writes |
|---|---:|---:|---|
| value-kind-lost | 9/24 | 5/100 | `data[i]` / `row[1]` / `x.method()` loses the container kind; bytes treated as int |
| tuple-unpack | 7/24 | 8/100 | `for a, b in records:`, `x, y = fn()`, `a, b = pair` |
| mixed-return-kind | 7/24 | 2/100 | one path returns `bytes`, another an `int` (`parse`/`transform`); `return code, out` with a bytearray |
| bytes-str-methods | 6/24 | 1/100 | `bytes.isdigit()`, `.lstrip()`, `.strip()`, `.index()`, `.decode()`, `bytes.translate` |
| module-level-constant | 6/24 | 6/100 | `STOP_WORDS = set(...)`, `LOWER = str.maketrans(...)`, `DIGIT_VALUE = {}` |
| dict-of-containers | 4/24 | 11/100 | `accounts[id] = [name, initial, True]`, `venue_stats[code] = [0,0,0]` |
| generated-prelude | 4/24 | 10/100 | `from array import array`; `collections.Counter`/`deque`; `re`, `csv`, `enum`, `datetime` |
| none-optional | 3/24 | 6/100 | `d.get(k)` with no default, `None` sentinels |
| int64-literal | 2/24 | 0/100 | `18446744073709551615` masks |
| buffer-io | 2/24 | 0/100 | `sys.stdin.buffer.readline()`, `sys.stdout.buffer` |

**Corpus-typical** (gdev only or mostly):

| reason | gdev | vibe | what the corpus programs do |
|---|---:|---:|---|
| generic-annotation | 11/100 | 0/24 | `list[T]`, `Any`, `Type[...]`, `int \| tuple`, `tuple[str, ...]`, `re.Match` |
| dict-of-containers | 11/100 | 4/24 | dict whose values are lists/tuples |
| generated-prelude | 10/100 | 4/24 | `datetime`, `namedtuple`, `csv`, `enum`, `random`, `re` preludes |
| class-dunders | 8/100 | 1/24 | `__str__`/`__repr__`/`__eq__`/`__lt__`, `print(object)`, `@property`, `__slots__` |
| tuple-unpack | 8/100 | 7/24 | mixed |
| unsupported-module | 15/100 | 3/24 | `json`, `statistics`, `collections`, `itertools`, `functools`, `re`, `tempfile` |
| comprehension | 6/100 | 1/24 | 2-clause comprehensions, class-body comprehensions |

## Reading of the numbers

- **The single largest mover is compiler-generated code, not the user's Python.**
  `generated-prelude` is 16 programs and 128 blocker instances, and 5 programs have no
  other blocker. The blocks are in `prelude_array.py` (`_AilArray.__init__`, `__delitem__`,
  `_AIL_ARRAY_PRELUDE`, `_AIL_ARR_MISSING`, `_ail_arr_check`), the namedtuple prelude
  (`_AilNT` dunders, `_replace`, `_asdict`), the csv prelude (`_AilCsvReader.__next__`), the
  enum prelude (`_AilIntEnum` numeric dunders and module constants), the `deque` prelude
  (`_AilDeque.buf` field of array type), the datetime helper
  (`_ail_dt_from_iso_datetime`), the random helper (`_ail_rng`), and the regex engine
  (`_ail_re_dp/ds/dm`, `_ail_re_sub0`). `stdlib5.prelude()` / `smalllib5.run_array` inject
  these as Python; `strictmode` then checks them as if the user wrote them.
- **`unsupported-module` is the biggest user-visible family** (21 programs): `json` 8,
  `statistics` 3, `collections` 5, `itertools`/`functools`/`re` 1-2 each, `tempfile` 1.
  These are refusals by name, so they are loud, but they keep plain Python off the typed
  path. Several are one function away from the subset (`itertools.pairwise`, `takewhile`,
  `statistics.median`, `collections.Counter`).
- **None/Optional is the biggest single semantic cluster** among the user-code reasons
  (12 programs; AI and corpus). `pyreachs8` built Optional for annotated
  parameters/returns/locals; the survivors are the un-annotated shapes: one-argument
  `dict.get` (`acc.get(r[1])`), `None` as a literal list element, and `str | None` /
  `int | None` (scalars, not only class types).
- **The rest of the top five are small but clean**: int64 literals (4, 3 sole), parameter
  mutation (4, 3 sole), generators (4, 3 sole). Each is one semantic decision, not a pile
  of inference.
- **The high-appearance next tier** is dict-of-containers (18), tuple-unpack (16),
  mixed-container (15), value-kind-lost (14), module-level-constant (13), mixed-return-kind
  (10), bytes-str-methods (9). These matter most for AI-written code (value-kind-lost
  9/24, tuple-unpack 7/24, mixed-return 7/24, module-level-constant 6/24,
  bytes-str-methods 6/24) and are the natural pyreach10 batch.
- `refused` programs (16) are not a separate reason: most share the blocker lists above and
  add a *general-path* refusal (`tally_lang` uses a compiled regex as a value, `tree_fold`
  a compiled pattern, `g13_010` `__mro__`, `g14_006` `__dataclass_fields__`), so moving the
  typed path does not automatically make them build.

## Reproduce

```sh
python3 lab/pyreach9/census.py -j 2 -o lab/pyreach9/census.jsonl   # ~31 min on 4 vCPU
python3 lab/pyreach9/classify.py --dump > lab/pyreach9/programs.txt
```
