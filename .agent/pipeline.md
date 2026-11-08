# job job-setord2-11080819  started 2026-11-07T23:20:01Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. All three review defects were real on HEAD; fixed and verified.

**Fixes**
1. **Stale test** — `test_ail_sets_general.test_s3` still expected the removed refusal. It now compares the int-set walk with CPython. (`test_ail_setorder.INT_ORDER` also gains the 40×128 growth-after-rehash case and the six-tuple display.)
2. **Rehash probing** — both `ail_setx_ct_insert_clean` and `ail_iset_cp_insert_clean` advanced `i` through the nine linear probes before the perturb step; CPython leaves `i` at the original slot. Both now probe via a local index and perturb from the unchanged `i`.
3. **Tuple constant folding** — `_folded_set_elt` in both `pyboxed2` and `pyfunc` no longer excludes `ast.Tuple`; the compile-and-inspect check now sees `fold_tuple`'s Constant, matching CPython.

**Probes** (`bash ~/tools/cmp.sh`, general + default), all match CPython:
`p_coll2` (40×128 list/repr/len), `p_coll2b` (deletions), `p_coll2c` (`pop`), `p_typed_dense` (typed `set[int]` growth/discard/walk), `p_tuple`, `p_tuple2`, `p_nested` (nested/empty/float/bool/None tuples), `p_frozen_tuple`, `p_tuple_rt` (runtime tuple sets via argument, dict value, list item), `p_walk`.

**Tests** (final commit `d865642`): `test_ail_sets_general`+`test_ail_setorder` 12/12 (45 s), `test_ail_int_dict_set` 5/5 (12 s), `test_ail_collections` 13/13 (357 s), `test_ail_files` 18/18 (111 s), `test_ail_corpus_findings3` 2/2 (255 s), `test_ail_safetynet` 5/5 (134 s). `tools/update_manifest.py --check` passes. Docs updated (DEVLOG entry at top, DIFFERENCES row).
[commandcode stop=end_turn turns=35 out_tokens=15865]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have enough evidence. Time check: ~32 minutes in, so I'll write the report now.

## Review 2

**What the change really does:** fixes the three review defects — both CPython-table `insert_clean` emulations now probe linearly through a non-mutating local index so the perturb step starts from the original slot; `_folded_set_elt` in `pyboxed2`/`pyfunc` no longer excludes `ast.Tuple`, so tuple-constant set displays take CPython's frozenset-constant path; `test_ail_sets_general.test_s3` compares the walk with CPython, `test_ail_setorder` gains the 40×128 and six-tuple cases, plus DEVLOG/DIFFERENCES/manifest updates. This matches the report.

**Verified**
- Defect 1 (stale test): `test_ail_sets_general` now passes (32.0 s); S3 builds and compares the walk.
- Defect 2 (rehash probing): `p_coll2` (40×128 list/repr/len/pop), `p_coll3` (deletions + re-add + drain), `p_typed_dense` (typed `set[int]`) match CPython on general and default; all differ on `/tmp/base`.
- Defect 3 (tuple folding): `p_tuple` (review's 6 pairs), `p_tuple2` (2/3/4 elements, nested, empty, float/bool/None), `p_tuple3` (duplicates, `1<<4`, unary signs, nested), `p_two_elt` match on both builds; `p_tuple`/`p_tuple2` differ on base.
- `dis` confirms CPython folds set displays only at n≥3 and folds tuple displays, so the existing `len > 2` gate plus the new tuple check is right.
- Runtime tuple sets on the targeted general path: `--general-only` output matches CPython for 8 and 60 tuples and for `p_coll2`. Values through an argument, a list item and a dict value (`p_runtime_tuple`) match.
- Non-feature C: generated C for `p_noset` and `p_control` differs from base only in the six header lines of `ail_setx_ct_insert_clean`; program statements are byte-identical (`--debug-dir`).
- `test_ail_sets_general` 32.0 s, `test_ail_setorder` 43.9 s, `test_ail_safetynet` 134.2 s — 3/3 pass. `update_manifest.py --check` rc=0; DEVLOG top entry and DIFFERENCES row present.

**Pre-existing** (identical output on `/tmp/base`, all involve typed-inferred `set[tuple[...]]`, which uses the insertion-ordered typed set rather than the emulated table):
- `p_tg8`, `p_tuple_growth`, `p_typed_tuple`: iteration/pop order differs from CPython on both trees; `p_attr_alias` raises `TypeError: '_AilS_Pi_iQ' object is not iterable` on both. The general-only path matches CPython for the same programs.
- `set[int] = {(1,2),(3,4),(5,6)}` exits 1 with `TypeError: object of type '_AilS_Pi_iQ' has no len()` on both trees.
- `(1 << 70, ...)` in a display: named compile-time refusal on both trees (acceptable).

**Unverified**
- Instruction counts: `tools/icount` cannot run here (`perf_event_open: Permission denied`). Wall time of the tiny gdev programs is ~0.00 s; the runtime diff is one extra add per linear probe, no algorithmic change.
- Worker-claimed but unedited modules (`test_ail_int_dict_set`, `collections`, `files`, `corpus_findings3`) not re-run; mutation-during-iteration not re-probed (the fix does not touch iteration).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=35 out_tokens=37790]

## full suite
test_ail_lang_gaps

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
The failing module was `test_ail_lang_gaps`, specifically `test_refusals_name_the_rewrite`: for `let s = set(); s.add("a"); print(s.pop())`, the refusal for a str-keyed unannotated set had stopped naming the `sorted(s)` rewrite.

I updated `_untyped_set_table` in `AIL_CURRENT/python/pkg-v12/pyfunc.py` so both the str and bytes refusals point at `sorted(s)` for a fixed order (alongside the existing "annotate it" advice). The manifest was regenerated.

Verification:
- `test_ail_lang_gaps` — 7 tests OK
- `test_ail_setorder` + `test_ail_sets_general` — 12 tests OK (my set-order fix and its tests intact)
- `test_ail_safetynet` + `test_ail_int_dict_set` — 10 tests OK
- `tools/update_manifest.py --check` — rc=0

Committed as `f651f1f`.
[commandcode stop=end_turn turns=33 out_tokens=15267]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T02:28:10Z
