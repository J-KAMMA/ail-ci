# AIL development log

## 2026-10-21 — fuzz10: f-strings and str.format

Differential fuzzing of f-string/`str.format` specs (conversions, nested fields, dynamic width
and precision, fill/alignment, `=`, bool/None, escaped braces): 130 small programs, 119 identical
on both builds before any change, 10 corrected to valid CPython programs after the run, 1 runtime
limit (`:c` above U+FFFF). Three silent differences fixed, with `AIL_CURRENT/test_ail_fuzz10.py`:

1. The IR text lowerer silently dropped sign, `#`, grouping, `=` alignment and non-decimal int
   types; such fields now stay on the legacy formatter.
2. The general-path runtime parser/padder did not parse an explicit `=` alignment and did not
   treat a space sign as a sign under zero padding; the `0` flag now fills with zeros beside an
   explicit alignment unless a fill character was written (cruntime.py, safetyrt.py).
3. The typed path did not infer a bool through `for b in (True, False)`, and `!s` with a format
   spec formatted the number instead of its text; both now convert before formatting.

No new lasting CPython differences were added, so `docs/spec/DIFFERENCES.md` (not present in this
checkout) has no new rows.
