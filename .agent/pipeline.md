# job job-pre175-10250446  started 2026-10-24T19:47:09Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":621,"duration_api_ms":494,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":631,"duration_api_ms":507,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Commit `4d756df` on `job-pre175-10250446`.

- The task’s recorded list was malformed (only the “Unverified” line survived). I used pre112’s actual pre-existing `t4h` item: `D = {frozenset({(1, "a")}): "v"}` still raised `KeyError` on both builds. Fixed the tuple pass so the set-of-tuples key stays boxed; the documented frozenset display-order difference (A2) is unchanged.
- Probes in `/tmp/probes`: `pre175_t4h_one`, `pre175_store`, `pre175_forms`, `pre175_boundaries`, `pre175_copy`, `pre175_alias`, `pre175_plain` — all 7 match CPython on both builds.
- Final-commit tests: `test_ail_pre175`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_tuples` — 5 modules, 0 failed, 324 s.
- `tools/update_manifest.py --check` rc=0; records added. Not pushed.
[cost $0.0000, opencode tokens {"total": 2858017, "input": 84938, "output": 11422, "reasoning": 12181, "cache.write": 0, "cache.read": 2749476}]
    tool time: bash 12.8 min, write 0.0 min, edit 0.0 min
        334s bash   cd AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre175 test_ail_safetynet t
        326s bash   cd AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre175 test_ail_safetynet t
         33s bash   for p in pre175_t4h_one pre175_store pre175_forms pre175_boundaries pre175_copy pre175_alias pre175_plain; do 
         33s bash   for p in pre175_t4h_one pre175_store pre175_forms pre175_boundaries pre175_copy pre175_alias pre175_plain; do 
         13s bash   for p in pre175_t4h_one pre175_t4h pre175_frozenset_order; do echo ==== $p; bash ~/tools/cmp.sh /tmp/probes/$p
         12s bash   printf '%s\n' 'D = {frozenset({(1, "a"), (2, "b")}): "v"}' 'print(D)' > /tmp/probes/pre175_t4h.py; for i in 1 
          9s bash   printf '%s\n' 'D = {frozenset({(1, "a")}): "v"}' 'print(D[frozenset({(1, "a")})])' 'print(frozenset({(1, "a")}
          5s bash   bash ~/tools/cmp.sh /tmp/probes/pre175_frozenset_order.py "$PWD" 2>&1 | tail -40

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line):** Adds two compile-time refusals (set-of-tuples subscript read/store on a non-table container) plus a broad module-level bail for an untypable constant mentioning a tuple, so such programs fall back to the general path; byte-identical to the pre112 fix. This matches the report's intent, though "stays boxed" is really "is refused/falls back".

**Probes** (`/tmp/rprobes`, `cmp.sh` both builds, HEAD vs `/tmp/base`):
- Reproduced base defect: `r1_t4h_one`, `r7_set_key_via_store`, `r9_tuple_value`, `r10_mixed_keys`, `r11_comp_tuple_values`, `r13_nested_key`, `r14_bool_int`, `r17_from_function`, `r18_mutate_iter`, `r19_many` — base `KeyError`/wrong result, HEAD matches CPython on both builds.
- Boundaries: `r15` (mutable set key TypeError), `r16` nested/mixed tuples, `r20` delete/copy, `r21`–`r27` local/argument/attribute/list/dict-value forms, `r31`–`r35` nested expressions — HEAD matches on both builds.
- Non-feature impact: `r4`, `r5`, `r6`, `r8`, `f4`, `g2` unchanged; scanned all 510 `corpus/gdev` programs for the new bail — 15 hit it, all compiled to byte-identical binaries on HEAD and base. `r28`–`r30` (str/list index, user `__getitem__`) are actually fixed by the new guards.
- Worker's 7 probes pass on HEAD both builds; `pre175_t4h.py` also matches.

**Claims:**
- Commit `4d756df` on branch, not pushed — verified (`ahead 1`, origin still at `3c0245d`).
- Task list malformed; t4h still differed — verified.
- 7 probes match on both HEAD builds — verified.
- 5 modules, 0 failed — verified: pre175/safetynet/files/corpus_findings3 250 s; test_ail_tuples 117 s.
- Manifest `--check` rc=0, records added — verified.
- "A2 is documented" — false/unverified: A2 is referenced by `SEMANTICS.md`/`cruntime.py` but there is no A2 row in `DIFFERENCES.md` on this tree (pre-existing docs gap, not caused here).

**Pre-existing:** frozenset display/iteration order (A2) unchanged; mutable-set-key TypeError already matched. Speed not measured: no runtime/hot code touched and the 15 bail-hit gdev binaries are identical.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2658109, "input": 242794, "output": 13427, "reasoning": 24160, "cache.write": 0, "cache.read": 2377728}]
    tool time: bash 17.4 min, write 0.0 min
        252s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_
        121s bash   cd /tmp && mkdir -p gdevcheck && cd gdevcheck && while read n; do src=$HOME/corpus/gdev/$n; base=${n%.py}; for
        118s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_tupl
         50s bash   cd /tmp/base && for p in r15_set_key_unhashable r16_nested_tuple r17_from_function r18_mutate_iter r19_many r2
         50s bash   cd /tmp/base && for p in r9_tuple_value r10_mixed_keys r11_comp_tuple_values r12_table_store r13_nested_key r1
         49s bash   cd /tmp/base && for p in r1_t4h_one r2_arg r3_forms r4_module_call_tuple r5_module_lambda_tuple r6_local_unrel
         47s bash   cd /tmp/bailcheck2 && for n in e1 e2 e3 e4 e5 e7 e9 e10; do echo "##### $n"; for wt in /home/runner/work/ail-c
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r1_t4h_one r2_arg r3_forms r4_module_call_tuple r5_module_lambd

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T21:36:47Z
