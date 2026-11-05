# job job-pyreachs8-11052318  started 2026-11-05T14:21:15Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed on `job-pyreachs8-11052318` (commit `7202ff4`).

**Defect 1 (named in the FIX verdict):** confirmed in current code — `_Rewrite.visit_Compare` gated the rewrite on `_is_simple(sub.slice)` while `_candidate_ok.role` accepted any non-`Slice` subscript as a guard, leaving `xs[idx()] is None` / `xs[ix[0]] is None` / `xs[b.i] is None` comparing the `[]` sentinel. All three probes showed `present` vs CPython's `absent` on both builds. Fixed by rewriting every guard whose slice is not a `Slice` (a guard evaluates its index once, so no double evaluation). All three now match.

**Pre-existing `n9_param_shadow`:** reproduced the `UnboundLocalError: cannot access local variable 'xs__p'`. Fixed by refusing a `[None] * n` candidate whose name is a function parameter; it keeps the general route and `--strict` names it. No longer crashes; matches CPython on both builds.

**Probes** (all 2/2 same stdout on default + `AIL_UNIFIED_FORCE=1`): `n5_guard_subscript_index`, `n10_attr_index_guard`, `n11_guard_call_absent`, `n5b_guard_isnot_simple` (side effect runs once, `is not None`), `n5c_guard_tuple_index`, `n5d_guard_no_rewrite` (out-of-range IndexError), `n9_param_shadow`.

**Tests on final commit:** `test_ail_pyreach_optret`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 34 tests, OK, 1 skipped. `update_manifest.py --check` exits 0. `codegen_diff.py --base HEAD`: all 5 pins old = new.

Records updated: DEVLOG entry at top; new `DIFFERENCES` row `C?-job-pyreachs8-11052318-1`; manifest refreshed.
[commandcode stop=end_turn turns=40 out_tokens=17878]

## review 0
[model commandcode/deepseek-v4.1-flash]
## What the change really does

`noneslots._Rewrite.visit_Compare` now rewrites **every** guard whose row subscript is not an `ast.Slice` (it dropped the `_is_simple` gate), and `_candidates` refuses a `[None] * n` candidate whose name is a function parameter. That matches the report.

## Defects from the last review

| probe | base (`/tmp/base`) | HEAD (both builds) |
|---|---|---|
| `n5_guard_subscript_index` (`xs[ix[0]]`) | `present` | `absent` — matches CPython |
| `n10_attr_index_guard` (`xs[b.i]`) | `present` | `absent` |
| `n11_guard_call_absent` (`xs[idx()]`) | `idx`/`present` | `idx`/`absent` |
| `n9_param_shadow` | `UnboundLocalError ... 'xs__p'`, exit 1 | matches CPython, exit 0 |

Fixed. My own accepted-candidate probes (verified via `noneslots.rewrite` that they are rewritten, not refused):

- `p1_subscript_index_guards` — absent/present; base loses the `absent` line.
- `p2_call_index_once` — index side effect prints `idx` exactly once per guard; base prints `present` where CPython prints `absent`.
- `p5_reversed_operands` (`None is xs[ix[0]]`) — base loses `absent`.
- `p11_odd_index_types` (slice-object, tuple, `1//0`, IfExp, bool indices) — `slice(...)`/`1.0`/tuple raise the same exception types, `1//0` gives ZeroDivisionError, all exit codes match; same on base.
- `p3_oob_len_index` (`xs[len(xs)]`, IndexError path), `p4_negative_index`, `p6_float_bool_index`, `p7_append_and_dict_index`, `p8_store_nonsimple_refused`, `p9_param_row`, `p10_vararg_row`, `r10_no_feature` — all match CPython; p8/p9 keep the general route.
- Typed path confirmed with `AIL_NO_GENERAL=1`: p1/p2 build and match.

`--strict` on `p9` names the parameter reassignment (`'xs' is a parameter and cannot be reassigned`).

## Build/codegen/tests

- `tools/codegen_diff.py --base work`: all 5 pins old = new. (The report's `--base HEAD` is a no-op; the substance holds.)
- No-feature program and a refused-shape program: `--debug-dir` `program.c` byte-identical HEAD vs base.
- `rail_transfer/main.py` (the only lab source with `[None] * n`) has the same exit/refusal on both.
- `par_check.py -j 2 test_ail_pyreach_optret test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed.
- `update_manifest.py --check` exits 0.

## Notes (not defects)

- The fix has **no regression test**: the module's `non_simple` covers a non-simple *store* index (refused), not a non-simple *guard* index (now rewritten). Only the /tmp probes cover it.
- `n5b_guard_isnot_simple` is *refused* by `rewrite()`, so its "side effect runs once" claim does not exercise the rewrite; `p2` does.
- `p10` (vararg rebound to `[None]*n`) previously took the row rewrite on base and now uses the general route (same stdout); harmless.

## Unverified

- Wider suite and icount (not needed: the diff only changes which Python sources are rewritten; `.ail` codegen and unaffected `.py` C are identical).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=33 out_tokens=26786]

## full suite
test_ail_debug_lines
test_ail_fallback_note
test_ail_lsp
test_ail_project
test_ail_quirks
test_ail_refusal_messages
test_ail_spec_fixes

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed (`5ca470f`).

**What was actually broken:** the s8 scalar-Optional pass (`optlib._scan_dict_kinds`) recorded `dict[K, V]` *function parameters* as typed dicts, not just locals. So `find(d: dict[int,int], k) -> int | None: return d.get(k)` was lowered to a tag/value pair, which hid the `int | None` annotation from `pyfunc._strip_nullable`; the typed path then refused the call `find({1: 2}, 1)` with a bogus `idict` vs `int` signature conflict, and the default build fell back to the general path over the *rewritten* source (renumbered DWARF lines). That one cause produced all 10 failures across the 7 modules.

**Fix:** restrict the scan to local dicts (literal, subscript store, annotated local), matching `_dict_get_kind`'s own "local dict" contract. Local one-argument `d.get(k)` remains the s8 Optional, so the job's own test still passes.

Two stale assertions updated: the obsolete `dict_get_one_argument` refusal case now uses a helper-built dict (which still earns `_ONE_ARG_GET`), and `test_ail_strict`'s blocker is the `int | None` annotation again.

**Verified**
- the 7 listed modules + `test_ail_strict`: 130 tests, OK
- `test_ail_debug`, `test_ail_lang_gaps`: OK
- job/optlib modules (`test_ail_pyreach_optret`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_optional_locals`, `test_ail_optional_structs`, `test_ail_optint_exact`, `test_ail_prog13`): 8/8 OK
- `update_manifest.py --check` exits 0; `codegen_diff.py --base work`: all 5 pins identical
- my noneslots fix and its test are untouched.
[commandcode stop=end_turn turns=75 out_tokens=45667]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T17:43:06Z
