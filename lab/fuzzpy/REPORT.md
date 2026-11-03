# fuzzpy: differential fuzzing of plain Python (default build)

Date: 2026-11-03. Seeds 1-500, 500 generated programs, two jobs, chunks of 100.
Every program ran under `ulimit -v 1500000` with a 10 s timeout, and was compared with
CPython 3.12 on stdout, the last stderr line and the exit status.

## Counts

| class | count |
|---|---|
| silent | 0 |
| loud-ok | 115 |
| crash | 0 |
| refused | 30 |
| other | 355 |

`other` is 346 programs identical to CPython plus the 9 stderr-only differences below.
Typed path: 257/500 (51.4%); general path: 243/500 (48.6%).
`summary.json` has one row per seed with its class, path and first differing line.

`loud-ok` is the declared int64 behaviour (the program stops loudly where CPython grows a
big int). It is counted but not filed. The raw `seed22` finding is also this case: its
compile-time `int64 constant out of range` is a loud int64 stop, not a crash.

## Findings

Silent wrong outputs: none. Crashes: none.

All 9 differences are stderr-only: stdout and exit status match CPython; the last stderr
line differs on the default (typed) path. The general path matches CPython in every case.
They reduce to the pre-existing typed-trap text limitation: an uncaught trap prints the
bare message without its exception class prefix, and `KeyError` also loses the key.

1. `001.py` — `IndexError: string index out of range` vs `string index out of range`
   (seeds 9, 380).
2. `002.py` — `IndexError: pop from empty list` vs `pop from empty list` (seed 45).
3. `003.py` — `ZeroDivisionError: float division by zero` vs `division by zero`
   (seeds 141, 190, 249); the AIL text also drops the word "float".
4. `004.py` — `ZeroDivisionError: integer modulo by zero` vs `integer modulo by zero`
   (seed 150).
5. `005.py` — `KeyError: 'a'` vs `key error` (seed 152); the AIL text also loses the key.

Each file reproduces with `bash ~/tools/cmp.sh lab/fuzzpy/findings/NNN.py $PWD`.
