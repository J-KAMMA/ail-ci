Commit `d53b95b` on `job-fuzz10-10220606` (fixes in `f75a3d9`); tree clean, manifest `--check` passes.

**Results:** 130 small f-string/`str.format` programs. After fixes, 129 valid programs: 128 match CPython on both builds, 1 still errors at run time (`:c` above U+FFFF). No remaining silent wrong stdout in this set.

**3 causes fixed:**
1. IR text lowering silently dropped sign, `#`, grouping, `=` alignment and non-decimal int types; such fields now use the legacy formatter.
2. Runtime spec parsing/padding did not handle explicit `=` alignment, zero-fill beside explicit alignment, or space-sign zero padding (`cruntime.py`, `safetyrt.py`).
3. Typed path did not infer bools from `for b in (True, False)`, and `!s` with a spec formatted the number instead of its text.

**Probes** (`/tmp/probes`, both builds): `f10_sign_int`, `f10_sign_float`, `f10_eq_align`, `f10_bool_tuple`, `f10_conversion_s`, `f10_general_int`, `f10_escaped_nested` — all 2/2 same as CPython.

**Tests on final commit:** new `test_ail_fuzz10` 2/2; `test_ail_boolfield` 3, `test_ail_cov2` 7, `test_ail_stdlib_batch1` 12, `test_ail_ir_s4a` 25, `test_ail_corpus_findings3` 2, `test_ail_safetynet` 5, `test_ail_files` 18 (1 skipped) — all pass.

**Remaining:** `f"{0x1F600:c}"` hits the 16-bit runtime internal error on both builds (not a silent answer); `!a` remains refused by name. `DEVLOG.md` added; this checkout has no `DIFFERENCES.md`, so no new rows.
[cost $0.1110, opencode tokens {"total": 13648479, "input": 231047, "output": 35980, "reasoning": 24524, "cache.write": 0, "cache.read": 13356928}]
