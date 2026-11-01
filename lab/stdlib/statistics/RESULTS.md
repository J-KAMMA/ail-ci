# `statistics` coverage (job-std_statistics-11011523)

Environment: CPython 3.12.3, the default build `python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python`
(typed path first, general path as the fallback). Date: 2026-11-01.

## Before the fixes

| program | result | first message |
| --- | --- | --- |
| 01_score_summary.py | typed | |
| 02_modes.py | typed | |
| 03_string_modes.py | typed | |
| 04_float_stats.py | typed | |
| 05_quantiles_report.py | refused | `statistics.quantiles used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev are, over a list of int) (the general path could not build this program either); general path: statistics.quantiles (not yet published in NAMES_library.json)` |
| 06_covariance_correlation.py | refused | `statistics.covariance used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev are, over a list of int) (the general path could not build this program either); general path: statistics.covariance (not yet published in NAMES_library.json)` |
| 07_regression.py | refused | `statistics.linear_regression used here is not built (...) ; general path: statistics.linear_regression (not yet published in NAMES_library.json)` |
| 08_normal_dist.py | refused | `statistics.NormalDist used here is not built (...) ; general path: statistics.NormalDist (not yet published in NAMES_library.json)` |
| 09_weighted_stats.py | refused | `statistics.fmean with keyword arguments (mu=, xbar=, weights=...) is not built (the general path could not build this program either); general path: statistics.fmean() with the keyword argument weights is not built on the general path` |
| 10_grouped_stats.py | general | typed refused `statistics.variance` with `xbar=` / `mu=`; the general path printed CPython's output |
| 11_geometric_harmonic.py | general | typed refused `statistics.geometric_mean` / `statistics.harmonic_mean`; the general path printed CPython's output |
| 12_error_handling.py | typed | |

Before: 7 of 12 built (5 typed, 2 general), 5 refused.

## After the fixes

| program | result |
| --- | --- |
| 01_score_summary.py | typed |
| 02_modes.py | typed |
| 03_string_modes.py | typed |
| 04_float_stats.py | typed |
| 05_quantiles_report.py | typed |
| 06_covariance_correlation.py | typed |
| 07_regression.py | refused (follow-up) |
| 08_normal_dist.py | refused (follow-up) |
| 09_weighted_stats.py | typed |
| 10_grouped_stats.py | general |
| 11_geometric_harmonic.py | general |
| 12_error_handling.py | typed |

After: 10 of 12 build (8 typed, 2 general) and all 10 match CPython's stdout and exit code. The test
`AIL_CURRENT/test_ail_std_statistics.py` (registered by `tests.d/test_ail_std_statistics.txt`) compiles every
passing program in the default mode, runs it and compares both exit code and stdout with CPython.

## What was fixed

* `statistics.quantiles` over `list[int]` and `list[float]`, with `n=` and `method=("exclusive"|"inclusive")`
  (`strt.quantiles_int` / `quantiles_f`, lowered by `statlib`). Error messages and their precedence follow
  CPython (`n < 1`, fewer than two points, then an unknown method).
* `statistics.covariance` and `statistics.correlation(..., method="linear")` over two int or float lists.
  The product sum is CPython's `math.sumprod` semantics: every float product is split with Dekker's
  two-product and the pieces are summed once by the existing `fsum`, which matters for ordinary data
  (`covariance([60, 83, 48, 100, 26], [12, 62, 3, 49, 55])` is `216.15`, not `216.14999999999998`).
* `statistics.fmean(data, weights=...)` and the second positional weights argument, over int/float lists,
  including the length, zero-sum and empty errors.
* The refusal test in `test_ail_stdlib_batch4.py` and the named-refusal list in `test_ail_genlib.py` now use
  `statistics.linear_regression` for the name that stays unsupported.

`correlation(..., method="ranked")` is refused by name; only `method="linear"` is built. Forced general-path
builds (`AIL_UNIFIED_FORCE=1`) still refuse these names because the general path does not publish them; the
default build uses the typed path for every passing program above.

## Follow-ups (out of scope here)

* `07_regression.py` needs the named-tuple result of `statistics.linear_regression` and `proportional=`.
  Exact refusal:
  `lab/stdlib/statistics/07_regression.py:7:5: not in the subset: statistics.linear_regression used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev, quantiles, covariance, correlation are, over a list of int) (the general path could not build this program either); general path: statistics.linear_regression (not yet published in NAMES_library.json)`
* `08_normal_dist.py` needs `statistics.NormalDist` (pdf, cdf, inv_cdf, quantiles, samples). Exact refusal:
  `lab/stdlib/statistics/08_normal_dist.py:5:5: not in the subset: statistics.NormalDist used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev, quantiles, covariance, correlation are, over a list of int) (the general path could not build this program either); general path: statistics.NormalDist (not yet published in NAMES_library.json)`
* `quantiles` of ints interpolates with int64 arithmetic; data near the int64 limit whose scaled
  numerator leaves int64 stops with the language's loud `OverflowError` instead of CPython's float. Exact
  big-integer interpolation is a larger feature, not part of this task.

## Probes (in `/tmp/probes`, run with `bash .agent/cmp.sh <probe> $PWD`)

| probe | default build | forced general build |
| --- | --- | --- |
| p_q_edges.py (n=0/-2/1/2/3/4/10/100, both methods, empty, one, duplicates, negatives, unknown method) | same stdout/exit as CPython | refused by name (`statistics.quantiles ... not yet published`) |
| p_q_float.py (float quantiles, inclusive/exclusive, one, empty) | same | refused by name |
| p_cov_corr_edges.py (negative ints, the 216.15 case, constant, short, one, invalid method) | same | refused by name (`statistics.covariance ...`) |
| p_cov_corr_float.py (float covariance/correlation, identity, formatted result) | same | refused by name |
| p_fmean_weights_edges.py (keyword and positional weights, negative weights, floats, zero sum, empty, length mismatch) | same | refused by name (`fmean ... weights ... general path`) |
| p_fmean_badkw.py (unknown keyword) | refused by name (`statistics.fmean does not take the keyword argument extra here`) | refused by name |
| p_st_values_refused.py (data through an attribute, a list item and a dict value) | refused by name (`statistics.quantiles: the element type ... is not known here`) | refused by name |
| p_st_correlation_ranked.py (`method="ranked"`) | refused by name (`statistics.correlation(..., method='ranked') is not built`) | refused by name |

The 10 `lab/compare/src/*/main.ail` programs' generated C was compared with the base commit: all 10 are
byte-identical. Of the CPython `main.py` sources, the 7 that build in the default mode are also
byte-identical; `scar_life`, `tally_lang` and `tree_fold` do not build in the default mode on either tree.
