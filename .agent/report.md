Implemented and committed on `job-fuzz13-10220829` at `a802180`.

Fixed 3 causes:
- Float `%`/`divmod` signed zero: `5.0 % -5.0` and `divmod(5.0, -5.0)[1]` now yield `-0.0`; `-5.0 % 5.0` yields `0.0`.
- `sum(xs, start)`: str start now raises CPython’s `TypeError`; tuple starts no longer print truncated fixed-shape tuples (`sum([(1,), (2,)], ())` now prints `(1, 2)`).
- Two-arg `min()`/`max()` of mixed int/float now compares exactly on the default build, preserving the selected operand and its type above 2**53.

Added `AIL_CURRENT/test_ail_fuzz13.py` (registered in `ail_check.py` and CI shards), plus DIFFERENCES placeholder rows `C?-job-fuzz13-10220829-1..3` and a DEVLOG entry.

Verification:
- 46 probe programs in `/tmp/probes`; 40 match CPython on both builds. 6 are non-silent build/runtime failures: `chr_ord`, `int_base_types`, `isinstance_empty`, `isinstance_tuple`, `round_special`, `round_special2`.
- Final-commit tests: `test_ail_fuzz13`, `test_ail_fuzz3`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_unified` — all 8 passed.
- `test_ail_silent6` still fails on its pre-existing `G17_SRC`/`functools.partial` case; reproduced at the base commit `5ff6370`.
- Manifest and CI-shard checks pass.
[cost $0.1678, opencode tokens {"total": 20218453, "input": 492870, "output": 29984, "reasoning": 28143, "cache.write": 0, "cache.read": 19667456}]
