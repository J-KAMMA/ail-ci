# job job-fbnarrow4-11090312  started 2026-11-08T18:13:28Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. All three review defects are fixed and verified.

**Defects**
1. `.sort()` on a narrowed class field — fixed by making `ail_list_sort` a `_Generic` macro (alongside `ail_list_reverse`), so `ail_list_sort(&obj->f_w)` dispatches to `ail_ilist_sort`. The exact reviewer probe (`field_sort_just.py`) now prints `1 2 3`, and `field_sort_method.py` matches CPython, including `reverse=True` and a run-time widening.
2. Stale manifest — regenerated; `python3 tools/update_manifest.py --check` exits 0.
3. Key-sort columns — int columns (`_ail_sk*_c*`) are now `ail_ilist`, converted exactly via `ail_obj_field_list_move`. `_sort_column` emits a width-aware descriptor (kind 4 int32 / kind 0 int64 after widening), and the KEYSORT kind-4 comparator is injected only when narrowing is enabled, so default C is unchanged. Float/str columns correctly stay `ail_flist`/`ail_slist` (probed: float key sort builds and matches). The report was corrected and its unmeasured gate/RSS rows marked unverified.

**Probes** (narrow, default, `AIL_UNIFIED_FORCE=1`, and narrow+force; all match CPython): `field_sort_just`, `field_sort_method`, `keysort` (stable equal keys, multi-column, widening key), `fkeysort` (float key). Default `keysort` C contains 0 narrow artifacts; `cruntime.py` is unchanged.

**Tests** (on final code): `test_ail_narrow_int` 16/16 OK (added narrowed-field sort, key-column-narrow-in-C, widening key), `test_ail_safetynet` 5/5 OK, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2 OK.

Committed as `42f45e8`; not pushed (per `C:\Users\bluec\ail-work` rules for this runner).
[commandcode stop=end_turn turns=153 out_tokens=64579]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: fbnarrow4 (fix round)

**What the change really does.** Makes `ail_list_sort` a `_Generic` macro dispatching `ail_ilist*` to `ail_ilist_sort`, teaches KEYSORT a kind-4 (int32) column only when narrowing is enabled, marks int key-column comprehension targets narrow at emission and moves their buffer via `ail_obj_field_list_move`, plus manifest/report/test updates. Matches the report.

**Status of review-1 defects**
1. Field `.sort()` — **fixed**. Narrow build of `field_sort_just.py` and `field_sort_method.py` matches CPython; C shows `ail_ilist f_w` and `ail_list_sort(&(v_t)->f_w)` resolving through the macro to `ail_ilist_sort`.
2. Manifest — **fixed**. `python3 tools/update_manifest.py --check` exits 0.
3. Key-sort columns — **fixed**. `keysort_edge` C has `ail_ilist v__ail_sk1_c0` and `{(c.wide ? 0 : 4), ...}`; float/str columns stay `ail_flist`/`ail_slist` (kind 1/2). Widened keys (`keysort_wide`) match CPython.
   The gate table/compare-lab rows remain **not measured**; the report now says so honestly. Default was not flipped, so this is a documentation gap, not a code defect.

**Probes** (`/tmp/rprobes/`, narrow and default; g-path also `AIL_UNIFIED_FORCE=1`): `field_sort_just`, `field_sort_method`, `keysort_edge`, `keysort_wide`, `keysort_bound` (int32 min/max + stability), `keysort_types` (float/str keys), `field_slice_alias` (slice/copy independence after mutation), loop-keyed sort (`/tmp/ksloop`, buffer reuse), `nofeature`. All match CPython in every mode; no refusals needed, no crashes.

**Default C unchanged:** `nofeature.py` and `keysort_edge.py` `--debug-dir program.c` sha256 identical on `/tmp/base` and HEAD; default keysort C has zero `kind == 4` / narrow artifacts.

**Report claims:** field sort, key columns narrow, float/str wide, cruntime.py untouched, default C unchanged — verified. Test counts, tree_fold RSS/binary-size and gate rows — unverified here (not required / not measured).

**Pre-existing:** none found.

**Unverified:** RSS/gate/compare-lab numbers; `test_ail_files`/`test_ail_corpus_findings3` (not required); speed not re-measured — default `program.c` is byte-identical, so no hot-path change.

Tests on HEAD: `test_ail_narrow_int` ok 34.8s, `test_ail_safetynet` ok 84.3s, 0 failed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=35 out_tokens=29062]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T20:02:06Z
