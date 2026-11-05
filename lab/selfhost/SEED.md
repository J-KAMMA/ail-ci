# Estimate of the committed C seed

Measured on `2026-11-05` (base commit `02796a50b344bf219af144c190b148b797e8876c`). Measurement only: no compiler source was edited.

The self-hosting plan commits the generated C of the AIL-written compiler so a user can
build AIL with only a C compiler. This estimates how large that C seed would be, from a
corpus of programs that build today.

## Corpus

47 programs built (plus the two bare builds); 7 failed to build and are listed only in
`seed_corpus.json`. 21 built on the typed path and 26 on the general path; by AST nodes the
mix is 62.7% typed / 37.3% general.

| mode | programs | AST nodes | C bytes | gzip bytes | binary bytes (stripped) |
|------|----------|-----------|---------|------------|--------------------------|
| typed | 21 | 30021 | 6,488,227 | 1,674,417 | 1,141,176 |
| general | 26 | 17827 | 26,736,740 | 4,805,433 | 9,110,104 |

Fixed runtime part (bare build, subtracted before every fit): typed C 135,284 bytes / binary
14,472 bytes; general C 561,350 bytes / binary 55,616 bytes.

## Fits (least squares through the origin)

| model | slope | R^2 | median abs error |
|-------|-------|-----|------------------|
| typed C per AST node | 93.98 | 0.795 | 19.9% |
| typed C per source line | 847.57 | 0.773 | 18.5% |
| typed binary per AST node | 21.77 | 0.766 | 24.9% |
| typed binary per source line | 195.92 | 0.743 | 27.4% |
| general C per AST node | 546.20 | 0.506 | 25.7% |
| general C per source line | 4394.67 | 0.424 | 24.3% |
| general binary per AST node | 343.94 | 0.548 | 49.1% |
| general binary per source line | 2771.01 | 0.459 | 44.8% |

The general per-line C fit is weak (R^2 0.424); the per-node fit is used where it is
the better one. The worst-decile ratio is dominated by the small stdlib programs, whose
generated C carries per-module glue the bare build does not include, so it is a bound.

The estimate uses the better-fitting unit per mode and metric (C: typed per_node, general per_node;
binary: typed per_node, general per_node).

## Compiler scope (counted with `ast`, never compiled)

`AIL_CURRENT/python/pkg-v12/*.py` plus `ail_chatgpt.py`, `ail_syntax.py` and
`ail_modules.py`: 160 files, 188,365 source lines (no blank/comment lines), 1,508,278 AST nodes,
3,266 top-level functions.

## Estimates

| bytes | low (all typed, best fit) | mid (corpus typed/general mix) | high (all general, worst decile) |
|-------|---------------------------|-------------------------------|----------------------------------|
| C source | 141,881,434 | 396,163,712 | 10,642,332,482 |
| C gzipped | 27,671,071 | 77,263,626 | 2,075,569,199 |
| binary, stripped | 32,849,809 | 213,909,228 | 5,673,710,177 |

The gzip estimate applies the corpus ratio 0.195 (gzip bytes / C bytes) to the C estimate.

## How the numbers compare

- C source: low 141.9 MB, mid 396.2 MB, high 10642.3 MB; mid is 3.96x GitHub's 100 MB file
  limit and high is 106.42x it.
- gzipped C: low 27.7 MB, mid 77.3 MB, high 2075.6 MB; mid is 0.77x GitHub's 100 MB file
  limit and high is 20.76x it.
- binary: low 32.8 MB, mid 213.9 MB, high 5673.7 MB; mid is 2.14x GitHub's 100 MB file
  limit and high is 56.74x it.
- The mid C estimate (396.2 MB) does not fit GitHub's 100 MB file limit as one file; the
  gzipped mid estimate (77.3 MB) does, so committing the C gzipped or split into files is
  required by the mid case, and the high case fits neither.
- Today's Python sources of the compiler are 205,201 lines in 160 files; the C seed's mid
  estimate is 1930.6 bytes per Python source line.

## What could make this wrong

- The corpus is small (47 programs) and much smaller than the compiler: the largest row is
  3,841 AST nodes against 1,508,278 for the compiler. The fit is a per-node ratio, so a compiler
  that emits disproportionately more C per node (long functions, many string literals,
  large constant tables) lands above it.
- The corpus is written for AIL's current subset. A self-hosting compiler is one huge
  module with module-level state and many small helpers; C emitted per AST node for a
  program of 200k lines may differ from small programs because the runtime is shared.
- The self-hosted compiler is not written yet, so its AST node count is the Python
  compiler's. A different implementation or AST shape moves the estimate directly.
- The typed/general mix is unknown before the rewrite. The low estimate assumes the whole
  compiler becomes typed code; the high estimate uses the general path's worst decile
  ratio, which is a deliberately pessimistic bound, not a prediction.
- Generated C is counted once per program. The real seed links the compiler's own modules
  plus the C runtime; duplicates of the runtime across translation units are not modeled.

<!-- estimates: {"binary_bytes":{"high":5673710177,"low":32849809,"mid":213909228},"c_bytes":{"high":10642332482,"low":141881434,"mid":396163712},"gzip_bytes":{"high":2075569199,"low":27671071,"mid":77263626}} -->
