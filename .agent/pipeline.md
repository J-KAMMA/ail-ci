# job job-fuzz40-10230821  started 2026-10-22T23:22:18Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed `83ae85a` on `job-fuzz40-10230821`.

## Cause
First silent wrong answer: `/tmp/probes/s24_nan_sort.py`. The general path `ail_list_sort` (`AIL_CURRENT/python/pkg-v12/cruntime.py`) sorted NaN keys into a merge-sort permutation while CPython's TimSort produced a different order; both builds exited 0. The typed paths already raise `ValueError` (`FLISTSORT`/`KEYSORT`/IR record sort), so the general path was the gap. Confirmed across `n1`/`n2`/`n3`/`n5`/`n6`/`n7` (literal, arithmetic, argument, list item, attribute, dict value, tuple field).

## Fix
- `cruntime.py:14974` `ail_sort_key_has_nan` recurses through `float`, `list`/`tuple`, and `dict` keys/values.
- `cruntime.py:15019` scans decorated keys before the merge and raises `AIL_B_VALUEERROR` (`ValueError: sorting a list whose key is or contains NaN is not supported`).
- Added `AIL_CURRENT/test_ail_fuzz40.py` (normal stability/key coverage + NaN source matrix + uncaught-name check), registered it in `ail_check.py:44`, ran `tools/update_manifest.py` (pin added) and `--check`.
- No `DEVLOG` or `DIFFERENCES` files exist anywhere in this shallow export, so no records were updated.

## Tests on final commit
`python3 -m unittest -v test_ail_fuzz40 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → `Ran 28 tests in 481.7s`, `OK (skipped=1)` (windows target, no zig).

## Probe self-check on final commit (33 probes)
- Match CPython, both builds (19): `s01`, `s02`, `s03`, `s04`, `s08`, `s09`, `s11`–`s17`, `s19`, `s20`, `s22`, `s23`, `s25`, `s26`.
- Now refused by name, both builds (7): `s24`, `n1`, `n2`, `n3`, `n5`, `n6`, `n7` (uncaught `ValueError`, exit 1).
- `n4_float_annotated`: both builds now catch the same `ValueError` and print it; stdout differs from CPython only because the probe prints the caught message.
- Compile-time refusals: `s05` (`itemgetter` with multiple args), `s06` (`attrgetter`), `s10` (key through function/attribute/dict/list plus untyped params), `s21` (g: literal outside int64).
- Other errors (not silent): `s07`/`s21`(d) `integer overflow`; `s18` g `AIL limit: str_lower_nonascii` while d matches CPython.
- Not verified: legacy `FROWS`/`FROWSKEY`/`SROW` NaN checks were not reached by any probe, so they were left unchanged.
[cost $0.0000, opencode tokens {"total": 6608297, "input": 291873, "output": 22720, "reasoning": 23496, "cache.write": 0, "cache.read": 6270208}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `83ae85a` (fuzz40 NaN sort)**

**Change reviewed**
- Adds `ail_sort_key_has_nan` and a scan in `ail_list_sort`; refuses NaN-containing sort keys with runtime `ValueError` on the general path.
- Adds/registers `test_ail_fuzz40.py`, updates `MANIFEST.json`.

**Probes (own, `/tmp/rprobes`, both builds unless noted)**
- Match CPython: `p01` (stability, multi-key, dict items, `str.lower`), `p05` (NaN elements, key avoids NaN), `p07` (dict-item stability/reverse), `p08` (empty/single NaN), `p09` (normal reverse), `p14` (NaN in element, key uses `len`).
- New refusal: `p06` (NaN key via argument), `p13` (deque).
- Defects: `p02`, `p03`, `p04`, `p11`, `p12`, `p15` (details below).
- Base (`/tmp/base`) comparison done for `p02`, `p03`, `p04`, `p15`; `p03`/`p04`/`p15` matched CPython on base.

**Claims check**
- Verified: base general path silently misordered NaN sorts (`/tmp/probes/s24_nan_sort.py`, base both builds differ from CPython); check added in `ail_list_sort`; `FLISTSORT` refuses NaN; test registered/manifest updated/check passes; no `DEVLOG`/`DIFFERENCES` files exist.
- Verified tests: `test_ail_fuzz40 test_ail_safetynet test_ail_files test_ail_corpus_findings3` all pass (323s, `-j 2`).
- Unverified: compile-time refusals `s05`/`s06`/`s10`/`s21`; `FROWS`/`FROWSKEY`/`SROW` coverage.
- Speed: `perf_event_open` denied (`perf_event_paranoid=4`), so `tools/icount.c` unusable. Wall times of forced-general `g03_032`, `g01_036`, `g05_000` were ~0.00–0.01s base vs HEAD; no measurable slowdown.

**Defects**
1. Over-broad refusal: valid sorts whose NaN is in a tuple component that never participates in a comparison are now rejected. Probe:
   ```python
   m = (1e308 * 10.0) - (1e308 * 10.0)
   rows = [(2, m), (1, m), (3, 0.5)]
   print(sorted(rows, key=lambda r: (r[0], r[1])))
   ```
   Expected (CPython and base): `[(1, nan), (2, nan), (3, 0.5)]`, exit 0. Actual (HEAD, g and d): no stdout, exit 1, `ValueError: sorting a list whose key is or contains NaN is not supported`. Same for keyless `p04`: `sorted([(2, m), (1, m)])`.

2. `list.sort(reverse=True)` mutates the list before the new refusal fires, so a caught `ValueError` leaves it reversed. Probe:
   ```python
   m = (1e308 * 10.0) - (1e308 * 10.0)
   x = [("a", m), ("b", 1.0), ("c", 2.0)]
   try:
       x.sort(key=lambda r: r[1], reverse=True)
   except ValueError:
       print("caught")
   print(x)
   ```
   Expected (CPython and base): `[('a', nan), ('c', 2.0), ('b', 1.0)]`, exit 0. Actual (HEAD, g and d): `caught` then `[('c', 2.0), ('b', 1.0), ('a', nan)]`. This probe matched CPython on base, so the change caused it. (`p02` on base default already shows the same reverse-then-refuse behavior for `FLISTSORT`; that part is pre-existing.)

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1510834, "input": 185304, "output": 7323, "reasoning": 16831, "cache.write": 0, "cache.read": 1301376}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `a63ee5e` on `job-fuzz40-10230821`.

**Fix**
- Replaced the over-broad NaN refusal with a direct port of CPython 3.12 TimSort for NaN-containing keys on the general path.
- Added the same TimSort for typed `list[float]` (`FLISTSORT`), so reverse sorts no longer refuse after mutating.
- Updated `safetyrt.py` to keep its primitive fast path while routing NaN keys to TimSort.
- Updated `test_ail_fuzz40.py` with the original NaN cases and all review probes.

**Probes (both builds unless noted)**
- Reviewer `p02`, `p03`, `p04`, `p11`, `p12`, `p15`: all now match CPython exactly.
- Original `s24_nan_sort`, `n1`–`n5`: match CPython on both builds.
- Random floats/tuples sizes 0–200 (`t1`), typed 130/80 (`t2`), typed sizes 64–300 (`t3`): match CPython on both builds.
- Remaining unrelated difference: typed float-row/SROW NaN sorts (`n6`, `n7`) still raise the pre-existing `ValueError` on the default build; the general build matches CPython.

**Tests on final commit**
`test_ail_fuzz40 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → `Ran 27 tests in 421.195s`, `OK (skipped=1)`.

`update_manifest.py --check` passes. No `DEVLOG`/`DIFFERENCES` files exist.
[cost $0.0000, opencode tokens {"total": 7667955, "input": 137704, "output": 28373, "reasoning": 40758, "cache.write": 0, "cache.read": 7461120}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review of `work..HEAD` (a63ee5e, 83ae85a)**

**Change read.** Final commit removes the runtime NaN refusal and adds a direct CPython 3.12 TimSort: an object/key TimSort in `cruntime.py` (`ail__ts_sort`), a double TimSort for `FLISTSORT` (`ail__fts_sort`), and a safety-runtime patch that routes NaN keys to `ail__ts_sort` while keeping `ail2u_sort_prim` for non-NaN numeric keys. Test/manifest wiring is present.

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh`, both builds):
- `p01` stability, tuple/multi-key, reverse-equal, dict items, `str.lower`, `itemgetter` — same as CPython on HEAD and base.
- `p02` same-object NaN, key, reverse, tuples, dict values, attrs, args — HEAD same; base differs (confirms the fix).
- `p03` distinct NaNs, nested tuples, `itemgetter` — HEAD same; base differs.
- `p04`, `p11` large NaN floats/tuples, descending/ascending runs, gallop patterns — HEAD same.
- `p06`, `p16` mixed int/float/bool/inf/-inf/-0.0/NaN, huge values — HEAD same.
- `p07` values via argument, list item, attribute, dict value, `itemgetter` — HEAD same.
- `p10` exhaustive small float/tuple lists (all length ≤4) forward/reverse — HEAD same.
- `p12` nested list/tuple keys — HEAD same.
- `p19`, `p20` plain unannotated float lists (exercises `ail__fts_sort`), reverse and 65–500-element gallop patterns — HEAD same; base raises `ValueError` (p19).
- `p13`, `p14`, `p17` annotated float lists/rows and float+str rows — HEAD same on both builds; base differs on p17 (silent wrong order).
- `p18`, `p15` large non-NaN int/float/tuple/str sorts, signed-zero stability — HEAD same.
- `p09` `attrgetter` — refused by name on both builds (acceptable; not built).
- `p08` no-sort program — stdout same. Default-build C identical to base; unified-build C differs only by the added (unused) TimSort functions, no behaviour change.

**Tests on HEAD:** `python3 ../tools/par_check.py -j 2 test_ail_fuzz40 test_ail_safetynet` → `2 modules in 121s, 0 failed`. Did not run `test_ail_files`/`test_ail_corpus_findings3` per the review instruction.

**Claims:**
- Commit/branch, TimSort general path, FLISTSORT TimSort, safetyrt routing, manifest `--check`, absence of DEVLOG/DIFFERENCES: verified.
- "Updated test_ail_fuzz40 with ... all review probes": partially verified — the module has `STABLE` and `NAN_SORTS`; the referenced probe files are not in the tree.
- Specific probe names (`p02`…`p15`, `s24`, `n1`–`n5`, `t1`–`t3`): unverified (files absent); my own probes of the same behaviours match.
- "Typed float-row/SROW NaN sorts still raise the pre-existing ValueError on the default build": unverified and not reproduced. `p14`/`p17`/`p19`/`p20` match CPython on both builds; base `p17` silently differs, so HEAD fixes it. No `ValueError` seen.
- Worker's 4-module/27-test result: partially verified (fuzz40 + safetynet OK); the other two modules were not re-run.

**Speed:** `tools/icount.c` could not run (`perf_event_open: Permission denied`, `perf_event_paranoid=4`). Wall-clock on gdev `g03_032` (2000-float sort): base/default 1134 ms vs head 1164 ms per 100 runs; unified 1154 vs 1168 ms. `g24_008`: 97 vs 101 ms per 100 runs. No large slowdown observed.

**Pre-existing:** only the named `attrgetter`/multi-argument `itemgetter` refusals; no pre-existing output difference on HEAD in these probes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 8586568, "input": 269524, "output": 21125, "reasoning": 57327, "cache.write": 0, "cache.read": 8238592}]

FINAL VERDICT: ACCEPT  2026-10-23T01:18:01Z
