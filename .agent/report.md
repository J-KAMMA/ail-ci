# job job-pre414-10281317  started 2026-10-28T04:22:25Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"9f2aa602-8212-43b9-ad1c-108ae44f0bbf","session_id":"bb775a8d-6c01-4710-b4fd-d2f57ae1894b"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"b7e23065-ff58-4dea-ba8a-5b6c8775b1e7","session_id":"2b89afbe-b6c1-4742-b999-7072b8ea93c4"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `33ff862` on `job-pre414-10281317`.

The task file’s pre-existing list was blank; from the pre396 review, the first remaining item was the exception-instance name in item errors. `del MyErr()[0]` printed `'exception' object doesn't support item deletion` where CPython prints `'MyErr' ...`. Fixed `ail__tname_c` to use the class-name path for `AIL_T_EXC` as well as `AIL_T_INST` (`AIL_CURRENT/python/pkg-v12/cruntime.py:14815`).

Probes in `/tmp/probes/pre414`, both builds:
- `p_exc_name.py`: differed before, now matches CPython.
- `e_all.py`: deletion with int/bool keys, subclass, alias, argument, list item, attribute, dict value, plus item reads/stores; matches CPython.
- `p_inst_name.py` matches; `p_class_sub.py`, `p_bad_index.py`, `p_raise_index.py` remain separate pre-existing causes and are unchanged.

Added `test_ail_pre414.py`; registered it in `ail_check.MODULES` and `tools/ci_shards.json`; added DEVLOG/DIFFERENCES rows. Final-commit tests: `test_ail_pre414`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 222s. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 4778127, "input": 246433, "output": 9917, "reasoning": 17841, "cache.write": 0, "cache.read": 4503936}]
    tool time: bash 10.0 min, edit 0.0 min, write 0.0 min
        310s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre414 test_ail_safetynet test_ail_files test_ai
        224s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre414 test_ail_safetynet test_ail_files test_ai
         20s bash   cd /tmp/probes/pre414 && for p in p_exc_name.py p_class_sub.py p_bad_index.py p_raise_index.py p_inst_name.py;
          7s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre414 2>&1 | tail -25
          5s bash   cd /tmp/probes/pre414 && python3 - <<'PY' p='e_all.py'; s=open(p).read() s=s.replace("def del_builtin():\n    
          4s bash   cd /tmp/probes/pre414 && bash ~/tools/cmp.sh p_exc_name.py /home/runner/work/ail-ci/ail-ci 2>&1 | grep -E "cpy
          4s bash   cd /tmp/probes/pre414 && cat > e_all.py <<'EOF' class MyErr(Exception):     pass   class Sub(MyErr):     pass 
          4s bash   cd /tmp/probes/pre414 && python3 - <<'PY' p='e_all.py' s=open(p).read() s=s.replace("\n\ndef show(label, fn):\

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** `ail__tname_c` now takes the class-name path for `AIL_T_EXC` as well as `AIL_T_INST`, so error messages about an exception value name its class; plus a new test module and records. The diff matches that description.

**Probes (CPython oracle, both builds)**
- `p_exc_name.py`: base both builds said `'exception'`; HEAD both match CPython (`'MyErr'`).
- `e_all.py`: HEAD both match on del/get/set, int/bool keys, subclass, alias, argument, list item, attribute and dict value.
- `r1_exc_items.py`: all non-slice item routes fixed; `del MyErr()[0:1]` still says `'exception'` on base and HEAD (separate slice helper).
- `r2_exc_ops.py`: additive/concat/iterability/string-index/join/startswith names now match; `%` truncation and comprehension iteration remain wrong on base and HEAD.
- `r3_inst_items.py`, `r5_misc_tname.py`: no new differences versus base; ordinary-instance slice wording and exception attribute names are unchanged pre-existing.
- `r6_exc_names.py`: exception subclass of `OSError` and a 250-character class name now match CPython; non-ASCII class name is refused by name on both.
- `r4_plain.py` (no feature use): `--debug-dir` `program.c` is byte-identical to the base build.

**Claims:** fix, `p_exc_name`, `e_all`, `p_inst_name`, the three unchanged pre-existing probes, test registration, records, and `update_manifest.py --check` are verified. The four-module 222s test claim is partly verified: I reran `test_ail_pre414` and `test_ail_safetynet` (2 modules, 0 failed, 106s); `test_ail_files`/`test_ail_corpus_findings3` were not rerun per reviewer instructions.

**Pre-existing (unchanged on base):** slice deletion on exception/ordinary instances (`does not`/`doesn't` wording and `'exception'` name), attribute errors naming `instance`/`exception`, `%` operand-message truncation, `A[0]` class-subscript wording, bad/raising `__index__` during `del`.

The DEVLOG/DIFFERENCES wording "deletion ... of an item" is too broad for slice deletion, which remains the old behaviour; it is a separate pre-existing path, not caused by this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1224367, "input": 64590, "output": 7615, "reasoning": 13730, "cache.write": 0, "cache.read": 1138432}]
    tool time: bash 4.8 min
        108s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre414 t
         27s bash   cd /tmp/rprobes && python3 - <<'PY' p='r2_exc_ops.py' s=open(p).read() s=s.replace("""def counter():     from 
         26s bash   cd /tmp/rprobes && python3 - <<'PY' import re p='r1_exc_items.py' s=open(p).read() s=s.replace("""def del_vale
         24s bash   cd /tmp/probes/pre414 && for p in p_exc_name.py e_all.py p_inst_name.py p_class_sub.py p_bad_index.py p_raise_
         24s bash   cat > /tmp/rprobes/r1_exc_items.py <<'EOF' class MyErr(Exception):     pass class Sub(MyErr):     pass class H
         22s bash   cd /tmp/rprobes && for p in r1_exc_items.py r2_exc_ops.py r5_misc_tname.py; do echo ==== $p HEAD; bash ~/tools
         20s bash   cd /tmp/rprobes && for p in r1_exc_items.py r2_exc_ops.py r3_inst_items.py r4_plain.py r5_misc_tname.py; do ec
         11s bash   cd /tmp/probes/pre414 && for p in p_class_sub.py p_bad_index.py p_raise_index.py; do echo ==== $p BASE; bash ~

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T06:01:16Z
