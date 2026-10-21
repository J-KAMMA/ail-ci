Committed on `job-intenum4-10220559` as `8bfa137`.

**Changes**
- Added `__pow__` / `__rpow__` to `_AilIntEnum`; 2- and 3-argument `pow()` now accept IntEnum/IntFlag members.
- Equality is now value-based only between int-like enum members. An IntEnum/IntFlag member no longer equals a plain Enum/Flag member with the same value; StrEnum follows the same rule. Cross-kind arithmetic/ordering now raises instead of returning a numeric result.
- Int `% 0` now says `integer modulo by zero`; `//` and `divmod(int, 0)` keep `integer division or modulo by zero`; float `divmod(x, 0)` says `float divmod()` on both general and typed paths.
- Added `AIL_CURRENT/test_ail_intenum4.py`, plus `DIFFERENCES.md` and `DEVLOG.md`.
- `update_manifest.py` run and `--check` passes.

**Probes — all 10 match CPython on both `g` and `d`**
`pow_basic.py`, `enum_int_edges.py`, `eq_enum.py`, `enum_ops_plain.py`, `enum_cross_behavior.py`, `divmod_text.py`, `zero_division_int.py`, `zero_division_float.py`, `typed_divmod_zero.py`, `int_pow.py`. `typed_divmod_zero.py` also matches on the typed path with `AIL_NO_GENERAL=1`, IR 0 and 1.

**Tests**
- 9/10 modules pass on the final commit: `test_ail_intenum4`, `test_ail_cov2`, `test_ail_stdlib5`, `test_ail_deqctr`, `test_ail_exc_str`, `test_ail_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- `test_ail_silent6` fails, but the same failure reproduces on the untouched base archive: `pyboxed2.py:1295 AttributeError: 'Lambda' object has no attribute 'lineno'` while compiling its `functools.partial` source. It is pre-existing and unrelated.

Not pushed. One caveat: reversed cross-enum comparison *error text* still names `'instance'` in some cases; the final probe verifies the exception type, not that pre-existing wording.
[cost $0.23, turns 112]
