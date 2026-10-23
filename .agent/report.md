# job job-fuzz78-10232333  started 2026-10-23T14:34:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `9c8e377`.

- First differing probe: `{**xs}` with a non-mapping. Empty list/str silently produced `{}`; `[1, 2]` caused an IndexError. `_ail_dmerge` now checks `isinstance(d, dict)` and raises `TypeError`, matching CPython.
- Added `AIL_CURRENT/test_ail_fuzz78.py` and registered it in `ail_check.MODULES` / `ci_shards.json`.
- Probes: 25 run; 18 matched CPython on both builds, 7 were named compile-time refusals (`**kwargs`, mixed/multiple `*args`, `*args` defs, dict subclass), none silently differed.
- Other observed differences were only those named refusals, unchanged by this fix.
- Tests: `test_ail_fuzz78`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `python3 tools/update_manifest.py --check` returns 0.
- No `DEVLOG`/`DIFFERENCES` files exist in this export, so no record files were updated.
[cost $0.0000, opencode tokens {"total": 6116525, "input": 335662, "output": 13586, "reasoning": 10605, "cache.write": 0, "cache.read": 5756672}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

Change: `_ail_dmerge` now requires `isinstance(d, dict)` before merging a `**` part. Non-mapping iterables (list/str/set/tuple/int) now raise `TypeError`, which is correct for those. But the check is too strict: CPython accepts any mapping protocol object, not only `dict` instances.

### Defect (caused by the change)

1. `**` of a real mapping that is not a `dict` subclass now fails. Base matched CPython; HEAD raises `TypeError`.

   Probe `/tmp/rprobes/p13.py`:
   ```python
   from collections import ChainMap

   def main() -> None:
       a: dict[str, int] = {"x": 1, "y": 2}
       b: dict[str, int] = {"y": 20, "z": 3}
       cm: ChainMap[str, int] = ChainMap(a, b)
       print({**cm})
       print({**cm, "w": 4})
   main()
   ```
   - CPython/base (general and default): `{'y': 2, 'z': 3, 'x': 1}` then `{'y': 2, 'z': 3, 'x': 1, 'w': 4}`, exit 0.
   - HEAD: no stdout, exit 1, `TypeError: 'ChainMap' object is not a mapping`.
   - ChainMap is a supported AIL library type (`test_ail_stdlib5`), so this is a real regression.

   Probe `/tmp/rprobes/p04.py` (user mapping with `keys`/`__iter__`/`__getitem__`): CPython/base print `{'a': 1, 'b': 2}`, exit 0; HEAD exits 1 with the same `TypeError`. Cause: `AIL_CURRENT/ail_syntax.py:849` should test the mapping protocol (or at least `keys`/`__iter__`), not `isinstance(d, dict)`.

### Pre-existing (base also differs from CPython; not blockers)

- `/tmp/rprobes/p09.py`, keys-only mapping: CPython `{'a': 1}`; base `TypeError 'instance' object is not iterable`; HEAD `TypeError 'KeysOnly' object is not a mapping`.
- `/tmp/rprobes/p12.py`, `keys()` disagrees with `__iter__`: CPython `{'a': 1}`; base `{'b': 2}`; HEAD `TypeError`. Both wrong, so not introduced by this change.
- `UserDict`, `MappingProxyType`, `class D(dict)` are named compile-time refusals on both builds (acceptable).

### Verifying other claims

- Non-mapping inputs: verified. HEAD matches CPython for list/str/bytes/bool/float/int/tuple/set/None through argument, list item, attribute and dict value (`p01`/`p02`/`p03`/`p08`). Base showed exactly the reported `{}` for empty list and `IndexError` for `[1,2]` (`p01` base).
- New test + registration: verified in diff (`test_ail_fuzz78`, `ail_check.MODULES`, `ci_shards.json`).
- Tests: ran `test_ail_fuzz78` and `test_ail_safetynet` with `-j 2` on HEAD: 2 modules, 0 failed. `test_ail_files`/`test_ail_corpus_findings3` not run (worker claims them; unverified).
- `python3 tools/update_manifest.py --check`: rc 0, verified.
- No `DEVLOG`/`DIFFERENCES` files: verified.
- "No silently differing probes": false; `p13`/`p04` silently differ on HEAD.
- Program not using the feature (`nofeature.py`): `--debug-dir` `program.c` byte-identical base vs HEAD; only temp paths in `native_report.json` differ.
- Speed: only `g24_012.py` in `~/corpus/gdev` uses `{**}` (module-init, not hot). `tools/icount.c` could not run (`perf_event_open: Permission denied`), but the added check is O(1) per part at startup only.

VERDICT: FIX

1. `_ail_dmerge` rejects non-`dict` mappings that CPython accepts. Probe `/tmp/rprobes/p13.py` (`ChainMap`) and `/tmp/rprobes/p04.py` (custom `keys`/`__iter__`/`__getitem__` class): expected CPython/base output `{'y': 2, 'z': 3, 'x': 1}` / `{'a': 1, 'b': 2}` exit 0; HEAD prints nothing, exits 1 with `TypeError: 'ChainMap' object is not a mapping` / `TypeError: 'M' object is not a mapping`. Fix `AIL_CURRENT/ail_syntax.py:849` to accept the mapping protocol (e.g. iterate `keys()` when present) and add these cases to `test_ail_fuzz78.py`.
[cost $0.0000, opencode tokens {"total": 782858, "input": 36419, "output": 6218, "reasoning": 11133, "cache.write": 0, "cache.read": 729088}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `fc62969`.

- `_ail_dmerge` now merges dicts directly and any other mapping through `keys()`; non-mappings still raise CPython’s `TypeError`. This fixes the ChainMap regression and also corrects the pre-existing keys-only / `keys()` vs `__iter__` cases.
- Added ChainMap, keys-only, and keys/`__iter__` disagreement coverage to `test_ail_fuzz78.py`.

Probes (all match CPython on both builds):
`p13` (ChainMap), `p04` (custom mapping), `p09` (keys-only), `p12` (keys vs `__iter__`), plus new `fuzz78_review_mappings.py` (argument/list item/attribute/dict value) and `fuzz78_review_nonmapping.py` (empty/negative/wrong types/None).

Tests: `test_ail_fuzz78`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib5`, `test_ail_collections` — 6 modules, 0 failed. Post-commit `test_ail_fuzz78` — 0 failed. `update_manifest.py --check` rc 0. No DEVLOG/DIFFERENCES files exist in this export.
[cost $0.0000, opencode tokens {"total": 1208742, "input": 44165, "output": 6912, "reasoning": 7585, "cache.write": 0, "cache.read": 1150080}]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 1922472, "input": 57857, "output": 6163, "reasoning": 13460, "cache.write": 0, "cache.read": 1844992}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T17:15:38Z
