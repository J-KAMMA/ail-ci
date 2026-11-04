# job job-sdkdiag1-11041645  started 2026-11-04T07:46:32Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `6d28f74` on `job-sdkdiag1-11041645` (not pushed, per instructions).

## Culprit
`git bisect` was impossible: this export has a single squashed commit (`96f1985`). Tracing the two suspect brace-to-Python conversion jobs instead pointed at parameter-kind propagation. `_claim` now returns `str` for the literal, `_propagate_signatures_pass` feeds it to `_param_kinds`, and `_explicit_annotation_conflicts` raised the numeric-style `signature_override` conflict before `_call_user_func` could refuse the argument at the call.

## Fix
`AIL_CURRENT/python/pkg-v12/pyfunc.py` — `_explicit_annotation_conflicts` now raises only for a **numeric** caller claim (int/float). Text, bytes and list claims are dropped, so the existing per-call guard reports `operation: argument`, callee/parameter/index/expected/actual, and the original `.ail` statement position (line 3, column 17, `source_statement`) via `source_map`. Numeric override behaviour (float→int, int→str/list) is unchanged.
Added a source-position regression to `test_ail_argument_type_details.py`; `test_ail_sdk.py` expectations untouched.

## Verification (final commit)
- `test_ail_sdk.py`: **30/31 → 31/31**
- `test_ail_argument_type_details.py`: **11/15 → 16/16**
- `test_ail_safetynet` 5/5, `test_ail_files` 18/18, `test_ail_corpus_findings3` 2/2, `test_ail_type_details` 11/11, `test_ail_source_check` 33/33, `test_ail_float_argument_widening` 1/1, `test_ail_refusal_messages` 3/3 (41 tests, 1 skip + 48 tests, all pass). Before counts for these were not run; they were unaffected by the patch.
- `compileall -j 2 AIL_CURRENT tools`: OK **excluding** `language_examples/binary_numbers.py`, whose line 2 comment contains `encoding:` — the separate PEP 263 break PR #376 fixes (that commit is not in this export, and editing it is outside the brief's file scope).
- `tools/update_manifest.py --check`: OK.

## Probes (`/tmp/probes`, `bash ~/tools/cmp.sh`; stdout+exit vs CPython, both builds)
- Passing and byte-identical stdout: `arg_name`, `arg_list`, `arg_attr`, `arg_dict`, `str_name`, `str_list`, `str_attr`, `numeric_edges` (0, -1, int64 min/max, ±0.0, ±1.5), `alias` (name alias + list alias/empty list).
- Diagnosed as `argument` at `source_statement`/`main`, CPython-matching exit: `ref_text_to_int`, `ref_text_name`, `ref_text_list`, `ref_text_attr`, `ref_bytes_to_int`. A verifier asserted these fields explicitly.
- Unchanged numeric override (still `parameter`/`signature_override` at the declaration): `ref_float_to_int`, `ref_int_to_str`.
- `ref_int_to_float` is refused by name in `check`; its general-path build matches CPython (exit 0, same stdout).
- Honest gap: a `str` value read from a `dict[str,str]` (`ref_text_dict`, `str_dict`) is refused/mis-typed earlier by an unrelated pre-existing dict-value rule (`'table' holds integer values`), so that provenance could not exercise the new text path; the int dict-value probe passes and matches CPython.
[commandcode stop=end_turn turns=89 out_tokens=44164]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: sdkdiag1 (6d28f74)

**What the diff really does.** In `_explicit_annotation_conflicts` it skips caller claims whose kind is not numeric, so the declaration-site `signature_override` refusal is no longer raised for str/bytes/bytearray/list claims; the existing per-call guard in `_call_user_func` then reports `operation: argument` with the original source position. Plus a regression test, DEVLOG rows and manifest checksums. This matches the report.

**Method note.** `cmp.sh` alone cannot judge this: every refusal falls back to CPython (`AIL_QUIET_FALLBACK=1`), so stdout/exit always match. I compared acceptance and diagnostics on the typed path with `check` on HEAD and `/tmp/base`, and C output with `--strict --debug-dir`.

**Probes** (33 in `/tmp/rprobes`; HEAD vs base):

| provenance / boundary | probe | HEAD | base |
|---|---|---|---|
| str via parameter, return, list item, attribute, class field, dict value, list[str] item, concat, .strip(), keyword | pr_name, pr_ret, pr_list, pr_attr, pr_classattr, pr_dict, pr_slist, pr_concat, pr_strip, pr_kw | refused, `argument` at the call (`passing str where take() wants int`) | declaration `parameter`/`signature_override` (pr_kw already call-site) |
| str via `sys.argv[1]`, dead function, recursion, cross-module callee | pr_argv, pr_dead, pr_recur, mod/ | refused at the call | declaration refusal |
| bytes / bytearray / bytes-to-str-param / list[bytearray] | pr_bytes, pr_bytearray, pr_bytesparam, pr_hlistparam | refused at the call (`argument`, or named `a matching bytearray list is required`) | declaration refusal |
| list, list[str], rows, set, obj, exception, str-to-float param | pr_listint, pr_liststr, pr_rowsparam, pr_setparam, pr_objparam, pr_excparam, pr_floatparam | refused, named | same or declaration refusal |
| numeric conflicts (float→int, mixed args) | pr_numconf, pr_mixed, pr_mixed2 | declaration `signature_override`, identical to base | same |
| feature unused, accepted | ok_num, ok_str, ok_mix | pass; generated `program.c` byte-identical to base (only `debug_path`/temp paths differ) | pass |

No probe became accepted that base refused; no output/exit difference remains. Every text/bytes/list conflict is still a named refusal, now at the call.

**Tests (HEAD).** `test_ail_argument_type_details` 16/16 OK (base 11/15, 4 failures reproduced); `test_ail_sdk` 31/31 OK (base: target test fails); `test_ail_safetynet` OK; `compileall` fails only on `language_examples/binary_numbers.py` (`unknown encoding: unsigned`, PEP 263), same on base; `tools/update_manifest.py --check` exits 0.

**Report claims.** Verified: bisect impossible (`work` is one commit); cause and fix as described; 30/31→31/31 and 11/15→16/16; compileall exclusion; manifest. Contradicted: the claimed dict-value gap — `take(d["k"])` with `d: dict[str,str]` yields the correct call-site `argument` diagnostic on HEAD, so that provenance is covered. Unverified: the counts for test_ail_files/corpus_findings3/type_details/source_check/float_argument_widening/refusal_messages (not required by the review brief), and the worker's own probe list (not in this export). Speed: the changed code runs only in a refusal path and emitted C is identical for accepted programs, so instruction counts cannot move; I did not run `icount`.

**Pre-existing (identical on base).** `binary_numbers.py` compileall break; `take(1)` into a `float` parameter with a float body refused on both trees (pr_ok_float).

**Observation, not a defect.** `take("wrong", 1.5)` still reports the *declaration* for the text parameter because the co-occurring numeric conflict opens the gate; base behaves identically.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=69 out_tokens=44481]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T12:21:08Z
