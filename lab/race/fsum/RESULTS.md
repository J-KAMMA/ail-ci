# fbfsum1: the opt-in fixed-order float sum, measured

`docs/design/PAR_REDUCE.md` (fbred1) defined the shared-int reduction; fbred2 built `PARRED`;
fbred3 lowered `acc += e` on an int accumulator.  This job implements D2 option b: the same
shape on a **float** accumulator, behind the compile-time opt-in `AIL_PAR_FSUM=fixed`.

## The rule

With the opt-in, `acc += e` on a float `acc` in a parallel body sums in fixed chunks of 4096
iterations.  Chunk `c` covers `[lo + c*4096, min(lo + (c+1)*4096, hi))`, so the layout depends
only on the iteration range.  Each chunk starts from `-0.0` (the IEEE identity: `-0.0 + x == x`
for every `x`, including `+0.0` and `-0.0`) and adds left to right; afterwards `acc` adds the
chunk sums left to right in chunk order, from its value before the loop.  NaN and infinities
flow as in any IEEE sum.  The result is deterministic but is not CPython's serial last bits;
`docs/DIFFERENCES.md` records that.

`lab/race/fsum/model.py` (`fixed_sum`) is that order written in Python; every probe below is
compared with it.  The runtime never uses a timed probe prefix: it would move the chunk
boundaries with the timing.

## Probe status (10 probes, `lab/race/fsum/`)

Built with `AIL_PAR_FSUM=fixed python3 -B AIL_CURRENT/ail_chatgpt.py compile <p> --syntax python
-o <exe>`, run at `AIL_THREADS` 1, 2, 4 and 16, **five runs each**, against `model.fixed_sum`.
**200 of 200 runs** printed the reference `repr`; every probe produced exactly one
`(exit status, stdout)` pair over all 20 runs.

| probe | covers | reference (`repr`) |
|---|---|---|
| `f01_ordinary` | 10000 ordinary values, eight chunks | `24997500.0` |
| `f02_cancel` | `1e16, 1.0, -1e16` | `0.0` |
| `f03_nan` | NaN (and +inf/-inf) flow through | `nan` |
| `f04_inf` | infinity flows through | `inf` |
| `f05_negzero` | all `-0.0`, acc starts `-0.0` | `-0.0` |
| `f06_below` | n = 4095, one partial chunk | `1364.9999999999688` |
| `f07_at` | n = 4096, exactly one chunk | `1365.333333333302` |
| `f08_above` | n = 4097, a full chunk and one item | `1365.6666666666354` |
| `f09_three` | 3 items at 16 threads | `0.0` |
| `f10_start` | acc starts at `100.0`, two chunks | `1249850.0` |

Without the opt-in (and with `AIL_PAR_FSUM=yes`), all ten are refused with exactly the old
text: `'acc' carries a value between iterations, so it must be an int local of the enclosing
function; write instead: ...`.  The whole stderr is byte-identical to `origin/integ`'s refusal
for the same program.

## `program.c` hashes (without the opt-in)

`PYTHONHASHSEED=0 AIL_NO_CACHE=1 --debug-dir`, this tree against `origin/integ` (a `git archive`
export): the 10 `lab/compare/src/*/typed.py` and the 16 `lab/race/reduce/*.py` probes.
**22 identical, 0 different.**  The new `PARREDF` part is only added to `ctx.parts` when
`AIL_PAR_FSUM=fixed`, so a default build never emits it.

## Bench (4-thread speedup)

`lab/race/fsum/bench_fsum.py`: `acc += i * 0.001` over 200,000,000 iterations, median of 3
runs of `/usr/bin/time -f %e`.  This runner: 4 logical CPUs (2 physical cores, 2 threads each).

| `AIL_THREADS` | runs (s) | median |
|---|---|---|
| 1 | 0.17 0.17 0.17 | 0.17 |
| 2 | 0.09 0.08 0.09 | 0.09 |
| 4 | 0.06 0.06 0.06 | 0.06 |

4-thread speedup: **0.17 / 0.06 = 2.83x** (target at least 2.5x).  All three thread counts print
`19999999900000.0`.

## Tests

`AIL_CURRENT/test_ail_par_fsum.py` (3 tests): the ten probes match the reference at 1/2/4/16
threads, three runs each; without the opt-in each is refused with the old text; an
`AIL_PAR_FSUM` value other than `fixed` does not opt in.
