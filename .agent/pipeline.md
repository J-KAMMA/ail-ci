# job job-pre371-10280520  started 2026-10-27T20:20:49Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"81bf9487-94e2-4552-8583-1fa79602936d","context_usage_ratio":0.019627},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16195819274285714}},"permission_denials":[],"fast_mode_state":"off","uuid":"8958ac29-dda8-46ae-a6a7-1853320a3afc","session_id":"47a018cd-0a0d-45a1-ba95-cfb4bd4dc241"}

## worker report 0
[model qoder/DeepSeek-Flash]
**Fixed: the first still-differing pre357 item — annotated constructor store.**

`class Box: def __init__(self, v): self.v: float = v` + `int(Box(1e300).v)` overflowed at run time on both builds. Cause: `_known_class_attributes` collected only `ast.Assign` from `__init__`, ignoring `ast.AnnAssign` with a value, so the attribute stayed unknown. It now collects both (an annotation without a value is not a store and stays ignored). Commit `06450a0`.

**Probes** (`bash ~/tools/cmp.sh`, both builds, in `/tmp/probes/pre371`):
- 16 refusal probes r01–r16: refused by name on both builds (r15 as `int64 constant expression out of range`) — direct, negative, keyword, second positional, default, module constant, list item, dict value, class attribute, alias, list/dict item, function argument, wrapper, string annotation.
- 10 match probes m01–m10: CPython-identical on both builds — in-range int/float/str/bool, 9e18, int64 boundary, dynamic value, later store, non-conversion read, annotation-only store.
- r17 (value through a plain object's attribute): still runtime `integer overflow`, identical with a plain store on the base → pre-existing, not caused by this change.
- The reviewer's other item (`v = int(v)` before the store) still overflows on both builds — separate pre-existing cause, unchanged.

**Tests on final tree:** `test_ail_pre371`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` passes. DIFFERENCES row `C?-job-pre371-10280520-1` and DEVLOG entry added; not pushed.

## review 0
[model qoder/DeepSeek-Flash]
**Report**

**What the change really does:** `_known_class_attributes` (AIL_CURRENT/ail_chatgpt.py:652) now also records `self.attr: T = value` statements in `__init__` as attribute stores for the `int()` constant-fold screen; annotation-only statements remain ignored. Plus tests/DIFFERENCES/DEVLOG/MANIFEST. Matches the report.

**Probes** (22, `/tmp/rprobes`, `bash ~/tools/cmp.sh`, general + default, HEAD vs `/tmp/base`):
- p01 (`self.v: float = v`, `int(Box(1e300).v)`) — base: runtime `integer overflow` on both builds; HEAD: refused by name, both builds. **Original item fixed.**
- p02 (`self.v: float = 1e300` constant) — base overflow; HEAD refused by name.
- p06 (list item), p09 (annotation type ignored), p10 (required kwonly param) — HEAD refused by name; base overflow (p10 base refused too, other message).
- p03 (negative, 9e18, int64 min, default), p07 (plain store), p14 (str "123"/int64 min), p15 (annotated + later plain store) — CPython-identical both builds.
- q1/q3/q4 (class attr + annotated instance store, duplicate annotated stores, class/instance read) — CPython-identical both builds; no wrong value from the class-attribute fallback.
- q2, q5 (class attr 1e300 read via instance/class) — HEAD refuses by name (CPython big int → acceptable refusal); base overflow.
- Pre-existing (identical HEAD vs base): p05 (store after construction), p08 (annotated store outside `__init__`), p11 (`v=int(v)` after store), p12 (wrapper returns instance), p13 (`v=int(v)` before store), q6 (value via plain object's attribute), p04 — runtime `integer overflow` or refusal on both.

**C unchanged:** `--debug-dir` program.c identical for a non-feature program (plain class store, list/dict, int()).

**Tests:** `tools/par_check.py -j 2 test_ail_pre371 test_ail_safetynet` → 2 modules, 0 failed (51.3s/137.8s). `tools/update_manifest.py --check` rc=0.

**Report claims:** verified — original repro, cause, fix shape, 16 refusal + 10 match cases (counts match committed test; `bigint_string` refusal message is `int64 constant expression out of range`), r17-style and `v=int(v)` remain pre-existing, manifest row, DIFFERENCES/DEVLOG. Not re-run: test_ail_files, test_ail_corpus_findings3 (worker claims pass; outside my required set). Speed not checked: change is compile-time only and non-feature emitted C is byte-identical.

**Nit (non-blocking):** the `_known_class_attributes` docstring still says instance attributes are folded only from a "direct `self.attr = value`".

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T21:54:45Z
