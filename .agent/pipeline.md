# job job-pre358-10280158  started 2026-10-27T16:59:13Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"067f3b5c-37be-4daa-a8a6-5dd6af7995d4","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"35d26d8a-1181-4764-a830-4354681804b9","session_id":"4e384b21-6875-4357-ab71-aaa3ec893e13"}

## worker report 0
[model qoder/DeepSeek-Flash]
Committed `094e1b9` on `job-pre358-10280158`.

**Reproduced first difference (both builds):** `d = {"k": "9223372036854775808"}; int(d.get("k"))` — CPython prints the big integer; both builds stopped with `integer overflow` (`t04` does the same via a parameter list item and was the second item).

**Fix:** the int64 constant fold now evaluates `dict.get(key)` / `dict.get(key, default)` with a constant key, and a module-level dict literal/alias is foldable when its only uses are subscript reads or `.get` calls (`AIL_CURRENT/ail_chatgpt.py:755`, `:1128`). The route is refused by name: `int64 constant expression out of range`, both builds. A dict held in a class/instance attribute is deliberately not folded, so in-place mutation (`c.d["k"] = ...`) still matches CPython.

**Probes** (`/tmp/probes/pre358`, `cmp.sh`, both builds), 18 programs:
- Refused by name (12): `t02`, `t02_alias`, `t02_bytes`, `t02_empty_default`, `t02_get_default_big`, `t02_inline_get`, `t02_key_from_attr`, `t02_key_from_dict`, `t02_key_from_list`, `t02_negative`, `t02_whitespace`, `t02_direct_subscript` (already refused before).
- Match CPython (5): `t02_boundaries`, `t02_dynamic_ok`, `t02_in_range`, `t02_mutated_class_d`, `t02_mutated_in_range`.
- `t04.py` (parameter list item) still differs with `integer overflow`; separate pre-existing cause, not changed.

**Records/tests:** added `AIL_CURRENT/test_ail_pre358.py` (2 tests, 22 programs), registered in `ail_check.MODULES` and `tools/ci_shards.json`, plus DEVLOG and a `C?-job-pre358-10280158-1` DIFFERENCES row. Final-state `par_check -j 2 test_ail_pre358 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed, 370 s. `update_manifest.py` run; `--check` exit 0.

## review 0
[model qoder/DeepSeek-Flash]
All probes and tests are done. Here is my review.

## Review of `job-pre358-10280158` (commit `094e1b9`)

**What the change really does** (matches the report): `ail_chatgpt.py:755` adds a `dict.get(key[, default])` constant-fold branch (constant key, no keywords, base is a `Dict`/`Name`/`Subscript`), and `:1128` lets `_safe_module_containers` treat a `.get()` call as a read-only use, so a module-level dict literal/alias whose only uses are subscript reads or `.get` calls enters `known` and the int64 `int()` checker refuses out-of-range results by name. No codegen change.

**Task item.** `t02` (`d={"k":"9223372036854775808"}; print(int(d.get("k")))`) — HEAD: both builds refuse with `int64 constant expression out of range`; base: both overflow. Fixed as claimed. `t04` (`int(xs[0])` from a parameter) still overflows on HEAD *and* base — unchanged, as the report states; the task asked for one cause.

**Claims verified.** Fold location/behaviour (code + probes); refusal wording on both builds; 18 probe files (12 refused/5 match/t04) and 22 test programs (11 refused + 2 float + 9 match) present; attribute/instance dicts not folded; `test_ail_pre358` + `test_ail_safetynet` re-run: 2 modules, 0 failed, 139 s; `update_manifest.py --check` exit 0. Not re-run (per review rules): `test_ail_files`, `test_ail_corpus_findings3` (so the worker's "4 modules, 370 s" is partially unverified). Speed: not applicable — compile-time-only, C unchanged.

**Probes** (`/tmp/rprobes`, `cmp.sh`, both builds):
- Match CPython: `p_mut_alias` (alias then `e["k"]=…`), `p_mut_func` (mutation via argument), `p_global_mut`, `p_del_key`, `p_alias_alias_mut`, `p_list_hold`, `p_plain_get`, `p_alias_chain_inrange`, `p_present_none` (`{"k":None}` → TypeError), `p_local_and_inline`, `p_unhashable` (`get(["k"])` → TypeError).
- Refused by name on HEAD, overflow on base (correct: CPython gives a big int): `p_bool_key` (`{1:…}.get(True)`), `p_dup_keys`.
- `p_mut_methods2`: `update`/`pop` routes match; `dict |= dict` TypeError on both.
- `p_no_feature`: `--debug-dir` `program.c` byte-identical to base in default and general builds; `native_report.json` differs only in temp paths.

No false refusal found: every mutation route the analysis should catch is caught (subscript/`del`/alias/argument/`global`/`update`/`pop`/list-held), so the fold only fires when the literal is the value the program actually reads.

**Pre-existing** (identical on base, not blocking): `int(outer["a"].get("k"))` with a nested-dict literal → `integer overflow` (nested dicts aren't `_foldable_container`); `print(int(d.get("k")))` in a class body that also binds `d` → empty stdout/exit 0; `.get(..., default=…)` → same named subset refusal; `d.setdefault` (no-op) then big → overflow.

**Unverified:** the two extra worker modules above; instruction counts (not applicable).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T18:34:56Z
