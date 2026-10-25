# job job-pre217-10252305  started 2026-10-25T14:15:13Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":412,"duration_api_ms":290,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":412,"duration_api_ms":285,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `b065c16` on `job-pre217-10252305` (no push).

**Fix:** direct calls now honour a parameter/local/cell/closure binding that shadows a module function, so calls before assignment raise `UnboundLocalError` and calls after `side = None` raise `TypeError`. The typed path refuses the shape by name and falls back to the general path.

**Verification (final commit):**
- 8 modules, 0 failed: `pre217`, `pre165`, `unbound`, `optional_locals`, `nested_functions`, `safetynet`, `files`, `corpus_findings3`.
- Probes: 14 match CPython on both builds; 4 refused by name (`p_shadow_default`, `p_shadow_keyword`, `p_shadow_nonlocal`, `p_shadow_through_values`).
- `update_manifest.py --check` rc=0; `ci_shards.py --check` rc=0.

DIFFERENCES row `C?-job-pre217-10252305-1` and DEVLOG entry added.
[cost $0.0000, opencode tokens {"total": 11946226, "input": 330950, "output": 23626, "reasoning": 36962, "cache.write": 0, "cache.read": 11554688}]
    tool time: bash 14.6 min
        497s bash   cd AIL_CURRENT && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre217 test_ail_pre165 test_ail_unb
         64s bash   for p in /tmp/probes/p_shadow_*.py; do printf '%-32s ' "$(basename $p)"; out=$(timeout 300 bash ~/tools/cmp.sh
         63s bash   cat > /tmp/probes/p_shadow_alias.py <<'EOF' def side(x):     return x   def twice(x):     return x * 2   def m
         54s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre217 2>&1 | tail -50
         54s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old="
         35s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old="
         34s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old="
         26s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_shadow_call.py <<'EOF' def side(x):     return x   def main():    

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does (matches report):** `_call_name` now routes a direct call of a module-function name that is also a parameter/local/cell/closure/free binding through `call_value`; `expr_Name`'s function-value path excludes those bindings; the typed path refuses such calls by name and skips optional-`None` lowering when the name is called.

**Verified**
- `test_ail_pre217` + `test_ail_safetynet`: `ok`, 0 failed (61.6s / 126.1s).
- Worker's 14 `p_shadow_*` probes: match CPython on both builds; the 4 named refusals build-refuse as claimed.
- `update_manifest.py --check` rc=0; `ci_shards.py --check` rc=0; DIFFERENCES/DEVLOG rows present.
- General/typed fix works for plain functions, parameters, aliases, list/dict/attr values, loop/except targets, builtins, classes, non-callables, nested/local unbound cases (my `r1–r26`).
- No-feature C unchanged: `program.c` identical HEAD vs `/tmp/base` for `hello.ail`, a closure program and a call-heavy program.

**Defects introduced by the change**
1. `/tmp/rprobes/p37_local_method.py` — `side = "ab".upper; print(side())`. CPython prints `AB` (exit 0). HEAD builds and exits 1 with `AttributeError: 'str' object has no attribute 'upper'` on both builds. Base refused at compile time by name (`not in the subset: side() called without a required argument x`), which is acceptable; the change replaced an acceptable refusal with a runtime error. Same root in `p40_list_method.py` (`side = ["ab".upper][0]`) and `p41_attr_method_shadow.py` (bound method via attribute).
2. `/tmp/rprobes/p42_callable_instance.py` — `side = C(); print(side(2))`. CPython prints `3` (exit 0). Base printed `2` (already wrong, but no crash); HEAD exits 1 with `TypeError: 'instance' object is not callable` on both builds. The change caused a crash where the base at least produced output; `call_value` only supports `AIL_T_FUNC` values.

Expected for both: CPython result, or a named compile-time refusal; not a runtime error.

**Pre-existing (identical on `/tmp/base`, not blocking)**
- `r3_module_shadow.py` / `p09_module_rebind.py`: module-level rebinding of a module function is still ignored (`102` expected, `2`).
- `p18_star_shadow.py`: call through a shadowing local with `*args` still uses the module function (`11` expected, `1`).
- `p32_global_closure_rebind.py`: global rebind through a closure still stale.
- `p38_plain_method_value.py`, `p39_user_method_shadow.py`: method-value calls already runtime-error on base.

**Unverified:** the other 6 worker test modules; CI shard timing; instruction counts (only compile-time paths changed, generated C identical for non-feature programs).

VERDICT: FIX
1. Method values in a shadowing local turn a named compile refusal into a runtime `AttributeError` (`p37`, `p40`, `p41`).
2. Callable instances in a shadowing local turn output into a runtime `TypeError` (`p42`).
[cost $0.0259, opencode tokens {"total": 1396463, "input": 52432, "output": 7929, "reasoning": 15526, "cache.write": 0, "cache.read": 1320576}]
    tool time: bash 11.4 min
        220s bash   cd /tmp/rprobes && date && for p in p*.py; do b=${p%.py}; out=$(timeout 300 bash ~/tools/cmp.sh $p /home/runne
        128s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         52s bash   cd /tmp/rprobes && for p in p09_module_rebind p18_star_shadow p32_global_closure_rebind p37_local_method p38_p
         52s bash   cd /tmp/probes && date && for p in p_shadow_after_assign p_shadow_alias p_shadow_attr p_shadow_call p_shadow_d
         35s bash   cd /tmp/rprobes && for v in '"abc"' '7' '[1,2]' 'True' '1.5'; do n=$(echo "$v"|tr -cd 'a-z0-9'); cat > r22_non
         31s bash   cd /tmp/rprobes && for p in p39_user_method_shadow p40_list_method_shadow p41_attr_method_shadow; do echo "===
         26s bash   cd /tmp/rprobes && for p in r1_nested_shadow r2_nested_unbound r3_module_shadow r4_loop_after r5_except_types 
         23s bash   cd /tmp/rprobes && cat > r15_nested_same_optional.py <<'EOF' def side(x):     return x  def main():     side =

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0434, opencode tokens {"total": 3101902, "input": 118202, "output": 8264, "reasoning": 19788, "cache.write": 0, "cache.read": 2955648}]
    tool time: bash 4.7 min
        126s bash   cd /tmp/probes && for p in p_method_value_*.py p_callable_instance_*.py p_shadow_*.py; do echo "==== $p"; time
        117s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre217 test_ail_safetynet 2>&1 | ta
         17s bash   cd /tmp/probes && for p in p_shadow_keyword.py p_shadow_nonlocal.py p_shadow_through_values.py p_shadow_defaul
         11s bash   cd /tmp/rprobes && for f in p37_local_method.py p40_list_method.py p41_attr_method_shadow.py p42_callable_inst
         11s bash   cd /tmp/rprobes && for f in p37_local_method.py p41_attr_method_shadow.py p42_callable_instance.py; do echo ==
          0s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre217 test_ail_safetynet 2>&1 | ta
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -10 && git diff --stat
          0s bash   cd AIL_CURRENT && grep -nP '(?<![.\w])([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)(?!\s*\()' test_ail_*.py | grep -vE '\.(py
(cut off after 60 minutes)

## review 1 failed to run: [cost $0.0000, opencode tokens {}]     tool time:  (cut off after 60 minutes) 

## review 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-25T18:20:49Z
