# job job-pre361-10280245  started 2026-10-27T17:46:04Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"6ccd85bb-b02b-4388-9650-b3d63e0cbfd6","context_usage_ratio":0.019627},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"b7511187-ad79-4ff5-b3a9-5fcc0ce4d00d","session_id":"8f109012-d7b9-42bb-966a-f2e880ad2774"}

## worker report 0
[model qoder/DeepSeek-Flash]
**Report**

The exported task lost its item list. I recovered it read-only from the `job-pre352-10280028` branch: the final review's first pre-existing item is **r20** — `try: x = C` / `except Exception: x = D` / `print(x().f())` gave CPython `55`, both builds exited 1 with `AttributeError: 'C' object has no attribute 'g'`.

**Cause/fix:** the field/method collision screen resolved a call target written as `C()` but not through a variable (`x = C; x()`). `_classes_of` in `AIL_CURRENT/python/pkg-v12/pyfront.py` now resolves a call-target name through its in-scope assignments (bare class name, alias chain, all try/handler assignments) and propagates that resolution through argument, list-item, attribute and dict-value routes. Confirmed as a named compile-time refusal on both builds (`also stores an instance field named f`).

**Probes** (`/tmp/probes/pre361`, `cmp.sh`, both builds):
- Refused by name (10): `r20`, `r20_same`, `r20_nonclass`, `chain`, `arg_route`, `list_route`, `attr_route`, `dict_route`, `reassigned`, `later_module2`.
- Match CPython (3): `noncolliding`, `param_noncolliding`, `no_feature`.
- Still pre-existing `AttributeError` on both builds, unchanged (2): `walrus`, `loop` (no assignment-table entry). `later_module` (CPython `NameError`) is now refused by name.

**Records:** added `test_ail_pre361.py` (2 tests, 10 refused + 3 matching programs, both builds), registered in `ail_check.MODULES` and `tools/ci_shards.json`; DEVLOG + DIFFERENCES row `C?-job-pre361-10280245-1`.

**Final commit `b3514f3`:** `test_ail_pre361`, `test_ail_pre278`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **5 modules, 283 s, 0 failed**. `update_manifest.py --check` rc 0. Not pushed; no icount run (refusal-only front-end change).

## review 0
[model qoder/DeepSeek-Flash]
All checks are complete. Writing the report.

## Review report — job pre361 (commit `b3514f3`)

**What the diff really does (one line):** adds a `names_are_classes` flag to `_classes_of` in `pyfront.py` so the field/method-collision screen resolves a `.f()` *receiver that is a call through a variable* (`x()` where `x = C`, an alias chain, or a class reached via argument / list item / attribute / dict value) and refuses it by name at compile time. Matches the report.

**Fix verified:** r20 on base (`/tmp/base`) → both builds exit 1 with `AttributeError: 'C' object has no attribute 'g'` (CPython `55`); on HEAD both builds now stop with the named refusal `...also stores an instance field named f (CPython calls the field)`.

**Probes** (HEAD vs base, `cmp.sh`, both builds):
| probe | HEAD | base |
|---|---|---|
| p1 r20 try/handler | refused by name | runtime AttributeError |
| p3 dict two keys / p9 dict single | refused / **matches CPython** | runtime err / matches |
| p2 list `[D,C]` idx 0 / p10 list `[D]` | refused / **matches** | matches / matches |
| p11 `x=h.k` attribute alias | refused by name | runtime AttributeError |
| p12 arg, p13 branch, p14 kw-arg | matches / matches / refused | matches / matches / runtime err |
| p18 tuple-unpack, p19 unrelated alias, p17 empty index, p7 no-feature, p8 no receiver | matches CPython | matches |
| p15 walrus, p16 for-target | runtime AttributeError (identical on base) | same |

- **C unchanged for no-feature program:** `program.c` byte-identical base vs HEAD (17520 B, sha `46b6f712…`); only `native_report.json` temp paths differ. Structural reason: the screen only ever *raises*; it never edits the AST, and `_classes_of` is used only inside `refuse_field_method_call`.
- **No runtime/IO change**, so the 4b ownership probes and icount are not applicable.
- **Tests:** `par_check -j 2 test_ail_pre361 test_ail_safetynet` → `test_ail_pre361 53.0s ok`, `test_ail_safetynet 121.3s ok`, 2 modules, 0 failed. `update_manifest.py --check` rc 0; DEVLOG has a top `2026-10-27` entry; DIFFERENCES row and both `ci_shards.json` entries present.

**Pre-existing (identical on base, do not block):**
- p6 `y=C; y().g()` → runtime `AttributeError 'C' object has no attribute 'g'` on both.
- p15 walrus and p16 `for`-target receivers → same runtime `AttributeError` on both (as the report states).
- p4/p5 attribute access written as `H().k()` → unrelated refusal `the method .k() (on a instance:H)` on both.

**Observation (not a defect):** p2 `ks=[D,C]; ks[0]().f()` now refuses by name where base matched CPython 7 — the list route is index-insensitive. It is a named compile-time refusal, which the review rules accept; the constant-key dict route (p9) is precise.

**Claims checked:** fix reproduced & fixed ✓; assignment/argument/list/attribute/dict resolution ✓; named refusal both builds ✓; walrus/for unchanged ✓; unrelated class keeps CPython ✓; 10-refused/3-match test module ✓ (test passes); records/manifest ✓. **Not re-run** (per instructions): the other reported modules (pre278, files, corpus_findings3).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T19:24:07Z
