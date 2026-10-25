# DEVLOG

## 2026-10-25 - bigint-fix07 (job-bigint-fix07-10260546)

- Module-variable reads/writes no longer force the general path on the Python surface. `ir/driver.py`
  drops the blanket refusal and treats the local proof's unknown module-variable operand as the
  int64 static it is, so the IR lowers `global.load` / `global.store` as before the big-int work.
- `bigcap.py` uses the module literal of a `global`-written variable for a constant power when no
  other unit (and no earlier store in the same function) can have replaced it. This keeps
  `e = 2; e **= 5` on the typed path instead of marking every exponent >= 4.
- Probes: `mv1.py` prints `2` with `AIL_NO_GENERAL=1`; `test_ail_globals` 32/32. `test_ail_bigint`,
  `test_ail_tint`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files` and
  `test_ail_corpus_findings3` pass. `test_ail_dunders`, `test_ail_nested_functions` and
  `test_ail_unbound` keep the same pre-existing failures as the base commit.
