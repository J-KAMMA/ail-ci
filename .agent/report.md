# job job-fuzz95-10270015  started 2026-10-26T15:16:07Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":328,"duration_api_ms":197,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":319,"duration_api_ms":194,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `38f0329` on `job-fuzz95-10270015`.

**Fixes**
- `pyfunc.py`: emit `TIMSORTIDX` only when a struct sort key has a float field; restores the pinned C for unrelated struct programs (`test_ail_record_initializers`).
- `cruntime.py`: float `qsort` call uses `L->n`, matching the generated-code assertion in `test_ail_numeric_profiles`.
- `test_ail_numeric_profiles_native.py`: updated the stale `ValueError` expectations to CPython's Timsort NaN order while keeping the NaN-sort coverage.
- `bench/compare.py`: ported the `fmt` upper-bound fix for `test_ail_pre110` (that module is absent from this branch, so I verified it with the integration test: 7/7 pass).

**Verification**
- Final commit: `par_check.py -j 2` ran 14 modules (9 listed available + `fuzz95`, `int_sort`, `safetynet`, `files`, `corpus_findings3`): **14/14 pass**.
- Probes: `p_nan_direct`, `p_nan_routes`, `p_nan_key`, `p_nan_nested`, `p_nan_alias`, `p_nan_struct`, `p_no_sort` — all same stdout as CPython on both builds.
- Extra struct probe: float-key sort with NaN emitted `TIMSORTIDX` and matched CPython; int-key and no-sort structs omitted it.
- `update_manifest.py --check` passes. No push.
[cost $0.0669, opencode tokens {"total": 6737948, "input": 121529, "output": 18490, "reasoning": 29865, "cache.write": 0, "cache.read": 6568064}]
    tool time: bash 12.9 min, edit 0.0 min
        409s bash   cd AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_grid_return test_ail_numeric_bindin
        238s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_grid_return test_ail_numeric_bindin
         41s bash   cd /tmp/merged/AIL_CURRENT && printf '%s\n' test_ail_grid_return test_ail_numeric_bindings test_ail_numeric_pr
         32s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "===== $(basename $p) ====="; bash ~/
         15s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_fuzz95 2>&1 | tail -20
          8s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_numeric_profiles_native 2>&1 | tail -40
          7s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_grid_return 2>&1 | tail -40
          4s bash   cd /tmp/merged/AIL_CURRENT && AIL_NO_CACHE=1 PIPE_CC=$(command -v gcc) AIL_EXTRA_CFLAGS=-Werror=incompatible-p

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Report**

Change really does: gate struct-sort `TIMSORTIDX` emission on a float field appearing in a sort key; change `qsort(..., n, ...)` to the equivalent `L->n`; update `test_ail_numeric_profiles_native` from the old `ValueError` expectation to CPython Timsort NaN order; port `_fmt_bound` from `origin/integ` in `bench/compare.py`. Matches the worker report.

**Probes** (all `cmp.sh`, both builds, all match CPython):
- `p_float_list_nan`, `p_unrelated_ints`, `p_combo` — typed/boxed NaN sorts, unrelated int program.
- `p_struct_float_nan2`, `p_struct_negkey`, `p_struct_float_no_nan` — typed struct float-key sorts incl. NaN, reverse, negative key, tuple key.
- `p_struct_int_sort`, `p_floatfield_intkey`, `p_struct_no_sort` — no float-key sort; TIMSORTIDX correctly absent, output matches.
- `p_method_sort` — sort in a class method; TIMSORTIDX present, matches.
- `p_struct_extra` — argument/general-path cases; matches.

C inspection: unrelated/no-sort struct C differs from `work` only by removal of the `TIMSORTIDX` block; `test_ail_record_initializers` pinned SHA now passes (fails on `/tmp/base`, verified). No changed program needs `ail__timsort_idx` without it being emitted.

**Tests on HEAD**: 11 modules (`9 available listed` + `fuzz95` + `safetynet`) pass; plus `files`, `int_sort`, `corpus_findings3` pass; `sort_keys` passes. `update_manifest.py --check` passes.

**Claims**
- TIMSORTIDX gating / pinned C restored: verified.
- `qsort` `L->n`: verified (same value as `n`).
- Native NaN test update: verified; still checks bit multiset and zero-leak cleanup.
- `bench/compare.py` port: verified equal to `origin/integ`; the claimed 7/7 `test_ail_pre110` integration run is **unverified** — that module is absent here.
- `14/14` pass claim: verified.

Minor: DEVLOG says the Timsort change “broke three modules” while the task listed ten; documentation nit only.

Pre-existing: none observed. Speed: not applicable (no runtime hot-path change).

VERDICT: ACCEPT
[cost $0.0442, opencode tokens {"total": 3748759, "input": 100216, "output": 10625, "reasoning": 19870, "cache.write": 0, "cache.read": 3618048}]
    tool time: bash 8.0 min
        227s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        171s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         20s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_
         12s bash   cat > /tmp/rprobes/p_struct_float_nan.py <<'EOF' class Row:     def __init__(self, k: float, v: int) -> None: 
          9s bash   cd /tmp && rm -rf dbg_head dbg_base dbg_integ && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$
          9s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) ====="; 
          6s bash   cat > /tmp/rprobes/p_struct_extra.py <<'EOF' class Row:     def __init__(self, k: float, v: int) -> None:     
          4s bash   cat > /tmp/rprobes/p_struct_negkey.py <<'EOF' class Row:     def __init__(self, k: float, v: int) -> None:    

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T17:01:48Z
