# fuzzpy: differential fuzzing of plain Python (default build)

Date: 2026-11-03; re-run and re-verified 2026-11-04. Seeds 1-500, 500 generated programs, two
jobs, chunks of 100. Every program ran under `ulimit -v 1500000` with a 10 s timeout, and was
compared with CPython 3.12 on stdout, the last stderr line and the exit status.

## Counts

| class | count |
|---|---|
| silent | 0 |
| loud-ok | 115 |
| crash | 0 |
| refused | 30 |
| other | 355 |

`other` is 346 programs identical to CPython plus the 9 stderr-only differences below.
470 programs built: 227 on the typed path (48.3%) and 243 on the general path (51.7%). The other
30 were refused at compile time before a path was chosen; `summary.json` labels those rows `typed`
because no fallback happened, so its path totals read typed 257 / general 243.
`summary.json` has one row per seed with its class, path and first differing line; a clean re-run
of seeds 1-500 reproduces all 500 rows exactly.

`loud-ok` is the declared int64 behaviour (the program stops loudly where CPython grows a big
int): 82 stop at compile time on a constant expression, 33 at run time with `OverflowError`. It
is counted but not filed. The raw `seed22` finding is one of the compile-time stops, not a crash.

## Findings

Silent wrong outputs: none. Crashes: none.

All 9 differences the fuzzer hit are stderr-only: stdout and the exit status match CPython, and
only the last stderr line differs on the default (typed) path. The general path matches CPython
in every case. They share one cause: a typed/default trap prints only its message text, without
the exception class prefix. Reduced to `001.py`-`005.py`.

1. `001.py` — `IndexError: string index out of range` vs `string index out of range` (seeds 9,
   380; seed 354 is the same cause for a list: `IndexError: list index out of range` vs
   `list index out of range`).
2. `002.py` — `IndexError: pop from empty list` vs `pop from empty list` (seed 45).
3. `003.py` — `ZeroDivisionError: float division by zero` vs `division by zero` (seeds 141, 190,
   249); the AIL text also drops the word "float".
4. `004.py` — `ZeroDivisionError: integer modulo by zero` vs `integer modulo by zero` (seed 150).
5. `005.py` — `KeyError: 'a'` vs `key error` (seed 152); the AIL text also loses the key.

Reducing the findings exposed four more distinct message defects (`006.py`-`009.py`). Each is
seen on the default path only; the general path matches CPython.

6. `006.py` — floor division by zero: `ZeroDivisionError: integer division or modulo by zero` vs
   `integer division by zero` (the prefix and the words "or modulo" are lost).
7. `007.py` — `min()`/`max()` of an empty list parameter: `ValueError: min() iterable argument is
   empty` vs `min() of an empty sequence`.
8. `008.py` — `str.index` not found: `ValueError: substring not found` vs `ValueError` (no text).
9. `009.py` — bytes index: `IndexError: index out of range` vs `bytes index out of range`.

The trap text is path-dependent. These match CPython on both builds: a dict lookup through a
parameter; a string index of a dict value; `//` by zero through an attribute; float division of a
dict value; `pop()` on a list parameter; `int("x")` and `int + str` (ValueError and TypeError
keep their prefixes); `min()`/`max()` of a local empty list or a literal `[]`; and `1 // 0` as a
constant expression.

Each file reproduces with `bash ~/tools/cmp.sh lab/fuzzpy/findings/NNN.py $PWD`.

## Probes

53 probe programs in `/tmp/probes` covered the boundaries: local, argument, list item, attribute
and dict value for index, pop, dict lookup, division and modulo; empty and non-empty containers;
literal versus variable divisors; caught exceptions; exceptions raised inside nested calls; bytes
indexing; `str.index`; `min()`/`max()` on empty and non-empty lists; int64 add, multiply and
subtract at the boundary; compile-time constant overflow.

- 25 differ on the default path only and match CPython on the general path: the defects behind
  `001.py`-`009.py`.
- 20 match CPython on both builds (the path-dependent cases listed above).
- 7 are the declared loud int64 stop (`OverflowError` with exit 1, or a named compile-time
  refusal) while CPython goes on; not bugs by owner decision.
- 1 is a named compile-time refusal: a bare `raise` is "not in the subset".
