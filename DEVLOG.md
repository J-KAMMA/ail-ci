# Development log

## 2026-10-23 - job-fuzz63-10231421

- Fixed the sign of a zero float remainder (`%`) on the general, unified and boxed paths: CPython uses the divisor's sign (`copysign(0.0, divisor)`), so `-0.0 % 1.0` is `0.0` and `0.0 % -1.0` is `-0.0`. Added `AIL_CURRENT/test_ail_fuzz63.py` with literal, argument, list, dict, attribute, augmented-assignment, chained and nonzero boundary cases on both builds.
