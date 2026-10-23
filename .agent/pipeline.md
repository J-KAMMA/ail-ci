# job job-pre1-10240007  started 2026-10-23T15:08:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the pre-existing positional-only refusal recorded by the `modules3` review (the quoted note was registration-only; the actual difference was `kwonly_default` with `def f(a, /, *, b=2)`).

**Commit:** `381dfe6` — `pre1: bind positional-only parameters on the general path`
- `pyboxed2.py`: bind `posonlyargs` before `args`; reject positional-only names passed as keywords; nested defs too.
- `unified.py`: include positional-only annotations in hints.
- Added `AIL_CURRENT/test_ail_pre1.py` (4 tests), `DEVLOG` entry, refreshed `MANIFEST.json` (`--check` passes).

**Probes** (`cmp.sh`, both builds; 20 programs):
- Matched CPython (14): `p_kwonly_default`, `p_kwonly_posonly`, `p_posonly_alias`, `p_posonly_default`, `p_posonly_defaults`, `p_posonly_methods`, `p_posonly_nested`, `p_posonly_typed`, `p_posonly_unrelated`, `p_posonly_values`, `p_posonly_varargs`, `p_pre1_case1`, `p_pre1_case2`, `p_pre1_case3`.
- Refused by name (6): `p_posonly_keyword_refuse`, `p_posonly_duplicate`, `p_posonly_method_kw_refuse`, `p_posonly_nested_kw_refuse`, `p_posonly_missing`, `p_posonly_star_call` (last is the pre-existing starred-call limit).
- Non-positional-only `program.c` and `program_mix0.c` hashes are identical to the base tree.

**Tests on final commit:** `test_ail_pre1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 255 s, 0 failed.

No `DIFFERENCES` file exists in this CI mirror, so no row was added.
[cost $0.0000, opencode tokens {"total": 6174490, "input": 254255, "output": 17413, "reasoning": 12262, "cache.write": 0, "cache.read": 5890560}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `381dfe6` against `/tmp/base` (work). Probes are in `/tmp/rprobes`; sampled the worker's probes in `/tmp/probes`.

**Verified**
- Base refuses `def f(a, /, *, b=2)` on both builds; HEAD matches CPython. Positional-only ordering, defaults (including def-time evaluation), `*args`/`**kwargs`, methods/static/classmethods/properties, inheritance, nested defs, `lru_cache`, generators, exceptions, typed/unified hints all matched in ~50 probes.
- A positional-only name passed as a keyword is refused by name (typed, untyped, method, nested, duplicate/missing/too-many/star calls).
- Non-posonly output unchanged: `g00_000` and `g01_010` `program.c` and binaries are byte-identical to base; `update_manifest.py --check` exits 0.
- `test_ail_pre1` + `test_ail_safetynet`: 2 modules, 0 failed.
- `test_ail_pre1.py` has 4 tests, DEVLOG entry present, no DIFFERENCES file exists.

**Unverified**
- The worker's 20 named probes and the `test_ail_files`/`test_ail_corpus_findings3` run claim (not rerun per review rules). `program_mix0.c` hash claim.
- Instruction counts: `perf_event_open` is denied in this container. The change is compile-time only and the two gdev binaries are identical, so no runtime impact.

**Pre-existing** (same failures on base without positional-only)
- Bound method used as a value: `AttributeError`.
- `cls.attr` inside a classmethod: `AttributeError`.
- Nested defs with non-constant defaults, and function values with defaults, are refused.
- Note: `def f(a=1, /, **kw); f(a=2)` is refused on HEAD although CPython puts `a` in `kw`; this is a named compile-time refusal and is acceptable under the review rules.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 5045399, "input": 108003, "output": 14522, "reasoning": 25594, "cache.write": 0, "cache.read": 4897280}]

FINAL VERDICT: ACCEPT  2026-10-23T15:52:02Z
