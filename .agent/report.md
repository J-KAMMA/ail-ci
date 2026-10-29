# job job-refuzz95-10300605  started 2026-10-29T21:30:42Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"46714f47-9c4e-4ed2-84cb-2b7fcf026d2f","context_usage_ratio":0.019629},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"53e33f23-991c-410c-9d9c-a00b03349c54","session_id":"9c2c2109-0700-4df2-b6aa-e073ae92e18a"}

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Committed on `job-refuzz95-10300605` as `fb13f99` (no push).

## What changed
- `AIL_CURRENT/python/pkg-v12/cruntime.py`: boxed `ail_list_sort` now scans the decorate keys before merging and raises a named `ValueError` ("…refuses rather than differ silently from CPython (DIFFERENCES C?-job-refuzz95-10300605-1)") when a key is a NaN float, including a NaN inside a tuple/list key. NaN-free keys keep the same stable merge sort. The exact strings `safetyrt.patch_sortprim` patches are preserved.
- The typed path already refused (bare `ValueError` via `ail_flist_sort`/KEYSORT), so both builds now stop by name.
- `AIL_CURRENT/test_ail_refuzz95.py` (new, registered in `ail_check.py`); updated `test_ail_unified.py` `sortnan` (it had pinned the old silent behaviour) to expect the named refusal on both builds.
- `DEVLOG.md` (2026-10-29 entry) + one `DIFFERENCES.md` row `C?-job-refuzz95-10300605-1`.

## Probes (`cmp.sh`, both g and d) in `/tmp/probes/refuzz95`
- `p_repro` (all 4 reproducer lines): refused by name, both builds.
- `p_routes` (direct, argument, list item, attribute, dict value, aliased): all six refused with the message, both builds.
- `p_nan_tuple`, `p_nan_listkey`, `p_nan_allnan`: refused, both builds.
- `p_nan_keyfn`: refused (g: named message; d: bare `ValueError` from the typed KEYSORT stop).
- `p_keyerr`: a user `ValueError` raised in a key keeps its message, both builds.
- `p_noner` (ints, floats, negatives, `reverse=True`, `key=`, tuples, strings, `-0.0`, empty, single, `inf`, 10-element merge, stability, `.sort()`): matches CPython, both builds.

## Tests
- Required set on `fb13f99`: `test_ail_refuzz95`, `test_ail_numeric_profiles`, `test_ail_numeric_profiles_native`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → **53 tests, OK (1 skipped)**.
- Extra risk run before commit: `test_ail_nan_arith`, `test_ail_silent2`, `test_ail_silent6`, `test_ail_genlib` (statistics sorts) → OK.
- `tools/update_manifest.py` run, `--check` passes; codegen pins are sort-free and unchanged.

## Residual / follow-up
I did not port Timsort; NaN keys are refused by name rather than reproduced. The refusal is a runtime stop, so computed/dynamic NaN sources (e.g. `INF - INF`) are still caught. NaN-free sorts are unchanged; any program that includes the sort runtime carries the guard, while sort-free programs (all generated-code pins) are byte-identical.

## review 0
[model qoder/DeepSeek-Flash]
All probes and tests are done. Here is my review report.

## What the change really does

`AIL_CURRENT/python/pkg-v12/cruntime.py:15749-15760` adds `ail__sort_nan_check` (scan the decorate keys; a `AIL_T_FLOAT` NaN raises a named `ValueError`; recurse into tuple/list keys up to depth 32) and calls it at `:15801` just before the merge in the boxed v2 `ail_list_sort`. NaN-free keys keep the identical stable merge sort. Plus a new `test_ail_refuzz95`, a `sortnan` expectation change in `test_ail_unified`, DEVLOG/DIFFERENCES/MANIFEST. This matches the report; the report just omits the depth-32 cap.

## Report claims

| claim | status |
|---|---|
| boxed `ail_list_sort` scans keys, raises named ValueError incl. NaN in tuple/list key | **verified** — `p_repro`, `p_routes`, `p_edge`, `p_nanfn`: `ERR ValueError` on both builds, uncaught stderr carries the message + `C?-job-refuzz95-10300605-1` |
| typed path already refused (bare ValueError) | **verified** — `cruntime.py:29988` FLISTSORT and `:30129` KEYSORT are outside the diff; `p_caught` default-build uncaught stderr is bare `ValueError` |
| NaN-free keys keep the same stable sort/order | **verified** — `p_noner` (23 prints: ints, floats, reverse, key, tuples, nested lists, 10-element merge, `-0.0`, inf, stability, `key=abs`, NaN-in-values-with-int-key) and `p_keyok` (tuple/list keys of floats) are byte-identical to CPython on both builds |
| `safetyrt.patch_sortprim` strings preserved | **verified** — `safetyrt.py:2299` head still matches; the guard line sits before the patched `ail2u_sort_prim` call; `test_ail_unified` pins `ktmp = NULL` and passes |
| new module registered; `sortnan` updated | **verified** — `ail_check.py` diff; tests pass |
| DEVLOG/DIFFERENCES/update_manifest | **verified** — 2026-10-29 entry, row uses placeholder id, `update_manifest.py --check` rc=0, commit ends with Co-Authored-By |
| sort-free C byte-identical; sort programs carry the guard | **verified** — `q_nosort` `program.c` identical head vs base; `q_intsort`/`q_floatsort` differ by exactly the 20 guard lines |
| base really had the silent difference | **verified** — base `p_repro` prints `[1.0, 2.0, 3.0, nan]` vs CPython `[3.0, nan, 1.0, 2.0]` on both builds; head refuses |
| "53 tests, OK (1 skipped)" | **unverified** — I only ran the reviewer-required three modules |

## Tests (HEAD, `-j 2`)

`test_ail_refuzz95`, `test_ail_safetynet`, `test_ail_unified` → **0 failed** (114.6s / 134.3s / 383.5s).

## Probes (both builds unless noted)

`p_repro`, `p_routes` (arg, list item, attribute, dict value, alias, generator, key float/tuple/list), `p_edge`, `p_nanfn`, `p_keyerr`, `p_keyok`, `p_noner`, `p_deep`, `p_stats2`, `p_decnan`, `p_stats3` — NaN sorts stop by name; NaN-free ones match CPython. `p_decnan` (Decimal NaN) matches on head *and* base.

## Pre-existing (identical on base, non-blocking)

- **Nested key deeper than 32 levels is still silent**: `p_deep` — head refuses depth 5/31/32 but at depth 33/40 both builds print `[1.0, 2.0, 3.0, nan]` where CPython prints `[3.0, nan, 1.0, 2.0]`; base is silent at every depth. The report does not mention the `depth < 32` cap. Widen/remove it in the follow-up (the comparator itself already recurses).
- Key function raising: `p_keyerr` leaves `xs` reversed for `reverse=True` (`[2.0, 1.0, 3.0]` vs CPython `[3.0, 1.0, 2.0]`), identical on base.
- Legacy opt-in `AIL_GENERAL=v1` (pyboxed/OBJ, untouched) still sorts NaN silently (`v1s2`: `[1.0, 2.0, 3.0, nan]`).

## Loud collateral (accepted by the task's refusal option)

- Over-refusal where CPython succeeds: `sorted([nan])`, `[nan, nan]`, single nested list, dict keys containing NaN — task permits refusing any NaN-key sort; a compile-time refusal would be broader.
- `sorted([nan, "a"])`: CPython TypeError, head ValueError (both non-zero); base also TypeError, so the guard fires first.
- `statistics.median` over NaN data now refuses on both builds (`p_stats2`/`p_stats3`); base default already refused bare ValueError, base general matched CPython — the builds are now consistent, and even-length medians genuinely depend on sort order.
- `reverse=True` refusal leaves the list reversed before the exception (both builds the same).
- Every sort-using program's C changes, not only NaN-capable ones (report discloses sort-free-only byte identity).

Speed: `perf_event_open` is denied here, so `icount` fails. Wall clock on 1M-float + 1M-keyed-tuple sort: base 0.49s, head 0.49–0.50s — no measurable cost.

## Unverified

The worker's wider module set (numeric profiles, files, corpus_findings3, nan_arith/silent2/silent6/genlib) was not rerun; `AIL_NO_GENERAL=1` and `AIL_GENERAL=v1` beyond the single observation above were not exercised.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-29T23:58:29Z
