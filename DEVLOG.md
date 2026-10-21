# Development log

## 2026-10-21

- Fuzzed 384 small random programs (str methods and str/list slices, both builds) against CPython.
  One silent difference: the general path's shared start/end clamp for `str.find`/`rfind`/`index`/
  `rindex`/`count`/`startswith`/`endswith` treated an inverted or past-the-end window as the empty
  window at the clamped start (`"aXbXc".find("", 10, 0)` printed `5`, CPython `-1`). `ail__win` now
  reports window validity and does not clamp `start` above the length; list/tuple `index` uses the
  same answer. Added `AIL_CURRENT/test_ail_fuzz3.py` with the window cases plus the method/slice and
  zero-step comparisons, registered it in `ail_check.MODULES`, and refreshed the manifest pins.
