# job job-fuzz73-10231543  started 2026-10-23T06:44:46Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `23f6de0`.

**Defect:** `[1] in d.keys()` returned `False` where CPython raises `TypeError: unhashable type: 'list'`. A `dict_keys` view is set-like and hashes its operand; the runtime scanned the snapshot with equality only. Fixed in `cruntime.py:ail_op_contains` by hashing first only for keys views. Values/items views keep compare-by-equality membership.

**Probes (both builds, all match CPython):**
- `f73_keys_unhashable.py` — list/dict/set, tuple nesting, empty view, via argument/list item/attribute/dict value.
- `f73_keys_hashable.py` — bool/int/float equal keys, tuples, frozensets, huge/negative/zero, empty, aliases, values/items views.
- `f73_keys_alias_bounds.py` — mutation through alias, clear, huge/negative keys, empty view.

**Tests on final commit:** 7 modules, 0 failed (`test_ail_fuzz73`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_silent1`, `test_ail_gaps_api2`, `test_ail_int_dict_set`). Manifest update and `--check` pass.

**Other difference seen:** `reversed(d)` raises `TypeError: 'dict' object is not reversible` on both builds; CPython returns reversed keys. `reversed(d.keys()/values()/items())` matches. This was not fixed (non-silent, one-cause rule).

**Records:** this export contains no `DEVLOG` or `DIFFERENCES` file, so no entries were added.
[cost $0.0000, opencode tokens {"total": 3117142, "input": 236440, "output": 12887, "reasoning": 8679, "cache.write": 0, "cache.read": 2859136}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed diff, ran probes on HEAD and `/tmp/base`, and re-ran the two required test modules.

**Claims**
- Verified: `[1] in d.keys()` (and dict/set/nested-tuple items) now raises `TypeError` as CPython does; base printed `False`.
- Verified: hash-first is gated on `aux == 1` (keys views); values/items membership probes still match.
- Verified: `reversed(d)` differs identically on base (both builds raise; CPython returns reversed keys) — pre-existing, non-silent.
- Verified: manifest `--check` passes, commit has the co-author trailer, no DEVLOG/DIFFERENCES files exist.
- Verified: `test_ail_fuzz73` and `test_ail_safetynet` pass on HEAD (0 failed). Other 5 modules not rerun, per reviewer rules.
- Unverified: speed (`perf_event_open: Permission denied`). The added path is a predictable branch on list membership; no indication of a hot-path regression.
- Incomplete: the worker's probe set missed views used as the *item*, which hides a regression (below).
- Unchanged-code check: non-view dict program's generated `program.c` differs only by the 4 inserted runtime lines.

**Pre-existing**
- `reversed(d)` raises `TypeError: 'dict' object is not reversible` on both builds; CPython returns its keys.

**VERDICT: FIX**
1. Regression: `d.values()` is hashable in CPython, so membership in `d.keys()` must be a plain `False`; the new hash-first path raises. Probe `/tmp/rprobes/p7_views_as_item.py`:
   ```python
   d = {'a': 1}
   print(d.values() in d.keys())
   ```
   Expected: `False` (matches base), actual HEAD: `TypeError: unhashable type: 'list'`. Cause: `ail_obj_hash` hashes a values view as if it were a list.
2. Related wrong hash error for view items in the same probe (not silent, but still not CPython): `d.items() in d.keys()` expected `TypeError: unhashable type: 'dict_items'`, actual `'list'`; `d.keys() in d.keys()` expected `'dict_keys'`, actual `'list'`. Base printed `False`, so the change improves the exit but the message names the internal list.
[cost $0.0000, opencode tokens {"total": 805413, "input": 59541, "output": 5940, "reasoning": 8028, "cache.write": 0, "cache.read": 731904}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `ail_obj_hash` (`AIL_CURRENT/python/pkg-v12/cruntime.py:14481`): values views now hash by identity (`False` for `d.values() in d.keys()`), and keys/items views report `dict_keys`/`dict_items` instead of `list`.

Commit: `0c12df5` (manifest `--check` passes, co-author trailer present).

Probes on both builds (all stdout equal to CPython):
- `p7_views_as_item`: pass
- `p8_values_hashable`: pass (CPython rc 1 / same KeyError)
- `p9_view_items_all`: pass
- `p10_other_membership`: pass
- `p11_views_as_item_final`: pass

Tests on final commit: `test_ail_fuzz73`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `reversed(d)` remains pre-existing/non-silent, unchanged.
[cost $0.0000, opencode tokens {"total": 1852098, "input": 114288, "output": 8026, "reasoning": 6136, "cache.write": 0, "cache.read": 1723648}]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 1487119, "input": 67221, "output": 5757, "reasoning": 12541, "cache.write": 0, "cache.read": 1401600}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T09:41:55Z
