# DEVLOG

## 2026-10-23 - fuzz44 review: isolated value-form regression test

- Reviewer defect: the correctness programs in `test_ail_fuzz44.py` all contained a construct that
  forced the general path on the base commit, so the module passed there except for the diagnostic
  text test. Added an isolated `is None` value-form case for each of `append`, `reverse`, `sort` and
  `extend`; all four fail on the base default build (`False`) and match CPython (`True`) on HEAD.

## 2026-10-23 - fuzz44: list mutation methods used as values

- `xs.append(v)`, `xs.extend(it)`, `xs.reverse()`, `xs.sort()` and `xs.clear()` return None in
  CPython. The typed path had no None value and emitted the void C call into a temporary, so the
  default build failed in the C compiler while the general path printed the right answer.
- The typed path now refuses that value form by name (`list.append() returns None; use it as a
  statement`), so the default build takes the general path; a plain statement call is still built
  by the fast typed emitter.
- Added `AIL_CURRENT/test_ail_fuzz44.py`; no new silent difference remains, so no DIFFERENCES row.
