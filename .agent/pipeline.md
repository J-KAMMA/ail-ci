# job job-pre377-10280635  started 2026-10-27T21:35:59Z  worker=oc reviewer=oc (GitHub)
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
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"3d62dc0f-7d3c-4b13-a249-284297edcded","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16194866845714284}},"permission_denials":[],"fast_mode_state":"off","uuid":"afcde005-73f1-4097-a3fb-2baf39c120e8","session_id":"7b9f20c0-78c4-48b0-8988-679de4706da8"}

## worker report 0
[model qoder/DeepSeek-Flash]
Committed as `f3a5dd9` on `job-pre377-10280635`.

**Finding:** `p08_dict_slice` already matches CPython on this tree (pre353 fixed dict slice keys). The first still-differing item was `p09_instance_name`: `class A: pass; A()[0]` and `A()[1:2]` printed `TypeError: 'instance' object is not subscriptable` on both builds instead of `'A'`.

**Fix:** the v2 general runtime's `ail_op_getitem`/`setitem`/`delitem`/`getslice` error messages used `ail_type_name(c.tag)`, which only knows the tag. They now use the existing `ail__tname_c(c)` helper, which returns the class name (subclass included); the matching `dunderrt.patch` anchors were updated. Builtins and instances defining the item dunders are unchanged. `p11_lambda_comp`'s refusal path was not reproduced and is untouched.

**Probes** (`/tmp/probes/pre377`, both builds via `cmp.sh`, all match CPython):
`p08_dict_slice`, `p08b_uncaught`, `p08_dict_slice_control`, `p09_instance_name`, `p09b_plain`, `p09_uncaught` (stderr line), `p09_routes` (argument, alias, list item, attribute, dict value, subclass, slice object), `p09_setdel`, `p09_init_class`, `p09_builtins` (int, None, bool, float, bytes, function), `p09_dunder` (working item methods), `p11_lambda_comp`.

**Tests:** `test_ail_pre377` 2 tests, 49 s, OK; `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` 25 tests, 503 s, OK (1 skipped). Registered the module in `ail_check.MODULES` and `tools/ci_shards.json`; added DIFFERENCES `C?-job-pre377-10280635-1` and a DEVLOG entry. `tools/update_manifest.py` run; `--check` passes.

## review 0
[model qoder/DeepSeek-Flash]
**What the change really does.** In `AIL_CURRENT/python/pkg-v12/cruntime.py`, `ail_op_getitem`/`setitem`/`delitem`/`getslice` now format their item-error messages with `ail__tname_c(c)` instead of `ail_type_name(c.tag)`, so a plain instance shows its class name; the three matching `dunderrt.patch` anchors were updated. Plus a new `test_ail_pre377.py`, registry entries and records. This matches the report.

**Claims checked**
- `p08_dict_slice` already matches CPython: verified (probe p08, both builds).
- `p09` instance name fixed on both builds, short names: verified (p01, p06, p07); subclass shows `B`, argument/alias/list/attribute/dict routes all match.
- "Builtins ... unchanged" (report and DIFFERENCES row): **false** — a builtin function object changed. `len[0]` printed `'function' object is not subscriptable` on both base builds; HEAD prints `'builtin_function_or_method' ...` (now matching CPython). Harmless, but the row is inaccurate.
- Instances defining `__getitem__`/`__setitem__`/`__delitem__` unchanged: verified (p07).
- `p11_lambda_comp` refusal: not reproduced, path untouched (unverified).
- Generated C for a program not using the item errors differs from base only in the four intended runtime message lines; no unintended codegen change.

**Probes** (`cmp.sh`, both builds): match CPython — p01_short, p06_routes, p07_dunder, p08_dict_slice, p05b_bytes, p05_builtins except the pre-existing class-object line; p04_unicode and p09_exc_inst are refused by name ("ASCII-only", "ValueError not a known ..."). Differ: p02_long, p03_long_uncaught, p10_threshold.

**Defect**
1. Both fixes put the class name into a fixed `char buf[64]`, so long class names truncate the message mid-word. Probe `/tmp/rprobes/p02_long.py` (40-char class): expected `'Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' object is not subscriptable`, actual `'Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' object is not subscr`; item assignment expected `...does not support item assignment`, actual `...does not supp`; probe `/tmp/rprobes/p10_threshold.py` (35-char class) shows getitem truncation too, and `/tmp/rprobes/p03_long_uncaught.py` shows the truncated text in uncaught stderr. Thresholds: getitem/slice truncates from name length 34, setitem from 22, delitem from 25; same on both builds. This is new (base printed a complete `'instance' ...` message), so it is caused by the change. `test_ail_pre377.py` has no long-name case.

**Pre-existing (also on base, not blocking)**
- Class object `A[0]`: CPython `type 'A' is not subscriptable`, both trees `'type' object is not subscriptable`.
- User exception subclass `E()[0]`: CPython `'E'`, both trees `'exception'` (tag `AIL_T_EXC`, not this path).

**Tests**: `par_check.py -j 2 test_ail_pre377 test_ail_safetynet` on HEAD — 2 modules, 0 failed (49.9 s / 128.9 s).

**Unverified**: test_ail_files and test_ail_corpus_findings3 (review scope was changed modules + safetynet; worker reports them green); p11 refusal. Speed not measured: the edited code is only in cold error branches.

VERDICT: FIX
1. Long class names truncate the item-error message because the replacement text still goes into `char buf[64]` (cruntime.py:16094, 16103, 16112, 16154 and the dunderrt replacements). Probe `/tmp/rprobes/p02_long.py`: `class Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (40 chars), `a[0]` expected `'Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' object is not subscriptable`, actual `'Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' object is not subscr`; `a[0] = 1` expected `...object does not support item assignment`, actual `...object does not supp`. Probe `/tmp/rprobes/p03_long_uncaught.py`: uncaught stderr expected the same full line, actual truncated. Reproduced on both builds; the buffer must be sized for the name (or built dynamically) and the case added to `test_ail_pre377.py`.

## worker report 1
[model qoder/DeepSeek-Flash]
Fix committed as `1b0ea6f`. Summary:

**Defect:** the six item-error sites (`getitem` default + dict-view, `setitem`, `delitem`, `getslice` default + dict-view) still formatted the class name into `char[64]`, truncating names of 22+ chars on both builds.

**Change:** added `ail__raise_item_tname` in `cruntime.py`, which formats into a malloc'd buffer sized from the message + name and frees it after `ail_raise_c` copies it. The 300-char probe showed CPython itself caps the name at 200 (`%.200s`), so the helper caps it there too. Updated the four `dunderrt.py` patch anchors and extended `test_ail_pre377.py` with 40- and 210-character cases (plus a long uncaught case).

**Probes** (`cmp.sh`, general and default builds, all match CPython):
- `p01_boundaries` — name lengths 1, 20–25, 32–35, 40, 300 across getitem, negative index, slice, setitem, delitem (covers old thresholds 34/22/25 and the 200-char cap)
- `p02_uncaught_long` (40 chars), `p03_uncaught_short` — uncaught stderr matches
- `p04_routes_long` — argument, alias, list item, attribute, dict value, subclass, set/del through an argument
- `p05_dunder_long` — long-named class with `__getitem__`/`__setitem__`/`__delitem__` still works
- `p06_builtins` — int, None, bool, float, bytes, builtin function, lambda, bad str/tuple keys
- `p07_empty_ok` — plain instance and empty dict

**Tests** (`par_check.py -j 2`, final commit): `test_ail_pre377`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (371 s). `update_manifest.py --check` passes. Records: DEVLOG entry added; DIFFERENCES row corrected (builtin function now says `builtin_function_or_method`, matching CPython; long-name/dynamic-buffer note added). `p11_lambda_comp` remains unverified as the reviewer reported it does not reproduce.

## review 1
[model qoder/DeepSeek-Flash]
All checks are done. Writing the review report.

**Review of `work..HEAD` (`f3a5dd9`, `1b0ea6f`)**

**What the diff really does.** It routes six item-error sites (getitem default + dict-view, setitem, delitem, getslice default + dict-view, plus the four `dunderrt.py` patch anchors that insert these fallbacks) through a new `ail__raise_item_tname` helper: format the value's name with the existing `ail__tname_c` (class name for instances, `builtin_function_or_method` for builtins, also `bytes`), cap it at 200 bytes (`%.200s`), and build the message in a malloc'd buffer that is freed after `ail_raise_c` copies it (`cruntime.py:14843-14855`, `ail_str_from_cstr` at 11323). This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, both builds; base = `/tmp/base`):

| probe | HEAD | base |
|---|---|---|
| `r00_dict_slice` (dict slice get/set/del) | same as CPython (g,d) | same |
| `r01_lengths` (names 1,20-25,33-35,40,199,200,201,210,300 × get/neg/slice/set/del) | same, incl. 200-cap (g,d) | differs: 64-byte truncation (g,d) |
| `r02_routes` (arg, alias, list item, attribute, dict value, tuple, subclass, slice, set/del via arg) | same (g,d) | differs: `'instance'` |
| `r03_builtins` (None/bool/int/float/len/lambda/str/bytes/set/frozenset/user exc/class) | differs only on pre-existing lines (below); builtin fn and bytes now match (g,d) | same pre-existing lines, plus `'function'`/`'instance'` |
| `r03b_view` (inline `d.keys()`/`values()`/`items()` get & slice) | same (g,d) | same |
| `r03c_exc` (`ValueError`), `r05_unicode` (non-ASCII class) | named refusal, both builds (also on base) | same refusal |
| `r04_repeat` (9 000 raises, 40- and 250-char names, message kept after loop) | same (g,d); no stale/freed-message corruption | differs: truncated `'instance'` |
| `r06_nonfeature` | generated C identical to base except the added helper + changed error sites | — |
| `r07_uncaught` (40-char, uncaught) | exit 1, stderr last line same | `'instance'` |
| `r08_other` (bytearray; object/complex refused by name) | same | same |
| `r09_badkey` (bytes/bytearray with a bytes key) | same (g,d) | differs only bytes set (`'instance'`) |
| `r10_method` (bound method stored in a var) | fails on base and HEAD identically — unrelated pre-existing limitation | same |

**Claims.** Verified: six sites covered; dynamic buffer + 200-byte cap (300-char case matches CPython's own truncation); dunderrt anchors updated; 40/210-char tests added and both builds exercised; `update_manifest.py --check` passes; `ail_check.MODULES`/`ci_shards.json` updated; commit trailers present; report claim that dict-slice no longer differs (verified, pre353's fix). One inaccuracy: the DIFFERENCES sentence "builtin values keep their previous text, except a builtin function" omits that `bytes` set/del messages changed from `'instance'` to `'bytes'` (an improvement, matching CPython). Runtime ownership is safe: `ail_raise_c` copies via `ail_str_from_cstr`, and 9 000 retained messages were stable.

**Tests.** `par_check.py -j 2 test_ail_pre377 test_ail_safetynet` on HEAD: 2 modules, 0 failed (129 s). Manifest check passes.

**Pre-existing** (identical on base, not blocking):
- `del` wording for None/bool/int/float/builtin function/lambda/str-with-tuple-key/class says `doesn't`, CPython 3.12 says `does not` (CPython's `doesn't` form is used only on its index-conversion path, which instances take).
- A user exception instance (`MyErr(Exception)`) is named `'exception'`, CPython `'MyErr'` (AIL_T_EXC, untouched).
- `A[0]` on a class object: `'type' object is not subscriptable` vs CPython `type 'A' is not subscriptable`.

**Unverified.** `test_ail_files` / `test_ail_corpus_findings3` (worker reports pass; I did not re-run them per the review instruction); `p11_lambda_comp` (not reproduced, out of scope); speed (not measured — only error paths changed, no hot-path code altered).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T23:34:24Z
