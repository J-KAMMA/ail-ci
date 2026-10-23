# Development log

## 2026-10-23

- job-fuzz90-10231630 review fix: `ail_is` now refuses only equal text whose answer CPython
  cannot reproduce (same/empty/one-character values and equal bytes), compares bytes contents,
  and never refuses `bytearray`; equal longer strings built at run time match CPython again.
  Added the unequal-bytes, `bytearray`, dynamic and single-value cases to `test_ail_fuzz90.py`.
- job-fuzz90-10231630: refused `is` / `is not` on equal str and bytes values by name
  (`C?-job-fuzz90-10231630-1`), at compile time for two constants and at run time for values
  reaching the operator through a name, argument, container or field. Added `test_ail_fuzz90.py`.
  A separate `integer overflow` failure for `-2**63` chains was observed and left as pre-existing.
