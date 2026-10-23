# job job-fuzz56-10231354  started 2026-10-23T04:55:34Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Found and fixed: a `@contextmanager` generator that replaces a body exception with a **new exception of the same type and message** was treated as the sent exception, so AIL re-raised the original. `prelude_with.py` now compares `e2 is exc` like CPython.

- Probes: 14 matched CPython on both builds; 2 refused (BaseException handler, constructing builtin exception). Other differences seen: `__exit__` receives `tb=None` (p1), and a generator re-raising `StopIteration` becomes `RuntimeError` (cm_stopiter_probe) — not fixed.
- Tests on final commit `de942e0`: `test_ail_fuzz56`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `test_ail_cov2` also passed. Manifest `--check` passes.
- Added `test_ail_fuzz56.py` (4 programs), registered it, refreshed manifest and CI shard weights. No push. `DIFFERENCES.md`/`DEVLOG` are absent from this export, so no entries were added.
[cost $0.0000, opencode tokens {"total": 2562914, "input": 200858, "output": 12518, "reasoning": 10978, "cache.write": 0, "cache.read": 2338560}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: contextmanager exception identity fix

**Change** (`de942e0`): `_AilGenCM.__exit__` now compares `e2 is exc` (as CPython 3.12 does) instead of class-name + message. Also adds `test_ail_fuzz56.py`, registers it, updates manifest and CI shard. No other source changes.

**Probes** (`~ /tools/cmp.sh`, both general/default builds, run on HEAD and base):
- `p_same` (new same-type/same-message replacement): base differs (`caught True 1` vs CPython `False 2`); HEAD matches. Confirms both the bug and the fix.
- `p_bare` (same object re-raised), `p_suppress`, `p_difftype`, `p_rt`, `p_helper`: match CPython on both builds.
- Values via argument/attribute/dict/list (`p_sources`), nested with (`p_nested`), custom `__exit__` truthiness incl. 0/1/""/[]/None (`p_custom`), empty/zero/negative/huge yields (`p_empty`): all match.
- `p_plain` (no with/contextlib): generated `program.c`/`program_mix0.c` byte-identical to base (`--debug-dir`).

**Pre-existing (identical on base, not blocking):**
- `p_stopiter`: re-raised `StopIteration` becomes `RuntimeError generator raised StopIteration` on both builds.
- `p_tb`: `__exit__` receives `tb=None`; base and HEAD both differ from CPython.

**Tests** on HEAD (`python3 ../tools/par_check.py -j 2`): `test_ail_fuzz56`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (4 modules, 178s). Manifest `--check` and JSON parse pass; no whitespace errors.

**Claim check:** fix verified; `tb=None` and StopIteration differences verified; four named test modules verified; manifest/registration verified; DIFFERENCES.md/DEVLOG genuinely absent; the `test_ail_cov2` claim was not rerun (unverified). The "14 probes / 2 refusals" count could not be reproduced (probes not committed) but is not material.

**Speed:** no hot-path effect—the changed line runs only when a generator raises while handling an exception. The only gdev program using `contextmanager` (`g15_036.py`) handles `BaseException` and is refused, so no relevant benchmark exists.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 739322, "input": 63023, "output": 5569, "reasoning": 11786, "cache.write": 0, "cache.read": 658944}]

FINAL VERDICT: ACCEPT  2026-10-23T05:17:06Z
