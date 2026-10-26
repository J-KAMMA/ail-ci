# job job-rbpre51-10261856  started 2026-10-26T10:08:37Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":522,"duration_api_ms":404,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":545,"duration_api_ms":428,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `15815fd` on `job-rbpre51-10261856` (not pushed).

- Re-applied pre51; kept newer pre206 wording and added the accepted surrogate-pair/non-BMP type decode. Added `test_ail_pre51.py` and registered it.
- Probes: `/tmp/probes/pre51_errors.py`, `pre51_codes.py`, `pre51_z.py` match CPython on both builds; non-BMP/surrogate literal probes are refused by name.
- Final tests: pre51, pre206, pre225, pre243, pre103, safetynet, files, corpus_findings3 — 8 modules, 206s, 0 failed.
- `update_manifest.py --check` passes; `tools/diff_ids.py` is not present on this tree.
[cost $0.0000, opencode tokens {"total": 1993194, "input": 67090, "output": 9320, "reasoning": 10480, "cache.write": 0, "cache.read": 1906304}]
    tool time: bash 8.9 min, edit 0.0 min
        283s bash   python3 tools/par_check.py -j 2 test_ail_pre51 test_ail_pre206 test_ail_pre225 test_ail_pre243 test_ail_pre103
        208s bash   python3 tools/par_check.py -j 2 test_ail_pre51 test_ail_pre206 test_ail_pre225 test_ail_pre243 test_ail_pre103
         27s bash   for p in /tmp/probes/pre51_errors.py /tmp/probes/pre51_codes.py /tmp/probes/pre51_z.py; do echo "=== $p"; bash
         12s bash   for p in /tmp/probes/pre51_errors.py /tmp/probes/pre51_codes.py /tmp/probes/pre51_z.py; do echo "=== $p"; bash
          3s bash   cat > /tmp/probes/tmp_sur.py <<'PY' def apply(v, s):     try:         return repr(format(v, s))     except Exc
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre51-10241239 2>&1 | tail -20
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo check:$?; git status --shor
          0s bash   git add AIL_CURRENT/test_ail_pre51.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** only the format-spec parser in `safetyrt.py` changes: `wide_type` and the two diagnostic helpers become 32-bit, and a high+low surrogate pair is decoded into one non-BMP type code. The pre206 space-sign/whole-spec/NUL/`\xNN` wording is untouched. Adds `test_ail_pre51.py`, manifest, DEVLOG and a DIFFERENCES row. Matches the report.

**Probes (both builds unless noted):**
- `errors.py` (space sign, invalid spec with NUL/BMP, unknown codes, via arg/list/attr/dict): same as CPython on HEAD and base.
- `valid.py` (`z` flag forms, ordinary str/int/float formatting): same as CPython on HEAD and base.
- `wide.py`, `surrogates.py`, `literal.py`: non-BMP/`chr` surrogate/literal refused by name on both builds, as reported.
- `reach.py` (`bytes.decode` non-BMP) and `runtime_chr.py` (runtime `chr(128512)`): internal error, but identical on base.
- `unrelated.py`: `--debug-dir` `program.c` byte-identical between HEAD and `/tmp/base`; `native_report.json` differs only in temp paths.

**Tests:** `test_ail_pre51`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 206 s, 0 failed. Remaining four modules from the worker's 8-module claim were not re-run.

**Claims:** branch/commit, reapply scope, test registration, manifest `--check`, and absence of `tools/diff_ids.py` verified. The probe and test claims are consistent with what I ran; the other four modules are unverified. The report's "path is not reachable from source" holds for the normal 16-bit builds; the wide-embed build needed to exercise the latency of the new decode cannot be built here (`python/out` absent), so that specific path is unverified.

**Pre-existing:** non-BMP `bytes.decode`/runtime `chr` internal errors and the non-BMP-literal refusal behave the same on base.

**Speed:** not checked; change is confined to format-error/parse code, not hot loops.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1911286, "input": 117824, "output": 8236, "reasoning": 17290, "cache.write": 0, "cache.read": 1767936}]
    tool time: bash 4.6 min
        207s bash   date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre51 test_ail_safetynet test
         21s bash   cat > /tmp/rprobes/reach.py <<'PY' def show(v, s):     try:         print('OK', repr(format(v, s)))     except
         16s bash   for p in wide surrogates errors valid; do echo "===== $p HEAD"; timeout 180 bash ~/tools/cmp.sh /tmp/rprobes/$
         10s bash   for p in errors valid; do echo "===== $p BASE"; timeout 180 bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base; 
          7s bash   cat > /tmp/rprobes/literal.py <<'PY' print(format(1, '\U0001F600')) PY echo "=== HEAD"; timeout 120 bash ~/too
          5s bash   cd /tmp/rprobes; echo "=== BASE general"; export AIL_UNIFIED_FORCE=1; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 pyth
          5s bash   rm -rf /tmp/dbg /tmp/dbg_head /tmp/dbg_base; mkdir -p /tmp/dbg; cd /tmp/rprobes; AIL_NO_CACHE=1 AIL_QUIET_FALL
          2s bash   cat > /tmp/rprobes/runtime_chr.py <<'PY' def show(v, s):     try:         print('OK', repr(format(v, s)))     

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T11:35:18Z
