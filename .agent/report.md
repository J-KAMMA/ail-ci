# job job-pre283-10270202  started 2026-10-26T17:03:45Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"success","duration_ms":1887,"duration_api_ms":1761,"is_error":false,"num_turns":1,"result":"pong","stop_reason":"end_turn","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Committed as `a903cf4` on `job-pre283-10270202` (not pushed).

**Reproduced:** `class Box: v = 1.0` + `Box.v = 2.5` → CPython prints 2.5; both builds raised `AttributeError: 'type' object has no attribute 'v'`. Cause: the general path keeps class attributes in read-only module slots and copies them onto instances.

**Change (refusal by name, no semantic rewrite):**
- `pyboxed2._refuse_class_attr_store` (called from `_assign_target` and AugAssign): a direct, unshadowed class base is refused at compile time, exit 3 (`not in the subset: assigning the class attribute Box.v; …`). The typed path is untouched, so classes it already handled still match CPython on the default build.
- `ail_chatgpt._check_class_attribute_assignment`: refuses a class alias, or a class read out of a literal list/tuple/dict (constant index, negative included), exit 2 on both builds.
- `ail_inst_setattr_chk`: a base only known to hold a class at run time raises a named `NotImplementedError` instead of the misleading `AttributeError`.

**Probes** (46 in `/tmp/probes`, each via `cmp.sh`):
- 24 refused by name at compile time on both builds: `c1`–`c5`, `c9`, `c10`, `m1`–`m6`, `n5`, `n6`, `n10`–`n12`, `p283`, `t4`, `t6`–`t8`, `t11_tuple`.
- 12 match CPython on both builds: `c6`–`c8`, `c11`, `c13`, `n3`, `n7`–`n9`, `n13`, `t9`, `t10` (instance stores; local/parameter/loop/closure shadowing; value types int/float/str/bool/negative; rebound alias; empty container; mutated container).
- 5 match on default / refused on general: `c16`, `t1`–`t3`, `t5` (typed class-attribute support preserved).
- 2 refused by name at run time on both builds (`n1` parameter, `n2` instance-attribute route) — not statically provable, so not compile-time; this is honest runtime refusal, stdout still differs from CPython.
- Unrelated pre-existing probes unchanged: `c15` (`del` refusal), `n4` (builtin class as value: `name 'int' is not defined`), `ref_front` (int64).

**Tests** on the committed tree: `test_ail_pre283`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_dunders`, `test_ail_typed_inherit` — 6 modules, 320 s, 0 failed (`-j 2`). `tools/update_manifest.py` run; `--check` passes. DEVLOG and DIFFERENCES (`C?-job-pre283-10270202-1`) updated; module registered in `ail_check.MODULES` and `ci_shards.json`.

**Not verified:** instruction-count/speed (not measured; the runtime edit is one well-predicted cold-path compare per attribute store), and runtime-route parity for `n1`/`n2` (refused, not matched).

## review 0
[model qoder/DeepSeek-Flash]
**Review of `a903cf4` (job-pre283-10270202)**

**What the diff really does** (matches the report): stores whose base is statically a class are refused — `pyboxed2._refuse_class_attr_store` raises `Unsupported` for a direct unshadowed class name (`_assign_target` and AugAssign), `ail_chatgpt._check_class_attribute_assignment` refuses aliases and constant-index reads of literal list/tuple/dict class containers, and `cruntime.ail_inst_setattr_chk` raises a named `NotImplementedError` when the base tag is `AIL_T_CLASS` at run time. Test/registration files added.

**Verified claims**
- Reproduction: `class Box: v = 1.0; Box.v = 2.5` — CPython prints 2.5; base both builds `AttributeError: 'type' object has no attribute 'v'`; HEAD both builds refuse by name (`r01`).
- Exit codes: direct → 3 on both builds; alias/literal container → 2 on both (`r10`, `r11`).
- Runtime route: parameter, instance-attribute, computed index, `global` name → named `NotImplementedError` (`r05`–`r07`, `r12`, `r17`, `r25`).
- Typed path preserved: class with `__init__` + direct `Box.v = 2.5` matches CPython on the default build, refused on general (`r23`; base default also matched).
- No regressions found: instance stores through a parameter, list item, dict value, rebound class name, mutated container, mixed class/instance list and dict, negative index, out-of-range index all match both builds (`r02`, `r03`, `r04`, `r09`, `r13`, `r14`, `r16`, `r19`–`r22`, `r27`).
- No-feature program: generated `program.c` on HEAD and base is byte-identical (0-line diff), so codegen is untouched; the runtime error path uses the same stack-buffer/`ail_cstr` copy pattern as the existing `ail_attr_not_inst`.
- `update_manifest.py --check` rc 0; 46 files in `/tmp/probes` (claim true).
- Tests on HEAD: `test_ail_pre283`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 226 s, 0 failed.

**Pre-existing (do not block; same divergence on base, only the error name changed)**
- Class base reaching the store through a computed index, a function return, an instance attribute, a parameter, a conditional alias, or a `global`-declared class name: CPython prints the new value; base raised `AttributeError`, HEAD raises the named `NotImplementedError` (`r05`, `r06`, `r07`, `r12`, `r17`, `r25`). `r17` is statically provable but is only caught at run time — minor gap, not a new difference.
- `del Box.v` still refused (`del on a Attribute`) — unchanged from base (`r08`).

**Unverified**
- Instruction counts: `perf_event_open` is denied on this runner, so no before/after icount. The runtime edit is one well-predicted tag compare on the instance-store path plus a cold branch; no measurement.
- Individually re-running all 46 worker probes (representative subset above), and the worker's extra `test_ail_dunders`/`test_ail_typed_inherit` (not in the required set).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T18:33:29Z
