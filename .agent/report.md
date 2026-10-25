# job job-pre257-10260536  started 2026-10-25T20:47:56Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":488,"duration_api_ms":359,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":500,"duration_api_ms":371,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `0fd7afd` — `Fix closure over an outer local callable`.

- Fixed both causes: tuple-pass lambda alias removal inside nested scopes, and `_call_name` preferring module functions/builtins over captured `free_names`/`ptr_names`.
- Added `AIL_CURRENT/test_ail_pre257.py`; updated `DEVLOG.md`, `DIFFERENCES.md`, manifest.
- Passed `test_ail_pre257`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on the final tree; earlier targeted `test_ail_tuples`, `test_ail_nested_functions`, `test_ail_pre165`, `test_ail_pre127`, `test_ail_builtin_shadowing` also passed.
- Still separate pre-existing differences, not addressed: `import_shadow` and ordinary lambda-assignment shadow (`shadow_assign`).
[cost $0.0000, opencode tokens {"total": 9284082, "input": 259056, "output": 18308, "reasoning": 27262, "cache.write": 0, "cache.read": 8979456}]
    tool time: bash 12.9 min
        405s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre257 test_ail_pre165 test_ail_pre127 test_ail_
        213s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre257 test_ail_safetynet test_ail_files test_ai
         50s bash   cat > /tmp/probes/p257_local_callable_module_def.py <<'EOF' def f():     return 1  def outer():     def inner(
         44s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre257 2>&1 | tail -30
         15s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p11a.py <<'EOF' def f():     return 1  def outer():     def inner():
         15s bash   for p in p11a p11b p11c p11d; do echo ==== $p; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD; done
          9s bash   cat > /tmp/probes/p257_unbound_call_before_assign.py <<'EOF' def f():     return 1  def outer():     def inner
          3s bash   bash ~/tools/cmp.sh /tmp/probes/p257_import_shadow.py $PWD

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** leaves `name = lambda ...` as written when `name` is loaded inside a nested `def`/lambda (tuple pass), and makes the general `_call_name` prefer captured `free_names`/`ptr_names` over module functions/builtins. This matches the report.

**Probes** (`cmp.sh`, both builds unless noted):
- Fixed: `a_p11` 101 (base 1); `b_rebind` `(2, 3)` (base `(1, 1)`); `c_builtin`, `d_arg`, `g_loop`, `i_param_shadow`, `j_comp`, `k_nesteddef`, `l_return_capture`, `m_comp_after`, `o_module_lambda`, `s_nonlocal_param`, `t_nonlocal_attr`, `u_key`, `w_nested_lambda_loop`, `x_dict_value`, `y_escape`, `z_class`, `ae_global_inner`, `ag_global_inner_builtin`, `ac_noncallable`, `ad_wrongargs` all match CPython.
- Named refusals (acceptable): `f_ptr_nonlocal`, `q_nonlocal`, `r_nonlocal_builtin`, `n_kwargs` (base returned wrong `1`), `ab_star`, `h_classbody`.
- Control C: a plain program's `program.c` is byte-identical between base and HEAD on both paths.

**Pre-existing** (identical on base, so not blocking): `global f` in outer then nested call `1` vs `101`; ordinary lambda shadow prints `1` vs `UnboundLocalError`; imported `sqrt` shadow `4.0` vs `101`; two-level capture gives `1`/`(1,1)` instead of `101`/`(2,3)`; outer-parameter plus inner `global f` compiler `KeyError` crash.

**Tests:** `test_ail_pre257` 43.3s, `test_ail_safetynet` 104.6s, `test_ail_files` 105.2s, `test_ail_corpus_findings3` 166.8s — all ok. `update_manifest.py --check` rc 0; commit has the required `Co-Authored-By`.

**Report claims:** fix, records, manifest, four required tests and the two remaining pre-existing differences verified. Earlier targeted modules and speed/icount were not re-checked (unverified); the change is not a speed task and non-feature C is unchanged.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1517513, "input": 62156, "output": 7447, "reasoning": 23526, "cache.write": 0, "cache.read": 1424384}]
    tool time: bash 6.2 min
        168s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
        106s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre257 t
         16s bash   cd /tmp/rprobes; printf '%s\n' a_p11 b_rebind f_ptr_nonlocal n_kwargs p_global q_nonlocal r_nonlocal_builtin |
         12s bash   cd /tmp/rprobes; printf '%s\n' i_param_shadow j_comp k_nesteddef l_return_capture m_comp_after n_kwargs o_modu
          9s bash   cd /tmp/rprobes; for p in a_p11 b_rebind c_builtin d_arg e_delete f_ptr_nonlocal g_loop h_classbody; do (bash 
          8s bash   cd /tmp/rprobes; printf '%s\n' ah_transitive ai_transitive_after aj_transitive_rebind | xargs -P2 -I{} bash -c
          8s bash   cd /tmp/rprobes cat > u_key.py <<'EOF' def outer():     f = lambda x: -x     def g():         return f(1)     
          7s bash   cd /tmp/rprobes cat > ac_noncallable.py <<'EOF' def f():     return 1  def outer():     def inner():         r

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T22:36:27Z
