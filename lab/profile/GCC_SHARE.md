# gcc time: runtime prelude vs the program's own code

Measured 2026-10-28 on the GitHub Actions runner (gcc 13.3.0, `cc` = gcc, `-j 2`).
Reproduce with `python3 lab/profile/measure_gcc_share.py 20`.

**Result: 18.8% of gcc time is the runtime prelude, 81.2% is the program's own code.**
The prelude is below 30%, so nothing was cached: this commit is the measurement only.

## Method

The compiler emits one C translation unit per program, in one of two shapes:

- the **typed path** (`cruntime` preamble, `py_main`): the runtime pieces, then the
  program's functions and `main`. `native_report.json` maps every program function body to a
  byte offset.
- the **general path** (`pyboxed2`, taken when the typed path refused the program): its
  translation unit carries the boxed runtime preamble and the `pf_*` program functions. Its
  report has **no mapped bodies**: the source regions in it describe the typed C that was
  refused, not the boxed unit that was written.

Each sampled program was compiled once with `compile --syntax python --debug-dir`, keeping
the generated C, and split as follows:

- typed path: at the first mapped program function body;
- general path: at the program-specific section comment before the interned attribute-name
  ids / forward declarations / program functions.

Everything before the split is the **prelude**, the rest is **program code**. The two shapes
are told apart by their preamble headers, not by the presence of `py_main`.

gcc was timed on `-c` with the flags the build itself used
(`-O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd
-fno-asynchronous-unwind-tables`), median of 5 runs, after one warm-up run:

- `full` — the whole generated C;
- `prelude` — the prelude text alone, which compiles as its own translation unit;
- `empty` — a trivial translation unit, the gcc startup floor (8.2 ms per run here).

`share = (prelude - empty) / (full - empty)`. The pooled share sums milliseconds over the
sample, so it weights a build by its cost; mean and median over programs are reported too.

## Sample

All 219 `.py` files under `lab/corpus/programs/*/` were shuffled with seed 20261028 and
walked in order; the first 20 that build were measured (11 general path, 9 typed path).
Four earlier candidates are refused by name and were skipped: `t456` (`sorted(d.items())`
tuple values), `t176` (`json.loads` needs a declared type), `t432` (generator expression
nested in a generator expression), `t419` (decimal). `t385.py` exists in both corpus
directories and both copies were measured.

| # | program | path | split | C bytes | full ms | prelude ms | prelude share |
|---|---------|------|-------|--------:|--------:|-----------:|--------------:|
| 1 | glm/t307.py | general | section | 584386 | 1633.2 | 383.6 | 23.1% |
| 2 | glm/t010.py | typed | mapped | 160866 | 324.1 | 31.8 | 7.5% |
| 3 | deepseek/t078.py | general | section | 587547 | 1136.6 | 389.6 | 33.8% |
| 4 | deepseek/t474.py | typed | mapped | 255483 | 609.4 | 283.9 | 45.9% |
| 5 | deepseek/t482.py | general | section | 682942 | 2817.5 | 403.2 | 14.1% |
| 6 | deepseek/t306.py | typed | mapped | 211418 | 338.4 | 35.5 | 8.3% |
| 7 | deepseek/t411.py | general | section | 593896 | 1768.1 | 390.6 | 21.7% |
| 8 | deepseek/t457.py | typed | mapped | 185570 | 433.7 | 38.1 | 7.0% |
| 9 | glm/t486.py | typed | mapped | 554316 | 2492.5 | 57.4 | 2.0% |
| 10 | deepseek/t264.py | general | section | 568603 | 1650.4 | 390.6 | 23.3% |
| 11 | glm/t275.py | general | section | 567202 | 1727.1 | 390.5 | 22.2% |
| 12 | deepseek/t308.py | typed | mapped | 182620 | 315.1 | 33.2 | 8.2% |
| 13 | deepseek/t339.py | general | section | 557211 | 1339.8 | 388.9 | 28.6% |
| 14 | deepseek/t080.py | typed | mapped | 195261 | 462.5 | 275.8 | 58.9% |
| 15 | glm/t385.py | general | section | 605799 | 2217.2 | 393.2 | 17.4% |
| 16 | glm/t166.py | general | section | 683783 | 2678.1 | 408.0 | 15.0% |
| 17 | glm/t095.py | typed | mapped | 277346 | 484.4 | 45.0 | 7.7% |
| 18 | deepseek/t208.py | general | section | 612874 | 2103.2 | 392.8 | 18.4% |
| 19 | deepseek/t385.py | general | section | 573583 | 1784.1 | 382.3 | 21.1% |
| 20 | deepseek/t443.py | typed | mapped | 209117 | 428.0 | 36.7 | 6.8% |

## Totals

| measure | value |
|---|---|
| gcc `-c` time, 20 programs | 26,743 ms |
| of which prelude (minus gcc floor) | 4,987 ms |
| **pooled prelude share** | **18.8%** |
| mean share over programs | 19.5% |
| median share over programs | 17.9% |
| general path only (11 programs) | 20.3% pooled |
| typed path only (9 programs) | 13.1% pooled |
| prelude bytes / generated C bytes | 93.0% (8,233,534 / 8,849,823) |

The prelude is 93% of the C *text* but only 18.8% of the gcc *time*: at `-O2`, optimizing the
program's own functions costs far more than parsing the (large) prelude.

As a check on the truly fixed part, a minimal program (`print(0)`, typed path) has a
20,649-byte prelude and takes 27.8 ms full vs 19.4 ms prelude and 8.5 ms empty in this run —
about 11 ms of gcc time per build for the base every program carries.

With gcc at about 59% of a build, the prelude is roughly `0.188 * 59% = 11.1%` of a build;
the program's own code is the remaining ~47.9%.

## Caveats

- The prelude text measured here includes the runtime pieces this program selected
  (`LIST`, `STR`, `OBJ`, ...) and, on the typed path, the few program declarations emitted
  before the first mapped body. It is therefore an upper bound on the strictly fixed prelude.
- Precompiled alone, the prelude's unused `static` functions are dropped early; in the full
  translation unit the prelude functions the program calls are optimized/inlined there, and
  that cost is counted in the program share. The split is the cost of the prelude text
  itself, which is what a cached object or PCH would remove.
- Shares vary widely per program (2.0% to 58.9%); two programs exceed 30% (`t080` 58.9%,
  `t078` 33.8%). Pooled and median shares are below 30%, so the condition "fixed part over
  30% of gcc time" is not met and no cache was built.
