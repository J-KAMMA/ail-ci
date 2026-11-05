# AIL limitations and documented differences

These are behaviours a reader might expect to match CPython 3.12 but that AIL deliberately does
not, with the reason and the stop rule. Everything else either matches CPython or is refused by
name (see `DIFFERENCES.md`).

## Recursion depth

AIL does **not** emulate CPython's default recursion limit of 1000. Recursion runs on the real C
stack, so a depth that fits keeps working: `descend(5000)` completes and prints its result, where
CPython raises `RecursionError` at its default limit. This is an owner decision (2026-11-05);
`lab/safety/stops/09_rec_deep5000.py` is classified as a **documented difference**, not as a
silent-wrong row.

Only an actual stack exhaustion stops the program. It stops loudly and by name:

- the general path (and the default build for a recursive method or nested function) counts
  frames in `AIL_FRAME_ENTER`/`AIL_FRAME_LEAVE` and raises
  `RecursionError("maximum recursion depth exceeded")` at `AIL_MAX_GENERAL_CALL_DEPTH` (10000)
  through its ordinary exception path, so `except RuntimeError` and `except RecursionError` catch
  it and a `finally` runs;
- the typed path keeps its own check at `AIL_MAX_RECURSION_DEPTH` (50000) and reports the same
  name;
- an uncaught one exits 1 with `RecursionError: maximum recursion depth exceeded` as the last
  stderr line. It never dies with a bare signal and empty stderr.

Because the general path's frames are larger than the typed path's, its cap is lower. Both caps
are well above the depth of any program that worked before the guard existed.
