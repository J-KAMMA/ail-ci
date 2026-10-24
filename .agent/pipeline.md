# job job-pre170-10250443  started 2026-10-24T19:43:26Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":435,"duration_api_ms":316,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":389,"duration_api_ms":273,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Commit `b122d0f` on `job-pre170-10250443`.

**Found:** `test_ail_files` and `test_ail_corpus_findings3` passed unchanged; speed was not measurable here; the remaining `b_dup`/`g_dup2` case still differed. Fixed duplicate class-body attributes read through a class value so the last definition wins, including aliases, arguments, containers, `getattr`/`hasattr`, array-entry programs, and class-name shadowing/rebinding without regressions. DIFFERENCES row `C?-job-pre170-10250443-1`, DEVLOG updated, manifest check passes.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- `p_dup`, `p_dup2`, `p_sources`, `p_missing`, `p_shadow_local`, `p_rebind_mod`, `p_rebind_glob`, `p_shadow`: match CPython.
- `cv_method`: compile-time refusal by name (`reading method C.m through a class value`).
- `p_method`: named runtime `NotImplementedError` for a dynamically reached method (refused by name).
- Pre-existing `cv_exc_attr` / `cv_args_attr` differences remain identical on base; not fixed.

**Tests on final commit:** `test_ail_pre170`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
[cost $0.0867, opencode tokens {"total": 7544463, "input": 238978, "output": 15123, "reasoning": 33274, "cache.write": 0, "cache.read": 7257088}]
    tool time: bash 14.4 min, edit 0.0 min, write 0.0 min
        228s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre170 test_ail_safetynet test_ail_files test_ai
        145s bash   python3 AIL_CURRENT/test_ail_corpus_findings3.py > /tmp/cf3.log 2>&1; echo "exit $?"; tail -80 /tmp/cf3.log
         95s bash   python3 AIL_CURRENT/test_ail_files.py > /tmp/files.log 2>&1; echo "exit $?"; tail -60 /tmp/files.log
         93s bash   git add AIL_CURRENT/test_ail_pre170.py AIL_CURRENT/python/pkg-v12/pyboxed2.py && python3 tools/update_manifest
         88s bash   git add AIL_CURRENT/test_ail_pre170.py && python3 tools/update_manifest.py >/tmp/manifest3.log 2>&1 && python3
         83s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre170 test_ail_safetynet > /tmp/pre170.log 2>&1
         35s bash   { for p in p_dup p_dup2 p_sources p_missing cv_method p_method; do echo "########## HEAD $p"; bash ~/tools/cmp
         26s bash   cd /tmp/probes; for p in p_shadow_local p_rebind_mod p_rebind_glob p_shadow p_dup p_dup2 p_sources p_missing; 

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Registers every class-body entry in source order on the class object and adds runtime class-value attribute lookup (aliases/args/containers, `getattr`/`hasattr`), initialises class bodies in the array-entry shape, and routes class names that are rebound through module slots. This matches the report; it is broader than “duplicate attribute” but consistent with it.

**Probes (`bash ~/tools/cmp.sh`, both builds, HEAD vs `/tmp/base`):**
- `p_rebind`, `p_order3`, `p_values`, `p_shared`, `p_side`, `p_shadowbase`, `p_ann`, `p_mixed`, `p_exc`, `p_clsm`: HEAD matches CPython; base fails on class-value reads.
- `p_array2` (array-entry, extra arg): `3 2 5 7 9` on both builds.
- `p_cvm`: compile-time refusal `reading method C.m through a class value`.
- `p_rm2` (dynamic name): named runtime `NotImplementedError`; base also refused.
- `p_dunder2`: direct `C.__name__` with a class-body `__name__` assignment prints `x` (CPython `C`) — identical on base.
- `p_predef`, `p_update`, `p_dc`, `p_selfref`, `p_getattr2`: differ from CPython on HEAD, but the same constructs already fail on base (pre-existing class assignment/handler gaps).
- `p_nofeature`: stdout matches; general-path C differs only by the new shared preamble and one unconditional `ail__class_attr_slots = g_slots_arr;` line, no emitted-logic change.

**Tests:** `test_ail_pre170`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed on HEAD. Manifest `--check` passes; DIFFERENCES/DEVLOG entries are present and correctly dated.

**Claims:** verified — duplicate/alias/container/getattr/hasattr/array-entry behaviour, shadow/rebind handling, compile-time method refusal, named dynamic refusal, tests and manifest. Unverified — the exact pre157 `b_dup`/`g_dup2` and worker `p_*` probe files are absent (equivalents were probed), and instruction counts (perf_event_open denied: `Permission denied`).

**Pre-existing (not caused by this change):** direct `C.__name__` class-body override; class attribute writes (`C.x = ...`); class-body self-reference; dataclass class attributes; class name assigned before its `class` definition; compile-time `getattr` of any method name.

VERDICT: ACCEPT
[cost $0.0831, opencode tokens {"total": 5560971, "input": 210828, "output": 11030, "reasoning": 48233, "cache.write": 0, "cache.read": 5290880}]
    tool time: bash 6.0 min
        136s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings
         83s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre170 test_ail_safetynet > /t
         16s bash   cat > /tmp/rprobes/p_rebind.py <<'EOF' class C:     x = 1  print(C.x) C = 5 print(C) try:     print(C.x) excep
         11s bash   cat > /tmp/rprobes/p_getattr2.py <<'EOF' class B:     v = 'base'  class C(B):     v = 'sub'     w = 0  print(g
          9s bash   echo BASE; bash ~/tools/cmp.sh /tmp/rprobes/p_dc.py /tmp/base 2>&1 | tail -14; cat > /tmp/rprobes/p_dc2.py <<'
          9s bash   for p in p_update p_dunder p_rebind; do echo "########## BASE $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp
          7s bash   cat > /tmp/rprobes/p_classcall.py <<'EOF' class C:     def m(self):         return 1      @classmethod     def
          6s bash   sed -i "s/    c = 10 \*\* 30/    c = 1000/" /tmp/rprobes/p_values.py && bash ~/tools/cmp.sh /tmp/rprobes/p_val

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T21:09:52Z
