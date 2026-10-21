# Devlog

## 2026-10-21 - job-fuzz13-10220829

Differential fuzz round 13, builtins and conversions (44 small programs compared with CPython on the
general path and the default build). Fixed three causes: signed zero in float remainder/divmod,
`sum(xs, start)` with a str or tuple start, and two-argument `min()`/`max()` of a mixed int and
float on the default build. Added `AIL_CURRENT/test_ail_fuzz13.py`. Remaining differences are
non-silent build or runtime errors, listed in the job report (round of inf/nan, round outside
int64, `isinstance(x, ())`, chr/ord of non-BMP values, and the existing `test_ail_silent6`
G17_SRC `functools.partial` general-path crash, which reproduces at the base commit).
