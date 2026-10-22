# job job-fuzz23-10230421  started 2026-10-22T19:23:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first silent match difference: guard names were not substituted with Python scope rules.

- `case [x] if all(x == 9 for x in [1, 2])` on `[9]` printed `hit` here, `miss` in CPython.
- A free pattern name inside a guard lambda raised `NameError`.
- `matchlower.py` now shadows lambda parameters/comprehension targets correctly and substitutes their free names.

Commit: `dd98f7e`

Probes (`bash ~/tools/cmp.sh`, both builds): `p16b`, `p16`, `p18a`, `p19` all `same stdout`; `p01`–`p05`, `p09`, `p12`, `p17` also matched. `p11` was refused by name for out-of-range int64 literals.

Other observed differences, left unfixed:
- Sequence pattern on `range`: `TypeError: 'range' object is not subscriptable` (`p10`).
- Missing class attribute in a subclass or conditionally-initialized field raises `AttributeError` instead of failing the case (`p13`, `p14`).
- A heterogeneous list loop variable can reach a list `repr` helper, printing `[a]` for a dict (`p06`, `p08`, `p10`); match results themselves are correct.

Tests on final commit: `test_ail_fuzz23`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_match` — 5 modules, 0 failed (327s). `update_manifest.py --check` passes.

The export has no `DEVLOG` or `docs/spec/DIFFERENCES.md`, so no record files were edited.
[cost $0.0000, opencode tokens {"total": 5161468, "input": 123314, "output": 19122, "reasoning": 25368, "cache.write": 0, "cache.read": 4993664}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `dd98f7e` (match guard substitution)**

Scope: `matchlower.py` `_substitute` now tracks lambda/comprehension scopes; new `test_ail_fuzz23.py`; registration in `ail_check.py`; manifest pins.

**Probes (HEAD, both builds unless noted)**
- `comp_scopes.py` (comp target shadow, first iterable, nested/if/dict comps, restoration): HEAD matches CPython; base differs on the shadow/restoration cases → fix effective.
- `lambda_core.py`, `lambda_in_comp.py` (param/default shadowing, nested lambda, comp+lambda): HEAD matches; base refuses by name (acceptable).
- `lambda_free.py`: base `NameError`; HEAD matches CPython.
- `shapes.py` (star sequence, `**rest`, class, or-pattern, negative/empty): match results correct; only repr-of-object text differs (pre-existing).
- `match_noguard.py` / `nofeature.py`: both builds match CPython, generated `program.c`/`program_mix0.c` byte-identical to base.
- `comp_targets.py`, `comp_attrtarget.py`: named refusal (“Subscript/Attribute for-target”); acceptable.
- `walrus.py`: differs, but identically on base → pre-existing.
- Worker probes spot-checked: `p16b`, `p16`, `p18a`, `p19`, `p10`, `p11`, `p13`, `p06`.

**Tests**
- `test_ail_fuzz23` 11.8s ok; `test_ail_safetynet` 117.9s ok (`-j 2`, 0 failed).
- `update_manifest.py --check` rc=0. `ci_shards.py --check` reports `test_ail_fuzz23` unassigned, but the workflow’s `--shard` fallback still runs it; not required by the job.

**Report claims**
- Commit and guard-scope fix: verified.
- Stated `hit`/`miss` example and lambda `NameError`: verified.
- `p16b/p16/p18a/p19` same: verified; `p11` int64 refusal: verified.
- `p01–p05,p09,p12,p17`: unverified (not rerun; simple guards unaffected by this diff).
- Range pattern, missing class attr, dict repr differences: verified pre-existing (base identical).
- “5 modules, 0 failed”: fuzz23+safetynet verified; other three unverified.
- No `DEVLOG`/`DIFFERENCES.md` in export: verified.
- Extra pre-existing difference not listed: `p06` `None` subject raises `TypeError` instead of matching `_`.

**Pre-existing (non-blocking)**
- Walrus in a guard uses the pattern value, not the walrus result (HEAD == base).
- `[a, b, *rest]` on `range` crashes (`range` not subscriptable); `repr` of str/dict in the boxed-list path.
- Missing class attribute raises `AttributeError` instead of failing the case; `None` subject crash above.

The change fixes the target bug without regressions in the probed boundaries; no defect attributable to it.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2037908, "input": 66269, "output": 9382, "reasoning": 22417, "cache.write": 0, "cache.read": 1939840}]

FINAL VERDICT: ACCEPT  2026-10-22T19:50:35Z
