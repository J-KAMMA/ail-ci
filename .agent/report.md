# job job-pyreachs5c-11050253  started 2026-11-04T17:57:37Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
**Report**

All three review defects are fixed and verified.

**Defect 1 — role map ignored rebinding.** `_record_roles` now returns the binding-node ids it introduces; `_record_bound_names` enumerates every binding of a name (assign/annassign/augassign, for/with, named expressions, parameters, lambda args, comprehension targets, except-handlers, `del`). A role name with any other binding refuses the lowering, so the dict keeps the old route. Probes `s_twodict_loop.py`, `s_name_reuse.py`: CPython `10 20 1 100 2 200` / `7 10 20 5 6`; both builds now identical (previously TypeError/empty stdout or a C compile error).

**Defect 2 — unsound `d.get(k)` proof.** `_proven` and the `if k in d:` guard path now call `_key_stable(k, start, end)`: no name read by the key may be rebound between the store (or the guard test) and the use. `q_stalekey.py` → `typeerror\nend`, `q_guard_stale.py` → `typeerror\nend`, both builds match CPython.

**Defect 3 — stale manifest.** `python3 tools/update_manifest.py` ran; `--check` prints nothing on the final commit.

**Probes (all 8, default + `AIL_UNIFIED_FORCE=1`, byte-compared to CPython):** `s_twodict_loop`, `s_name_reuse`, `q_stalekey`, `q_guard_stale`, `p_twodict_ok`, `p_row_alias`, `p_get_key_const`, `p_guard_ok` — all same stdout and exit code on both builds.

**Tests on the final tree:** `test_ail_pyreach_dictrows` 9/9 (par_check 1/1, ok), `test_ail_safetynet` 5/5, `test_ail_pytyped_reach` + `test_ail_collections` 26/26, `test_ail_files` + `test_ail_corpus_findings3` 20/20 (1 skipped). `.ail` codegen untouched (`lower_dict_of_records` runs only from `python_surface`).

Committed as `4e2d3c7` (not pushed), working tree clean apart from the untracked harness file `.agent/pipeline.md`.
[commandcode stop=end_turn turns=43 out_tokens=24452]

## review 0
[model commandcode/deepseek-v4.1-flash]
## What the change really does

One commit (`4e2d3c7`) that repairs the s5 record-dict lowering: `_record_roles` now returns the binding-node ids it introduces, and `_record_bound_names` enumerates other bindings, so a role name bound anywhere else refuses the lowering; `_proven` and the `if k in d:` guard path call a new `_key_stable` that rejects key rebindings between store/guard and use. Manifest regenerated. Matches the report.

## Defects

1. **`_key_stable` is a line interval (`start < line <= end`), so a rebinding on the store's (or guard's) own line is missed; the unsound one-argument `d.get(k)` proof (review defect 2) remains at that boundary.**
```python
# /tmp/rprobes/p_sameline.py
def main():
    d = {}
    k = 1
    d[k] = ["a", 1]; k = 2
    try:
        r = d.get(k)
        print(r[1])
    except TypeError:
        print("typeerror")
    except KeyError:
        print("keyerror")
    print("end")
main()
```
Expected `typeerror\nend`; actual both builds `keyerror\nend`.
```python
# /tmp/rprobes/p_guardsameline.py
def main():
    d = {}
    k = 1
    d[k] = ["a", 1]
    if k in d: k = 2; r = d.get(k)
    print("end")
main()
```
Expected `end` (exit 0); actual uncaught `KeyError: 2`, exit 1. Guard line == use line, so `_key_stable(start=guard_line, end=use_line)` checks nothing.

2. **The proof tracks rebinding only, not mutation of a container read by the key.**
```python
# /tmp/rprobes/p_keymut.py
def main():
    d = {}
    a = [1]
    d[a[0]] = ["x", 5]
    a[0] = 2
    try:
        r = d.get(a[0])
        print(r[1])
    except TypeError:
        print("typeerror")
    except KeyError:
        print("keyerror")
    print("end")
main()
```
Expected `typeerror\nend`; actual both builds `keyerror\nend`. A safe repair: only prove presence for keys that are a bare `Name` or a constant, and compare `(lineno, col_offset)` of store/guard vs use rather than line ranges.

Both reproduce identically on `work`, so they are not regressions — but they are the exact silent difference the fix task ("never leave ... a silent difference", defect 2) was to close.

## Verified

- **Defect 1 fixed**: `s_twodict_loop.py` and `s_name_reuse.py` match CPython on both builds at HEAD (default C compile no longer fails); both differ on `work`.
- **Defect 2 closed for the reviewed probes**: `q_stalekey.py`, `q_guard_stale.py`, `p_guard_ok.py` match CPython on both builds. `p_match_row.py` (match-pattern reuse) now matches too, and `p_match_bind2`/`p_vplainloop`/`p_del_role` match (lowering refused → general path).
- **Defect 3 fixed**: `tools/update_manifest.py --check` exits 0, silent.
- **Tests on final commit**: `test_ail_pyreach_dictrows` 25.6s ok, `test_ail_safetynet` 163.2s ok (2 modules, 0 failed, `-j 2`).
- **C unchanged where expected**: codegen pins identical vs `work` (`tools/codegen_diff.py --base work`); a non-feature `.py` gives byte-identical `program.c`; a lowering-using program (`p_guard_ok`) gives byte-identical `program.c` HEAD vs base → no speed impact.

## Claims check

- Defect 1 fixed — verified. Defect 3 fixed — verified.
- Defect 2 "no name read by the key may be rebound between the store (or guard) and the use" — **false** at the same-line boundaries above (rebinding not caught; mutation never caught).
- `.ail` codegen untouched — verified. Tests — verified. Their other probes (`p_twodict_ok`, `p_row_alias`, `p_get_key_const`) not rerun; `test_ail_pytyped_reach`/`test_ail_collections`/`test_ail_files`/`test_ail_corpus_findings3` not rerun (not in the changed set, per instructions).

## Unverified

Speed/icount (runtime C is byte-identical, so none expected); those extra modules.

VERDICT: FIX

1. `/tmp/rprobes/p_sameline.py` and `/tmp/rprobes/p_guardsameline.py`: expected `typeerror`/`end`, actual `keyerror`/uncaught `KeyError` exit 1 — same-line rebinding bypasses the line-interval `_key_stable`.
2. `/tmp/rprobes/p_keymut.py`: expected `typeerror`/`end`, actual `keyerror`/`end` — mutation of a container element read by the key leaves the one-argument `d.get(k)` presence proof unsound.
[commandcode stop=end_turn turns=29 out_tokens=20678]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Committed as `d0d8eaa`. All three review defects are fixed and verified.

**Fixes**
- `_key_stable` now orders store/guard/use by `(line, col_offset)` (new `_pos`) and checks each binding target's own position, so a rebinding on the store's/guard's own line is caught.
- Presence is proved only for a bare-name or constant key; a subscript/attribute key (e.g. `a[0]`) is never proved, closing the mutation case. `flat_stores`, `deletes` and guard entries now hold positions instead of line numbers.
- Manifest regenerated (`--check` clean).

**Probes** (`bash ~/tools/cmp.sh`, general `AIL_UNIFIED_FORCE=1` and default builds, all `same stdout`, exit 0):
- `p_sameline.py` → `typeerror`/`end` (was `keyerror`)
- `p_guardsameline.py` → `end` (was uncaught `KeyError`)
- `p_keymut.py` → `typeerror`/`end` (was `keyerror`)
- Regression set: `p_guard_ok`, `p_proven_ok`, `p_get_key_const`, `p_row_alias`, `p_twodict_ok`, `p_sameline_after`, `q_stalekey`, `q_guard_stale`, `s_name_reuse`, `s_twodict_loop` — all match CPython.
- Confirmed valid bare-name `get` still lowers typed (`v_d__f0/__f1` in generated C); the three defect probes fall back to the general path.

**Tests** (`-j 2`): `test_ail_pyreach_dictrows` 9/9 ok, `test_ail_safetynet` 5 ok, `test_ail_pytyped_reach` 13 ok, `test_ail_collections` 13 ok, `test_ail_files` 18 ok (1 skip), `test_ail_corpus_findings3` 2 ok. `codegen_diff.py --base work` reports no diffs.
[commandcode stop=end_turn turns=38 out_tokens=15636]

## review 1
[model commandcode/deepseek-v4.1-flash]
## What the change really does

One line: it makes `lower_dict_of_records` refuse a record-dict when any role name has a binding outside the roles the lowering introduces, and makes the one-argument `d.get(k)` presence proof position-ordered by `(line, col)` over store/guard → use, restricted to bare-name or constant keys.

## Claims check

| Claim | Status |
|---|---|
| Defect 1 fixed (role map ignores rebinding) | **verified** — review probes `s_twodict_loop.py`, `s_name_reuse.py` now match CPython on both builds; new `_record_bound_names` + count check in `_lower_record_dict` confirms in code |
| Defect 2 fixed (unsound `get` proof) | **verified** — `q_stalekey.py`, `q_guard_stale.py`, `p_sameline.py`, `p_keymut.py` → `typeerror`/match; `_key_stable` rejects non-Name/Constant keys |
| Defect 3 fixed (manifest) | **verified** — `update_manifest.py --check` rc 0; only the `ail_syntax.py` hash line changed |
| `flat_stores`/`deletes`/guards hold positions | **verified** in the diff |
| Valid bare-name `get` still lowers typed | **verified** — `__f0` field lists present; the typed probe's `program.c` is byte-identical to base |
| Tests: dictrows 9/9, safetynet 5, pytyped_reach 13, collections 13 | **verified** on HEAD (`par_check -j 2`, all ok) |
| test_ail_files / corpus_findings3 pass, `codegen_diff --base work` clean | **unverified** (not required; `.ail` path is untouched — `lower_dict_of_records` is called only from `python_surface`) |

Also checked: role name reused as a plain loop variable / after reassignment leaves the source unchanged (`p_role_reuse_plain` matches); non-feature program's `program.c` byte-identical to base; `d.pop`/`d.clear` force the old route; match-capture and import rebinding fall back; constant keys with `if k in d:` still lower and match.

## Pre-existing (identical on base, do not block)

- `p_loop_rebind.py` (key name rebound on a later loop iteration *after* the get textually): HEAD and `/tmp/base` both print `1 keyerror` where CPython prints `1 typeerror`. The loop-hole existed in the base proof.
- `p_items_unpack.py` (`for k, (a, b) in d.items()`): compiler crash `AttributeError: 'Tuple' object has no attribute 'id'` at `pyfunc.py:28613`, identical on base.

## Speed

Change is compile-time only; no runtime/buffer/memory path touched, and the generated C for a typed probe is byte-identical to base, so no icount run was needed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=36 out_tokens=22557]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T20:20:32Z
