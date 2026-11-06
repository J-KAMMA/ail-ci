# Expected outputs of the `lab/race/reduce` probes

Each probe `pNN_*.py` is the parallel shape of `docs/design/PAR_REDUCE.md`; `pNN_*_twin.py` is the
same program with `par_range` replaced by `range` (for the `sum(map)` probes, a sequential map pass
followed by a sequential sum).  The expected output below is the twin's, measured in the default
AIL build (`python3 -B AIL_CURRENT/ail_chatgpt.py compile <twin> --syntax python -o <exe>`), not
hand-written.  "CPython" is `python3 <twin>`; a probe whose twin reaches the int64 boundary differs
there on purpose, because AIL stops loudly and CPython prints the exact big int.

Reproduce all of them with:

```sh
for t in lab/race/reduce/*_twin.py; do
  p=${t%_twin.py}; python3 -B AIL_CURRENT/ail_chatgpt.py compile "$t" --syntax python -o /tmp/t.exe
  /tmp/t.exe; echo "exit $?"
done
```

## Results

| probe | shape | expected stdout | exit | AIL stderr (first line) | CPython |
|---|---|---|---|---|---|
| `p01_small_sum` | `acc += i`, 100 items | `4950` | 0 | - | same |
| `p02_negative_sum` | `acc += -3*i - 7`, 100 items | `-15550` | 0 | - | same |
| `p03_prefix_overflows_total_fits` | `acc += xs[i]`, total 5, prefix `2^62, 2^63` | *(empty)* | 1 | `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)` | `5` (differs: no int64) |
| `p04_overflow_first` | `acc += xs[i]`, first add overflows | *(empty)* | 1 | `OverflowError: integer overflow in + ...` | `9223372036854775809` (differs) |
| `p05_overflow_last` | 10 items, the last add overflows | *(empty)* | 1 | `OverflowError: integer overflow in + ...` | `9223372036854775818` (differs) |
| `p06_exception_before_overflow` | `term(i)` raises at 1, overflow would come at 4 | *(empty)* | 1 | `ZeroDivisionError: integer division or modulo by zero` | same stdout and exit (traceback text differs) |
| `p07_exception_after_overflow` | overflow at 3, `term(i)` raises at 6 | *(empty)* | 1 | `OverflowError: integer overflow in + ...` | same stdout and exit; stderr kind is `ZeroDivisionError` (AIL stops at int64 first) |
| `p08_try_catches_overflow` | `try` around the loop, `acc = 10`, `[2^62, 2^62, -1]` | *(empty)* | 1 | `OverflowError: integer overflow in + ...` | `9223372036854775817` (differs) |
| `p09_two_accumulators` | `acc += i` and `neg -= i` | `4950 -4950` | 0 | - | same |
| `p10_sum_map_exception_after_overflow` | `sum(ex.map(f, range(5)))`, f raises at 3, sum would overflow at 1 | `caught ZeroDivisionError 0` / `0` | 0 | - | same |
| `p11_n_zero` | `par_range(0, 0)` | `7` | 0 | - | same |
| `p12_n_one` | `par_range(0, 1)` | `12` | 0 | - | same |
| `p13_more_workers_than_items` | 3 items, more workers than items | `3` | 0 | - | same |
| `p14_sum_map_basic` | `sum(ex.map(sq, range(10)))` | `285` | 0 | - | same |
| `p15_sum_pool_map` | `sum(p.map(sq, range(10)))` | `285` | 0 | - | same |
| `p16_min_overflow` | `acc += xs[i]`, `[-2^62, -2^62, -1]` | *(empty)* | 1 | `OverflowError: integer overflow in + ...` | `-9223372036854775809` (differs) |

## The `try` probe

`p08` is the one probe whose expected output is **not** the twin's current output.  In the default
AIL build an int overflow outside a parallel region is a loud stop (`ail_die`), not a catchable
exception, so the twin prints nothing and exits 1 even though it has a `try`.  The design
(`PAR_REDUCE.md`, "A caught overflow") says the reduction raises `OverflowError` on the calling
thread through the runtime's trap path, which a `try` around the loop can catch.  After fbred2/3
this probe must print

```
caught OverflowError 4611686018427387914
4611686018427387914
```

`10 + 2^62` fits; the second `2^62` is the add that stops, so `acc` is the last prefix that fit.
Until then the probe is refused by name (`parallel for cannot be inside try; put the loop in its
own fn`), which is a second, separate rule that fbred2/3 must also lift for this spelling.

## Today's build status (before fbred2/3)

Measured with the same compile command.  Of the 16 parallel probes:

| status | count | probes |
|---|---|---|
| refused, shared int in a parallel body (`'acc' is read before the body assigns it`) | 12 | p01-p07, p09, p11-p13, p16 |
| refused, `parallel for cannot be inside try` | 1 | p08 |
| builds today and equals its twin | 3 | p10, p14, p15 (`sum` over an executor/Pool map is already lowered on the typed parallel path) |

So fbred3 moves 12 of these 16 from refused to "equals the sequential twin"; `p08` needs the
`try` rule as well, and the three `sum(map)` probes already match.
