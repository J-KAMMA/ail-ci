Implemented and committed on `job-fuzz11-10220826` (`1cb1fd7`, docs follow-up `d6486dd`).

**Fuzz run:** 97 small programs across generators/closures, run with `cmp.sh` on both builds. 3 causes fixed:
1. Generator return values: `StopIteration.value`/`.args`, `next(g)` preservation, `next(g, default)`.
2. `g.close()` now throws GeneratorExit at the yield so `finally` runs; `except Exception` does not swallow it.
3. A nested function’s own `global` resolves to module storage even when the enclosing function has a local of the same name.

**Remaining:** 5 open differences recorded in `DIFFERENCES.md` (`C?-job-fuzz11-10220826-1..5`): unclosed/dropped generators skip `finally`; closing an outer `yield from` does not close the subgenerator; `iter(g) is not g`; generator expressions are eager; bare `except:` does not catch close’s GeneratorExit.

**Probes (all match CPython on both builds):** `probe_values.py`, `probe_close.py`, `probe_close_catch.py`, `probe_globals.py`, `probe_global_rec.py`, `probe_boundary.py`; plus `g01_basic`, `g28_gen_return_list`, `p0`, `stop_args`, `stop_value_assign`, `next_default`, `c14a`, `global_scope2`. The remaining-diff probes reproduce the five rows above.

**Tests on final code:** `test_ail_fuzz11`, `test_ail_nested_functions`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_globals`, `test_ail_genlib` — 7/7 passed. Manifest `--check` passes.
[cost $0.2321, opencode tokens {"total": 22773726, "input": 834979, "output": 34025, "reasoning": 34770, "cache.write": 0, "cache.read": 21869952}]
