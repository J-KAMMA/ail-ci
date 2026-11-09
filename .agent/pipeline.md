# job job-rbobs4-11100024  started 2026-11-09T15:26:01Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The accepted obs4 change was already fully present in this branch's base commit; the interrupted run had committed it. I verified that, re-ran everything on a new final commit, and added no source changes.

**State**
- Every path in the obs4 delta (`eb8b28cf`..`job-obs4-op1109`, excluding `.agent`, `corpus`, `MANIFEST.json`) hashes identically to `FETCH_HEAD`; all four `tests.d` registrations present.
- `tools/diff_ids.py` does not exist on this tree. `python3 tools/update_manifest.py --check` exits 0.
- New commit `9c7d2caa` (DEVLOG verification entry only; no code change was needed). No DIFFERENCES row.

**Tests on final commit `9c7d2caa`** (`-j 2`): `test_ail_cpython_hybrid`, `test_ail_hybrid_calls`, `test_ail_hybrid_lists`, `test_ail_hybrid_methods`, `test_ail_observe`, `test_ail_examples_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **9 modules, 0 failed, 223 s**.

**Probes** (`/tmp/probes`, C-from-CPython oracle)
- `p_consts` (int/float/str/bool constants; argument/list-item/attribute/dict channels), `p_calls` (native→native, negatives, bools, self/mutual recursion, depth 100, fib 20), `p_methods` (Tree read-only methods, empty/negative/OOB, int-for-float arg, retyped/bool/big fields, subclasses, attr/dict receiver), `p_edges` (empty/NUL/Unicode strings, empty/negative/bool lists, attribute and dict values): **both general and default builds same stdout as CPython**, exit statuses equal.
- Hybrid (`ail build --cpython`, compared against CPython): `p_consts` SAME 3 natives, `p_calls` SAME 5, `p_methods` SAME 5, `p_edges` SAME 3, `p_big` SAME 4, `p_rebind` SAME 4. `_ail_is_native` true for all 5 call natives and all 5 `Tree` methods.
- `p_big` covers the int64-overflow fallback: `score(10)`=10^19, `10*2^62`, list sum 2^63−1, `2^63` addition — all exact.
- `p_rebind` covers rebound/retyped/deleted constants and a rebound callee: `'ten'*3`='tententen', `3*True`=3, NameError after `del`, rebound `sq`→30 — all exact.

`p_big`/`p_rebind` were verified through the hybrid build, not `cmp.sh`: the general compiler's documented int64 stop and whole-file constant rebinding make those cases inapplicable there. `del obj.attr` is refused by the general build ("not in the subset: del on a Attribute"), so that boundary is covered by `test_ail_hybrid_methods`, which passes.
[commandcode stop=end_turn turns=60 out_tokens=45958]

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 0
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=run_error turns=1 out_tokens=0 error=POST /alpha/generate → 429 error: You've reached your weekly usage limit for your plan. Your limit resets at 2026-11-10T16:50:36.053Z. Please wait for the window to reset or upgrade your plan to conti]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

FINAL VERDICT: ERROR  2026-11-09T16:16:33Z
