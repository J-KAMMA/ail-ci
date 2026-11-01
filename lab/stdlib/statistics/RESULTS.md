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
  A non-literal `method=` is refused by name at compile time; only the literal `"linear"` is built
  (literal `"ranked"` keeps its own refusal), so a computed method cannot leak into a runtime error.
* `statistics.fmean(data, weights=...)` and the second positional weights argument, over int/float lists,
  including the length, zero-sum and empty errors. For two int lists the products are summed exactly in
  int64 (checked, so a product that leaves int64 stops with `OverflowError`) and the result is CPython's
  int / float division, which keeps the last bits above 2**53:
  `fmean([2**53+1]*3, weights=[1, 1, 1])` is `9007199254740994.0`. The denominator is still `fsum` of the
  weights converted to float, as in CPython, and it is checked for zero before the product sum.
* The refusal test in `test_ail_stdlib_batch4.py` and the named-refusal list in `test_ail_genlib.py` now use
  `statistics.linear_regression` for the name that stays unsupported.

`correlation(..., method="ranked")` is refused by name; only `method="linear"` is built. Forced general-path
builds (`AIL_UNIFIED_FORCE=1`) still refuse these names because the general path does not publish them; the
default build uses the typed path for every passing program above.

## Review fixes

The review found two defects in the first commit; both are fixed in the follow-up commit.

* A non-literal `correlation(..., method=...)` used to build and then stop with
  `ValueError: Unknown method: 'ranked'`; it is now refused by name at compile time (probe
  `j_ranked_var.py`). `p_corr_method_var.py` shows that both a computed `"linear"` and a computed
  `"bogus"` are refused by the same message; `p_corr_method_literal.py` still matches CPython for
  literal `"linear"` / `"bogus"`.
* Weighted `fmean` over two int lists converted both lists to float first, so values above 2**53 lost
  the last bits (`l_fmean_bigint.py`: `9007199254740992.0` instead of `9007199254740994.0`). The int
  path now sums the products exactly and divides once; `l_fmean_bigint.py`, `p_fmean_int_exact.py`,
  `p_fmean_int_mixed.py`, `p_fmean_int_errors.py`, `p_fmean_huge_weights.py` and `p_fmean_paths.py`
  match CPython. A product sum that leaves int64 stops loudly with `OverflowError`
  (`p_fmean_int_overflow.py`), never with a wrapped value; exact big-integer products are a larger
  feature, recorded below.

## Follow-ups (out of scope here)

* `07_regression.py` needs the named-tuple result of `statistics.linear_regression` and `proportional=`.
  Exact refusal:
  `lab/stdlib/statistics/07_regression.py:7:5: not in the subset: statistics.linear_regression used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev, quantiles, covariance, correlation are, over a list of int) (the general path could not build this program either); general path: statistics.linear_regression (not yet published in NAMES_library.json)`
* `08_normal_dist.py` needs `statistics.NormalDist` (pdf, cdf, inv_cdf, quantiles, samples). Exact refusal:
  `lab/stdlib/statistics/08_normal_dist.py:5:5: not in the subset: statistics.NormalDist used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, pvariance, variance, pstdev, stdev, quantiles, covariance, correlation are, over a list of int) (the general path could not build this program either); general path: statistics.NormalDist (not yet published in NAMES_library.json)`
* `quantiles` of ints interpolates with int64 arithmetic; data near the int64 limit whose scaled
  numerator leaves int64 stops with the language's loud `OverflowError` instead of CPython's float. Exact
  big-integer interpolation is a larger feature, not part of this task.
* Weighted `fmean` of two int lists whose product sum leaves int64 (`[2**53+1]*3` with the same weights)
  stops with the language's loud `OverflowError`; CPython's `math.sumprod` uses unbounded ints. The loud
  stop is the required behaviour (never a wrapped value); exact big-integer product sums are a larger
  feature.

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

Review probes (also run with `bash .agent/cmp.sh <probe> $PWD`):

| probe | default build | forced general build |
| --- | --- | --- |
| j_ranked_var.py (method held in a variable, `"ranked"`) | refused by name (`statistics.correlation(..., method=...) needs the literal 'linear' here; a computed method is not built`) | refused by name |
| l_fmean_bigint.py (weighted int fmean above 2**53, 3 and 5 points) | same stdout/exit as CPython (`9007199254740994.0` twice) | refused by name |
| p_fmean_int_exact.py (positional/keyword weights, negative data and weights, mixed magnitudes) | same | refused by name |
| p_fmean_int_mixed.py (int data with float weights, float data with int weights, literal lists) | same | refused by name |
| p_fmean_int_errors.py (length mismatch, zero-sum int weights, empty, literal length mismatch) | same | refused by name |
| p_fmean_huge_weights.py (products above 2**53 inside int64; zero-sum weights with large magnitudes) | same stdout and exit 1 as CPython | refused by name |
| p_fmean_paths.py (lists through a function argument) | same | refused by name |
| p_fmean_paths_refused.py (list item) | refused by name (`statistics.fmean with weights: the element type of the data is not known here`) | refused by name |
| p_fmean_attr_refused.py (attribute) | refused by name (same element-type message) | refused by name |
| p_fmean_dict_refused.py (dict value through a `dict[str, list[int]]` annotation) | refused by name (`'table' is annotated dict[str, list[int]], which this compiler has no rule for`) | refused by name |
| p_fmean_int_overflow.py (product sum leaves int64) | loud `OverflowError` (not a wrapped value); CPython prints the exact float | refused by name |
| p_corr_method_var.py (computed `"linear"` and `"bogus"` through a function argument) | refused by name (same computed-method message) | refused by name |
| p_corr_method_literal.py (literal `"linear"`, literal `"bogus"`) | same stdout/exit as CPython | refused by name |

The 10 `lab/compare/src/*/main.ail` programs' generated C was compared with the base commit: all 10 are
byte-identical. Of the CPython `main.py` sources, the 7 that build in the default mode are also
byte-identical; `scar_life`, `tally_lang` and `tree_fold` do not build in the default mode on either tree.
