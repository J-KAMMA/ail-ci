# job job-pre395-10281000  started 2026-10-28T01:05:51Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"f4a92e26-6632-4628-8a55-403315c4e908","session_id":"27a11ab2-3bfe-415e-8e3e-126c0a4c6f16"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"92210b71-23df-49b9-9c9a-cc663ae711dd","session_id":"16d5a264-d8e5-4c62-92c7-b970e1705c44"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing item: class-object subscription now says `type 'A' is not subscriptable` on both builds.

- Code: `ail_op_getitem`/`ail_op_getslice` in `cruntime.py` now name the class; dunderrt patches still apply.
- Commit: `dbb336d` on `job-pre395-10281000`.
- Probes (`/tmp/probes/pre395`, both builds): `p01_direct`, `p02_routes`, `p03_dunderpatch` match CPython; original `class_sub.py` matches. `p04_exc.py` still differs as recorded (exception subclass, not fixed).
- Exploratory, unchanged: plain `A()[0]` still says `'instance'`; `del A[0]` says `doesn't support` vs CPython `does not support`.
- Tests: `test_ail_pre395`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 308 s, 0 failed.
- `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 4545519, "input": 1442675, "output": 11024, "reasoning": 14572, "cache.write": 0, "cache.read": 3077248}]
    tool time: bash 6.4 min, edit 0.0 min
        310s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre395 test_ail_safetynet test_ail_files test_ai
         21s bash   mkdir -p /tmp/probes/pre395 && cat > /tmp/probes/pre395/p01_direct.py <<'EOF' class A:     pass   class B(A): 
         16s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre395 2>&1 | tail -20
         13s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre395 2>&1 | tail -30
          9s bash   mkdir -p /tmp/probes/pre395 && cat > /tmp/probes/pre395/class_sub.py <<'EOF' class A:     pass print(A[0]) EOF
          8s bash   bash ~/tools/cmp.sh /tmp/probes/pre395/class_sub.py "$PWD"; echo ====; bash ~/tools/cmp.sh /tmp/probes/pre395/
          4s bash   mkdir -p /tmp/dbg395 && cp /tmp/probes/pre395/class_sub.py /tmp/dbg395/p.py && cd /tmp/dbg395 && AIL_UNIFIED_F
          4s bash   cat > /tmp/probes/pre395/tmp_inst.py <<'EOF' class A: pass try:     print(A()[0]) except TypeError as e:     p

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete. No source edits or commits made.

**What the change does:** Adds a v2-runtime helper `ail__raise_class_not_subscriptable` and routes `AIL_T_CLASS` in `ail_op_getitem`/`ail_op_getslice` to it, so `A[0]`/`A[1:2]` now say `type '<name>' is not subscriptable`; plus test/docs/manifest/shard registration.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs `/tmp/base`; both g and d builds):
- `p01_index` (int/neg/wide/bool/None/float/str/empty/tuple keys, slices, alias, subclass): HEAD matches CPython both builds; base differs. 
- `p02_routes` (argument, list item, dict value, attribute, return, slices): HEAD matches; base differs. 
- `p05_longnames` (127/128/200-char names): HEAD matches (stack+heap paths); base differs. 
- `p07_dunder` (`__getitem__`/`__add__` dunderrt patch active; instance, class, B): HEAD matches. 
- `p09_slicezero`, `p13_literal_slicezero` (slice step 0): HEAD matches. 
- `p10_initclass`, `p11_init_nocatch`, `p12_general_nofeature`: HEAD matches (no-feature general program unaffected). 
- `p04_unicode`: refused by name on both (non-ASCII not in subset) — acceptable. 
- `p03e_user`: `E[0]`, `E[1:2]` fixed; `E()[0]` still `'exception'` vs CPython `'E'` on both. 
- `p06a_classgetitem`: class with `__class_getitem__` still errors (`type 'A' ...`) vs CPython `('got', 0)` on both (base: `'type' ...`). 
- `p08_inst_del`: `A()[0]` `'instance'` vs `'A'`; `del A[0]` `doesn't` vs `does not` on both; assignment matches. 
- Non-feature typed program: `--debug-dir program.c` byte-identical HEAD vs base; only report paths differ.

**Report claims:** fixed message on both builds — verified; getitem/getslice + dunderrt patch — verified; commit dbb336d — verified; p04_exc still differs — verified; `A()[0]`/`del` unchanged — verified; `test_ail_pre395`+`test_ail_safetynet` green — verified (2 modules, 0 failed, 109s); `update_manifest.py --check` — verified. `test_ail_files`/`test_ail_corpus_findings3` — unverified (not re-run per review scope). Message copy/free is safe: `ail_raise_c` copies via `ail_str_from_cstr` before `free(msg)`, and the name is read into a plain buffer before any GC allocation.

**Pre-existing (identical on base):** `E()[0]` → `'exception'`; `A()[0]` → `'instance'`; `del A[0]` → `doesn't support`; `__class_getitem__`/metaclass subscription unsupported; non-ASCII identifiers refused by name; builtin classes not first-class; `AIL_GENERAL=v1` cannot build classes.

**Speed:** not measured — `perf_event_open` is permission-denied here; the added work is a switch case and a branch reached only after all supported slice types return (cold), so no hot-path change expected.

**Unverified:** the two worker test modules above; worker's own `/tmp/probes/pre395` files (used equivalent probes); exact v1-path behavior (v1 cannot build classes).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2422975, "input": 46721, "output": 9329, "reasoning": 31949, "cache.write": 0, "cache.read": 2334976}]
    tool time: bash 3.9 min
        111s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date; python3 ../tools/par_check.py -j 2 test_ail_pre395 tes
         32s bash   cd /tmp/rprobes && cat > p03e_user.py <<'EOF' class E(Exception):     pass   def show(label, c, k):     try:  
         25s bash   date; cd /tmp/rprobes; for p in p01_index p02_routes p03_builtin_exc p04_unicode p05_longnames p06_classgetite
          8s bash   cd /tmp/rprobes && cat > p08_inst_del.py <<'EOF' class A:     pass   def main():     try:         A()[0]     e
          7s bash   cd /tmp/rprobes && cat > p03_builtin_exc.py <<'EOF' def show(label, c, k):     try:         c[k]     except Ty
          7s bash   cd /tmp/rprobes && cat > p03c_exc.py <<'EOF' def show(label, c, k):     try:         c[k]     except TypeError
          7s bash   cd /tmp/rprobes && cat > p10_initclass.py <<'EOF' class A:     def __init__(self, x: int) -> None:         sel
          5s bash   cd /home/runner/work/ail-ci/ail-ci && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icoun

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T02:46:41Z
