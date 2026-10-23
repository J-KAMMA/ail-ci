# DEVLOG

## 2026-10-23

- fuzz42: fixed bool `abs()` on the general path. `abs(False)`/`abs(True)` kept the BOOL tag and
  printed `False`/`True` instead of CPython's `0`/`1`; the inline lowering in `pyboxed2.py` (and the
  same lowering behind the builtin-as-`key=`/`map()` wrapper) now calls `ail_bi_abs`, which boxes an
  intlike argument as an int. Added `test_ail_fuzz42.py`.
