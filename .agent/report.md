# job job-pre367-10280933  started 2026-10-28T00:34:08Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> vice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"e9c27b13-c2d4-4912-a6ec-61cb9edeece6","context_usage_ratio":0.019627},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.1625677470285714}},"permission_denials":[],"fast_mode_state":"off","uuid":"23fbd44e-7b87-4f64-ba8d-b06b1f549330","session_id":"65f847a8-7f39-477c-b191-8face945dac4"}

## worker report 0
[model qoder/DeepSeek-Flash]
Fixed and committed. All ten modules pass on the final commit.

**Cause:** the pre367 power checker (`_check_int64_binpow_constants`) refused with its generic `int64 constant expression out of range` before three older checks that own their contexts.

**Fix (`AIL_CURRENT/ail_chatgpt.py`, commit `c38d78a`):** the checker now defers when
- the node is a `str.split`/`rsplit` maxsplit constant (restores pre97/pre190/pre200/pre205 wording),
- the power is a syntactic literal power forming the whole RHS of a plain assignment (restores pre160's emitter wording, `outside the signed 64-bit range`),
- a syntactically constant base |b|≥2 has an exponent the front end does not see as constant (restores pre273's `constant base N … computed at run time`).

Name-based powers (argument, list item, attribute, dict value, closure) are still refused by name.

**Probes (`/tmp/probes`, both builds, `bash ~/tools/cmp.sh`):**
- refused by name: `p1_saturate_assign`, `p2_maxsplit_pow`, `p3_variable_pow_local`, `p4_variable_pow_inrange`, `p5_name_base_refused`, `p9_assign_name_pow`, `p10_list_dict_attr`
- match CPython: `p6_inrange_local`, `p7_closure_shadow`, `p8_maxsplit_inrange`
- 10/10 as required (CPython match or named refusal).

**Tests on final commit (`par_check.py -j 2`):** 10 modules, 0 failed — the six reported (pre160, pre190, pre200, pre205, pre273, pre97), plus pre367, safetynet, files, corpus_findings3. Also passed earlier on the same code: pre113, pre33, pre331, pre334, pre335, pre338, pre351. `update_manifest.py` run, `--check` exit 0. DEVLOG entry added (2026-10-28). No new DIFFERENCES row: no new CPython divergence, only restored diagnostics.

## review 0
[model qoder/DeepSeek-Flash]
Premise confirmed: pre160 and pre273 fail on `work` with exactly the generic binpow wording, and pass on HEAD.

---

# Review report

**What the change really does (one line):** in `_check_int64_binpow_constants` it adds three early returns — `id(node) in maxsplit`, a syntactic-int power that is the whole plain-assignment RHS (not directly in a class body), and a syntactic base |b|≥2 whose exponent is not syntactically constant — so that the pre97/pre160/pre273 checks report before the new pre367 checker; the helper constants mirror `pyfront.int_constant`/`_pow_exponent_is_constant`, and `_binpow_assignment_value` mirrors the existing `_check_constant_out_of_range` assignment rule. This matches the report.

**Tests (HEAD, `par_check.py -j 2`):** 10 modules, 0 failed — pre97, pre160, pre190, pre200, pre205, pre273, pre367, safetynet, files, corpus_findings3 (303 s). Base re-check: `test_ail_pre160` and `test_ail_pre273` both fail on `/tmp/base` with the reported generic wording. `update_manifest.py --check` exit 0; DEVLOG entry present at top; no test file edited; no DIFFERENCES row added. All consistent with the report.

**Probes (`/tmp/rprobes`, both builds, `cmp.sh`, HEAD vs `/tmp/base`):**
- Refused by name, both builds (only wording/position intended to change): p01 `x = 10**30` (module), p02 `a = 10**30` (function), p03 `x = (1<<200)**2`, p04 `x = 2**63`, p05 `x = -(2**64)`, p06 `x: int = 10**30`, p07 class-body `x = 10**30` (still generic wording), p08 module `2**n`, p09 closure, p10 attribute, p12 `s.split(" ", 2**63)` (maxsplit wording restored), p15 argument, p16 `3**(6*11)`, p17 `3**(2**6)`, p19 list item, p20 dict value, p22 lambda.
- Match CPython on both builds: p11 `2**(10/2)` → 32.0, p14 no-pow, p18 `2**-70`, p21 `(-2)**63 / 2**63-1 / 10**18`, p23 `x = -2**63`, p24 `x = 2**64-2**64`, plus the worker's p6/p7/p8 rerun → same stdout `g`/`d`.
- **No probe is accepted on HEAD where base refused, and none matches CPython on HEAD where base did not.** p13 (`3**(1<<200)`) is unusable as a probe: CPython itself cannot compute it (hung; killed by timeout).

**Unchanged C:** `--debug-dir` output for p14 (no powers) differs only in temp paths in `native_report.json`; `program.c` is byte-identical between HEAD and base, both builds.

**Claims:** all report claims verified (wordings, name-based refusals via pre367 tests, 10/10 tests, manifest, DEVLOG, no DIFFERENCES row). Minor imprecision: "pre160's emitter wording" — in my p02 the `outside the signed 64-bit range` text came from the front-end constant-fold pass, not the emitter; same observable result, not a defect. Non-blocking nit: `_binpow_syntactic_int_node` includes `ast.Div`, which can never denote an int; it is harmless (p11 matches CPython) because that path only defers to checks that handle float powers.

**Pre-existing:** none found; all base/HEAD differences are the intended wording restorations.

**Speed:** the change is compile-time checker logic only, no codegen/runtime change (verified by identical `program.c`), so no icount run was needed.

**Unverified:** wider suite and the extra modules the worker listed (pre113, pre33, pre331, pre334, pre335, pre338, pre351) were not rerun; worker's probe files p1–p5/p9/p10 were verified only indirectly (equivalent shapes in my probes and passing pre97/pre160/pre273/pre367).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T02:19:48Z
