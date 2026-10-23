# Development log

## 2026-10-23

- job-fuzz90-10231630: refused `is` / `is not` on equal str and bytes values by name
  (`C?-job-fuzz90-10231630-1`), at compile time for two constants and at run time for values
  reaching the operator through a name, argument, container or field. Added `test_ail_fuzz90.py`.
  A separate `integer overflow` failure for `-2**63` chains was observed and left as pre-existing.
