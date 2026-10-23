# Development log

## 2026-10-23 - job-fuzz72-10231542

- Fixed general-path `str.casefold()` on non-ASCII text (`C?-job-fuzz72-10231542-1`): the boxed
  path now uses the full Unicode casefold table instead of the ASCII-only `lower()` helper.
- Added `AIL_CURRENT/test_ail_fuzz72.py`, covering sharp s, Turkish i, final sigma, combining
  marks, fullwidth digits, empty/large inputs, indirect values, and the compile-time refusal of a
  casefold argument.
