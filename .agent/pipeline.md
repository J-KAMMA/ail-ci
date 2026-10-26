# job job-pre296-10270440  started 2026-10-26T19:41:29Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":321,"duration_api_ms":203,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":298,"duration_api_ms":168,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `7b44633` on `job-pre296-10270440`.

**Fixed (first pre-existing from rbpre54):** a local parameter/local named `round` was ignored, so `def apply(round, x): return round(x)` printed `-6`/`int` where CPython prints `-16.5`/`float` on both builds. The general path now reads the activation binding before builtin dispatch; the typed path refuses the call by name and falls back. Covers parameter, local, closure, list item, attribute and dict value; non-callable keeps `TypeError`; unshadowed `round` unchanged.

**Probes** (`/tmp/probes/p296_*`, both builds):
- Match CPython: `param`, `local`, `closure`, `routes`, `callable_param`, `noncallable`, `unshadowed`, `len_local`, `len_param`, `abs_local`, `no_feature`.
- Refused by name: `builtin_value` (passing the builtin `round` as a value; pre-existing gap).
- Remaining pre-existing edge, not the target: a lambda assigned after an unbound call is dropped by a separate scan, so `unbound` still differs on both builds; `unbound_none` now matches on the general build but the default build still inlines it.

**Tests on final commit:** `test_ail_pre296`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing`, `test_ail_pre218` — 6 modules, 271s, 0 failed. `update_manifest.py --check` exits 0.
[cost $0.0642, opencode tokens {"total": 7286678, "input": 158354, "output": 12742, "reasoning": 19262, "cache.write": 0, "cache.read": 7096320}]
    tool time: bash 7.4 min, edit 0.0 min
        273s bash   python3 tools/update_manifest.py --check && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre2
         69s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre296 test_ail_builtin_shadowing test_ail_pre21
         52s bash   cat > /tmp/probes/p296_param.py <<'EOF' def apply(round, x):     return round(x)  print(apply(lambda v: v * 3,
         17s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p296_shadow_param.py <<'EOF' def apply(round, x):     return round(x
         14s bash   cat > /tmp/probes/p296_unbound_none.py <<'EOF' def f(x):     round(x)     round = None  try:     f(-5.5) excep
         11s bash   cat > /tmp/probes/p296_len_local.py <<'EOF' def f(xs):     len = lambda v: 99     return len(xs)  print(f([1, 
          3s bash   bash ~/tools/cmp.sh /tmp/probes/p296_unbound.py "$PWD" 2>&1 | tail -20
          2s bash   mkdir -p /tmp/p296dbg && cd /tmp/p296dbg && cp /tmp/probes/p296_unbound.py p.ail && AIL_NO_CACHE=1 AIL_UNIFIED

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the diff does.** `pyboxed2._call_name` now checks `ctx.slot_of/ptr_names/clo_index/free_names/cell_slots` before builtin dispatch and calls the activation's own value; `pyfunc._call` refuses (named `Unsupported`) a call through a local that shadows a `PY_BUILTINS` name so the default build falls back. It also adds `test_ail_pre296.py`, registration, DIFFERENCES row, DEVLOG, and manifest pin. This matches the report.

**Probes** (all `cmp.sh`, both builds; sources in `/tmp/rprobes`):
- `r1_round_routes` (argument/list/attr/dict/default-kw lambda): both match CPython; base printed `-6`. Fixed.
- `r2_more_builtins` (`len,abs,max,min,sum,sorted` params/locals), `r3_type_ctors` (`int,str,type,format,bool`), `r4_print_shadow`, `r9/r25/r26/r27` (comprehension, lambda arg, nested def, method), `r34` (int/bool/negative-zero args), `r17` (import alias), `r18` (attribute method), `r19` (reassignment), `r22` (default param), `r23/r24` (statement calls): all match.
- `r12/r37` comprehension target named `round`/`len`: match; C for `r13/r14` byte-identical to base.
- `r6_noncallable`, `r29_len_noncallable`: exact CPython `TypeError` text matches.
- `r10_builtin_as_value`: refused both builds; `r15` kwargs through a local value: refused both (base refused differently).
- `r5_unbound`: both builds silent vs CPython `UnboundLocalError`; identical on base.
- `r11_no_feature` and `r13/r14`: `--debug-dir` `program.c` byte-identical to base.
- `r30` local `isinstance(x, int)`: HEAD refuses `name 'int' is not defined`, CPython prints `False`, base printed `True`; acceptable refusal (type object as a value is a pre-existing limitation), but the message is incidental.
- `r33` class-body `round = lambda...`: both HEAD and base print `-6` vs CPython `-16.5` (pre-existing, different scope, not the target).

**Tests on HEAD:** `test_ail_pre296` ok 30.9s, `test_ail_safetynet` ok 98.1s, `test_ail_builtin_shadowing` ok 16.0s, `test_ail_files` ok 107.5s, `test_ail_corpus_findings3` ok 167.1s. `update_manifest.py --check` exits 0.

**Claims:** Verified: general-path shadow read, typed refusal/fallback, parameter/local/closure/list/attr/dict coverage, non-callable `TypeError`, unshadowed `round` unchanged, unbound-lambda remains on both builds, `unbound_none` general matches/default inlines. Unverified: the "first pre-existing from rbpre54" ordering — `.agent/task.md` contains no list. I did confirm the `round`-parameter difference on both `work` and `origin/rbpre54`, so it is genuinely pre-existing and now fixed. The exact "271s" was not reproduced.

**Pre-existing (not blocking):** class-body local shadow (`r33`), unbound lambda after a call (`r5`), builtin `round` as a value (`r10`), and local `isinstance` with a builtin-type argument (`r30`, now an incidental-but-acceptable refusal).

**Unverified:** wider suite, other platforms, compile-time cost, exact item ordering in the missing rbpre54 list.

VERDICT: ACCEPT
[cost $0.0428, opencode tokens {"total": 2086804, "input": 77461, "output": 9659, "reasoning": 32452, "cache.write": 0, "cache.read": 1967232}]
    tool time: bash 9.5 min
        169s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
        100s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         48s bash   date; for p in /tmp/probes/p296_param.py /tmp/probes/p296_local.py /tmp/probes/p296_closure.py /tmp/probes/p29
         41s bash   date; for p in /tmp/rprobes/r*.py; do echo "########## $p"; timeout 300 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 |
         32s bash   cat > /tmp/rprobes/r12_comp_target.py <<'EOF' def f(xs):     ys = [round for round in xs]     return round(2.5
         23s bash   date; for p in /tmp/rprobes/r1_round_routes.py /tmp/rprobes/r2_more_builtins.py /tmp/rprobes/r4_print_shadow.p
         21s bash   cat > /tmp/rprobes/r30_isinstance_annotated.py <<'EOF' def f(isinstance, x: int) -> bool:     return isinstanc
         18s bash   cat > /tmp/rprobes/r25_lambda_param.py <<'EOF' print((lambda round, x: round(x))(lambda v: v * 3, -5.5)) EOF c

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T21:15:59Z
