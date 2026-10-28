# gcc time: runtime prelude vs the program's own code

Measured 2026-10-28 on the GitHub Actions runner (gcc 13.3.0, `cc` = gcc, `-j 2`).
Reproduce with `python3 lab/profile/measure_gcc_share.py 20`.

**Result: 19.5% of gcc time is the runtime prelude, 80.5% is the program's own code.**
The prelude is below 30%, so nothing was cached: this commit is the measurement only.

## Method

The compiler emits one C translation unit per program: the includes, the `cruntime.emit`
runtime pieces and helper declarations, then the program's functions and `pyc`'s `main`.
Each sampled program was compiled once with `compile --syntax python --debug-dir`, keeping
the generated C. `native_report.json` maps every program function body to a byte offset; the
text before the first mapped body is the **prelude**, the rest is **program code**.

gcc was timed on `-c` with the flags the build itself used
(`-O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd
-fno-asynchronous-unwind-tables`), median of 5 runs, after one warm-up run:

- `full` — the whole generated C;
- `prelude` — the prelude text alone, which compiles as its own translation unit;
- `empty` — a trivial translation unit, the gcc startup floor (7.2 ms per run here).

`share = (prelude - empty) / (full - empty)`. The pooled share sums milliseconds over the
sample, so it weights a build by its cost; mean and median over programs are reported too.

## Sample

All 219 `.py` files under `lab/corpus/programs/*/` were shuffled with seed 20261028 and
walked in order; the first 20 that build were measured (11 typed path, 9 general path).
Four earlier candidates are refused by name and were skipped: `t456` (`sorted(d.items())`
tuple values), `t176` (`json.loads` needs a declared type), `t432` (generator expression
nested in a generator expression), `t419` (decimal). `t385.py` exists in both corpus
directories and both copies were measured.

| # | program | path | C bytes | full ms | prelude ms | prelude share |
|---|---------|------|--------:|--------:|-----------:|--------------:|
| 1 | glm/t307.py | typed | 584386 | 1598.9 | 387.4 | 23.9% |
| 2 | glm/t010.py | general | 160866 | 290.4 | 31.3 | 8.5% |
| 3 | deepseek/t078.py | typed | 587547 | 1137.5 | 385.9 | 33.5% |
| 4 | deepseek/t474.py | general | 255483 | 594.6 | 278.7 | 46.2% |
| 5 | deepseek/t482.py | typed | 682942 | 2778.6 | 398.9 | 14.1% |
| 6 | deepseek/t306.py | general | 211418 | 327.6 | 35.1 | 8.7% |
| 7 | deepseek/t411.py | typed | 593896 | 1705.8 | 381.9 | 22.1% |
| 8 | deepseek/t457.py | general | 185570 | 422.2 | 37.4 | 7.3% |
| 9 | glm/t486.py | general | 554316 | 2387.1 | 55.2 | 2.0% |
| 10 | deepseek/t264.py | typed | 568603 | 1577.9 | 376.2 | 23.5% |
| 11 | glm/t275.py | typed | 567202 | 1671.7 | 383.9 | 22.6% |
| 12 | deepseek/t308.py | general | 182620 | 321.9 | 36.1 | 9.2% |
| 13 | deepseek/t339.py | typed | 557211 | 1309.0 | 384.3 | 29.0% |
| 14 | deepseek/t080.py | general | 195261 | 456.1 | 272.4 | 59.1% |
| 15 | glm/t385.py | typed | 605799 | 2217.9 | 396.6 | 17.6% |
| 16 | glm/t166.py | typed | 683783 | 3278.1 | 592.2 | 17.9% |
| 17 | glm/t095.py | general | 277346 | 692.9 | 64.5 | 8.4% |
| 18 | deepseek/t208.py | typed | 612874 | 2424.2 | 584.0 | 23.9% |
| 19 | deepseek/t385.py | typed | 573583 | 1989.7 | 391.9 | 19.4% |
| 20 | deepseek/t443.py | general | 209117 | 433.4 | 35.6 | 6.6% |

## Totals

| measure | value |
|---|---|
| gcc `-c` time, 20 programs | 27,615 ms |
| of which prelude (minus gcc floor) | 5,365 ms |
| **pooled prelude share** | **19.5%** |
| mean share over programs | 20.2% |
| median share over programs | 18.6% |
| typed path only (11 programs) | 21.2% pooled |
| general path only (9 programs) | 13.3% pooled |
| prelude bytes / generated C bytes | 97.1% (8,593,466 / 8,849,823) |

The prelude is 97% of the C *text* but only 19.5% of the gcc *time*: at `-O2`, optimizing the
program's own functions costs far more than parsing the (large) prelude.

As a check on the truly fixed part, a minimal program (`print(0)` in `main`) has a 20,717-byte
prelude and takes 40 ms full vs 28 ms prelude and 12 ms empty in this run — about 16 ms of
gcc time per build for the base every program carries.

With gcc at about 59% of a build, the prelude is roughly `0.195 * 59% = 11.5%` of a build;
the program's own code is the remaining ~47.5%.

## Caveats

- The prelude text measured here includes the runtime pieces this program selected
  (`LIST`, `STR`, `OBJ`, ...) plus program-specific class/module declarations emitted before
  the first function. It is therefore an upper bound on the strictly fixed prelude.
- Precompiled alone, the prelude's unused `static` functions are dropped early; in the full
  translation unit the prelude functions the program calls are optimized/inlined there, and
  that cost is counted in the program share. The split is the cost of the prelude text
  itself, which is what a cached object or PCH would remove.
- Shares vary widely per program (2.0% to 59.1%); two programs exceed 30% (`t080` 59.1%,
  `t078` 33.5%). Pooled and median shares are below 30%, so the condition "fixed part over
  30% of gcc time" is not met and no cache was built.
