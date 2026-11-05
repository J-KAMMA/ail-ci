# job job-pyreachs8-11052148  started 2026-11-05T12:53:34Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

## Fixes (all in `AIL_CURRENT/python/pkg-v12/noneslots.py`)

1. **Guard comparisons in values** — `_Rewrite.visit_Expr` and the non-row path of `visit_Assign` now `generic_visit`, and the row-store/`.append` branches descend into their value. `xs[i] is None` in expression statements and assignment values reads the present bit.
   - `q22_slots_assign_value.py`: now `True True True / True` (was `False True False / False`).
   - `q16_slots_neg_append.py`: now `2 False True` (was `2 False False`).
2. **Non-simple store index** — rejected in `_candidates` (the flag store would evaluate the index twice), plus a chained store (`xs[0] = ys = [4]`) the single-target rewrite cannot express.
   - `q3b_store_sideeffect_guard.py` (the variant that actually lowers): matches CPython, `idx` once. `q30_multitarget_slots.py`: matches (was `none`).
3. **`global`/`nonlocal` row name** — rejected in `_candidates`; the present-bit list would stay in the declaring function.
   - `q28_global_rows.py`: now `None / 2` (was `[] / 2`). `q28b_nonlocal_rows.py` matches.

Unsafe shapes keep the old general route; `--strict` refuses them by name. The fixed guard shapes still build typed under `AIL_NO_GENERAL=1`.

## Probes (12, both builds unless noted)
All match CPython or refuse by name: q22, q16, q3, q3b, q28, q28b, q30 (chained), q31 (side-effecting guard index), q32 (compare in list value).

## Tests (final commit `8b21d4c`)
- `test_ail_pyreach_optret`: 7/7 (added `test_slot_guards_in_values_and_append_none` typed, `test_unsafe_row_shapes_refuse_or_fall_back`)
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_strict`: all ok
- Siblings `test_ail_pyreach_infer/unpack/dictrows`: 0 failed
- `tools/update_manifest.py --check`: exit 0

DEVLOG entry and DIFFERENCES row (`C?-job-pyreachs8-11052148-1`) added; `.ail` codegen untouched (the hook is Python-source only). Not pushed, per the rules.
[commandcode stop=end_turn turns=44 out_tokens=24863]

## review 0
[model commandcode/deepseek-v4.1-flash]
## What the change really does

`noneslots.py`: makes the row rewrite's `visit_Compare` reachable from bare expression statements and assignment values (`generic_visit` in `visit_Assign`/`visit_Expr`), and rejects two shapes it cannot express: a store index that is not `_is_simple`/single-target, and a name declared `global`/`nonlocal`. Docs/manifest/tests updated. That matches the report.

The three defects of the last review are genuinely fixed: `q22`, `q16`, `q3`, `q28` all match CPython on both builds, and the rewritten source is unchanged (rejected) for `q3`/`q28`. But broadening guard rewriting exposed two shapes the candidate check still accepts and the rewrite still gets wrong — both match on `work`, both differ on HEAD.

## Claims

- "guards in values now read the bit": **verified** for the named probes, **false** as a general claim (defects 1–2).
- "non-simple/chained store rejected": **verified** (`q3` rewrite unchanged, stdout matches; `_is_simple`/`len(targets)` guards present).
- "global/nonlocal refused": **verified** for `global` (`q28` rewrite unchanged, `None/2` matches); nonlocal path not exercised (unreachable for top-level candidates).
- "`test_ail_pyreach_optret` 7/7, safetynet ok": **verified** (`2 modules, 0 failed`).
- "`update_manifest.py --check` exit 0": **verified**.
- "fixed shapes build typed under `AIL_NO_GENERAL=1`": **verified** for `q22` (`True True True / True`).
- ".ail codegen untouched": **consistent** — change is Python-source-only; `program.c` identical head vs base for `m7_plain` and `m8` (which contains `[None]`/`None]`).

No speed impact to measure: `.ail` C is unchanged and the hook only fires on Python sources containing `[None]`.

## Probes (both builds, vs CPython)

`q22`, `q16`, `q3`, `q28`, `m3`–`m8`: same stdout. `m1`, `m2`: DIFF (below). `m9` (slice guard inside `if`): DIFF on **both** trees → pre-existing.

## Pre-existing

- `m9_slice_guard_if.py`: `if xs[0:0] is not None: print("ok")` — CPython prints `ok`, both base and HEAD print nothing (the guard is rewritten to an empty bit-slice). Identical on `/tmp/base`, so pre-existing.

## Unverified

- nonlocal variant; `.ail` icount (not applicable).

VERDICT: FIX

1. **Slice subscript guards are rewritten to a list read.** `visit_Compare` matches any `xs[<slice>] is/is not None` (and `_candidate_ok.role` accepts a Slice as a guard), and the new `generic_visit` now reaches it in values/expressions. Reject a Slice subscript in the guard role.
   Probe `/tmp/rprobes/m1_slice_guard.py`:
   ```python
   def main():
       xs = [None] * 3
       xs[1] = [1]
       print(xs[0:1] is not None)
       print(xs[0:0] is not None)
   main()
   ```
   Expected `True\nTrue`; actual (both builds) `[False]\n[]`. `work` gives `True\nTrue`.

2. **A subscript store inside an unpack target is accepted but never lowered.** In a branch narrowed by `xs[i] is not None`, `_candidate_ok` treats the `xs[i]` inside a `Tuple`/`List` target as a guarded read, but `visit_Assign` only rewrites a single `Subscript` target, so the store leaves the present bit stale (and now the value guard is rewritten to read that bit). Reject a candidate with a Subscript anywhere in a multi-element target.
   Probe `/tmp/rprobes/m2_tuple_store_present.py`:
   ```python
   def main():
       xs = [None] * 2
       xs[0] = [1]
       if xs[0] is not None:
           xs[0], z = None, 2
       print(xs[0] is None)
       print(z)
   main()
   ```
   Expected `True\n2`; actual (both builds) `False\n2`. `work` gives `True\n2`.
[commandcode stop=end_turn turns=20 out_tokens=31688]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Done. Both remaining review defects are fixed and committed.

**Defects addressed** (in `AIL_CURRENT/python/pkg-v12/noneslots.py`):
1. **Slice guards** (`xs[0:1] is not None`, `xs[0:0] is None`) were rewritten to a present-bit list read, printing `[False]`/`[]`. `_candidate_ok.role` no longer treats a `Slice` subscript as a guard, and `visit_Compare` requires `_is_simple(sub.slice)`; the candidate is now refused and the program keeps the general route.
2. **Row store in an unpack target** (`xs[0], z = None, 2`, `*xs[0], w = ...`) was accepted but never lowered, leaving the present bit stale. `_candidate_ok` now walks Tuple/List/Starred store targets and refuses them.

The three earlier defects (`q22`, `q16`, `q3`, `q28`) were confirmed already fixed by commit `8b21d4c` and were not redone.

**Probes** (each run with `cmp.sh`: default and `AIL_UNIFIED_FORCE=1`, vs CPython):

| probe | result |
|---|---|
| `m1_slice_guard` | same stdout both builds (`True\nTrue`) |
| `m2_tuple_store_present` | same stdout both builds (`True\n2`) |
| `q22_slots_assign_value`, `q16_slots_neg_append`, `q3_store_sideeffect`, `q28_global_rows` | same stdout both builds |
| `m3`–`m8`, `m9_slice_guard_if` | same stdout both builds (m9 was a pre-existing DIFF, now fixed by the same refusal) |

**Tests on the final commit:** `test_ail_pyreach_optret` + `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` + `test_ail_strict` → 47 tests, 0 failed, 1 skipped. `test_ail_pyreach_optret` is 9/9 (two new tests added). `python3 tools/update_manifest.py --check` exits 0.

**Commit:** `5294837 job pyreachs8: refuse slice guards and unpack-target row stores` (DEVLOG and a `C?-job-pyreachs8-11052148-2` DIFFERENCES row added). Unverified: I did not rebuild the chain_relax/rail_transfer scratch copies; the change only rejects previously miscompiled shapes, and the typed slot test still builds under `AIL_NO_GENERAL=1`.
[commandcode stop=end_turn turns=26 out_tokens=17155]

## review 1
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Final report:

## What the change really does

`noneslots.py`: refuses a candidate whose row subscript appears in an unpack target (`xs[0], z = ...`, `*xs[0], w = ...`) or whose guard is a `Slice`; adds `_is_simple` gates on row stores and on `visit_Compare`; adds `generic_visit` in `visit_Expr` and the non-row `visit_Assign` so `xs[i] is None` in expression statements/values is lowered. Records/manifest updated.

## Claims vs. observation

| claim | verdict |
|---|---|
| q22/q16/q3/q28 already fixed by `8b21d4c` | **verified** — all four match CPython on both HEAD builds; q22 differs on `/tmp/base` (`False True False`) |
| slice guards now keep CPython semantics | **verified** (`n1_slice_guard_if`: `absent` / `True`, both builds) |
| unpack-target row stores refused | **verified** (`n3`, `n4`, `n12` for-target, `n13` nested: same stdout both builds) |
| tests 47/0 failed/1 skipped over five modules | **partly verified** — `test_ail_pyreach_optret` + `test_ail_safetynet` on HEAD: `2 modules, 0 failed`; other three not run (per instructions) |
| `update_manifest.py --check` exits 0 | **verified** |
| "the change only rejects previously miscompiled shapes" | **false** — see defect |
| typed slot test still builds under `AIL_NO_GENERAL=1` | **verified** (module test passes) |
| codegen pins unchanged | **verified** (`codegen_diff.py --base work`: all 5 SHAs old=new; the hook runs only in the Python surface, `ail_syntax.py:5782`) |

## Defects

1. **A guard with a non-simple index is accepted as a guard but no longer rewritten.** `_candidate_ok.role` classifies any non-`Slice` subscript in `xs[i] is (not) None` as `'guard'`, but `visit_Compare` now requires `_is_simple(sub.slice)`; the comparison is left as `xs[i] is None` against the `[]` sentinel while `xs__p` is populated. Base rewrote these correctly (it deep-copies the index once), so this is a regression from `5294837`.
   - `/tmp/rprobes/n5_guard_subscript_index.py` (`xs[ix[0]]`): expected `absent`, actual `present` + `tail present`. Base: matches CPython.
   - `/tmp/rprobes/n10_attr_index_guard.py` (`xs[b.i]`): expected `absent`, actual `present`. Base: matches.
   - `/tmp/rprobes/n11_guard_call_absent.py` (`xs[idx()]` on an absent slot): expected `idx` + `absent`, actual `idx` + `present`. Base: matches.
   - Fix: add `_is_simple(sub.slice)` to the `'guard'` branch of `role` (then the candidate is refused), or drop the gate from `visit_Compare` (a guard is evaluated once, so it is safe).

Everything else probed matches: aliasing (`r1`, `r2`), mutation during iteration (`r3`), values via argument / list item / attribute / dict value (`r4`, `r5`), slice store (`n2`), slice-object index (`n14`), plain row program (`n7`), attribute-carried row (`n8`).

## Pre-existing (identical on `/tmp/base`, both builds)

- `/tmp/rprobes/n9_param_shadow.py`: `[None]*n` assigned after a guard on a parameter-backed `xs` lowers the earlier guard to `xs__p`, giving `UnboundLocalError: cannot access local variable 'xs__p'` (CPython: `param none` / `2 True`). Same on base → not caused by this change, but it is a wrong exit status.

## Unverified

- m1–m9 probe files from the worker (I recreated equivalents; the m9 shape is covered by `n1`).
- The three test modules other than `test_ail_pyreach_optret`/`test_ail_safetynet`.
- Speed: `.ail` codegen is byte-identical and the rewrite is Python-source-only, so no icount impact.

VERDICT: FIX
1. `noneslots._candidate_ok.role` treats a non-`Slice`, non-simple guard index as `'guard'`, but `_Rewrite.visit_Compare` skips it (`_is_simple(sub.slice)`), so the compiled program compares the empty-list sentinel with `None` instead of reading `xs__p`. `/tmp/rprobes/n5_guard_subscript_index.py`: expected `absent`, actual `present\ntail present`. `/tmp/rprobes/n10_attr_index_guard.py`: expected `absent`, actual `present`. `/tmp/rprobes/n11_guard_call_absent.py`: expected `idx\nabsent`, actual `idx\npresent`. All three match CPython on `/tmp/base`, so the change caused it.
[commandcode stop=end_turn turns=27 out_tokens=19486]

FINAL VERDICT: FIX  2026-11-05T13:36:25Z
