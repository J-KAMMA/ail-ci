# job job-rbpre420-10312035  started 2026-10-31T11:36:15Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"d917ab68-25c8-4b96-89e1-9aa616499766","context_usage_ratio":0.019631},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"e90d39ea-b261-40fa-93a2-eb7ea3f32b8f","session_id":"673e206d-f6a1-4ef6-9a8b-263a094351d7"}

## worker report 0
[model qoder/DeepSeek-Flash]
Fixed and committed as `6a39c96`.

**Cause:** the pre420 re-apply made the v2 runtime's list/tuple getitem error text class-aware unconditionally, changing the generated C of every no-class general-path program. pre421 requires no-class C to stay base-identical.

**Fix:** restored the base `ail_type_name(key.tag)` runtime text and re-added the read-path rewrite to `pyboxed2._INDEX_ERROR_CLASS_EDITS`, gated with the write rewrites by `source_has_class`. Class-bearing programs still name the class (read/store/delete, 200-char cap); no-class programs emit base C.

**Tests (final code):**
- test_ail_pre421: 2/2 pass (was failing)
- test_ail_pre420: 1/1 pass
- test_ail_safetynet: 5/5; test_ail_files: 18 (1 skip); test_ail_corpus_findings3: 2/2
- test_ail_pre366: not present here or on origin/integ. Fetched its branch version and ran it: 28 refusal subtests fail identically on pristine HEAD and on this tree because this snapshot lacks the aliased power/int-wrapper feature it tests; its 14 matching subtests pass on both. Unrelated to this change, but not verifiable against a tree containing that feature.

**Probes (both builds, `cmp.sh`, all match CPython):**
- `pre420_routes.py` — instance/subclass/exception keys, argument/alias/list-item/attribute/dict-value routes, list+tuple, empty/negative/valid, `__index__`, bytes/bytearray/float/str/None/bool, store+delete
- `pre420_long.py` — class names 1/32/33/200/201/210
- `pre420_noclass.py` — float/str/None/bool keys, empty/negative, valid store/delete
- `pre420_uncaught.py` — uncaught error exit status
- No-class `--debug-dir` C: `ail_type_name(key.tag)` ×1, class-name `tnbuf` ×0; class-bearing C: 3 class-name writes.

`tools/update_manifest.py` run; `--check` passes. Only `.agent/pipeline.md` remains untracked (pre-existing).

## review 0
[model qoder/DeepSeek-Flash]
## Review report — job-rbpre420-10312035 (commit 6a39c96)

**What the change really does:** restores the v2 runtime's list/tuple getitem error to the base tag-based text (`ail_type_name(key.tag)`, fixed 96-byte buffer) and moves the class-name *read* rewrite back into `pyboxed2._INDEX_ERROR_CLASS_EDITS`, so all three rewrites (read + 2 writes) are applied only when `source_has_class` (a `ClassDef` in the program source). This makes no-class programs emit pre421's base C while class-bearing programs still name the class.

**Tests on HEAD** (`par_check.py -j 2`): `test_ail_pre420` ok, `test_ail_pre421` ok, `test_ail_safetynet` ok — 3 modules, 0 failed.

**Probes I wrote** (`/tmp/rprobes`, both builds via `cmp.sh`):
- `keys_class2.py` (class present; float/str/None/list/dict/tuple/bytes/bytearray/len/range keys) — match CPython.
- `long200.py` (class names 200 vs 201; read/store/delete) — match CPython (cap at 200).
- `store_class.py`, `multi_class.py` (store+delete, alternating long/short class names, buffer reuse) — match.
- `threads_class.py` (threads + class + bad index) — match; thread preamble rewrite applies.
- `uncaught_class.py` — exit 1 and stderr `...not C` match CPython.
- `no_feature.py` — match.
- `nested_class.py`, `nonascii.py` — refused by name on both builds (AIL subset), acceptable.
- `builtin_noclass.py`, `exc_via_raise.py` — **DIFF** for bytes/function/exception keys (see below).
- C identity: no-class C has `ail_type_name(key.tag)` read line ×1, 0 class-name `tnbuf` rewrites, base write text; class-bearing C has 3 class-name rewrites. Verified.

**Claims check:**
- No-class C base-identical (read line, 0 rewrites; 3 writes for class-bearing): **verified**.
- Class-bearing read/store/delete name the class, 200 cap: **verified** (pre421 + `long200`/`store_class`).
- pre420/pre421/safetynet pass: **verified**. test_ail_files / corpus_findings3: **unverified** (not re-run, per instructions).
- pre366 absent here and on origin/integ: **verified**. Its branch test fails **identically on base and HEAD** (Ran 2 tests, 28 failures, same subtest set — only `test_aliased_wrappers_are_refused_by_name`; `test_safe_aliased_wrappers_match_cpython` passes). Caused by this snapshot lacking the aliased power/int-wrapper feature, not by this change: **verified**. (The "14 matching subtests" number I did not count exactly.)
- `update_manifest.py --check` passes: **verified**. Only `.agent/pipeline.md` untracked: **verified**.

**Known behaviour change (not blocking):** a *no-class* source that indexes with a `bytes` or builtin-function key now prints `not instance` / `not function`, and an exception instance prints `not exception`, where CPython says `not bytes` / `not builtin_function_or_method` / `not ValueError` (`builtin_noclass.py`, `exc_via_raise.py`). On `work` these were correct; they revert here because pre421's test explicitly requires the no-class read line to be `ail_type_name(key.tag)`. The identical output is produced by origin/integ (the accepted pre421 base), so this is the mandated tradeoff of the task, not a new defect; class-bearing programs (any `ClassDef` in source) still name the key's class correctly.

**Speed:** not measured — the change only touches the getitem *error* branch and a compile-time string rewrite; the normal indexing path is unchanged.

`VERDICT: ACCEPT`

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-31T13:24:30Z
