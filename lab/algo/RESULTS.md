# `ail check --perf`: census and before/after

`ail check --perf` is static advice over the Python AST (`packaging/ail_lang/perflint.py`). It changes
no program output. This directory records what the first version finds on the existing programs and
what the suggested fix buys when it is applied.

Run:

```sh
python3 lab/algo/census.py          # per-rule hit tables (also --json)
python3 lab/algo/measure.py --runs 3   # before/after cases, stdout byte-compare and median wall time
```

Python 3.12.3, 4-core GitHub runner, 2026-11-07. Times below are the median of three runs of the
whole program (one warm-up run first).

## Census

Required sets: the ten `lab/compare/src/*/main.py` programs, the 50 corpus programs `lab/rundiff`
uses (`corpus/gdev` first 50 in name order) and every `.py` output in `lab/vibe/programs`. The all-gdev
and all-lab/corpus sets are shown too so a hit outside the required 50 is not hidden.

### compare (10)

| files | hits | P1 | P2 | P3 | P4 | P5 | P6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### corpus (50, rundiff1)

| files | hits | P1 | P2 | P3 | P4 | P5 | P6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 50 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |

- `corpus/gdev/g00_006.py:14:13` P3: string concatenation on `count_digits` inside a loop.

### corpus gdev (all 510)

| files | hits | P1 | P2 | P3 | P4 | P5 | P6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 510 | 2 | 1 | 0 | 1 | 0 | 0 | 0 |

- `corpus/gdev/g00_006.py:14:13` P3 (the required-50 hit above).
- `corpus/gdev/g15_022.py:84:16` P1: `items.index(item)` inside `enumerate(items)`.

### lab/corpus (all 219 programs)

| files | hits | P1 | P2 | P3 | P4 | P5 | P6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 219 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### lab/vibe (24 `.py` outputs)

| files | hits | P1 | P2 | P3 | P4 | P5 | P6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### False positives, checked by hand

The final census has **no false positives** in the required sets. Both hits were read by hand:

- `g00_006.py` P3: `count_digits += ch` accumulates a run-length count one digit at a time. True
  positive; the applied fix is the same pattern as `cases/p3_*` below.
- `g15_022.py` P1: `items.index(item) == i` inside `enumerate(items)` scans the list once per element,
  so it is O(n^2) by pattern. True positive, but it is a constant-size invariant check (four items),
  so no fix was applied; the scalable P1 case below measures the same fix.

The hand check did remove four false-positive shapes before this final census:

- P5 first flagged dynamic-programming comparisons (`a[i - 1] == b[j - 1]` in `lab/corpus/t255`,
  `t306`, `t308` and `corpus/gdev/g09_002`, `g10_028`). It now ignores subscript indices and does not
  treat two `range`/`enumerate`/`zip` loops as a pairwise item search.
- P4 first flagged `neighbours.sort()` inside `for neighbours in adj:` (`lab/corpus/t266`), where
  every iteration has a different list. A name bound by the loop target is now treated as
  loop-variant.
- P1 first treated sets and dicts as lists (`visited`, `disc`, `index` in `corpus/gdev/g08_014`,
  `g10_010`, `g10_026`, `g10_036`) because of `.remove` and subscript stores. Those are no longer
  list evidence.

## Applied fixes: output and wall time

`lab/algo/cases/pN_before.py` is a perflint hit; `pN_after.py` applies the reported fix. The harness
lints both, runs both, and compares stdout bytes. Every pair prints identical output and the hit
disappears after the fix.

| rule | before s | after s | speed-up | output identical | before hit | after hit |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | 1.501 | 0.020 | 74.2x | yes | P1 | - |
| P2 | 1.703 | 0.029 | 59.2x | yes | P2 | - |
| P3 | 1.997 | 0.049 | 40.5x | yes | P3 | - |
| P4 | 1.099 | 0.017 | 63.1x | yes | P4 | - |
| P5 | 1.199 | 0.021 | 58.4x | yes | P5 | - |
| P6 | 6.441 | 0.020 | 317.3x | yes | P6 | - |

Sizes: P1 20,000 membership tests over a 20,000-item list; P2 150,000 `pop(0)` calls; P3 250,000
`+=` pieces on a module-level string; P4 12,000 `sum()` calls over 12,000 items; P5 6,000 x 6,000
key comparisons; P6 60,000 list rebuilds. The P3 benchmark keeps the string at module scope because
CPython 3.12 rewrites a local `s += str` in place; the O(n^2) copy that the rule is about remains
when the string is shared, which is the shape a generated program often has and the cost AIL's
general path has.
