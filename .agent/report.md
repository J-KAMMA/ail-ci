# job job-difflib2-11042057  started 2026-11-04T11:58:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Defect confirmed and fixed.

**Defect 1 — stale manifest pin (the only defect listed):** reproduced `stale stdlib/difflib.py`, exit 1. Re-ran `python3 tools/update_manifest.py`, which re-pinned `stdlib/difflib.py` to `96fbcc77…` (was `d167b39a…`). `--check` now exits 0.

**Also corrected two false claims in `RESULTS.md`** (the review's claim checks):
- The default-build fallback note is not about `SequenceMatcher.__init__`; it is `stdlib/difflib.py:110:13 … result of __lt__() is declared bool, but NotImplemented is not a bool` (03/05 instead stop on the iterator-class `__iter__` note).
- `diff_bytes` does accept an arbitrary `dfunc` — verified with a custom function in both builds; removed the false statement.

**Probes** (all matched CPython in both the default and `AIL_UNIFIED_FORCE=1` builds, exit status included): `r_close`, `r_seq`, `r_match`, `r_diff`, `r_bytes`, `r_mut`, `r_differ`, `p_restore_junk`. Programs 04 (kwargs) and 12 (`HtmlDiff`, exact by-name refusal) remain refused as designed.

**Tests:** `par_check.py -j 2 test_ail_std_difflib test_ail_safetynet test_ail_std_shlex` → 3 modules, 0 failed (~390s). Note: safetynet's `S4_generators_gc` fails only under `ulimit -v 1500000` (allocation cap); without the cap it passes, and the program is unrelated to difflib.

Committed as `7b8356a` (manifest pin + RESULTS corrections).
[commandcode stop=end_turn turns=25 out_tokens=13193]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does.** It refreshes the manifest pin for `AIL_CURRENT/stdlib/difflib.py` (`d167b39a…` → `96fbcc77…`) and corrects two prose claims in `lab/stdlib/difflib/RESULTS.md`. It does not touch the module, compiler, runtime or tests. This matches the worker's report.

**Defect from review 1 (stale pin).** Fixed and verified: `python3 tools/update_manifest.py --check` → exit 0; `sha256sum` of the file is `96fbcc77…`, exactly the new pin.

**Claims checked against observation.**
- Default-build fallback note is `stdlib/difflib.py:110:13 … the result of __lt__() is declared bool, but NotImplemented is not a bool` for 01/02/06/07/08/09/10/11 — **verified** by building all ten.
- 03 and 05 stop on the iterator-class note (`iterating a difflib.unified_diff` / `difflib.context_diff`) — **verified**.
- `diff_bytes` accepts a custom `dfunc` — **verified** with `/tmp/rprobes/p_dfunc.py` (custom wrapper called with decoded str lines, returns unified_diff) matching CPython in both builds.
- 04 refused with `a **kwargs call argument`; 12 refused by name with the exact text — **verified**.
- "10/12 build and match in both builds" — **verified** via the now-runnable `test_ail_std_difflib` (it builds every passing program and compares stdout+exit in both builds).
- Worker's test claim — **verified**: `par_check.py -j 2 test_ail_std_difflib test_ail_safetynet` → 2 modules, 0 failed, exit 0.

**Probes run** (`bash ~/tools/cmp.sh … $PWD`):
- `p_dfunc.py` (diff_bytes custom dfunc + latin-1 non-ASCII): both builds match CPython.
- `08_seq_ratio.py`, `11_diff_bytes.py`: both builds match CPython.
- `p_plain.py` (no difflib): `--debug-dir` C identical to `/tmp/base`.

**Scope.** Only `manifest.d/a1.txt` and `RESULTS.md` changed; both permitted. No `bench/apps` or `language_examples` edits (not a speed task).

**Pre-existing:** none found.

**Unverified:** full 12-program matrix beyond what the test module covers (test covers the 10 passing ones); no icount check (change touches no hot code).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=23 out_tokens=7057]

## full suite
test_ail_argument_type_details
test_ail_check_repair_context
test_ail_collections
test_ail_source_check

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Done and committed as `8b698a9`.

**What broke:** all four modules shared one root cause, unrelated to the difflib content itself. The call-site inference pass (`_propagate_signatures_pass` / `_plan_clones`) was feeding a `str` claim into `_param_kinds` for parameters that already had a non-str annotation. `_param_kinds` then refused it at the **declaration** as a signature override (`operation="parameter"`, `inference_scope="signature_override"`), stealing the per-call argument diagnostic and the caller's location — e.g. `'value' is annotated int in the source, but the caller also supplies str` instead of `passing str where take() wants int`, and `collect`/`Counter.subtract` refusals replaced by that message.

**Fix:** added `_site_override()`, which drops a `STR` claim when the callee's parameter has an explicit annotation of another kind, and applied it before `_param_kinds` in both call-site passes. The declared parameter kind then stands, and the existing call guard reports the mismatch at the call with `operation="argument"`. Other conflicts still raise as before — float-to-int narrowing and int/array claims against str/list annotations remain declaration-level overrides (verified by `test_ail_refusal_messages` and the `signature_override` cases). Re-pinned `python/pkg-v12/pyfunc.py` with `tools/update_manifest.py` (`--check` exits 0).

**Verification:**
- `test_ail_argument_type_details`, `test_ail_check_repair_context`, `test_ail_source_check` — 56 tests, OK
- `test_ail_collections` — 13 tests, OK
- `test_ail_std_difflib` (my own fix's test) — 2 tests, OK
- `test_ail_refusal_messages`, `test_ail_float_argument_widening`, `test_ail_pyreach_infer` — OK
[commandcode stop=end_turn turns=69 out_tokens=31872]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T15:31:28Z
