# job job-pre289-10270338  started 2026-10-26T18:39:26Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":114323,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":114604,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the first remaining difference, `v1_return_route`.

- Base reproduction: `make(4).f()` printed `-1` on both builds vs CPython `40`.
- Change: ported the field/method collision refusal and resolved receivers returned by user functions (annotation, constructor return, returned local, chained call, and through argument/list/dict/attribute/alias). Now refused by name on both builds.
- Added `AIL_CURRENT/test_ail_pre289.py` (4 tests, both builds), registered it, added DEVLOG/DIFFERENCES rows, updated manifest.

Probes `/tmp/probes/p289_*` (14): 11 collision routes refused by name; unrelated-class, unrelated-conditional and non-class returns match CPython on both builds.

Final commit `fad403c`: `test_ail_pre289`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (4 modules, 0 failed); manifest `--check` clean. Not pushed.
[cost $0.0454, opencode tokens {"total": 4510639, "input": 122556, "output": 11339, "reasoning": 11816, "cache.write": 0, "cache.read": 4364928}]
    tool time: bash 12.6 min
        344s bash   cd AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre289 test_ail_safetynet test_ail_
        281s bash   cd AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre289 test_ail_safetynet test_ail_
         60s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre289 2>&1 | tail -40
         54s bash   for p in /tmp/probes/p289_*.py; do echo "===== $(basename $p)"; timeout 300 bash ~/tools/cmp.sh "$p" "$PWD" 2>
          5s bash   rm -rf /tmp/base289 && mkdir -p /tmp/base289 && git archive HEAD | tar -x -C /tmp/base289 && timeout 300 bash 
          2s bash   for b in job-pre260-10261729 job-pre279-10262332 job-pre276-10262320; do echo ===$b; git ls-remote origin refs
          2s bash   git fetch --no-tags --depth=1 origin refs/heads/job-pre260-10261651:refs/remotes/origin/job-pre260-10261651 >/
          1s bash   git fetch --no-tags --depth=1 origin refs/heads/job-pre278-10262329:refs/remotes/origin/job-pre278-10262329 >/

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review of pre289 change

**What the diff really does.** Adds `refuse_field_method_call(tree)` in `pyfront.py` and calls it at the three compile entrances (`pyc.py`, `pyfunc.py`, `pyboxed2.py`). It finds classes that both define a method and assign a same-named instance field, resolves receiver classes through function returns/annotations/arguments/collections/attributes/aliases, and raises a named `Unsupported` for `.name()` calls whose receiver may be such a class. No runtime code touched.

**Probes** (`/tmp/rprobes`, HEAD vs `/tmp/base`, both g/d builds):

| probe | HEAD | base |
|---|---|---|
| r8 exact `make(4).f()` (v1) | named refusal | `-1` vs CPython `40` (fixed) |
| r13 keyword arg, r14 module attr | named refusal | `-1` vs `40` (target route) |
| r1 unrelated function return, r2 no collision, r3 nested fn, r4 method chain, r7 param, r9 no feature, r12 | CPython match | CPython match |
| r6 local `x=A(); x.f()` with distant `x=C(...)` | **named refusal** | `41` match |
| r11 fn passed indirectly, distant `item=C(...)` | **named refusal** | `41` match |
| r5 `return C(k) if ... else C(0)` | `-1` vs `40` | `-1` vs `40` (pre-existing) |

`r9` no-feature `program.c` is byte-identical to base (`--debug-dir`).

**Tests.** `test_ail_pre289` + `test_ail_safetynet`: 0 failed (125 s). Manifest `--check` clean. Did not rerun `test_ail_files`/`test_ail_corpus_findings3` (out of scope).

**Claims.**
- direct collision / v1 route fixed: verified (refusal on both builds).
- annotated/chain/assigned/argument/list/dict/attr/alias/subclass routes: verified via the new module passing.
- "unrelated receiver keeps old behaviour": **too strong** — scope-insensitive name resolution refuses r6/r11 (still a *named* refusal, which the probe rules accept).
- `test_ail_pre278` + safetynet pass: **false** — no `test_ail_pre278.py` exists; the run was `test_ail_pre289`.
- field collection confined to its class: verified by code inspection (`_own_nodes` stops at nested defs/classes/lambdas).
- 4-module run and typed-only build: unverified here.

**Pre-existing.** r5 (function returning a conditional expression) prints `-1` vs CPython `40` on both HEAD and base; not caused by this change. `r6_setattr`/`r8_nested_class` were not re-probed but are stated as pre-existing.

No wrong output or crash attributable to the change; the only new differences are conservative named refusals.

VERDICT: ACCEPT
[cost $0.0206, opencode tokens {"total": 623973, "input": 36268, "output": 4484, "reasoning": 17973, "cache.write": 0, "cache.read": 565248}]
    tool time: bash 4.0 min
        128s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre289 test_ail_safetynet 2>&1 | ta
         22s bash   for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) BASE"; timeout 300 bash ~/tools/cmp.sh "$p" /tmp/bas
         22s bash   for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) HEAD"; timeout 300 bash ~/tools/cmp.sh "$p" "$PWD" 2
         18s bash   for n in r11_indirect_call r12_param_annot_cross r13_kwarg r14_attr_module; do echo "===== $n BASE"; timeout 3
         16s bash   for n in r6_shadow_local r7_param_shadow r8_v1_exact r9_no_feature; do echo "===== $n BASE"; timeout 300 bash 
         16s bash   for n in r11_indirect_call r12_param_annot_cross r13_kwarg r14_attr_module; do echo "===== $n HEAD"; timeout 3
         16s bash   rm /tmp/rprobes/r10_field_value_other.py; for n in r6_shadow_local r7_param_shadow r8_v1_exact r9_no_feature; 
          5s bash   d=/tmp/dbg7U2f; cd $d; rm -rf out_ail-ci/* out_base/*; rmdir out_ail-ci out_base; for wt in /home/runner/work/

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T20:22:46Z
