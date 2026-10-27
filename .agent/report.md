# job job-pre378-10280656  started 2026-10-27T21:57:17Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"35a2f750-2ee5-48f6-b9f7-5a28ce7dcc3c","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16194866845714284}},"permission_denials":[],"fast_mode_state":"off","uuid":"8f31756b-d345-4dfa-b241-096ec4f220b7","session_id":"2f97277a-94b1-4da5-9900-6b19db48d7ac"}

## worker report 0
[model qoder/DeepSeek-Flash]
**Report**

Reproduced the first still-differing review item: **p09** — an instance without `__getitem__` reported `TypeError: 'instance' object is not subscriptable`, where CPython names the class. `p08` (dict with slice key) already matched CPython on this tree; the nested `def slice` / `class slice` cases (p11, r11–r16) were already refused by name.

**Fix:** the v2 runtime's `ail_op_getitem` and `ail_op_getslice` fallbacks now use `ail__tname_c` instead of the tag-only `ail_type_name` (cruntime.py:16094, 16154), and dunderrt's string-matched getslice patch was updated to match (dunderrt.py:358-363). Subclasses name the subclass; builtins keep their type names.

**Probes** (`/tmp/probes/pre378`, both builds, 13 programs): 7 match CPython — `p08_dict_slice`, `p09_instance_name` (int/slice/str/float/None keys, subclass, builtin values), `p09_routes`, `p09_slice_routes`, `p09_uncaught`, `p09_control_getitem`, `r11_nested_def_module`; 6 are refused by name — `p11`, `r12`–`r16` (`a slice object the general path could not build` / `a nested class definition (slice)`).

**Tests** (on commit `6b5d96f`): test_ail_pre378 2 tests 37 s; test_ail_safetynet 5 tests 103 s; test_ail_files 18 tests 113 s (1 skip); test_ail_corpus_findings3 2 tests 195 s; targeted test_ail_pre353 3 tests 61 s and test_ail_pre354 1 test 53 s — all OK.

Records updated (DIFFERENCES `C?-job-pre378-10280656-1`, DEVLOG, `ail_check.MODULES`, ci_shards); `update_manifest.py --check` passes. The class object itself (`A[1]`) and the v1 emitter (`AIL_GENERAL=v1`) are separate pre-existing paths and were not changed.

## review 0
[model qoder/DeepSeek-Flash]
**Review of job-pre378 (commit 6b5d96f)**

What the change really does: in the v2 runtime it replaces the tag-only `ail_type_name(c.tag)` with `ail__tname_c(c)` in the `ail_op_getitem` default and the final `ail_op_getslice` fallback (cruntime.py:16094, 16154), and mirrors the getslice edit in dunderrt's string patch. It is a two-site error-text change; nothing else in the runtime moved. That matches the report.

**Probes** (`/tmp/rprobes`, both builds vs CPython, HEAD vs `/tmp/base` where relevant):

| probe | result |
|---|---|
| r01_keys (int/float/None/tuple/str/bool keys) | HEAD both builds = CPython; base said `'instance'` ×6 — fix confirmed |
| r02_slice (`slice(...)` key, both spellings) | HEAD both = CPython; base `'instance'` ×3 |
| r03_subclass (A<-B<-C, int and slice) | both = CPython (names B/C) |
| r04_routes (arg, alias, attr, dict value, list item; int+slice) | both = CPython |
| r05a_builtin_vals (int/float/None/bool) | both = CPython |
| r14_userfn (`userfn[0]`, `[0:1]`) | both = CPython (`'function'`) |
| r09_dunder (`__getitem__`, incl. slice, KeyError) | both = CPython |
| r12_views (`dict_keys/values/items`, int+slice) | both = CPython |
| r17 len-only instance | both = CPython |
| r10_plain (no feature) | both = CPython |
| r07_nonascii, r13_local_class | refused by name on both builds (pre-existing) |
| r06/r18 long class names | **mismatch** — see defect |
| r08_classobj (`A[1]`) | `'type' object is not subscriptable` on HEAD and base — pre-existing, untouched |

Worker probes re-checked: `p08_dict_slice` and `r11_nested_def_module` match; `p09_uncaught` exits 1 with matching stderr; p11/r12–r16 build-refused as reported.

**Defect (caused by the new code, not present identically on base):** class names longer than 33 chars are truncated by the unchanged `char buf[64]` at both new sites. 33-char names match; 34+ do not.

**Tests:** `test_ail_pre378` 38.2s and `test_ail_safetynet` 104.8s pass on HEAD; `update_manifest.py --check` exits 0.

**Claims:** fix location, base reproduction, p08/p11/r1x, subclass/builtin naming, dunderrt update, class-object and v1 untouched, records — verified. Worker's runs of test_ail_files, test_ail_corpus_findings3, test_ail_pre353/pre354 — not rerun (outside reviewer scope). Note: the v1 emitter (`AIL_GENERAL=v1`) still says `'instance'` (disclosed, out of the two cmp.sh builds); the DIFFERENCES row says "fixed" without that caveat.

**Speed:** not applicable — `ail__tname_c` is only reached on the raising path; no hot code changed, so no icount run.

VERDICT: FIX
1. `/tmp/rprobes/r18_namelen.py` (34-char class, int and slice keys): expected `'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB' object is not subscriptable`, actual on both builds `'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB' object is not subscriptabl` (also `/tmp/rprobes/r06_longname.py`, 40-char name). Both new sites keep `char buf[64]`; size the text from the class name (or raise with a dynamically built message) so the full name is printed, as `ail__tname_c` itself already grows its buffer.

## worker report 1
[model qoder/DeepSeek-Flash]
Report

**Defect fixed.** The pre378 fallbacks formatted `'<name>' object is not subscriptable` into `char buf[64]`, so names >33 chars were cut (message is name+31 bytes). Both sites now call a new `ail__raise_not_subscriptable` (cruntime.py:14843) that sizes its buffer from `ail__tname_c` and frees it after `ail_raise_c` copies the text. `dunderrt`'s two string-matched patches (getslice fallback, getitem default) were updated to the new text.

**Probes** (`/tmp/probes`, both builds via `cmp.sh`) — all match CPython:
- `p_long_int` / `p_long_slice` (40-char class, int and slice)
- `p_long_routes` (40-char through argument, alias, attribute, dict value, list item; int and slice)
- `p_boundary` (1 / 33 / 34 chars — the old truncation edge)
- `p_subclass_long` (40-char base and subclass, int + slice)
- `p_builtins` (int/float/None/bool and dict views)
- `p_dunder_slice`, `p_dunder_ops` (dunder dispatch, including the patched getitem text)
- `p_long_uncaught` (exit 1, identical stderr on both builds)

**Tests on final tree:** `test_ail_pre378` 2 OK (62.4s), `test_ail_safetynet` 5 OK (103.9s), `test_ail_files` 18 OK/1 skipped (65.9s), `test_ail_corpus_findings3` 2 OK (190.4s). `test_ail_pre378.py` gained the long-name int/slice, 33/34 boundary, long route/subclass and long uncaught cases.

`update_manifest.py` run; `--check` exits 0. A separate v1 probe (`AIL_GENERAL=v1`) confirmed v1 still prints `'instance'`; that caveat is now in the DIFFERENCES row.

Committed as `8262e89` (6 files). Untracked `.agent/pipeline.md` (job artifact) left uncommitted.

## review 1
[model qoder/DeepSeek-Flash]
## Review: pre378 follow-up (work..HEAD = 6b5d96f, 8262e89)

**What the change really does.** The v2 runtime's `ail_op_getitem`/`ail_op_getslice` fallbacks now name the value's class (`ail__tname_c`) instead of the tag table, and build the message through a new `ail__raise_not_subscriptable` that sizes a malloc'd buffer from the name instead of `char buf[64]`; `dunderrt`'s two string-matched patches (getslice fallback, getitem default) were retargeted to the new text. That matches the report.

**Claims checked**

| claim | result |
|---|---|
| old `buf[64]` truncated names >33 chars (msg = name+30+NUL) | verified: 6b5d96f used `ail__tname_c` into `char buf[64]`; 33 fits, 34 does not |
| helper at cruntime.py:14843 sizes from `ail__tname_c`, frees after `ail_raise_c` copies | verified (`ail_raise_c` does `ail_str_from_cstr`) |
| dunderrt's two patches updated | verified; `patch()` count==1 holds and dunder programs compile/run |
| probes all match CPython | verified independently (below) |
| `test_ail_pre378` 2 OK, `test_ail_safetynet` 5 OK | verified: my rerun 61.7s / 105.4s, 0 failed |
| `update_manifest.py --check` exit 0 | verified |
| v1 still says `'instance'` | verified statically (v1 text at cruntime.py:10295/10305 still `ail_type_name`) |
| `p08` dict+slice already matches | verified (p06: identical to CPython on HEAD and base) |
| nested `def slice` / `class slice` refused by name | verified (p10/p11) |
| committed 6 files in 8262e89 | verified |
| `test_ail_files`, `test_ail_corpus_findings3` | unverified — not rerun per reviewer scope |

**Probes** (`bash ~/tools/cmp.sh`, both builds; CPython = oracle)

| probe | result |
|---|---|
| p01_len (names 32/33/34/40/90, keys 0/1/-1 and slice) | same as CPython, both builds |
| p03_routes (long name via arg, alias, attr, dict value, list item; int+slice) | same |
| p04_builtins (int/float/None/bool/function/builtin/class) | same |
| p05_dunder (class with `__add__`, and with `__add__`+`__getitem__`; int/float/str/slice) | same (dunder-patched runtime) |
| p06_dict_slice (dict slice, empty dict, alias) | same — p08 already matches |
| p07_uncaught (40-char class) | exit 1, same stdout/stderr last line |
| p13_patch_msg (patched path via argument, `__iadd__`, `__getitem__` slice) | same |
| p15_counter (Counter slice/int) | same |
| p02_unicode | named refusal (v2 ASCII-only), same both builds |
| p10/p11 nested `def slice` / `class slice` | refused by name |

**No-feature C:** a program with no instance subscript produces byte-identical `program.c` and identical exe sha256 on base and HEAD (21212 bytes, `acc2fc9b…`). Speed: not applicable — the helper is only on the error branch; normal programs' C is unchanged.

**Pre-existing (identical on base, do not block)**
- `A[1]` class object: `'type' object is not subscriptable` vs CPython `type 'A' is not subscriptable` (p09_classobj; base same; declared in the row).
- Exception instances (`MyError()[1]`, slice): `'exception'` on both builds vs CPython's class name (p14_exc; base same).
- A user class literally named `_AilDeque_Foo` prints `'collections.deque'` (p08_weird_names); base prints `'instance'`. Both are wrong vs CPython; this is `ail__tname_c`'s internal-name special case (already used by attribute errors), newly reached for subscript errors. Residual, not new wrongness versus base.
- `x[1:2]` on an instance with `__getitem__` through an untyped route, and the nested-`slice` programs, are unchanged refusals/differences.

**Verdict**

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T23:52:19Z
